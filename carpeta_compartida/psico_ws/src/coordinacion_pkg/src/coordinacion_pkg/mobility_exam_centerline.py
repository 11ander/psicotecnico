# mobility_exam_centerline_py38.py
import cv2
import numpy as np
import mediapipe as mp
import time, math, argparse
from collections import deque
from typing import Optional, Tuple, List

def clamp(v, lo, hi): return max(lo, min(hi, v))
def rad2deg(r): return r * 180.0 / math.pi
def robust_mean(x): return (sum(x)/len(x)) if x else 0.0
def robust_std(x):
    if not x: return 0.0
    m = robust_mean(x)
    return math.sqrt(sum((xi - m) ** 2 for xi in x) / len(x))

mp_pose = mp.solutions.pose
mp_draw = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles

class MobilityExam:
    def __init__(self, window_secs=6, target_fps=30):
        self.N = int(window_secs * target_fps)
        self.dev_norm = deque(maxlen=self.N)
        self.head_norm = deque(maxlen=self.N)
        self.torso_deg = deque(maxlen=self.N)
        self.twist = deque(maxlen=self.N)
        self.lat_series = deque(maxlen=self.N)
        self.crossings = 0
        self._last_sign = None
        self.w_center = 0.40
        self.w_zigzag = 0.20
        self.w_head   = 0.15
        self.w_torso  = 0.15
        self.w_twist  = 0.10

    def update(self, midhip_x, nose_x, midsh_x, midsh_y, midhip_y,
               lsh_x, rsh_x, lsh_z, rsh_z, center_x, shoulder_width):
        sw = max(shoulder_width, 1e-6)
        dev = abs(midhip_x - center_x) / sw
        self.dev_norm.append(dev)

        lateral = (midhip_x - center_x) / sw
        self.lat_series.append(lateral)
        sign = 1 if lateral > 0 else (-1 if lateral < 0 else 0)
        if self._last_sign is not None and sign != 0 and sign != self._last_sign:
            self.crossings += 1
        if sign != 0:
            self._last_sign = sign

        head = abs(nose_x - midhip_x) / sw
        self.head_norm.append(head)

        vx = (midsh_x - midhip_x)
        vy = (midsh_y - midhip_y)
        angle_deg = abs(rad2deg(math.atan2(vx, max(vy, 1e-6))))
        self.torso_deg.append(angle_deg)

        twist_val = abs(lsh_z - rsh_z)  # z relativa
        self.twist.append(twist_val)

    def scores(self, elapsed_secs):
        center_rms = robust_std(self.dev_norm)           # bueno <=0.10, malo >=0.60
        s_center = clamp(100 * (1 - (center_rms - 0.10) / (0.60 - 0.10)), 0, 100)

        minutes = max(elapsed_secs / 60.0, 1e-6)
        crossings_rate = self.crossings / minutes
        deriv = [self.lat_series[i]-self.lat_series[i-1] for i in range(1,len(self.lat_series))]
        deriv_rms = robust_std(deriv)                    # bueno <=0.05, malo >=0.25
        s_cross = clamp(100 * (1 - (crossings_rate - 2.0) / (10.0 - 2.0)), 0, 100)
        s_curve = clamp(100 * (1 - (deriv_rms - 0.05) / (0.25 - 0.05)), 0, 100)
        s_zigzag = 0.6 * s_cross + 0.4 * s_curve

        head_rms = robust_std(self.head_norm)            # bueno <=0.10, malo >=0.60
        s_head = clamp(100 * (1 - (head_rms - 0.10) / (0.60 - 0.10)), 0, 100)

        torso_rms = robust_std(self.torso_deg)           # bueno <=3°, malo >=15°
        s_torso = clamp(100 * (1 - (torso_rms - 3.0) / (15.0 - 3.0)), 0, 100)

        twist_rms = robust_std(self.twist)               # bueno <=0.02, malo >=0.12
        s_twist = clamp(100 * (1 - (twist_rms - 0.02) / (0.12 - 0.02)), 0, 100)

        score = (self.w_center*s_center + self.w_zigzag*s_zigzag +
                 self.w_head*s_head + self.w_torso*s_torso + self.w_twist*s_twist)

        return score, {
            "center_rms": center_rms,
            "crossings_min": crossings_rate,
            "deriv_rms": deriv_rms,
            "head_rms": head_rms,
            "torso_rms_deg": torso_rms,
            "twist_rms": twist_rms,
            "s_center": s_center,
            "s_zigzag": s_zigzag,
            "s_head": s_head,
            "s_torso": s_torso,
            "s_twist": s_twist,
            "score": score
        }

def open_camera(preferred_index: Optional[int]) -> Tuple[Optional[cv2.VideoCapture], List[int]]:
    """Intenta abrir con V4L2; prueba índices 0 y 1 automáticamente si falla."""
    tried = []
    api = cv2.CAP_V4L2
    candidates = []
    if preferred_index is not None:
        candidates.append(preferred_index)
    for i in (0, 1):
        if i not in candidates:
            candidates.append(i)
    for idx in candidates:
        cap = cv2.VideoCapture(idx, api)
        tried.append(idx)
        if cap.isOpened():
            return cap, [idx]
        cap.release()
    return None, tried

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=None, help="Índice de cámara (0/1). Si no, auto")
    ap.add_argument("--exam_secs", type=float, default=30.0)
    ap.add_argument("--mirror", action="store_true", help="Vista espejo")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    args = ap.parse_args()

    cap, used = open_camera(args.cam)
    if cap is None:
        print("No se pudo abrir la cámara. Probados índices:", used)
        print("Sugerencias: 'v4l2-ctl --list-devices', revisa permisos del grupo 'video'.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or args.width)
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or args.height)
    center_x = W // 2

    exam = MobilityExam(window_secs=6, target_fps=30)
    started = False
    t0 = None
    final = None

    with mp_pose.Pose(static_image_mode=False, model_complexity=1,
                      smooth_landmarks=True, enable_segmentation=False,
                      min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:

        while True:
            ok, frame = cap.read()
            if not ok: break
            if args.mirror:
                frame = cv2.flip(frame, 1)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = pose.process(rgb)

            vis = frame.copy()
            cv2.line(vis, (center_x, 0), (center_x, H-1), (0, 255, 255), 2)

            if res.pose_landmarks:
                lm = res.pose_landmarks.landmark
                def L(idx):
                    p = lm[idx]
                    return (p.x * W, p.y * H, p.z)

                nose_x, nose_y, nose_z = L(mp_pose.PoseLandmark.NOSE)
                lsh_x, lsh_y, lsh_z = L(mp_pose.PoseLandmark.LEFT_SHOULDER)
                rsh_x, rsh_y, rsh_z = L(mp_pose.PoseLandmark.RIGHT_SHOULDER)
                lhp_x, lhp_y, lhp_z = L(mp_pose.PoseLandmark.LEFT_HIP)
                rhp_x, rhp_y, rhp_z = L(mp_pose.PoseLandmark.RIGHT_HIP)

                midhip_x = (lhp_x + rhp_x) * 0.5
                midhip_y = (lhp_y + rhp_y) * 0.5
                midsh_x  = (lsh_x + rsh_x) * 0.5
                midsh_y  = (lsh_y + rsh_y) * 0.5
                shoulder_width = abs(rsh_x - lsh_x) + 1e-6

                if started:
                    exam.update(midhip_x, nose_x, midsh_x, midsh_y, midhip_y,
                                lsh_x, rsh_x, lsh_z, rsh_z, center_x, shoulder_width)

                    elapsed = time.time() - t0
                    score, det = exam.scores(elapsed)

                    y0, dy = 30, 24
                    overlay = [
                        "Tiempo: {:.1f}s".format(max(0.0, args.exam_secs - elapsed)),
                        "Score: {:5.1f}/100".format(score),
                        "Centrado RMS: {:.3f} (ancho hombros)".format(det['center_rms']),
                        "Zigzag: {:5.1f} (cruces/min={:.1f}, dRMS={:.3f})"
                            .format(det['s_zigzag'], det['crossings_min'], det['deriv_rms']),
                        "Cabeza RMS: {:.3f}".format(det['head_rms']),
                        "Tronco RMS: {:.1f} deg".format(det['torso_rms_deg']),
                        "Torsion RMS: {:.3f}".format(det['twist_rms']),
                    ]
                    for i, txt in enumerate(overlay):
                        cv2.putText(vis, txt, (10, y0 + i*dy),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (40, 220, 40), 2)

                    if elapsed >= args.exam_secs:
                        final = (score, det)
                        break

                mp_draw.draw_landmarks(
                    vis, res.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_styles.get_default_pose_landmarks_style()
                )

            if not started:
                cv2.putText(vis, "Alinea la cinta del suelo con la linea amarilla.",
                            (10, H-60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 255, 200), 2)
                cv2.putText(vis, "[ESPACIO] Empezar 30s   [q] Salir",
                            (10, H-25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            cv2.imshow("Examen movilidad (Ubuntu/Py3.8)", vis)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            if key == ord(' ') and not started:
                started = True
                t0 = time.time()

    cap.release()
    cv2.destroyAllWindows()

    if final is not None:
        score, det = final
        print("\n===== RESULTADO EXAMEN (30s) =====")
        print("Score global              : {:5.1f} / 100".format(score))
        print("Centrado RMS              : {:.3f} (fracciones del ancho de hombros)".format(det['center_rms']))
        print("Zigzag (score)            : {:5.1f}".format(det['s_zigzag']))
        print("  - Cruces por minuto     : {:.1f}".format(det['crossings_min']))
        print("  - Curvatura dRMS        : {:.3f}".format(det['deriv_rms']))
        print("Cabeza RMS                : {:.3f}".format(det['head_rms']))
        print("Tronco RMS (deg)          : {:.2f}".format(det['torso_rms_deg']))
        print("Torsion RMS (|ΔZ hombros|): {:.3f}".format(det['twist_rms']))
        print("==================================\n")
    else:
        print("\nExamen no completado.\n")

if __name__ == "__main__":
    main()
