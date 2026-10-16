"""P1: DICT_5X5_50 ArUco -> contract.Observation, in cm and degrees.

Camera coordinates: +x right, +y down, +z forward. IPPE object corners:
(-s/2,+s/2,0), (+s/2,+s/2,0), (+s/2,-s/2,0), (-s/2,-s/2,0).
Translation is already in cm because marker_side_cm is in cm.
Yaw: n=R[:,2]; if n[2]>0, n=-n; degrees(atan2(n[0], -n[2])).
Positive yaw means the marker normal faces toward camera-right.
Reference: https://docs.opencv.org/4.x/d5/d1f/calib3d_solvePnP.html
"""

import time
import warnings

import cv2
import numpy as np

from contract import Observation


AMBIGUOUS_YAW_GAP_DEG = 12.0  # Demo heuristic; not a confidence bound.


def _yaw_deg(R):
    normal = R[:, 2].copy()
    if normal[2] > 0:
        normal = -normal
    return float(np.degrees(np.arctan2(normal[0], -normal[2])))


def _direction(value, tolerance):
    return 0 if abs(value) < tolerance else (1 if value > 0 else -1)


class Perceiver:
    def __init__(self, calib_path, marker_id=7, marker_side_cm=6.0):
        version = tuple(int(part) for part in cv2.__version__.split('.')[:2])
        if version < (4, 7) or not hasattr(cv2, 'aruco') or not hasattr(cv2.aruco, 'ArucoDetector'):
            raise RuntimeError('Need OpenCV >=4.7 with aruco: pip install opencv-contrib-python')
        if not 0 <= marker_id < 50:
            raise ValueError('marker_id must be in [0, 49] for DICT_5X5_50.')
        if not np.isfinite(marker_side_cm) or marker_side_cm <= 0:
            raise ValueError('marker_side_cm must be positive and finite.')
        with np.load(calib_path, allow_pickle=False) as calibration:
            self.K = np.array(calibration['K'], dtype=np.float64)
            self.dist = np.array(calibration['dist'], dtype=np.float64).reshape(-1, 1)
            raw_size = np.asarray(calibration['image_size'])
            self.approximate = ('method' in calibration and
                                str(calibration['method'].item()) == 'approx_fov')
            self.synthetic_calibration = ('method' in calibration and
                                           str(calibration['method'].item()) == 'synthetic_render')
        if (self.K.shape != (3, 3) or not np.isfinite(self.K).all()
                or min(self.K[0, 0], self.K[1, 1]) <= 0
                or not np.allclose(self.K[2], [0, 0, 1])):
            raise ValueError('Invalid calibration K: expected finite 3x3 pinhole matrix.')
        if self.dist.size not in (4, 5, 8, 12, 14) or not np.isfinite(self.dist).all():
            raise ValueError('Invalid distortion coefficients.')
        if (raw_size.shape != (2,) or not np.isfinite(raw_size).all()
                or np.any(raw_size <= 0) or np.any(raw_size != np.floor(raw_size))):
            raise ValueError('image_size must contain positive integer (width, height).')
        self.image_size = tuple(int(value) for value in raw_size)
        self._base_K = self.K.copy()
        self.marker_id = marker_id
        self.marker_side_cm = float(marker_side_cm)
        half = self.marker_side_cm / 2.0
        self.object_points = np.array([[-half, half, 0], [half, half, 0],
                                       [half, -half, 0], [-half, -half, 0]], np.float64)
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)
        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        self.detector = cv2.aruco.ArucoDetector(dictionary, params)
        if self.approximate:
            warnings.warn('Using APPROXIMATE FOV calibration; metric accuracy is unverified.',
                          RuntimeWarning, stacklevel=2)

    def _camera_matrix(self, frame):
        height, width = frame.shape[:2]
        sx, sy = width / self.image_size[0], height / self.image_size[1]
        # Only support a uniform resize, never silently assume a different crop/FOV.
        if not np.isclose(sx, sy, rtol=1e-3):
            raise ValueError(f'Frame {width}x{height} differs in aspect ratio from calibration '
                             f'{self.image_size}. Use the same camera mode and recalibrate.')
        self.K = self._base_K.copy()
        self.K[0] *= sx
        self.K[1] *= sy
        return self.K

    def process(self, frame, t_capture):
        """Return found=False for no target/invalid PnP; preserve perf_counter timestamp.

        reproj_err_px is mean Euclidean pixel error over the four corners.
        Equal-error solutions (<20% gap) are ambiguous when their correction
        directions differ, x/z differ by >1 cm, or yaw differs by >12 degrees.
        Nearly identical solutions with the same guidance are harmless.
        Duplicate target IDs also mark ambiguity. K follows the current frame
        resolution so P3 may use self.K/self.dist with cv2.drawFrameAxes.
        """
        def missing(corners=None):
            return Observation(t_capture=t_capture, t_detect_done=time.perf_counter(),
                               found=False, corners=corners)

        if frame is None or frame.size == 0:
            return missing()
        K = self._camera_matrix(frame)
        corners, ids, _ = self.detector.detectMarkers(frame)
        if ids is None:
            return missing()
        matches = np.flatnonzero(ids.reshape(-1) == self.marker_id)
        if matches.size == 0:
            return missing()
        # A duplicate printed ID has no unique identity: flag it even when choosing the largest.
        index = max(matches, key=lambda i: abs(cv2.contourArea(corners[i].reshape(4, 2))))
        image_points = np.ascontiguousarray(corners[index].reshape(4, 2), dtype=np.float64)
        # OpenCV 4.9 IPPE's rotation conversion is singular for some exactly
        # level squares (180-degree rotation). Break only that numeric symmetry
        # by 0.001 px in the solver input; retain original corners for scoring
        # and display. This is far below subpixel detector precision.
        solver_points = image_points.copy()
        solver_points[0, 1] += 0.001
        try:
            count, rvecs, tvecs, _ = cv2.solvePnPGeneric(
                self.object_points, solver_points, K, self.dist, flags=cv2.SOLVEPNP_IPPE_SQUARE
            )
            if not count:
                return missing(image_points)
            candidates = []
            for rvec, tvec in zip(rvecs, tvecs):
                if not np.isfinite(rvec).all() or not np.isfinite(tvec).all():
                    continue
                R, _ = cv2.Rodrigues(rvec)
                camera_points = (R @ self.object_points.T).T + tvec.reshape(1, 3)
                if np.any(camera_points[:, 2] <= 0):
                    continue
                projected, _ = cv2.projectPoints(self.object_points, rvec, tvec, K, self.dist)
                error = float(np.mean(np.linalg.norm(projected.reshape(4, 2) - image_points, axis=1)))
                if np.isfinite(error):
                    candidates.append((error, rvec, tvec, R))
        except cv2.error:
            return missing(image_points)
        if not candidates:
            return missing(image_points)
        candidates.sort(key=lambda item: item[0])
        error, rvec, tvec, R = candidates[0]
        yaw = _yaw_deg(R)
        ambiguous = matches.size > 1
        if len(candidates) > 1 and (candidates[1][0] - error) / max(error, 1e-9) < 0.20:
            other_yaw = _yaw_deg(candidates[1][3])
            position, other_position = tvec.reshape(3), candidates[1][2].reshape(3)
            # P4's near-frontal fix, with guards at the default guidance bands:
            # never suppress two solutions that disagree on readiness/direction.
            ambiguous |= (abs(other_yaw - yaw) > AMBIGUOUS_YAW_GAP_DEG
                          or _direction(yaw, 5) != _direction(other_yaw, 5)
                          or _direction(yaw, 7.5) != _direction(other_yaw, 7.5)
                          or _direction(position[0], 1) != _direction(other_position[0], 1)
                          or _direction(position[0], 1.5) != _direction(other_position[0], 1.5)
                          or np.any(np.abs(position[[0, 2]] - other_position[[0, 2]]) > 1)
                          or any((position[2] <= boundary) != (other_position[2] <= boundary)
                                 for boundary in (8, 15, 17.25)))
        return Observation(t_capture=t_capture, t_detect_done=time.perf_counter(), found=True,
                           x_cm=float(tvec.reshape(3)[0]), z_cm=float(tvec.reshape(3)[2]),
                           yaw_deg=yaw, reproj_err_px=error, ambiguous=bool(ambiguous),
                           corners=image_points.astype(np.float32),
                           rvec=rvec.copy(), tvec=tvec.copy())
