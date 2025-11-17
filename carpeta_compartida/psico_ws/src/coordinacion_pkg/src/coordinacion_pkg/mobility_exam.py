#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import time
import math
import csv
import os
from collections import deque

import cv2
import mediapipe as mp

# ===== MediaPipe =====
mp_drawing = mp.solutions.drawing_utils
mp_styles  = mp.solutions.drawing_styles
mp_pose    = mp.solutions.pose

# ===== Landmarks =====
NOSE = 0
L_SHOULDER, R_SHOULDER = 11, 12
L_HIP, R_HIP           = 23, 24
L_ANKLE, R_ANKLE       = 27, 28
REQ_LMS = [NOSE, L_SHOULDER, R_SHOULDER, L_HIP, R_HIP, L_ANKLE, R_ANKLE]

# ===== Parámetros =====
MIN_VIS = 0.6
WIN_SECS = 5.0                 # ventana de análisis
MIN_PERSON_FRAC = 0.20
MAX_PERSON_FRAC = 0.80

# Ponderaciones
W_TRONCO_LAT   = 0.25
W_TRONCO_PITCH = 0.15
W_ZIGZAG       = 0.30
W_COJERA_AMP   = 0.15
W_COJERA_TIME  = 0.15

# Rangos (menos es mejor)
TRONCO_LAT_OK,   TRONCO_LAT_MAX   = 4.0, 20.0      # grados
TRONCO_PITCH_OK, TRONCO_PITCH_MAX = 4.0, 20.0      # grados
ZIGZAG_OK,       ZIGZAG_MAX       = 0.01, 0.08     # std normalizada
COJERA_AMP_OK,   COJERA_AMP_MAX   = 0.10, 0.60     # 0..1
COJERA_T_OK,     COJERA_T_MAX     = 0.10, 0.60     # 0..1

# Dirección (acerca/aleja) por delta tamaño bbox
DIR_HIST_SEC = 1.5
DIR_THRESH = 0.01  # cambio mínimo fraccional para etiquetar dirección

# ---- Utilidades ----
def clamp01(x): return max(0.0, min(1.0, x))
def score_from_range(val, good, bad):
    if val <= good: return 1.0
    if val >= bad:  return 0.0
    t = (val - good)/(bad - good)
    return 1.0 - clamp01(t)

def midpoint(p, q): return ((p[0]+q[0])*0.5, (p[1]+q[1])*0.5, (p[2]+q[2])*0.5)

def angle_from_vertical_deg_2d(p_top, p_bottom):
    # 2D lateral: usa x,y (imagen). 0° vertical perfecto.
    dx = p_top[0] - p_bottom[0]
    dy = p_top[1] - p_bottom[1]
    ang = math.degrees(math.atan2(dx, -dy + 1e-9))
    return abs(ang)

def angle_pitch_from_vertical_deg_3d(p_top, p_bottom):
    # Pitch (chepa): usa y,z del vector (bottom->top). 0° vertical perfecto.
    dy = p_top[1] - p_bottom[1]   # y crece hacia abajo en imagen
    dz = p_top[2] - p_bottom[2]   # z relativo (MediaPipe: negativo hacia cámara)
    # Vertical ideal ~ -y; medimos inclinación en plano sagital (y-z)
    ang = math.degrees(math.atan2(abs(dz), abs(-dy) + 1e-9))
    return abs(ang)

def person_bbox_from_lms_xy(lms, W, H):
    xs, ys = [], []
    for lm in lms:
        xs.append(lm.x * W)
        ys.append(lm.y * H)
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    return x0, y0, x1, y1, (x1-x0), (y1-y0)

class RollingWindow:
    def __init__(self, seconds):
        self.seconds = seconds
        self.q = deque()  # (t, value)

    def push(self, t, value):
        self.q.append((t, value))
        self._trim(t)

    def _trim(self, t_now):
        while self.q and (t_now - self.q[0][0]) > self.seconds:
            self.q.popleft()

    def values(self):
        return [v for _, v in self.q]

    def times(self):
        return [t for t, _ in self.q]

    def last(self):
        return self.q[-1][1] if self.q else None

class EMA:
    def __init__(self, alpha=0.2, init=None):
        self.alpha = alpha
        self.y = init
    def push(self, x):
        if self.y is None:
            self.y = x
        else:
            self.y = self.alpha * x + (1 - self.alpha) * self.y
        return self.y
    def value(self): return self.y

def stddev(xs):
    n = len(xs)
    if n == 0: return 0.0
    m = sum(xs)/n
    return math.sqrt(sum((x-m)*(x-m) for x in xs)/n)

def detect_peaks(signal, times, min_sep_s=0.25):
    """
    Detecta picos simples por cambio de pendiente. Devuelve timestamps de picos y amplitudes aprox.
    """
    if len(signal) < 6:
        return [], []
    peaks_t, peaks_v = [], []
    prev_diff = 0.0
    last_peak_t = -1e9
    for i in range(1, len(signal)):
        diff = signal[i] - signal[i-1]
        if prev_diff > 0 and diff <= 0:
            # candidato a pico en i-1
            t = times[i-1]
            if (t - last_peak_t) >= min_sep_s:
                peaks_t.append(t)
                peaks_v.append(signal[i-1])
                last_peak_t = t
        prev_diff = diff
    # amplitudes pico a pico aproximadas
    amps = []
    for i in range(1, len(peaks_v)):
        amps.append(abs(peaks_v[i] - peaks_v[i-1]))
    return peaks_t, amps

def direction_from_size(history_frac):
    """
    Devuelve 'acerca', 'aleja' o 'estable' según tendencia reciente de la fracción de altura (bbox/H).
    """
    if len(history_frac) < 3:
        return "estable"
    delta = history_frac[-1] - history_frac[0]
    if delta > DIR_THRESH:
        return "acerca"
    if delta < -DIR_THRESH:
        return "aleja"
    return "estable"

def ensure_csv_header(path):
    exists = os.path.isfile(path)
    if not exists:
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "timestamp",
                "person_frac",
                "dir",
                "score_total",
                "tronco_lateral",
                "tronco_pitch",
                "zigzag",
                "cojera_amp",
                "cojera_time"
            ])

# ================== MAIN ==================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="/dev/video0")
    ap.add_argument("--width",  type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--fps",    type=int, default=30)
    ap.add_argument("--mirror", action="store_true")
    ap.add_argument("--complexity", type=int, default=1, choices=[0,1,2])
    ap.add_argument("--out_csv", default="", help="Ruta CSV para guardar métricas (por defecto en ./mobility_metrics_YYYYmmdd-HHMMSS.csv)")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    cap_source = int(args.device) if str(args.device).isdigit() else args.device
    cap = cv2.VideoCapture(cap_source, cv2.CAP_V4L2)
    if not cap.isOpened():
        print(f"No se pudo abrir la cámara {cap_source}")
        return

    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS,          args.fps)

    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Ventanas
    win_midhip_x   = RollingWindow(WIN_SECS)
    win_person_frac= RollingWindow(DIR_HIST_SEC)
    win_lank_y     = RollingWindow(WIN_SECS)
    win_rank_y     = RollingWindow(WIN_SECS)

    # EMA para puntajes
    ema_total = EMA(alpha=0.25)
    ema_sub   = {
        "tronco_lat":   EMA(alpha=0.3),
        "tronco_pitch": EMA(alpha=0.3),
        "zigzag":       EMA(alpha=0.3),
        "cojera_amp":   EMA(alpha=0.3),
        "cojera_time":  EMA(alpha=0.3),
    }

    # CSV
    if not args.out_csv:
        ts = time.strftime("%Y%m%d-%H%M%S")
        args.out_csv = f"./mobility_metrics_{ts}.csv"
    ensure_csv_header(args.out_csv)
    last_csv_flush = time.time()

    fps_prev = time.time()
    fps_alpha = 0.9
    fps_est = float(args.fps)

    # Buffer para zigzag segmentado por dirección
    zigzag_seg = {"acerca": deque(maxlen=256), "aleja": deque(maxlen=256), "estable": deque(maxlen=256)}

    with mp_pose.Pose(
        static_image_mode=False,
        model_complexity=args.complexity,
        smooth_landmarks=True,
        enable_segmentation=False,
        min_detection_confidence=0.3,
        min_tracking_confidence=0.3
    ) as pose:

        while True:
            ok, frame = cap.read()
            if not ok:
                print("No se pudo leer frame.")
                break
            if args.mirror:
                frame = cv2.flip(frame, 1)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = pose.process(rgb)

            status_text = "Buscando persona..."
            total_score = None
            subs = {}

            if res.pose_landmarks:
                lms = res.pose_landmarks.landmark

                # === DIBUJO DEL STICKMAN (siempre que haya landmarks) ===
                mp_drawing.draw_landmarks(
                    frame,
                    res.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing.DrawingSpec(color=(0, 255, 255), thickness=2, circle_radius=2),
                    connection_drawing_spec=mp_drawing.DrawingSpec(color=(0, 170, 255), thickness=2, circle_radius=2),
                )

                # BBox informativo, aunque la medición no sea válida
                x0, y0, x1, y1, _, _ = person_bbox_from_lms_xy(lms, W, H)
                cv2.rectangle(frame, (int(x0), int(y0)), (int(x1), int(y1)), (80, 180, 255), 2)


                # Check visibilidad
                if all(lms[i].visibility >= MIN_VIS for i in REQ_LMS):
                    # BBox / tamaño persona
                    x0, y0, x1, y1, bw, bh = person_bbox_from_lms_xy(lms, W, H)
                    person_frac = bh / (H + 1e-6)
                    win_person_frac.push(time.time(), person_frac)

                    if person_frac < MIN_PERSON_FRAC:
                        status_text = "Muy lejos (acércate)."
                    elif person_frac > MAX_PERSON_FRAC:
                        status_text = "Muy cerca (aléjate)."
                    else:
                        # Puntos 3D aproximados (x,y pixel; z relativo)
                        def P(idx):
                            return (lms[idx].x * W, lms[idx].y * H, lms[idx].z)

                        l_sh = P(L_SHOULDER); r_sh = P(R_SHOULDER)
                        l_hp = P(L_HIP);      r_hp = P(R_HIP)
                        l_an = P(L_ANKLE);    r_an = P(R_ANKLE)

                        mid_sh = midpoint(l_sh, r_sh)
                        mid_hp = midpoint(l_hp, r_hp)

                        # 1) Tronco lateral (2D)
                        tronco_lat_deg = angle_from_vertical_deg_2d(mid_sh, mid_hp)
                        s_tronco_lat = score_from_range(tronco_lat_deg, TRONCO_LAT_OK, TRONCO_LAT_MAX)

                        # 2) Pitch (chepa, 3D y-z)
                        tronco_pitch_deg = angle_pitch_from_vertical_deg_3d(mid_sh, mid_hp)
                        s_tronco_pitch = score_from_range(tronco_pitch_deg, TRONCO_PITCH_OK, TRONCO_PITCH_MAX)

                        # 3) Zigzag lateral segmentado por dirección
                        t_now = time.time()
                        midhip_x = mid_hp[0]
                        norm_x = (midhip_x - x0) / (bw + 1e-6)
                        win_midhip_x.push(t_now, norm_x)

                        # Dirección actual
                        frac_hist = win_person_frac.values()
                        dir_now = direction_from_size(frac_hist)
                        zigzag_seg[dir_now].append(norm_x)

                        # usamos solo la serie del tramo en curso
                        xs = list(zigzag_seg[dir_now])
                        zigzag_std = stddev(xs) if len(xs) >= 12 else 0.0
                        s_zigzag = score_from_range(zigzag_std, ZIGZAG_OK, ZIGZAG_MAX)

                        # 4) Cojera: amplitud y periodo (cada tobillo)
                        # Señal: y (pixel) de los tobillos
                        win_lank_y.push(t_now, l_an[1])
                        win_rank_y.push(t_now, r_an[1])
                        l_sig, r_sig = win_lank_y.values(), win_rank_y.values()
                        l_t,   r_t   = win_lank_y.times(),  win_rank_y.times()

                        s_coj_amp = 1.0
                        s_coj_time = 1.0
                        if len(l_sig) > 16 and len(r_sig) > 16:
                            # picos por tobillo
                            l_peaks_t, l_amps = detect_peaks(l_sig, l_t, min_sep_s=0.25)
                            r_peaks_t, r_amps = detect_peaks(r_sig, r_t, min_sep_s=0.25)

                            # Asimetría de amplitud (pico-pico medios)
                            if len(l_amps) >= 2 and len(r_amps) >= 2:
                                lA = sum(l_amps)/len(l_amps)
                                rA = sum(r_amps)/len(r_amps)
                                denom = (abs(lA) + abs(rA)) * 0.5 + 1e-6
                                asymA = abs(lA - rA) / denom
                                s_coj_amp = score_from_range(asymA, COJERA_AMP_OK, COJERA_AMP_MAX)

                            # Asimetría temporal (periodo entre picos medios)
                            def mean_period(ts):
                                if len(ts) < 3: return None
                                diffs = [ts[i]-ts[i-1] for i in range(1, len(ts))]
                                return sum(diffs)/len(diffs) if diffs else None

                            lP = mean_period(l_peaks_t)
                            rP = mean_period(r_peaks_t)
                            if lP and rP:
                                denom = (lP + rP)/2.0 + 1e-6
                                asymT = abs(lP - rP)/denom
                                s_coj_time = score_from_range(asymT, COJERA_T_OK, COJERA_T_MAX)

                        # ----- Suavizado (EMA) -----
                        s_tronco_lat   = ema_sub["tronco_lat"].push(s_tronco_lat)
                        s_tronco_pitch = ema_sub["tronco_pitch"].push(s_tronco_pitch)
                        s_zigzag       = ema_sub["zigzag"].push(s_zigzag)
                        s_coj_amp      = ema_sub["cojera_amp"].push(s_coj_amp)
                        s_coj_time     = ema_sub["cojera_time"].push(s_coj_time)

                        total = (
                            W_TRONCO_LAT   * s_tronco_lat +
                            W_TRONCO_PITCH * s_tronco_pitch +
                            W_ZIGZAG       * s_zigzag +
                            W_COJERA_AMP   * s_coj_amp +
                            W_COJERA_TIME  * s_coj_time
                        ) * 100.0
                        total = ema_total.push(total)

                        subs = {
                            "Tronco (lat)":   round(s_tronco_lat   * 100),
                            "Tronco (pitch)": round(s_tronco_pitch * 100),
                            "Zigzag":         round(s_zigzag       * 100),
                            "Cojera amp":     round(s_coj_amp      * 100),
                            "Cojera tiempo":  round(s_coj_time     * 100),
                        }
                        total_score = total
                        status_text = f"Analizando... ({dir_now})"

                        # ---- Log a CSV cada ~1 s ----
                        if time.time() - last_csv_flush >= 1.0:
                            with open(args.out_csv, "a", newline="") as f:
                                w = csv.writer(f)
                                w.writerow([
                                    time.strftime("%Y-%m-%d %H:%M:%S"),
                                    f"{person_frac:.3f}",
                                    dir_now,
                                    f"{total_score:.1f}",
                                    f"{(s_tronco_lat*100):.0f}",
                                    f"{(s_tronco_pitch*100):.0f}",
                                    f"{(s_zigzag*100):.0f}",
                                    f"{(s_coj_amp*100):.0f}",
                                    f"{(s_coj_time*100):.0f}",
                                ])
                            last_csv_flush = time.time()


                else:
                    status_text = "Persona parcial (visibilidad insuficiente)."

            # FPS
            now = time.time()
            inst = 1.0 / max(1e-6, (now - fps_prev))
            fps_prev = now
            fps_est = fps_alpha * fps_est + (1 - fps_alpha) * inst

            # Overlay
            y = 28
            cv2.putText(frame, f"FPS: {fps_est:.1f}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20,220,20), 2, cv2.LINE_AA); y += 28
            cv2.putText(frame, status_text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,0), 2, cv2.LINE_AA); y += 28

            if total_score is not None:
                cv2.putText(frame, f"Score total: {total_score:.0f}/100", (10, y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0,200,255), 2, cv2.LINE_AA); y += 30
                for k, v in subs.items():
                    cv2.putText(frame, f"{k}: {v}/100", (10, y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (220,220,220), 2, cv2.LINE_AA); y += 26

                if args.debug:
                    y += 8
                    cv2.putText(frame, "(DEBUG) CSV: "+os.path.basename(args.out_csv), (10, y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120,120,255), 2, cv2.LINE_AA); y += 22

            cv2.imshow("Examen de movilidad PRO (q para salir)", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
