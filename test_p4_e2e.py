"""P4: kiem tra dau-cuoi bang video ArUco RENDER (KHONG phai bang chung that).

python test_p4_e2e.py

Dung video marker id 7 o dung 12 tu the luoi + 2 ca loi (yaw 75, che 1 goc), chay chinh vong lap
collect_gt.run_live (phim duoc gia lap) voi Perceiver + AlignmentKF that, roi tom tat theo tu the.
Moi file nam trong thu muc tam. Exit 1 neu raw (P1) sai > 1 cm z hoac sai dau yaw o tu the luoi on dinh.
KF (P2) chi bao cao: ti le GOOD va sai so yaw theo tu the.
"""
import builtins
import os
import sys
import tempfile
import types

import cv2
import numpy as np
import pandas as pd

from calibrate import approximate_calibration
from test_perception import pose_rotation
import collect_gt

FAILS = [("fail_yaw75", 0.0, 60.0, 75.0, False), ("fail_occlude", 0.0, 60.0, 0.0, True)]
WARM = 40
PER = WARM + collect_gt.ARM_TIMEOUT + collect_gt.N_SHOT + 20  # du dai ke ca khi KF cho het han


def make_video(path, K, poses):
    half = 3.0
    obj = np.array([[-half, half, 0], [half, half, 0], [half, -half, 0], [-half, -half, 0]], np.float64)
    marker = cv2.aruco.generateImageMarker(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50), 7, 600)
    src = np.array([[0, 0], [599, 0], [599, 599], [0, 599]], np.float32)
    rng = np.random.default_rng(0)
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 30, (1280, 720))
    for x, z, yaw, occlude in poses:
        pts, _ = cv2.projectPoints(obj, pose_rotation(yaw), np.array([x, 0.0, z]), K, np.zeros(5))
        H = cv2.getPerspectiveTransform(src, pts.reshape(4, 2).astype(np.float32))
        g = cv2.warpPerspective(marker, H, (1280, 720), flags=cv2.INTER_LINEAR, borderValue=200)
        g = cv2.GaussianBlur(g, (3, 3), 0.8)
        if occlude:
            c = pts.reshape(4, 2)[0].astype(int)
            cv2.rectangle(g, tuple(c - 25), tuple(c + 25), 200, -1)
        base = g.astype(np.float32)
        for _ in range(PER):
            noisy = np.clip(base + rng.normal(0, 4, base.shape), 0, 255).astype(np.uint8)
            w.write(cv2.cvtColor(noisy, cv2.COLOR_GRAY2BGR))
    w.release()


def main():
    tmp = tempfile.mkdtemp(prefix="p4_e2e_")
    calib = os.path.join(tmp, "calib.npz")
    approximate_calibration(68, (1280, 720), calib)
    K = np.load(calib)["K"]
    poses = [(p[1], p[2], p[3], False) for p in collect_gt.GRID] + [f[1:] for f in FAILS]
    video = os.path.join(tmp, "grid.avi")
    make_video(video, K, poses)

    n_grid = len(collect_gt.GRID)
    answers = [str(v) for f in FAILS for v in (f[0], f[1], f[2], f[3])]
    counter = {"i": -1}

    def fake_wait(_):
        counter["i"] += 1
        k, off = divmod(counter["i"], PER)
        if off == WARM:
            return ord(" ")
        if off == PER - 1:
            return ord("k") if n_grid - 1 <= k < len(poses) - 1 else ord("n")
        return 255

    saved = (cv2.waitKey, cv2.imshow, cv2.destroyAllWindows, builtins.input)
    cv2.waitKey, cv2.imshow, cv2.destroyAllWindows = fake_wait, (lambda *a, **k: None), (lambda: None)
    builtins.input = lambda prompt="": answers.pop(0)
    out = os.path.join(tmp, "gt_runs_render.csv")
    try:
        collect_gt.run_live(types.SimpleNamespace(calib=calib, source=video, width=1280, height=720,
                                                  marker_side_cm=6.0, out=out))
    finally:
        cv2.waitKey, cv2.imshow, cv2.destroyAllWindows, builtins.input = saved

    d = pd.read_csv(out)
    wrap = lambda a: (a + 180) % 360 - 180  # noqa: E731
    d["err_raw_z"] = (d.est_raw_z - d.gt_z).abs()
    d["err_raw_yaw"] = wrap(d.est_raw_yaw - d.gt_yaw).abs()
    d["err_kf_yaw"] = wrap(d.est_kf_yaw - d.gt_yaw).abs()
    t = d.groupby("pose_id", sort=False).agg(
        z=("gt_z", "first"), yaw=("gt_yaw", "first"), found=("found", "mean"),
        raw_z_err=("err_raw_z", "median"), raw_yaw_err=("err_raw_yaw", "median"),
        kf_yaw_err=("err_kf_yaw", "median"), ambiguous=("ambiguous", "mean"),
        GOOD=("status", lambda s: (s == "GOOD").mean()), LOST=("status", lambda s: (s == "LOST").mean()))
    print("\nDU LIEU RENDER - KHONG phai bang chung. CSV:", out)
    print(t.round(2).to_string())

    grid = t.loc[[p[0] for p in collect_gt.GRID]]
    # P08 (z100 yaw20) la ca lat nghiem IPPE da biet: chi bao cao, khong tinh vao PASS cua raw
    stable = grid.drop(index="P08", errors="ignore")
    bad_raw = stable[(stable.found < 1) | (stable.raw_z_err > 1.0) | (stable.raw_yaw_err > 5.0)]
    weak_kf = grid[grid.GOOD < 0.9]
    print("\nRAW (P1):", "PASS" if bad_raw.empty else f"FAIL o {list(bad_raw.index)}")
    print("KF  (P2): GOOD >= 90% o", len(grid) - len(weak_kf), "/", len(grid), "tu the luoi",
          "" if weak_kf.empty else f"- yeu o {list(weak_kf.index)}")
    return 0 if bad_raw.empty else 1


if __name__ == "__main__":
    sys.exit(main())
