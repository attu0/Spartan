#!/usr/bin/env python3
"""Collect left/right chessboard pairs for calibration (needs a display).

  ros2 run spartan_depth_cam capture_pairs --board 9x6 --target 40 --out ~/calib

Saves out/left/NNN.png and out/right/NNN.png automatically when the board is found in both
eyes, is still, and is in a new pose. Keys: a = toggle auto, s = save now, q = quit.
"""
import argparse
import os
import time

import cv2
import numpy as np

from spartan_depth_cam.utils import open_stereo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", type=int, default=-1, help="/dev/videoN index, -1 = auto")
    ap.add_argument("--board", default="9x6", help="inner corners, e.g. 9x6")
    ap.add_argument("--target", type=int, default=40)
    ap.add_argument("--out", default=".")
    args = ap.parse_args()

    cols, rows = (int(v) for v in args.board.lower().split("x"))
    board = (cols, rows)
    out = os.path.expanduser(args.out)
    ld, rd = os.path.join(out, "left"), os.path.join(out, "right")
    os.makedirs(ld, exist_ok=True)
    os.makedirs(rd, exist_ok=True)
    if os.listdir(ld) or os.listdir(rd):
        raise SystemExit(f"{ld} or {rd} not empty - delete old images first")

    cap, dev = open_stereo(cv2, args.device)
    print("camera:", dev)

    def outer(c):                                   # 4 outer corners of the detected grid
        c = c.reshape(-1, 2)
        return np.array([c[0], c[cols - 1], c[-cols], c[-1]])

    saved, prev, still, last_t, auto, n = [], None, 0, 0.0, True, 0
    while n < args.target:
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        L, R = frame[:, :w // 2], frame[:, w // 2:]
        fL, cL = cv2.findChessboardCornersSB(cv2.cvtColor(L, cv2.COLOR_BGR2GRAY), board,
                                             cv2.CALIB_CB_ACCURACY)
        fR, cR = cv2.findChessboardCornersSB(cv2.cvtColor(R, cv2.COLOR_BGR2GRAY), board,
                                             cv2.CALIB_CB_ACCURACY)
        both = bool(fL and fR)

        new_pose = False
        if both:
            o = outer(cL)
            still = still + 1 if prev is not None and np.abs(o - prev).mean() < 0.7 else 0
            prev = o
            new_pose = all(np.abs(o - s).mean() > 40 for s in saved)
        else:
            prev, still = None, 0

        save = auto and both and still >= 4 and new_pose and time.time() - last_t > 1.0

        vis = frame.copy()
        if fL:
            cv2.drawChessboardCorners(vis[:, :w // 2], board, cL, True)
        if fR:
            cv2.drawChessboardCorners(vis[:, w // 2:], board, cR, True)
        vis = cv2.resize(vis, (w // 2, h // 2))
        msg = f"{n}/{args.target} both={both} still={still} newpose={new_pose} auto={auto}"
        cv2.putText(vis, msg, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 255, 0) if both else (0, 0, 255), 2)
        cv2.imshow("stereo", vis)

        k = cv2.waitKey(1) & 0xFF
        if k == ord("q"):
            break
        if k == ord("a"):
            auto = not auto
        if k == ord("s") and both:
            save = True
        if save:
            cv2.imwrite(os.path.join(ld, f"{n:03d}.png"), L)
            cv2.imwrite(os.path.join(rd, f"{n:03d}.png"), R)
            saved.append(outer(cL))
            n += 1
            last_t, still = time.time(), 0
            print("saved", n)
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
