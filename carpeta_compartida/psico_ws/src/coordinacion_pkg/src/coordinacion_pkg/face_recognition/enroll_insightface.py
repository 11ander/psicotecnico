# enroll_insightface.py
import os, argparse, time
import cv2, numpy as np
import insightface
from insightface.app import FaceAnalysis

def get_app():
    app = FaceAnalysis(name='buffalo_l')  # modelo con detección+embeddings
    app.prepare(ctx_id=0, det_size=(640,640))
    return app

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--shots", type=int, default=20)
    ap.add_argument("--cam", type=int, default=0)
    args = ap.parse_args()

    os.makedirs("data/dataset", exist_ok=True)
    os.makedirs(f"data/dataset/{args.name}", exist_ok=True)
    encs = []

    app = get_app()
    cap = cv2.VideoCapture(args.cam, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("No cam"); return

    print(f"Registrando {args.name} — pulsa ESPACIO para capturar ({args.shots})")
    while len(encs) < args.shots:
        ok, frame = cap.read()
        if not ok: break
        frame = cv2.flip(frame, 1)
        faces = app.get(frame)

        for f in faces:
            box = f.bbox.astype(int)
            cv2.rectangle(frame, (box[0],box[1]), (box[2],box[3]), (0,255,0), 2)

        cv2.putText(frame, f"Capturas: {len(encs)}/{args.shots} (Espacio=q)", (10,30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20,220,20), 2)
        cv2.imshow("Registro (InsightFace)", frame)
        k = cv2.waitKey(1) & 0xFF
        if k == ord(' '):
            if len(faces) != 1:
                print("Necesito exactamente 1 cara visible"); continue
            encs.append(faces[0].normed_embedding)  # vector 512-D normalizado
            cv2.imwrite(f"data/dataset/{args.name}/{int(time.time()*1000)}.jpg", frame)
            print("OK")
        elif k == ord('q'):
            break

    cap.release(); cv2.destroyAllWindows()
    if encs:
        encs = np.vstack(encs)
        names = np.array([args.name]*len(encs))
        path = "data/enc_insight.npz"
        if os.path.exists(path):
            d = np.load(path, allow_pickle=True)
            E = np.vstack([d["E"], encs])
            N = np.concatenate([d["N"], names])
        else:
            E, N = encs, names
        np.savez(path, E=E, N=N)
        print(f"Guardado {path} con {E.shape[0]} embeddings.")
