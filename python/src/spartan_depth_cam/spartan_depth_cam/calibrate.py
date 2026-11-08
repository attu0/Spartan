#!/usr/bin/env python3
"""Stereo calibration from the pairs saved by capture_pairs.

  ros2 run spartan_depth_cam calibrate --dir ~/calib --board 9x6 --square 0.025

Writes <dir>/stereo_calib.npz and <dir>/rectified_check.png.
Then copy stereo_calib.npz into src/spartan_depth_cam/config/ and rebuild.
"""
import argparse
import glob
import os

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".", help="folder containing left/ and right/")
    ap.add_argument("--board", default="9x6", help="inner corners, e.g. 9x6")
    ap.add_argument("--square", type=float, default=0.025, help="square size in metres (measure it!)")
    ap.add_argument("--mono-target", type=float, default=0.5)
    ap.add_argument("--min-pairs", type=int, default=20)
    args = ap.parse_args()

    cols, rows = (int(v) for v in args.board.lower().split("x"))
    board = (cols, rows)
    d = os.path.expanduser(args.dir)

    objp = np.zeros((cols * rows, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * args.square
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-7)

    lf = sorted(glob.glob(os.path.join(d, "left", "*.png")))
    rf = sorted(glob.glob(os.path.join(d, "right", "*.png")))
    if not lf or len(lf) != len(rf):
        raise SystemExit("left/right empty or counts differ")

    flags = cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY
    data = []
    for a, b in zip(lf, rf):
        ga, gb = cv2.imread(a, 0), cv2.imread(b, 0)
        fa, ca = cv2.findChessboardCornersSB(ga, board, flags)
        fb, cb = cv2.findChessboardCornersSB(gb, board, flags)
        if fa and fb:
            data.append((a, ca.astype(np.float32), cb.astype(np.float32)))
    size = ga.shape[::-1]
    print(f"image size {size}, pairs with board in both eyes: {len(data)}")
    if len(data) < args.min_pairs:
        raise SystemExit("not enough usable pairs - capture more")

    def mono(idx, keep):
        pts = [data[i][idx] for i in keep]
        r = cv2.calibrateCameraExtended([objp] * len(pts), pts, size, None, None)
        return r[0], r[1], r[2], r[-1].ravel()      # rms, K, D, per-view error

    keep = list(range(len(data)))
    while True:
        rl, K1, D1, pl = mono(1, keep)
        rr, K2, D2, pr = mono(2, keep)
        print(f"pairs {len(keep):3d}  mono RMS L {rl:.3f}  R {rr:.3f}")
        if (rl <= args.mono_target and rr <= args.mono_target) or len(keep) <= args.min_pairs:
            break
        err = np.maximum(pl, pr)
        worst = int(np.argmax(err))                 # drop one view at a time, the worst
        print("   dropped", data[keep[worst]][0], f"(err {err[worst]:.2f})")
        keep.pop(worst)

    n = len(keep)
    rms, K1, D1, K2, D2, R, T, E, F = cv2.stereoCalibrate(
        [objp] * n, [data[i][1] for i in keep], [data[i][2] for i in keep],
        K1, D1, K2, D2, size, flags=cv2.CALIB_FIX_INTRINSIC, criteria=crit)
    print(f"\nSTEREO RMS {rms:.3f}   baseline {np.linalg.norm(T):.4f} m   pairs {n}")
    for name, K in (("left", K1), ("right", K2)):
        print(f"{name}: fx {K[0, 0]:.0f} fy {K[1, 1]:.0f} cx {K[0, 2]:.0f} cy {K[1, 2]:.0f}")

    R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(K1, D1, K2, D2, size, R, T, alpha=0)
    npz = os.path.join(d, "stereo_calib.npz")
    np.savez(npz, K1=K1, D1=D1, K2=K2, D2=D2, R1=R1, R2=R2, P1=P1, P2=P2, Q=Q, size=size)

    mL = cv2.initUndistortRectifyMap(K1, D1, R1, P1, size, cv2.CV_16SC2)
    mR = cv2.initUndistortRectifyMap(K2, D2, R2, P2, size, cv2.CV_16SC2)
    i = keep[len(keep) // 2]
    pair = cv2.hconcat([cv2.remap(cv2.imread(lf[i]), *mL, cv2.INTER_LINEAR),
                        cv2.remap(cv2.imread(rf[i]), *mR, cv2.INTER_LINEAR)])
    for y in range(0, pair.shape[0], 40):
        cv2.line(pair, (0, y), (pair.shape[1], y), (0, 255, 0), 1)
    chk = os.path.join(d, "rectified_check.png")
    cv2.imwrite(chk, pair)
    print("saved", npz, "and", chk)


if __name__ == "__main__":
    main()
