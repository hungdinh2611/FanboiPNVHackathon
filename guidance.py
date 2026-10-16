# guidance.py
"""
Sinh chi dan ASCII khong dau va trang thai `aligned` tu (x_cm, z_cm, yaw_deg, status).
Su dung deadband (vung chet) va hysteresis (nguong vao/thoat khac nhau) de chu tren HUD
khong bi nhap nhay (flicker) khi gia tri dao dong quanh nguong.

Quy uoc he toa do (Muc 3 tai lieu):
- x_cm > 0: cong sac nam ben PHAI truc camera -> dau sac can SANG PHAI.
- x_cm < 0: cong sac nam ben TRAI truc camera -> dau sac can SANG TRAI.
- z_cm: khoang cach doc truc camera toi cong sac -> z > stop_z thi can TIEN.
- yaw_deg > 0: mat marker quay ve phia phai camera -> dau sac can XOAY PHAI / TRAI de doi dien thang.
"""
from __future__ import annotations

from typing import Tuple


class GuidanceGenerator:
    """
    Bộ sinh chỉ dẫn có trạng thái (lưu hysteresis) để chống nhấp nháy chữ trên màn hình.
    - Ngưỡng vào aligned (enter): |x| < 1.0 cm, |yaw| < 5.0 deg, z <= stop_z (mặc định 15.0 cm).
    - Ngưỡng thoát aligned (exit = 1.5x): |x| > 1.5 cm, |yaw| > 7.5 deg, hoặc z > stop_z + 2.25 cm.
    """

    def __init__(
        self,
        x_tol_cm: float = 1.0,
        yaw_tol_deg: float = 5.0,
        stop_z_cm: float = 15.0,
        min_z_cm: float = 8.0,
        hysteresis_ratio: float = 1.5,
    ) -> None:
        self.x_tol_cm = x_tol_cm
        self.yaw_tol_deg = yaw_tol_deg
        self.stop_z_cm = stop_z_cm
        self.min_z_cm = min_z_cm
        self.hysteresis_ratio = hysteresis_ratio

        # Trạng thái hysteresis
        self._is_aligned: bool = False
        self._x_ok: bool = False
        self._yaw_ok: bool = False
        self._z_ok: bool = False

    def reset(self) -> None:
        """Reset trạng thái hysteresis khi mất dấu (LOST)."""
        self._is_aligned = False
        self._x_ok = False
        self._yaw_ok = False
        self._z_ok = False

    def compute(
        self,
        x_cm: float,
        z_cm: float,
        yaw_deg: float,
        status: str,
    ) -> Tuple[str, bool]:
        """
        Trả về `(guidance_ascii, aligned)`.
        Không đưa chỉ dẫn điều hướng khi `status == "LOST"`.
        """
        if status == "LOST":
            self.reset()
            return "MAT DAU MARKER - GIU NGUYEN", False

        x_exit = self.x_tol_cm * self.hysteresis_ratio
        yaw_exit = self.yaw_tol_deg * self.hysteresis_ratio
        z_exit = self.stop_z_cm + (self.x_tol_cm * self.hysteresis_ratio * 1.5)

        # Cập nhật trạng thái từng trục theo deadband + hysteresis
        if self._x_ok:
            if abs(x_cm) > x_exit:
                self._x_ok = False
        else:
            if abs(x_cm) < self.x_tol_cm:
                self._x_ok = True

        if self._yaw_ok:
            if abs(yaw_deg) > yaw_exit:
                self._yaw_ok = False
        else:
            if abs(yaw_deg) < self.yaw_tol_deg:
                self._yaw_ok = True

        if self._z_ok:
            if z_cm > z_exit or z_cm < self.min_z_cm:
                self._z_ok = False
        else:
            if self.min_z_cm <= z_cm <= self.stop_z_cm:
                self._z_ok = True

        # Cập nhật trạng thái tổng `aligned` với hysteresis
        if self._is_aligned:
            if not (self._x_ok and self._yaw_ok and self._z_ok):
                self._is_aligned = False
        else:
            if (
                abs(x_cm) < self.x_tol_cm
                and abs(yaw_deg) < self.yaw_tol_deg
                and self.min_z_cm <= z_cm <= self.stop_z_cm
            ):
                self._is_aligned = True
                self._x_ok = True
                self._yaw_ok = True
                self._z_ok = True

        if self._is_aligned:
            if status == "DEGRADED":
                return "DO TIN CAY THAP - GIU NGUYEN", False
            return "DA CAN CHINH - SAN SANG CAM SAC", True

        parts: list[str] = []

        # 1. Chỉ dẫn lệch ngang x
        if not self._x_ok:
            dx = max(1, int(round(abs(x_cm))))
            if x_cm > 0:
                parts.append(f"SANG PHAI {dx} cm")
            else:
                parts.append(f"SANG TRAI {dx} cm")

        # 2. Chỉ dẫn góc xoay yaw
        if not self._yaw_ok:
            dyaw = max(1, int(round(abs(yaw_deg))))
            if yaw_deg > 0:
                parts.append(f"XOAY PHAI {dyaw} do")
            else:
                parts.append(f"XOAY TRAI {dyaw} do")

        # 3. Chỉ dẫn tiến/lùi theo z
        if z_cm < self.min_z_cm:
            dz = max(1, int(round(self.stop_z_cm - z_cm)))
            parts.append(f"LUI {dz} cm")
        elif not self._z_ok and z_cm > self.stop_z_cm:
            dz = max(1, int(round(z_cm - self.stop_z_cm)))
            parts.append(f"TIEN {dz} cm")

        if not parts:
            return "GIU NGUYEN VI TRI", False

        return " | ".join(parts), False
