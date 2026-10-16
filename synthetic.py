# synthetic.py
"""
Sinh chuoi Observation gia de P2, P3, P4 test he thong ma khong can webcam.
Bao gom:
1. Quỹ đạo tiến vào cổng sạc (z: 80 -> 15 cm, x: +15 -> 0 cm, yaw: +25 -> 0 deg),
   kèm nhiễu Gaussian tăng theo z^2, vài frame mất dấu (found=False) và vài outlier.
2. Tư thế đứng yên để kiểm tra độ lệch chuẩn (std) raw vs filtered.
"""
from __future__ import annotations

import time
from typing import Iterator, List
import numpy as np

from contract import Observation


def _fake_corners(x_cm: float, z_cm: float, yaw_deg: float) -> np.ndarray:
    """Sinh 4 goc marker gia tren anh (1280x720) de P3 test ve HUD."""
    cx = 640.0 + (x_cm / max(z_cm, 10.0)) * 800.0
    cy = 360.0
    half_s = (3.0 / max(z_cm, 10.0)) * 800.0
    skew = np.sin(np.radians(yaw_deg)) * half_s * 0.25
    return np.array(
        [
            [cx - half_s, cy - half_s + skew],
            [cx + half_s, cy - half_s - skew],
            [cx + half_s, cy + half_s - skew],
            [cx - half_s, cy + half_s + skew],
        ],
        dtype=np.float32,
    )


def generate_approach_sequence(
    n_frames: int = 240,
    fps: float = 30.0,
    seed: int = 42,
    start_time: float | None = None,
) -> List[Observation]:
    """
    Sinh chuỗi Observation giả mô phỏng đầu sạc tiến từ z=80 cm về z=15 cm:
    - Nhiễu đo thực tế tăng theo (z / 50)^2.
    - Một số frame bị che khuất (found=False).
    - Một số frame bị lóa / lật nghiệm (outlier lớn hoặc ambiguous=True).
    """
    rng = np.random.default_rng(seed)
    dt = 1.0 / fps
    t0 = time.perf_counter() if start_time is None else start_time

    observations: List[Observation] = []

    for i in range(n_frames):
        t_cap = t0 + i * dt
        t_det = t_cap + rng.uniform(0.004, 0.009)  # giả lập detect mất 4-9 ms

        # Tiến dần trong 80% thời gian đầu, 20% cuối giữ yên ở vị trí đã căn chỉnh
        alpha = min(1.0, i / max(1, int(n_frames * 0.8)))
        true_z = 80.0 + (15.0 - 80.0) * alpha
        # Dao động nhẹ khi chỉnh hướng tiến về 0
        true_x = 15.0 * (1.0 - alpha) * np.cos(alpha * np.pi * 1.5)
        true_yaw = 25.0 * (1.0 - alpha)

        # Khoảng frame 70..75: mất dấu ngắn (6 frame ~ 0.2s)
        if 70 <= i <= 75:
            observations.append(
                Observation(
                    t_capture=t_cap,
                    t_detect_done=t_det,
                    found=False,
                )
            )
            continue

        # Nhiễu Gaussian tăng theo z^2 (vì độ phân giải góc cố định, sai số độ sâu tỉ lệ với z^2)
        depth_scale = (true_z / 50.0) ** 2
        sigma_x_sim = 0.20 + 0.45 * depth_scale
        sigma_z_sim = 0.30 + 0.90 * depth_scale
        sigma_yaw_sim = 0.60 + 1.40 * depth_scale

        x_meas = float(true_x + rng.normal(0.0, sigma_x_sim))
        z_meas = float(true_z + rng.normal(0.0, sigma_z_sim))
        yaw_meas = float(true_yaw + rng.normal(0.0, sigma_yaw_sim))
        reproj_err = float(abs(rng.normal(0.35, 0.12)) + 0.15 * depth_scale)
        ambiguous = False

        # Bơm vài outlier rõ rệt (nhảy vọt do phản xạ hoặc góc nghiêng) để test Mahalanobis gating
        if i in (45, 110, 165):
            x_meas += float(rng.choice([-18.0, 22.0]))
            z_meas += float(rng.choice([-25.0, 30.0]))
            yaw_meas += float(rng.choice([-35.0, 40.0]))
            reproj_err = 2.8

        # Bơm vài frame mơ hồ nghiệm IPPE (ambiguous=True)
        if i in (90, 91, 140):
            ambiguous = True
            reproj_err = 1.6

        corners = _fake_corners(x_meas, z_meas, yaw_meas)
        rvec = np.array([[0.0], [np.radians(yaw_meas)], [0.0]], dtype=np.float64)
        tvec = np.array([[x_meas], [0.0], [z_meas]], dtype=np.float64)

        observations.append(
            Observation(
                t_capture=t_cap,
                t_detect_done=t_det,
                found=True,
                x_cm=x_meas,
                z_cm=z_meas,
                yaw_deg=yaw_meas,
                reproj_err_px=reproj_err,
                ambiguous=ambiguous,
                corners=corners,
                rvec=rvec,
                tvec=tvec,
            )
        )

    return observations


def generate_static_sequence(
    n_frames: int = 200,
    fps: float = 30.0,
    true_x_cm: float = 0.4,
    true_z_cm: float = 45.0,
    true_yaw_deg: float = -2.0,
    seed: int = 123,
    start_time: float | None = None,
) -> List[Observation]:
    """
    Sinh chuỗi Observation giả ở tư thế ĐỨNG YÊN để kiểm chứng độ giảm rung (std raw vs filtered)
    và kiểm tra tỉ lệ lỗi nằm trong +-2 sigma.
    """
    rng = np.random.default_rng(seed)
    dt = 1.0 / fps
    t0 = time.perf_counter() if start_time is None else start_time

    depth_scale = (true_z_cm / 50.0) ** 2
    sigma_x_sim = 0.25 + 0.55 * depth_scale
    sigma_z_sim = 0.35 + 1.00 * depth_scale
    sigma_yaw_sim = 0.70 + 1.50 * depth_scale

    observations: List[Observation] = []
    for i in range(n_frames):
        t_cap = t0 + i * dt
        t_det = t_cap + rng.uniform(0.004, 0.008)

        x_meas = float(true_x_cm + rng.normal(0.0, sigma_x_sim))
        z_meas = float(true_z_cm + rng.normal(0.0, sigma_z_sim))
        yaw_meas = float(true_yaw_deg + rng.normal(0.0, sigma_yaw_sim))
        reproj_err = float(abs(rng.normal(0.35, 0.10)))

        # Thêm 2 outlier ở giữa để đảm bảo filter không bị kéo lệch khi đứng yên
        if i in (60, 130):
            x_meas += 15.0
            z_meas -= 20.0
            yaw_meas += 30.0
            reproj_err = 3.2

        corners = _fake_corners(x_meas, z_meas, yaw_meas)
        rvec = np.array([[0.0], [np.radians(yaw_meas)], [0.0]], dtype=np.float64)
        tvec = np.array([[x_meas], [0.0], [z_meas]], dtype=np.float64)

        observations.append(
            Observation(
                t_capture=t_cap,
                t_detect_done=t_det,
                found=True,
                x_cm=x_meas,
                z_cm=z_meas,
                yaw_deg=yaw_meas,
                reproj_err_px=reproj_err,
                ambiguous=False,
                corners=corners,
                rvec=rvec,
                tvec=tvec,
            )
        )
    return observations


def stream_synthetic(
    fps: float = 30.0, realtime: bool = False, seed: int = 42
) -> Iterator[Observation]:
    """Generator phát liên tục các Observation giả (lặp lại đường tiến) cho P3 ghép thử."""
    dt = 1.0 / fps
    epoch = 0
    while True:
        seq = generate_approach_sequence(
            n_frames=240, fps=fps, seed=seed + epoch, start_time=time.perf_counter()
        )
        for obs in seq:
            if realtime:
                now = time.perf_counter()
                sleep_s = obs.t_capture - now
                if sleep_s > 0:
                    time.sleep(sleep_s)
                obs.t_capture = time.perf_counter()
                obs.t_detect_done = obs.t_capture + 0.005
            yield obs
            if not realtime:
                pass
        epoch += 1


if __name__ == "__main__":
    seq = generate_approach_sequence(n_frames=10)
    print(f"Generated {len(seq)} synthetic observations. Sample[0]:")
    print(seq[0])
