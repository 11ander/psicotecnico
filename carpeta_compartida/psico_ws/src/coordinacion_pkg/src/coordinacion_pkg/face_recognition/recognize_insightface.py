# recognize_insightface.py
import os, cv2, numpy as np
import insightface
from insightface.app import FaceAnalysis

THRESH = 0.32  # distancia coseno para ArcFace (más bajo = más estricto)

def load_db(path="data/enc_insight.npz"):
    if not os.path.exists(path): return None, None
    d = np.load(path, allow_pickle=True); return d["E"], d["N"]

def main():
    E, N = load_db()
    if E is None:
        print("Primero registra a alguien"); return

    app = FaceAnalysis(name='buffalo_l')
    app.prepare(ctx_id=0, det_size=(640,640))

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened(): 
        print("No cam"); return

    print("Reconocimiento activo (InsightFace). q para salir")
    while True:
        ok, frame = cap.read()
        if not ok: break
        frame = cv2.flip(frame, 1)
        faces = app.get(frame)

        for f in faces:
            box = f.bbox.astype(int)
            emb = f.normed_embedding  # ya normalizado L2
            # Distancia coseno a todos (menor es mejor)
            # cos_dist = 1 - cos_sim; como están normalizados, cos_sim = dot
            sims = E @ emb
            i = int(np.argmax(sims))
            cos_sim = float(sims[i])
            cos_dist = 1 - cos_sim

            if cos_dist < THRESH:
                name = N[i]
                conf = (1 - cos_dist/THRESH)  # 0..1
                label = f"{name} ({conf*100:.1f}%)"
                color = (0,200,0)
            else:
                label = "Desconocido"
                color = (0,0,255)

            cv2.rectangle(frame, (box[0],box[1]), (box[2],box[3]), color, 2)
            cv2.rectangle(frame, (box[0], box[3]-25), (box[2], box[3]), color, -1)
            cv2.putText(frame, label, (box[0]+5, box[3]-7),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

        cv2.imshow("Reconocimiento (InsightFace)", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release(); cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
