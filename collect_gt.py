"""P4: thu ground truth. Moi lan nhan SPACE ghi 30 Observation lien tiep vao data/gt_runs.csv.

Live:      python collect_gt.py --calib calib.npz [--source 0] [--marker-side-cm 6.0]
Du lieu gia (test evaluate.py khong can webcam):
           python collect_gt.py --synthetic --out data/gt_runs_synthetic.csv

Phim (live): SPACE chup 30 frame | N/P tu the tiep/truoc | E nhap GT thuc do | K dat nhan ca loi | Q thoat
Mot Kalman chay lien tuc suot phien; raw lay thang tu Observation.
Voi tu the luoi, SPACE chi "len co": chup bat dau khi KF da GOOD on dinh (STABLE_N frame).
Ca loi (K) chup ngay, vi muc dich la ghi lai phan ung cua he thong.
"""
import argparse
import csv
import os
import time

from contract import Observation, State
from filter import AlignmentKF

# Luoi 12 tu the trong protocol.md: (pose_id, gt_x, gt_z, gt_yaw)
GRID = [(f"P{i + 1:02d}", 0.0, z, yaw)
        for i, (z, yaw) in enumerate((z, yaw) for z in (30.0, 60.0, 100.0) for yaw in (0.0, 20.0, 40.0))]
GRID += [("P10", -15.0, 60.0, 0.0), ("P11", 15.0, 60.0, 0.0), ("P12", 15.0, 100.0, 0.0)]

FIELDS = ["pose_id", "case", "gt_x", "gt_z", "gt_yaw",
          "found", "est_raw_x", "est_raw_z", "est_raw_yaw",
          "est_kf_x", "est_kf_z", "est_kf_yaw", "sigma_x", "sigma_z", "sigma_yaw",
          "reproj_err", "ambiguous", "status", "latency_total_ms", "t"]
N_SHOT = 30
STABLE_N = 15     # SPACE chi bat dau chup khi KF GOOD lien tiep 15 frame (tranh chup luc KF chua bat kip)
ARM_TIMEOUT = 150  # ~5 s o 30 fps: qua han thi van chup va canh bao


def make_row(pose, case, obs: Observation, st: State):
    nan = float("nan")
    return {
        "pose_id": pose[0], "case": case, "gt_x": pose[1], "gt_z": pose[2], "gt_yaw": pose[3],
        "found": int(obs.found),
        "est_raw_x": obs.x_cm if obs.found else nan,
        "est_raw_z": obs.z_cm if obs.found else nan,
        "est_raw_yaw": obs.yaw_deg if obs.found else nan,
        "est_kf_x": st.x_cm, "est_kf_z": st.z_cm, "est_kf_yaw": st.yaw_deg,
        "sigma_x": st.sigma_x, "sigma_z": st.sigma_z, "sigma_yaw": st.sigma_yaw,
        "reproj_err": obs.reproj_err_px if obs.found else nan,
        "ambiguous": int(obs.ambiguous), "status": st.status,
        "latency_total_ms": st.latency_ms.get("total", nan), "t": obs.t_capture,
    }


def open_writer(path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    f = open(path, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if new:
        w.writeheader()
    return f, w


def run_synthetic(out):
    """Dung generate_static_sequence cua P2 tai tung tu the luoi; bo 60 frame dau cho KF hoi tu."""
    from synthetic import generate_static_sequence
    f, w = open_writer(out)
    for k, pose in enumerate(GRID):
        seq = generate_static_sequence(n_frames=60 + N_SHOT, true_x_cm=pose[1], true_z_cm=pose[2],
                                       true_yaw_deg=pose[3], seed=1000 + k, start_time=0.0)
        kf = AlignmentKF()
        for i, obs in enumerate(seq):
            st = kf.update(obs)
            if i >= 60:
                w.writerow(make_row(pose, "grid", obs, st))
    f.close()
    print(f"Da ghi {len(GRID) * N_SHOT} dong du lieu GIA vao {out}")


def ask_float(prompt, default):
    s = input(f"{prompt} [{default}]: ").strip()
    return float(s) if s else default


def run_live(args):
    import cv2
    from perception import Perceiver

    perceiver = Perceiver(args.calib, marker_id=7, marker_side_cm=args.marker_side_cm)
    src = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(src)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        raise SystemExit(f"Khong mo duoc nguon {args.source}")

    kf = AlignmentKF()
    f, w = open_writer(args.out)
    idx, case, pose = 0, "grid", GRID[0]
    shot_left = 0
    armed = 0          # so frame da cho ke tu khi nhan SPACE (0 = chua len co)
    good_streak = 0
    while True:
        if not cap.grab():
            print("Mat frame, thoat.")
            break
        t_cap = time.perf_counter()
        ok, frame = cap.retrieve()
        if not ok:
            continue
        obs = perceiver.process(frame, t_cap)
        st = kf.update(obs)
        good_streak = good_streak + 1 if st.status == "GOOD" else 0

        if armed:
            armed += 1
            if case != "grid" or good_streak >= STABLE_N or armed > ARM_TIMEOUT:
                if case == "grid" and good_streak < STABLE_N:
                    print(f"  CANH BAO {pose[0]}: KF chua GOOD on dinh sau {ARM_TIMEOUT} frame, van chup")
                shot_left, armed = N_SHOT, 0

        if shot_left > 0:
            w.writerow(make_row(pose, case, obs, st))
            shot_left -= 1
            if shot_left == 0:
                f.flush()
                print(f"  xong {pose[0]} ({case})")

        if obs.found and obs.corners is not None:
            cv2.polylines(frame, [obs.corners.astype(int).reshape(-1, 1, 2)], True, (0, 255, 0), 2)
        color = {"GOOD": (0, 200, 0), "DEGRADED": (0, 200, 255)}.get(st.status, (0, 0, 255))
        lines = [
            f"POSE {pose[0]} case={case}  GT x={pose[1]:.1f} z={pose[2]:.1f} yaw={pose[3]:.1f}",
            (f"RAW  x={obs.x_cm:6.2f} z={obs.z_cm:6.2f} yaw={obs.yaw_deg:6.1f} reproj={obs.reproj_err_px:.2f}"
             f"{' AMBIG' if obs.ambiguous else ''}") if obs.found else "RAW  khong thay marker id 7",
            f"KF   x={st.x_cm:6.2f} z={st.z_cm:6.2f} yaw={st.yaw_deg:6.1f}  "
            f"sig={st.sigma_x:.2f}/{st.sigma_z:.2f}/{st.sigma_yaw:.1f}  {st.status}",
            f"DANG CHUP {shot_left}" if shot_left else
            (f"CHO KALMAN ON DINH {good_streak}/{STABLE_N}" if armed else
             "SPACE chup | N/P tu the | E sua GT | K ca loi | Q thoat"),
        ]
        for j, s in enumerate(lines):
            cv2.putText(frame, s, (15, 35 + 32 * j), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)
        cv2.imshow("collect_gt (P4)", frame)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if shot_left or armed:
            continue  # khong doi tu the khi dang cho/chup
        if key == ord(" "):
            armed = 1
        elif key in (ord("n"), ord("p")):
            idx = (idx + (1 if key == ord("n") else -1)) % len(GRID)
            pose, case = GRID[idx], "grid"
        elif key == ord("e"):
            print(f"Nhap GT thuc do cho {pose[0]} (Enter giu nguyen):")
            pose = (pose[0], ask_float("x cm", pose[1]), ask_float("z cm", pose[2]), ask_float("yaw deg", pose[3]))
        elif key == ord("k"):
            label = input("Nhan ca loi (vd fail_glare, fail_yaw70, fail_blur, fail_occlude): ").strip() or "fail"
            case = label
            pose = (label, ask_float("GT x cm", pose[1]), ask_float("GT z cm", pose[2]),
                    ask_float("GT yaw deg", pose[3]))
    f.close()
    cap.release()
    cv2.destroyAllWindows()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--calib", default="calib.npz")
    ap.add_argument("--source", default="0")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--marker-side-cm", type=float, default=6.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    if args.synthetic:
        run_synthetic(args.out or "data/gt_runs_synthetic.csv")
    else:
        args.out = args.out or "data/gt_runs.csv"
        run_live(args)


if __name__ == "__main__":
    main()
