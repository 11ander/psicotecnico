#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, time, math, csv, threading
from collections import deque

import numpy as np
import cv2
import rospy
import actionlib
from sensor_msgs.msg import CompressedImage, Image

import mediapipe as mp
mp_drawing = mp.solutions.drawing_utils
mp_styles  = mp.solutions.drawing_styles
mp_pose    = mp.solutions.pose

from coordinacion_pkg.msg import (
    MobilityExamAction,
    MobilityExamResult,
    MobilityExamFeedback,
)

# ===== Landmarks =====
NOSE = 0
L_SHOULDER, R_SHOULDER = 11, 12
L_HIP, R_HIP           = 23, 24
L_ANKLE, R_ANKLE       = 27, 28
REQ_LMS = [NOSE, L_SHOULDER, R_SHOULDER, L_HIP, R_HIP, L_ANKLE, R_ANKLE]

# ===== Parámetros / Heurísticos =====
MIN_VIS = 0.6
MIN_PERSON_FRAC = 0.20
MAX_PERSON_FRAC = 0.80
WIN_SECS = 5.0
DIR_HIST_SEC = 1.5
DIR_THRESH = 0.01
TARGET_VALID_SECONDS = 30.0

# Ponderaciones
W_TRONCO_LAT   = 0.25
W_TRONCO_PITCH = 0.15
W_ZIGZAG       = 0.30
W_COJERA_AMP   = 0.15
W_COJERA_TIME  = 0.15

# Rangos (menos es mejor)
TRONCO_LAT_OK,   TRONCO_LAT_MAX   = 4.0, 20.0
TRONCO_PITCH_OK, TRONCO_PITCH_MAX = 4.0, 20.0
ZIGZAG_OK,       ZIGZAG_MAX       = 0.01, 0.08
COJERA_AMP_OK,   COJERA_AMP_MAX   = 0.10, 0.60
COJERA_T_OK,     COJERA_T_MAX     = 0.10, 0.60

WINDOW_TITLE = "MobilityExam Action Server"
MIRROR_VIEW  = False

# ============== Fuente ROS (último frame) ==============
class RosImageSource:
    def __init__(self, topic, compressed=True, queue_size=5):
        self.topic = topic
        self.compressed = compressed
        self._lock = threading.Lock()
        self._last_bgr = None
        self._count = 0
        if self.compressed:
            self._sub = rospy.Subscriber(topic, CompressedImage, self._cb_compressed, queue_size=queue_size)
            rospy.loginfo("Suscrito a CompressedImage: %s (q=%d)", topic, queue_size)
        else:
            from cv_bridge import CvBridge
            self._bridge = CvBridge()
            self._sub = rospy.Subscriber(topic, Image, self._cb_raw, queue_size=queue_size)
            rospy.loginfo("Suscrito a Image RAW: %s (q=%d)", topic, queue_size)

    def _cb_compressed(self, msg: CompressedImage):
        try:
            arr = np.frombuffer(msg.data, dtype=np.uint8)
            bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if bgr is None: return
            with self._lock:
                self._last_bgr = bgr
                self._count += 1
        except Exception as e:
            rospy.logerr_throttle(2.0, f"Decodificación JPEG falló: {e}")

    def _cb_raw(self, msg: Image):
        try:
            bgr = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            with self._lock:
                self._last_bgr = bgr
                self._count += 1
        except Exception as e:
            rospy.logerr_throttle(2.0, f"cv_bridge falló: {e}")

    def latest_bgr(self):
        with self._lock:
            return None if self._last_bgr is None else self._last_bgr.copy()

    def received_count(self):
        with self._lock:
            return self._count

# ============== Cálculo de métricas ==============
class RollingWindow:
    def __init__(self, seconds): self.seconds, self.q = seconds, deque()
    def push(self, t, val): self.q.append((t, val)); self._trim(t)
    def _trim(self, t):
        while self.q and (t - self.q[0][0]) > self.seconds: self.q.popleft()
    def values(self): return [v for _, v in self.q]
    def times(self):  return [t for t, _ in self.q]

def clamp01(x): return max(0.0, min(1.0, x))

def score_from_range(val, good, bad):
    if bad == good: return 1.0
    if val <= good: return 1.0
    if val >= bad:  return 0.0
    return 1.0 - (val - good) / (bad - good)

def midpoint(p, q): return ((p[0]+q[0])*0.5, (p[1]+q[1])*0.5, (p[2]+q[2])*0.5)

def angle_from_vertical_deg_2d(p_top, p_bottom):
    dx = p_top[0]-p_bottom[0]; dy = p_top[1]-p_bottom[1]
    return abs(math.degrees(math.atan2(dx, -dy + 1e-9)))

def angle_pitch_from_vertical_deg_3d(p_top, p_bottom):
    dy = p_top[1]-p_bottom[1]; dz = p_top[2]-p_bottom[2]
    return abs(math.degrees(math.atan2(abs(dz), abs(-dy) + 1e-9)))

def person_bbox_from_lms_xy(lms, W, H):
    xs = [lm.x*W for lm in lms]; ys = [lm.y*H for lm in lms]
    x0, x1 = min(xs), max(xs); y0, y1 = min(ys), max(ys)
    return x0, y0, x1, y1, (x1-x0), (y1-y0)

def stddev(xs):
    if not xs: return 0.0
    m = sum(xs)/len(xs)
    return math.sqrt(sum((x-m)*(x-m) for x in xs)/len(xs))

def detect_peaks(signal, times, min_sep_s=0.25):
    if len(signal) < 6: return [], []
    peaks_t, peaks_v = [], []
    prev_diff, last_peak_t = 0.0, -1e9
    for i in range(1, len(signal)):
        diff = signal[i] - signal[i-1]
        if prev_diff > 0 and diff <= 0:
            t = times[i-1]
            if (t - last_peak_t) >= min_sep_s:
                peaks_t.append(t); peaks_v.append(signal[i-1]); last_peak_t = t
        prev_diff = diff
    amps = [abs(peaks_v[i]-peaks_v[i-1]) for i in range(1, len(peaks_v))]
    return peaks_t, amps

def direction_from_size(history_frac):
    if len(history_frac) < 3: return "estable"
    delta = history_frac[-1] - history_frac[0]
    return "acerca" if delta > DIR_THRESH else ("aleja" if delta < -DIR_THRESH else "estable")

def cualitativo_rectitud(deg):
    if deg <= 4:   return "alineación lateral excelente"
    if deg <= 8:   return "ligera inclinación lateral, dentro de la normalidad"
    if deg <= 15:  return "inclinación lateral apreciable; podría mejorar"
    return "inclinación lateral marcada (posible alteración postural)"

def cualitativo_pitch(deg):
    if deg <= 4:   return "buena extensión dorsal (sin chepa)"
    if deg <= 8:   return "ligera flexión anterior (postura adelantada leve)"
    if deg <= 15:  return "tendencia a flexión anterior; vigilar ergonomía"
    return "flexión anterior marcada (posible hipercifosis postural)"

def cualitativo_zigzag(std):
    if std <= 0.015: return "trayectoria recta y estable"
    if std <= 0.035: return "ligero serpenteo, compatible con variaciones normales"
    if std <= 0.06:  return "zigzag moderado; posible inestabilidad leve"
    return "zigzag acusado; posible alteración del equilibrio o atención"

def cualitativo_asimetria(a, t):
    if a <= 0.12 and t <= 0.12: return "simetría de paso adecuada (sin signos de cojera)"
    if a <= 0.25 and t <= 0.25: return "asimetría leve de la marcha"
    if a <= 0.45 or  t <= 0.45: return "asimetría moderada; posible marcha antálgica"
    return "asimetría marcada; valorar causas de cojera o inestabilidad"

def generar_informe(final_score, m_lat, m_pitch, m_zig, m_asA, m_asT):
    txt = []
    if   final_score >= 85: nivel = "ÓPTIMO"
    elif final_score >= 70: nivel = "APTO"
    elif final_score >= 50: nivel = "LIMITADO"
    else:                   nivel = "NO APTO (orientativo)"
    txt.append(f"Resultado global: {final_score:.0f}/100 — {nivel}.")
    txt.append(f"Tronco (inclinación lateral media: {m_lat:.1f}°): {cualitativo_rectitud(m_lat)}.")
    txt.append(f"Tronco (flexión anterior/pitch medio: {m_pitch:.1f}°): {cualitativo_pitch(m_pitch)}.")
    txt.append(f"Trayectoria (zigzag std normalizado: {m_zig:.3f}): {cualitativo_zigzag(m_zig)}.")
    txt.append(f"Marcha (asimetría amplitud {m_asA:.2f}, temporal {m_asT:.2f}): {cualitativo_asimetria(m_asA, m_asT)}.")
    sugerencias = []
    if m_pitch > 8: sugerencias.append("trabajo postural/ergonómico y fortalecimiento dorsal")
    if m_lat > 8:   sugerencias.append("ejercicios de estabilidad lateral y core")
    if m_zig > 0.035: sugerencias.append("pruebas de equilibrio estático y dinámico")
    if m_asA > 0.25 or m_asT > 0.25: sugerencias.append("valorar técnica de marcha y posibles molestias articulares")
    if sugerencias:
        txt.append("Recomendaciones orientativas: " + "; ".join(sugerencias) + ".")
    txt.append("Aviso: este informe es orientativo y no constituye diagnóstico médico.")
    return txt

def ensure_csv_header(path):
    if not os.path.isfile(path):
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["timestamp","valid_elapsed_s","person_frac","dir",
                        "score_total","tronco_lat_deg","tronco_pitch_deg",
                        "zigzag_std","asim_amp","asim_t"])

# ==================== Servidor de acción ====================
class MobilityExamActionServer:
    def __init__(self):
        rospy.init_node("mobility_exam_action_server", anonymous=True)

        # Params
        self.topic       = rospy.get_param("~topic", "/xtion/rgb/image_raw/compressed")
        self.compressed  = rospy.get_param("~compressed", True)
        self.queue_size  = int(rospy.get_param("~queue_size", 5))
        self.complexity  = int(rospy.get_param("~complexity", 1))
        self.out_dir     = rospy.get_param("~out_dir", "")
        self.enable_ui   = bool(rospy.get_param("~enable_ui", True))
        self.mirror_view = bool(rospy.get_param("~mirror_view", False))

        if self.out_dir and not os.path.isdir(self.out_dir):
            os.makedirs(self.out_dir, exist_ok=True)

        ts = time.strftime("%Y%m%d-%H%M%S")
        base = os.path.join(self.out_dir, f"mobility_{ts}") if self.out_dir else f"./mobility_{ts}"
        self.csv_path = base + "_metrics.csv"
        self.report_path = base + "_report.txt"
        ensure_csv_header(self.csv_path)

        self.src = RosImageSource(self.topic, self.compressed, self.queue_size)
        threading.Thread(target=rospy.spin, daemon=True).start()

        self.server = actionlib.SimpleActionServer(
            "mobility_exam_action",
            MobilityExamAction,
            execute_cb=self.execute_cb,
            auto_start=False,
        )
        self.server.start()
        rospy.loginfo("Servidor 'mobility_exam_action' listo. (topic=%s, compressed=%s)", self.topic, self.compressed)

    def execute_cb(self, goal):
        fb = MobilityExamFeedback()
        res = MobilityExamResult()

        if not goal.ejecutar:
            fb.estado = "Goal con ejecutar=False. Nada que hacer."
            self.server.publish_feedback(fb)
            rospy.sleep(0.2)
            self.server.set_aborted(res, "ejecutar=False")
            return

        with mp_pose.Pose(
            static_image_mode=False, model_complexity=self.complexity,
            smooth_landmarks=True, enable_segmentation=False,
            min_detection_confidence=0.3, min_tracking_confidence=0.3
        ) as pose:

            win_midhip_x    = RollingWindow(WIN_SECS)
            win_person_frac = RollingWindow(DIR_HIST_SEC)
            win_lank_y      = RollingWindow(WIN_SECS)
            win_rank_y      = RollingWindow(WIN_SECS)
            zigzag_seg      = {"acerca": deque(maxlen=256), "aleja": deque(maxlen=256), "estable": deque(maxlen=256)}

            hist_total, hist_lat, hist_pitch = [], [], []
            hist_zig, hist_asA, hist_asT = [], [], []

            valid_elapsed = 0.0
            last_frame_t = time.time()
            finished = False

            if self.enable_ui:
                try: cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)
                except Exception: pass

            fb.estado = "Esperando frames de cámara…"
            fb.valid_elapsed = 0.0
            self.server.publish_feedback(fb)

            while not rospy.is_shutdown():
                if self.server.is_preempt_requested():
                    fb.estado = "Preempted por el cliente. Abortando."
                    self.server.publish_feedback(fb)
                    self.server.set_preempted()
                    break

                bgr = self.src.latest_bgr()
                if bgr is None:
                    time.sleep(0.002)
                    continue
                if self.mirror_view:
                    bgr = cv2.flip(bgr, 1)

                t_now = time.time()
                dt = t_now - last_frame_t
                last_frame_t = t_now

                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                res_pose = pose.process(rgb)

                status_text = "Buscando persona…"
                analyzing_valid = False

                if res_pose.pose_landmarks:
                    mp_drawing.draw_landmarks(
                        bgr, res_pose.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                        landmark_drawing_spec=mp_drawing.DrawingSpec(color=(0,255,0), thickness=2, circle_radius=2),
                        connection_drawing_spec=mp_drawing.DrawingSpec(color=(0,180,0), thickness=2, circle_radius=2),
                    )
                    lms = res_pose.pose_landmarks.landmark
                    H, W = bgr.shape[0], bgr.shape[1]

                    if all(lms[i].visibility >= MIN_VIS for i in REQ_LMS):
                        x0,y0,x1,y1,bw,bh = person_bbox_from_lms_xy(lms, W, H)
                        person_frac = bh/(H+1e-6)
                        win_person_frac.push(t_now, person_frac)
                        cv2.rectangle(bgr, (int(x0),int(y0)), (int(x1),int(y1)), (80,180,255), 2)

                        if person_frac < MIN_PERSON_FRAC:
                            status_text = "Muy lejos: acércate (pausa)."
                        elif person_frac > MAX_PERSON_FRAC:
                            status_text = "Muy cerca: aléjate (pausa)."
                        else:
                            analyzing_valid = True

                            def P(idx): return (lms[idx].x*W, lms[idx].y*H, lms[idx].z)
                            l_sh,r_sh = P(L_SHOULDER), P(R_SHOULDER)
                            l_hp,r_hp = P(L_HIP),      P(R_HIP)
                            l_an, r_an = P(L_ANKLE), P(R_ANKLE)
                            mid_sh = midpoint(l_sh, r_sh); mid_hp = midpoint(l_hp, r_hp)

                            tronco_lat_deg   = angle_from_vertical_deg_2d(mid_sh, mid_hp)
                            tronco_pitch_deg = angle_pitch_from_vertical_deg_3d(mid_sh, mid_hp)
                            s_tronco_lat   = score_from_range(tronco_lat_deg,   TRONCO_LAT_OK,   TRONCO_LAT_MAX)
                            s_tronco_pitch = score_from_range(tronco_pitch_deg, TRONCO_PITCH_OK, TRONCO_PITCH_MAX)

                            midhip_x = mid_hp[0]; norm_x = (midhip_x - x0)/(bw + 1e-6)
                            win_midhip_x.push(t_now, norm_x)
                            dir_now = direction_from_size(win_person_frac.values())
                            zigzag_seg[dir_now].append(norm_x)
                            xs = list(zigzag_seg[dir_now])
                            zigzag_std = stddev(xs) if len(xs) >= 12 else 0.0
                            s_zigzag = score_from_range(zigzag_std, ZIGZAG_OK, ZIGZAG_MAX)

                            win_lank_y.push(t_now, l_an[1]); win_rank_y.push(t_now, r_an[1])
                            l_sig, r_sig = win_lank_y.values(), win_rank_y.values()
                            l_t,   r_t   = win_lank_y.times(),  win_rank_y.times()
                            asymA, asymT = 0.0, 0.0
                            if len(l_sig) > 16 and len(r_sig) > 16:
                                l_peaks_t, l_amps = detect_peaks(l_sig, l_t, 0.25)
                                r_peaks_t, r_amps = detect_peaks(r_sig, r_t, 0.25)
                                if len(l_amps)>=2 and len(r_amps)>=2:
                                    lA = sum(l_amps)/len(l_amps); rA = sum(r_amps)/len(r_amps)
                                    denom = (abs(lA)+abs(rA))*0.5 + 1e-6
                                    asymA = abs(lA - rA)/denom
                                def mean_period(ts):
                                    if len(ts)<3: return None
                                    dif = [ts[i]-ts[i-1] for i in range(1,len(ts))]
                                    return sum(dif)/len(dif) if dif else None
                                lP, rP = mean_period(l_peaks_t), mean_period(r_peaks_t)
                                if lP and rP:
                                    denom = (lP + rP)/2.0 + 1e-6
                                    asymT = abs(lP - rP)/denom
                            s_coj_amp  = score_from_range(asymA, COJERA_AMP_OK, COJERA_AMP_MAX)
                            s_coj_time = score_from_range(asymT, COJERA_T_OK,   COJERA_T_MAX)

                            total_score = (
                                W_TRONCO_LAT   * s_tronco_lat +
                                W_TRONCO_PITCH * s_tronco_pitch +
                                W_ZIGZAG       * s_zigzag +
                                W_COJERA_AMP   * s_coj_amp +
                                W_COJERA_TIME  * s_coj_time
                            ) * 100.0

                            valid_elapsed += dt

                            hist_total.append(total_score)
                            hist_lat.append(tronco_lat_deg)
                            hist_pitch.append(tronco_pitch_deg)
                            hist_zig.append(zigzag_std)
                            hist_asA.append(asymA)
                            hist_asT.append(asymT)

                            if int(valid_elapsed) != int(valid_elapsed - dt):
                                with open(self.csv_path, "a", newline="") as f:
                                    w = csv.writer(f)
                                    w.writerow([
                                        time.strftime("%Y-%m-%d %H:%M:%S"),
                                        f"{valid_elapsed:.1f}",
                                        f"{person_frac:.3f}",
                                        dir_now,
                                        f"{total_score:.1f}",
                                        f"{tronco_lat_deg:.2f}",
                                        f"{tronco_pitch_deg:.2f}",
                                        f"{zigzag_std:.3f}",
                                        f"{asymA:.3f}",
                                        f"{asymT:.3f}",
                                    ])

                            status_text = f"Analizando ({dir_now})"
                            if valid_elapsed >= TARGET_VALID_SECONDS:
                                finished = True
                    else:
                        status_text = "Persona parcial (pausa: mejora encuadre/visibilidad)."

                fb.valid_elapsed = float(valid_elapsed)
                fb.estado = status_text
                self.server.publish_feedback(fb)

                if self.enable_ui:
                    y = 26
                    cv2.putText(bgr, status_text, (10,y), cv2.FONT_HERSHEY_SIMPLEX,0.8,(255,255,0),2,cv2.LINE_AA); y+=28
                    color = (0,255,0) if analyzing_valid else (0,165,255)
                    cv2.putText(bgr, f"Tiempo válido: {valid_elapsed:05.1f}s / {TARGET_VALID_SECONDS:.0f}s",
                                (10,y), cv2.FONT_HERSHEY_SIMPLEX,0.9,color,2,cv2.LINE_AA); y+=30
                    cv2.imshow(WINDOW_TITLE, bgr)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (27, ord('q')):
                        self.server.set_preempted()
                        break

                if finished:
                    m_total = sum(hist_total)/max(1,len(hist_total))
                    m_lat   = sum(hist_lat)/max(1,len(hist_lat))
                    m_pitch = sum(hist_pitch)/max(1,len(hist_pitch))
                    m_zig   = sum(hist_zig)/max(1,len(hist_zig))
                    m_asA   = sum(hist_asA)/max(1,len(hist_asA))
                    m_asT   = sum(hist_asT)/max(1,len(hist_asT))
                    informe = generar_informe(m_total, m_lat, m_pitch, m_zig, m_asA, m_asT)

                    try:
                        with open(self.report_path, "w", encoding="utf-8") as f:
                            f.write(f"Informe de movilidad — {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"Tiempo analizado (válido): {TARGET_VALID_SECONDS:.0f} s\n")
                            f.write(f"Nota final: {m_total:.0f}/100\n\n")
                            for line in informe: f.write(line+"\n")
                    except Exception as e:
                        rospy.logwarn("No se pudo escribir informe TXT: %s", e)

                    res.score = float(m_total)
                    res.informe = list(informe)
                    res.report_path = str(self.report_path)
                    res.csv_path = str(self.csv_path)
                    self.server.set_succeeded(res)
                    break

                if not self.enable_ui:
                    time.sleep(0.001)

            # fin while

        try:
            if self.enable_ui:
                cv2.destroyWindow(WINDOW_TITLE)
        except Exception:
            pass


def main():
    try:
        _ = MobilityExamActionServer()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
    finally:
        try: cv2.destroyAllWindows()
        except Exception: pass

if __name__ == "__main__":
    main()
