# filter.py
"""
Kalman Filter tuyen tinh 6 chieu (Constant-Velocity) bang NumPy thuan cho Charge-Port Alignment Assist.
Vector trang thai: state = [x, z, yaw, vx, vz, vyaw]^T (don vi: cm, deg, cm/s, deg/s).

Cac tru cot Track 4 duoc ap dung:
1. Bat dinh (Uncertainty):
   - Ma tran nhieu do R phu thuoc khoang cach z^2 (vi sai so goc/pixel chuyen thanh sai so do sau
     ti le voi z^2: sigma_z ~ (z^2 / (f * s)) * sigma_px) va tang them khi reproj_err_px hoac ambiguous cao.
   - Gating Mahalanobis d^2 = y^T * S^-1 * y <= chi2(df=3, p=0.99) = 11.345 de loai outlier dot ngot.
2. Thoi gian (Time):
   - dt thuc te lay tu obs.t_capture, xu ly mat dau ngan (<0.5s DEGRADED), mat dau dai (>0.5s LOST, >2.0s reset).
"""
from __future__ import annotations

import math
import time
import numpy as np

from contract import Observation, State
from guidance import GuidanceGenerator
from timing import LatencyTracker

# Ngưỡng Chi-square 3 bậc tự do ở mức tin cậy 99%: P(chi2_3 <= 11.3449) = 0.99
CHI2_3DOF_99 = 11.3449


def _wrap_angle_deg(angle: float) -> float:
    """Đưa góc (độ) về khoảng [-180, 180)."""
    return (angle + 180.0) % 360.0 - 180.0


class AlignmentKF:
    """
    Kalman Filter ước lượng trạng thái `[x, z, yaw, vx, vz, vyaw]` và độ bất định `(sigma_x, sigma_z, sigma_yaw)`.
    Thuộc tính bắt buộc theo `contract.py`:
      - `filter_enabled: bool`: nếu False, trả thẳng giá trị raw của Observation để demo so sánh Raw vs Filtered.
      - `update(obs: Observation) -> State`
    """

    def __init__(
        self,
        filter_enabled: bool = True,
        stop_z_cm: float = 15.0,
        lost_timeout_s: float = 0.5,
        reset_timeout_s: float = 2.0,
        sigma_max_x_cm: float = 8.0,
        sigma_max_z_cm: float = 12.0,
        sigma_max_yaw_deg: float = 20.0,
    ) -> None:
        self.filter_enabled: bool = filter_enabled
        self.stop_z_cm = stop_z_cm
        self.lost_timeout_s = lost_timeout_s
        self.reset_timeout_s = reset_timeout_s
        self.sigma_max_x_cm = sigma_max_x_cm
        self.sigma_max_z_cm = sigma_max_z_cm
        self.sigma_max_yaw_deg = sigma_max_yaw_deg

        self.guidance_gen = GuidanceGenerator(stop_z_cm=stop_z_cm)
        self.latency_tracker = LatencyTracker()

        # Ma trận quan sát H (3x6): chỉ đo trực tiếp [x, z, yaw]
        self.H = np.array(
            [
                [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            ],
            dtype=np.float64,
        )

        # Cận độ lệch chuẩn gia tốc quá trình (process noise): a_x, a_z (cm/s^2), a_yaw (deg/s^2)
        # Đặt đủ lớn để theo kịp pha giảm tốc khi đầu sạc dừng lại ở cổng sạc
        self.accel_std = np.array([15.0, 20.0, 35.0], dtype=np.float64)

        self.reset()

    def reset(self) -> None:
        """Khởi tạo lại filter khi mới bắt đầu hoặc sau khi mất dấu quá 2 giây."""
        self.initialized: bool = False
        self.x = np.zeros(6, dtype=np.float64)  # [x, z, yaw, vx, vz, vyaw]
        self.P = np.diag([25.0, 49.0, 100.0, 100.0, 100.0, 400.0]).astype(np.float64)
        self.last_t_capture: float | None = None
        self.last_valid_obs_t: float | None = None
        self.last_mahalanobis_sq: float = 0.0
        self.guidance_gen.reset()

    def _build_F_and_Q(self, dt: float) -> tuple[np.ndarray, np.ndarray]:
        """
        Xây dựng ma trận chuyển trạng thái F (mô hình vận tốc không đổi)
        và ma trận hiệp phương sai nhiễu quá trình Q (piecewise white noise acceleration).
        """
        F = np.eye(6, dtype=np.float64)
        F[0, 3] = dt
        F[1, 4] = dt
        F[2, 5] = dt

        dt2 = dt * dt
        dt3 = dt2 * dt / 2.0
        dt4 = dt2 * dt2 / 4.0

        Q = np.zeros((6, 6), dtype=np.float64)
        for idx in range(3):
            q_a = float(self.accel_std[idx] ** 2)
            Q[idx, idx] = dt4 * q_a
            Q[idx, idx + 3] = dt3 * q_a
            Q[idx + 3, idx] = dt3 * q_a
            Q[idx + 3, idx + 3] = dt2 * q_a

        return F, Q

    def _compute_R(self, obs: Observation) -> np.ndarray:
        """
        Tính ma trận nhiễu đo R = diag(sigma_x^2, sigma_z^2, sigma_yaw^2) phụ thuộc quan sát:
        - Công thức vật lý: với marker kích thước s và tiêu cự f, kích thước ảnh u ~ f*s/z
          => |dz| ~ (z^2 / (f*s)) * |du|. Do đó sai số độ sâu sigma_z và sai số ngang sigma_x
          tăng theo hàm bậc hai của khoảng cách (z / 50 cm)^2.
        - Khi `reproj_err_px` lớn (mờ chuyển động, che góc, ánh sáng lóa), tăng hệ số phạt reproj_factor.
        - Khi `ambiguous=True` (hai nghiệm IPPE của PnP phẳng có sai số tái chiếu gần nhau),
          nhân hệ số phạt vào phương sai để filter giảm trọng số (Kalman gain K nhỏ lại).
        """
        z_ref = max(10.0, min(200.0, float(obs.z_cm)))
        depth_factor = (z_ref / 50.0) ** 2

        # Hệ số phạt theo reprojection error (bình thường ~0.3-0.6 px; >0.5 px bắt đầu phạt mạnh)
        excess_reproj = max(0.0, float(obs.reproj_err_px) - 0.5)
        reproj_factor = 1.0 + 1.8 * excess_reproj

        # Công thức độ lệch chuẩn nhiễu đo theo khoảng cách và reprojection error:
        # sigma_x(z)   = (0.20 + 0.50 * (z / 50)^2) * reproj_factor  [cm]
        # sigma_z(z)   = (0.30 + 0.95 * (z / 50)^2) * reproj_factor  [cm]
        # sigma_yaw(z) = (0.60 + 1.50 * (z / 50)^2) * reproj_factor  [deg]
        sigma_x = (0.20 + 0.50 * depth_factor) * reproj_factor
        sigma_z = (0.30 + 0.95 * depth_factor) * reproj_factor
        sigma_yaw = (0.60 + 1.50 * depth_factor) * reproj_factor

        if obs.ambiguous:
            # Nghiệm PnP mơ hồ ảnh hưởng mạnh nhất tới góc nghiêng yaw và khoảng cách z
            sigma_x *= 2.0
            sigma_z *= 2.5
            sigma_yaw *= 4.0

        return np.diag([sigma_x**2, sigma_z**2, sigma_yaw**2]).astype(np.float64)

    def _extract_sigmas(self) -> tuple[float, float, float]:
        """Lấy (sigma_x, sigma_z, sigma_yaw) từ đường chéo chính của ma trận hiệp phương sai P."""
        sx = float(math.sqrt(max(1e-6, self.P[0, 0])))
        sz = float(math.sqrt(max(1e-6, self.P[1, 1])))
        syaw = float(math.sqrt(max(1e-6, self.P[2, 2])))
        return sx, sz, syaw

    def update(self, obs: Observation) -> State:
        """
        Cập nhật trạng thái từ `Observation` mới nhất và trả về `State`.
        """
        t_update_start = time.perf_counter()
        t_cap = float(obs.t_capture)

        # Tính dt từ t_capture của frame trước
        if self.last_t_capture is None:
            dt = 1.0 / 30.0
        else:
            dt = t_cap - self.last_t_capture
            if dt <= 0.0 or dt > 1.0:
                dt = 1.0 / 30.0
        self.last_t_capture = t_cap

        # =====================================================================
        # Chế độ TẮT FILTER (filter_enabled == False): trả thẳng giá trị raw
        # =====================================================================
        if not self.filter_enabled:
            if obs.found:
                R_raw = self._compute_R(obs)
                sx = float(math.sqrt(R_raw[0, 0]))
                sz = float(math.sqrt(R_raw[1, 1]))
                syaw = float(math.sqrt(R_raw[2, 2]))
                status = (
                    "DEGRADED"
                    if (obs.ambiguous or obs.reproj_err_px > 1.5)
                    else "GOOD"
                )
                x_out, z_out, yaw_out = (
                    float(obs.x_cm),
                    float(obs.z_cm),
                    float(obs.yaw_deg),
                )
                self.last_valid_obs_t = t_cap
            else:
                sx, sz, syaw = 9.9, 9.9, 25.0
                status = "LOST"
                x_out = float(self.x[0]) if self.initialized else 0.0
                z_out = float(self.x[1]) if self.initialized else 0.0
                yaw_out = float(self.x[2]) if self.initialized else 0.0

            guidance_str, aligned = self.guidance_gen.compute(
                x_out, z_out, yaw_out, status
            )
            t_flt_done = float(obs.t_detect_done) + (time.perf_counter() - t_update_start)
            lat = self.latency_tracker.record_filter_stage(
                obs.t_capture, obs.t_detect_done, t_flt_done
            )
            return State(
                t_capture=t_cap,
                x_cm=x_out,
                z_cm=z_out,
                yaw_deg=yaw_out,
                sigma_x=sx,
                sigma_z=sz,
                sigma_yaw=syaw,
                status=status,
                guidance=guidance_str,
                aligned=aligned,
                latency_ms=lat,
            )

        # =====================================================================
        # Chế độ BẬT KALMAN FILTER (filter_enabled == True)
        # =====================================================================
        # 1. Nếu chưa khởi tạo mà đã thấy marker -> khởi tạo trực tiếp tại quan sát đầu tiên
        if not self.initialized:
            if obs.found:
                R0 = self._compute_R(obs)
                self.x = np.array(
                    [obs.x_cm, obs.z_cm, obs.yaw_deg, 0.0, 0.0, 0.0], dtype=np.float64
                )
                self.P = np.diag(
                    [R0[0, 0], R0[1, 1], R0[2, 2], 25.0, 25.0, 100.0]
                ).astype(np.float64)
                self.initialized = True
                self.last_valid_obs_t = t_cap
                sx, sz, syaw = self._extract_sigmas()
                status = (
                    "DEGRADED"
                    if (obs.ambiguous or obs.reproj_err_px > 1.5)
                    else "GOOD"
                )
            else:
                sx, sz, syaw = 9.9, 9.9, 25.0
                status = "LOST"

            guidance_str, aligned = self.guidance_gen.compute(
                float(self.x[0]), float(self.x[1]), float(self.x[2]), status
            )
            t_flt_done = float(obs.t_detect_done) + (time.perf_counter() - t_update_start)
            lat = self.latency_tracker.record_filter_stage(
                obs.t_capture, obs.t_detect_done, t_flt_done
            )
            return State(
                t_capture=t_cap,
                x_cm=float(self.x[0]),
                z_cm=float(self.x[1]),
                yaw_deg=float(self.x[2]),
                sigma_x=sx,
                sigma_z=sz,
                sigma_yaw=syaw,
                status=status,
                guidance=guidance_str,
                aligned=aligned,
                latency_ms=lat,
            )

        # 2. Bước Dự đoán (Predict step): x_pred = F * x, P_pred = F * P * F^T + Q
        F, Q = self._build_F_and_Q(dt)
        self.x = F @ self.x
        self.x[2] = _wrap_angle_deg(float(self.x[2]))
        self.P = F @ self.P @ F.T + Q

        # Giảm nhẹ vận tốc khi không thấy marker (damping tránh trôi xa khi che khuất)
        if not obs.found:
            self.x[3:6] *= 0.80

        rejected_by_gate = False
        high_reproj = False

        # 3. Bước Cập nhật (Update step) nếu phát hiện được marker
        if obs.found:
            R = self._compute_R(obs)
            z_meas = np.array([obs.x_cm, obs.z_cm, obs.yaw_deg], dtype=np.float64)

            # Sai số cải tiến (innovation) y = z_meas - H * x_pred
            y = z_meas - (self.H @ self.x)
            y[2] = _wrap_angle_deg(float(y[2]))

            # Hiệp phương sai innovation S = H * P * H^T + R
            S = self.H @ self.P @ self.H.T + R
            try:
                S_inv = np.linalg.inv(S)
                d2 = float(y.T @ S_inv @ y)
            except np.linalg.LinAlgError:
                S_inv = np.linalg.pinv(S)
                d2 = float(y.T @ S_inv @ y)

            self.last_mahalanobis_sq = d2
            high_reproj = float(obs.reproj_err_px) > 1.5

            # Gating Mahalanobis (bậc tự do 3, ngưỡng 99% = 11.345) kết hợp dự phòng ngưỡng reproj cứng (> 4.0 px)
            if d2 <= CHI2_3DOF_99 and float(obs.reproj_err_px) <= 4.0:
                K = self.P @ self.H.T @ S_inv
                self.x = self.x + (K @ y)
                self.x[2] = _wrap_angle_deg(float(self.x[2]))

                # Công thức Joseph giúp P luôn đối xứng và xác định dương:
                # P = (I - K*H) * P * (I - K*H)^T + K * R * K^T
                I_KH = np.eye(6, dtype=np.float64) - (K @ self.H)
                self.P = I_KH @ self.P @ I_KH.T + K @ R @ K.T
                self.last_valid_obs_t = t_cap
            else:
                rejected_by_gate = True
                # Nếu bị gate liên tiếp (ví dụ vật thể vừa đổi vận tốc đột ngột), giảm vận tốc dự đoán
                self.x[3:6] *= 0.50

        # 4. Xác định trạng thái sức khỏe hệ thống (GOOD / DEGRADED / LOST)
        sx, sz, syaw = self._extract_sigmas()
        time_since_valid = (
            (t_cap - self.last_valid_obs_t)
            if self.last_valid_obs_t is not None
            else 999.0
        )

        sigma_exceeded = (
            sx > self.sigma_max_x_cm
            or sz > self.sigma_max_z_cm
            or syaw > self.sigma_max_yaw_deg
        )

        if time_since_valid > self.reset_timeout_s:
            # Mất marker quá 2.0 s -> reset filter
            x_last, z_last, yaw_last = (
                float(self.x[0]),
                float(self.x[1]),
                float(self.x[2]),
            )
            self.reset()
            status = "LOST"
            guidance_str, aligned = self.guidance_gen.compute(
                x_last, z_last, yaw_last, status
            )
            t_flt_done = float(obs.t_detect_done) + (time.perf_counter() - t_update_start)
            lat = self.latency_tracker.record_filter_stage(
                obs.t_capture, obs.t_detect_done, t_flt_done
            )
            return State(
                t_capture=t_cap,
                x_cm=x_last,
                z_cm=z_last,
                yaw_deg=yaw_last,
                sigma_x=sx,
                sigma_z=sz,
                sigma_yaw=syaw,
                status=status,
                guidance=guidance_str,
                aligned=aligned,
                latency_ms=lat,
            )

        if time_since_valid > self.lost_timeout_s or sigma_exceeded:
            status = "LOST"
        elif (
            not obs.found
            or obs.ambiguous
            or rejected_by_gate
            or high_reproj
        ):
            status = "DEGRADED"
        else:
            status = "GOOD"

        x_out = float(self.x[0])
        z_out = float(self.x[1])
        yaw_out = float(self.x[2])

        guidance_str, aligned = self.guidance_gen.compute(
            x_out, z_out, yaw_out, status
        )
        t_flt_done = float(obs.t_detect_done) + (time.perf_counter() - t_update_start)
        lat = self.latency_tracker.record_filter_stage(
            obs.t_capture, obs.t_detect_done, t_flt_done
        )

        return State(
            t_capture=t_cap,
            x_cm=x_out,
            z_cm=z_out,
            yaw_deg=yaw_out,
            sigma_x=sx,
            sigma_z=sz,
            sigma_yaw=syaw,
            status=status,
            guidance=guidance_str,
            aligned=aligned,
            latency_ms=lat,
        )
