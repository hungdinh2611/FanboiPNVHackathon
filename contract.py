# contract.py
from dataclasses import dataclass, field
import numpy as np

@dataclass
class Observation:            # P1 -> P2
    t_capture: float          # perf_counter() lúc grab frame
    t_detect_done: float
    found: bool
    x_cm: float = 0.0
    z_cm: float = 0.0
    yaw_deg: float = 0.0
    reproj_err_px: float = 0.0
    ambiguous: bool = False   # hai nghiệm IPPE có reproj error gần nhau
    corners: "np.ndarray | None" = None   # (4,2) để vẽ
    rvec: "np.ndarray | None" = None
    tvec: "np.ndarray | None" = None

@dataclass
class State:                  # P2 -> P3
    t_capture: float
    x_cm: float; z_cm: float; yaw_deg: float
    sigma_x: float; sigma_z: float; sigma_yaw: float
    status: str               # "GOOD" | "DEGRADED" | "LOST"
    guidance: str             # ASCII không dấu, vd "SANG PHAI 3 cm | TIEN 12 cm"
    aligned: bool
    latency_ms: dict = field(default_factory=dict)  # capture/detect/filter/total

# Giao diện bắt buộc:
# perception.py: class Perceiver(calib_path, marker_id=7, marker_side_cm=6.0); process(frame, t_capture) -> Observation
# filter.py:     class AlignmentKF: update(obs) -> State; thuộc tính filter_enabled: bool
# main.py:       python main.py --source 0|file.mp4 [--replay log.csv]
