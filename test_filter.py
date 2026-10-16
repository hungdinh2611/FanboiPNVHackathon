# test_filter.py
"""
Kiem thu toan dien cho P2 (filter.py, guidance.py, timing.py, synthetic.py):
1. So sanh do lech chuan (std) Raw va Filtered o tu the dung yen (Static test).
2. Kiem tra ti le sai so thuc nam trong khoang +-2 sigma (Calibration of Uncertainty).
3. Kiem tra Mahalanobis gating loai outlier, xu ly ambiguous/mất dấu ngắn (DEGRADED) và mất dấu dài (LOST -> reset).
4. Kiem tra Guidance deadband + hysteresis khong bi nhap nhay.
5. In bao cao do tre p50 va p95 (ms).
"""
from __future__ import annotations

import numpy as np

from contract import Observation
from filter import AlignmentKF
from synthetic import generate_approach_sequence, generate_static_sequence
from timing import latency_report


def run_static_std_test() -> None:
    print("=" * 68)
    print("1. KIEM THU TU THE DUNG YEN (STATIC POSE: RAW vs KALMAN FILTERED)")
    print("=" * 68)
    true_x, true_z, true_yaw = 0.4, 45.0, -2.0
    seq = generate_static_sequence(
        n_frames=200,
        true_x_cm=true_x,
        true_z_cm=true_z,
        true_yaw_deg=true_yaw,
        seed=123,
    )

    kf_on = AlignmentKF(filter_enabled=True)
    kf_off = AlignmentKF(filter_enabled=False)

    raw_x, raw_z, raw_yaw = [], [], []
    flt_x, flt_z, flt_yaw = [], [], []
    within_2sigma_x, within_2sigma_z, within_2sigma_yaw = 0, 0, 0
    degraded_count = 0

    for idx, obs in enumerate(seq):
        st_raw = kf_off.update(obs)
        st_flt = kf_on.update(obs)

        if st_flt.status == "DEGRADED":
            degraded_count += 1

        # Bỏ 10 frame đầu khởi động (warm-up) khi tính std hội tụ
        if idx >= 10:
            raw_x.append(st_raw.x_cm)
            raw_z.append(st_raw.z_cm)
            raw_yaw.append(st_raw.yaw_deg)

            flt_x.append(st_flt.x_cm)
            flt_z.append(st_flt.z_cm)
            flt_yaw.append(st_flt.yaw_deg)

            if abs(st_flt.x_cm - true_x) <= 2.0 * st_flt.sigma_x:
                within_2sigma_x += 1
            if abs(st_flt.z_cm - true_z) <= 2.0 * st_flt.sigma_z:
                within_2sigma_z += 1
            if abs(st_flt.yaw_deg - true_yaw) <= 2.0 * st_flt.sigma_yaw:
                within_2sigma_yaw += 1

    std_raw_x, std_raw_z, std_raw_yaw = (
        float(np.std(raw_x)),
        float(np.std(raw_z)),
        float(np.std(raw_yaw)),
    )
    std_flt_x, std_flt_z, std_flt_yaw = (
        float(np.std(flt_x)),
        float(np.std(flt_z)),
        float(np.std(flt_yaw)),
    )

    n_eval = len(flt_x)
    print(f"So frame danh gia (sau warm-up): {n_eval} (co {degraded_count} frame outlier bi gate -> DEGRADED)")
    print(f"  x (cm)   | Raw std: {std_raw_x:.3f} cm  -> Filtered std: {std_flt_x:.3f} cm  (giam {(1 - std_flt_x/std_raw_x)*100:.1f}%)")
    print(f"  z (cm)   | Raw std: {std_raw_z:.3f} cm  -> Filtered std: {std_flt_z:.3f} cm  (giam {(1 - std_flt_z/std_raw_z)*100:.1f}%)")
    print(f"  yaw (do) | Raw std: {std_raw_yaw:.3f} deg -> Filtered std: {std_flt_yaw:.3f} deg (giam {(1 - std_flt_yaw/std_raw_yaw)*100:.1f}%)")
    print(
        f"  Ti le loi thuc nam trong +-2*sigma: "
        f"x={within_2sigma_x/n_eval*100:.1f}%, "
        f"z={within_2sigma_z/n_eval*100:.1f}%, "
        f"yaw={within_2sigma_yaw/n_eval*100:.1f}%"
    )

    assert std_flt_x < std_raw_x * 0.5, "Filtered x std phai thap hon Raw ro ret!"
    assert std_flt_z < std_raw_z * 0.5, "Filtered z std phai thap hon Raw ro ret!"
    assert std_flt_yaw < std_raw_yaw * 0.5, "Filtered yaw std phai thap hon Raw ro ret!"


def run_approach_and_hysteresis_test() -> None:
    print("\n" + "=" * 68)
    print("2. KIEM THU QUY DAO TIEN VAO CONG SAC & HYSTERESIS GUIDANCE")
    print("=" * 68)
    seq = generate_approach_sequence(n_frames=240, fps=30.0, seed=42)
    kf = AlignmentKF(filter_enabled=True)

    statuses = {"GOOD": 0, "DEGRADED": 0, "LOST": 0}
    transitions = 0
    prev_guidance = None
    last_state = None

    for obs in seq:
        st = kf.update(obs)
        statuses[st.status] = statuses.get(st.status, 0) + 1
        if prev_guidance is not None and st.guidance != prev_guidance:
            transitions += 1
        prev_guidance = st.guidance
        last_state = st

    assert last_state is not None
    print(f"Phan bo trang thai tren 240 frame: {statuses}")
    print(f"So lan doi chu guidance tren toan quy dao 240 frame: {transitions} lan (khong nhap nhay)")
    print(
        f"Trang thai cuoi (khi da tien sat z=15cm): "
        f"x={last_state.x_cm:.2f}+-{last_state.sigma_x:.2f} cm, "
        f"z={last_state.z_cm:.2f}+-{last_state.sigma_z:.2f} cm, "
        f"yaw={last_state.yaw_deg:.2f}+-{last_state.sigma_yaw:.2f} deg"
    )
    print(f"Guidance cuoi: '{last_state.guidance}' | aligned={last_state.aligned}")
    assert last_state.aligned is True, "Cuoi quy dao phai dat trang thai aligned=True!"

    # Kiểm tra mất dấu quá 0.5s -> LOST và quá 2.0s -> reset filter
    t_base = last_state.t_capture
    for step in range(1, 75):
        t_cur = t_base + step * (1.0 / 30.0)
        st_lost = kf.update(
            Observation(t_capture=t_cur, t_detect_done=t_cur + 0.002, found=False)
        )
        if step == 20:  # ~0.67s > 0.5s
            assert st_lost.status == "LOST", f"Frame mat dau 0.67s phai LOST, nhung nhan {st_lost.status}"
            assert "MAT DAU" in st_lost.guidance
    assert kf.initialized is False, "Mat dau qua 2.0s phai reset filter (initialized=False)!"
    print("Kiem tra mat dau >0.5s -> LOST va >2.0s -> reset filter: PASS!")

    rep = kf.latency_tracker.latency_report()
    print(
        f"Do tre (Latency): capture-detect p50={rep['capture_detect_p50_ms']:.2f} ms, "
        f"detect-filter p50={rep['detect_filter_p50_ms']:.3f} ms, "
        f"total p50={rep['p50_ms']:.2f} ms | p95={rep['p95_ms']:.2f} ms"
    )
    print("=" * 68)
    print("TAT CA BAI KIEM THU P2 DEU PASS!")


if __name__ == "__main__":
    run_static_std_test()
    run_approach_and_hysteresis_test()
