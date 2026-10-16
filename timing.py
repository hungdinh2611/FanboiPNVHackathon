# timing.py
"""
Do do tre (latency) theo tung tang:
- capture_detect_ms: t_detect_done - t_capture
- detect_filter_ms:  t_filter_done - t_detect_done
- filter_display_ms: t_display_done - t_filter_done
- total_ms:          t_end - t_capture

Cung cap LatencyTracker va ham latency_report() tra ve p50 va p95 (ms) de dien vao State.latency_ms.
"""
from __future__ import annotations

from collections import deque
import time
from typing import Dict
import numpy as np


class LatencyTracker:
    """Theo dõi cửa sổ trượt các mốc thời gian và tính phân vị p50, p95 (ms)."""

    def __init__(self, window_size: int = 300) -> None:
        self.window_size = window_size
        self.capture_detect = deque(maxlen=window_size)
        self.detect_filter = deque(maxlen=window_size)
        self.filter_display = deque(maxlen=window_size)
        self.total = deque(maxlen=window_size)
        self._last_filter_done: float | None = None

    def record_filter_stage(
        self,
        t_capture: float,
        t_detect_done: float,
        t_filter_done: float | None = None,
    ) -> Dict[str, float]:
        """
        Ghi nhận độ trễ khi kết thúc tầng filter (P2) và trả về dict cho `State.latency_ms`.
        Nếu `t_filter_done` không truyền vào thì lấy `time.perf_counter()`.
        """
        if t_filter_done is None:
            t_filter_done = time.perf_counter()

        cap_det_ms = max(0.0, (t_detect_done - t_capture) * 1000.0)
        det_flt_ms = max(0.0, (t_filter_done - t_detect_done) * 1000.0)
        tot_ms = max(0.0, (t_filter_done - t_capture) * 1000.0)

        self.capture_detect.append(cap_det_ms)
        self.detect_filter.append(det_flt_ms)
        self.total.append(tot_ms)
        self._last_filter_done = t_filter_done

        report = self.latency_report()
        return {
            "capture": round(cap_det_ms, 3),
            "detect": round(cap_det_ms, 3),
            "filter": round(det_flt_ms, 3),
            "display": round(
                float(self.filter_display[-1]) if self.filter_display else 0.0, 3
            ),
            "total": round(tot_ms, 3),
            "p50_ms": round(report["total_p50_ms"], 3),
            "p95_ms": round(report["total_p95_ms"], 3),
        }

    def record_display_stage(self, t_display_done: float | None = None) -> float:
        """Ghi nhận độ trễ từ lúc xong filter tới lúc vẽ xong HUD (P3 có thể gọi thêm)."""
        if t_display_done is None:
            t_display_done = time.perf_counter()
        if self._last_filter_done is None:
            return 0.0
        flt_disp_ms = max(0.0, (t_display_done - self._last_filter_done) * 1000.0)
        self.filter_display.append(flt_disp_ms)
        if self.total:
            self.total[-1] = self.total[-1] + flt_disp_ms
        return flt_disp_ms

    def latency_report(self) -> Dict[str, float]:
        """Trả về thống kê p50 và p95 (ms) cho từng tầng và tổng."""
        def _p50_p95(buf: deque) -> tuple[float, float]:
            if not buf:
                return 0.0, 0.0
            arr = np.asarray(buf, dtype=np.float64)
            return float(np.percentile(arr, 50)), float(np.percentile(arr, 95))

        cd50, cd95 = _p50_p95(self.capture_detect)
        df50, df95 = _p50_p95(self.detect_filter)
        fd50, fd95 = _p50_p95(self.filter_display)
        tot50, tot95 = _p50_p95(self.total)

        return {
            "capture_detect_p50_ms": cd50,
            "capture_detect_p95_ms": cd95,
            "detect_filter_p50_ms": df50,
            "detect_filter_p95_ms": df95,
            "filter_display_p50_ms": fd50,
            "filter_display_p95_ms": fd95,
            "total_p50_ms": tot50,
            "total_p95_ms": tot95,
            "p50_ms": tot50,
            "p95_ms": tot95,
        }


# Tracker mặc định toàn cục để tiện gọi hàm `latency_report()` trực tiếp
_DEFAULT_TRACKER = LatencyTracker()


def record_latency(
    t_capture: float,
    t_detect_done: float,
    t_filter_done: float | None = None,
) -> Dict[str, float]:
    """Ghi nhận độ trễ vào tracker mặc định và trả về dict cho `State.latency_ms`."""
    return _DEFAULT_TRACKER.record_filter_stage(t_capture, t_detect_done, t_filter_done)


def latency_report(tracker: LatencyTracker | None = None) -> Dict[str, float]:
    """Trả về báo cáo p50 và p95 ms theo từng tầng (capture-detect, detect-filter, filter-display, total)."""
    target = _DEFAULT_TRACKER if tracker is None else tracker
    return target.latency_report()
