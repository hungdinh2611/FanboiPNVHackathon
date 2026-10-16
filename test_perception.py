"""P1 live pose checker; --self-test runs reproducible tests without a camera.

python test_perception.py --calib calib.npz --gt-z 50
python test_perception.py --self-test
"""

import argparse
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from calibrate import (approximate_calibration, board_points, calibrate_views,
                       find_corners, generate_patterns, save_calibration)
from perception import Perceiver


def pose_rotation(yaw_deg):
    """A printed marker facing the camera, with yaw matching the team convention."""
    yaw, _ = cv2.Rodrigues(np.array([0.0, -np.deg2rad(yaw_deg), 0.0]))
    facing, _ = cv2.Rodrigues(np.array([np.pi, 0.0, 0.0]))
    return cv2.Rodrigues(yaw @ facing)[0]


class PerceptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.K = np.array([[900., 0, 640], [0, 900., 360], [0, 0, 1]])
        self.path = self.root / 'calib.npz'
        save_calibration(self.path, self.K, np.zeros(5), 0.1, (1280, 720), method='chessboard')
        self.perceiver = Perceiver(self.path)
        self.frame = np.full((720, 1280), 255, np.uint8)

    def projected(self, x=4, z=50, yaw=25, K=None, dist=None):
        return cv2.projectPoints(self.perceiver.object_points, pose_rotation(yaw),
                                 np.array([float(x), 0., float(z)]),
                                 self.K if K is None else K,
                                 np.zeros(5) if dist is None else dist)[0].reshape(4, 2)

    def observation_at(self, x=4, z=50, yaw=25, frame=None):
        points = self.projected(x, z, yaw).astype(np.float32).reshape(1, 4, 2)
        with patch.object(self.perceiver, 'detector') as detector:
            detector.detectMarkers.return_value = ([points], np.array([[7]]), [])
            return self.perceiver.process(self.frame if frame is None else frame, time.perf_counter())

    def rendered_marker(self, marker_id=7, x=4, z=50, yaw=25):
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, 600)
        source = np.array([[0., 0.], [599., 0.], [599., 599.], [0., 599.]], np.float32)
        H = cv2.getPerspectiveTransform(source, self.projected(x, z, yaw).astype(np.float32))
        return cv2.warpPerspective(marker, H, (1280, 720),
                                   flags=cv2.INTER_NEAREST, borderValue=255)

    def test_geometry_units_and_yaw_sign(self):
        for z in (30, 50, 100):
            for yaw in (-40, -20, 20, 40):
                for x in (-5, 5):
                    with self.subTest(x=x, z=z, yaw=yaw):
                        obs = self.observation_at(x, z, yaw)
                        self.assertTrue(obs.found)
                        self.assertAlmostEqual(obs.x_cm, x, delta=0.001)
                        self.assertAlmostEqual(obs.z_cm, z, delta=0.001)
                        self.assertAlmostEqual(obs.yaw_deg, yaw, delta=0.01)

    def test_real_detector_on_rendered_markers(self):
        for z, yaw in ((30, -20), (50, 25), (100, 40)):
            with self.subTest(z=z, yaw=yaw):
                obs = self.perceiver.process(self.rendered_marker(z=z, yaw=yaw), time.perf_counter())
                self.assertTrue(obs.found)
                self.assertAlmostEqual(obs.z_cm, z, delta=1.5)
                self.assertAlmostEqual(obs.x_cm, 4, delta=0.3)
                self.assertAlmostEqual(obs.yaw_deg, yaw, delta=4)

    def test_exactly_frontal_marker_remains_valid(self):
        for x in (-5, 0, 5):
            obs = self.observation_at(x=x, z=50, yaw=0)
            self.assertTrue(obs.found)
            self.assertAlmostEqual(obs.z_cm, 50, delta=0.01)
            self.assertAlmostEqual(obs.yaw_deg, 0, delta=0.5)

    def test_duplicate_target_ids_are_ambiguous(self):
        frame = np.minimum(self.rendered_marker(x=-8), self.rendered_marker(x=8))
        obs = self.perceiver.process(frame, time.perf_counter())
        self.assertTrue(obs.found)
        self.assertTrue(obs.ambiguous)

    def test_other_marker_id_is_ignored(self):
        obs = self.perceiver.process(self.rendered_marker(marker_id=8), time.perf_counter())
        self.assertFalse(obs.found)

    def test_missing_marker_and_empty_frame(self):
        for frame in (self.frame, None, np.empty((0, 0), np.uint8)):
            self.assertFalse(self.perceiver.process(frame, time.perf_counter()).found)

    def test_timestamps_and_corner_shape(self):
        obs = self.observation_at()
        self.assertLessEqual(obs.t_capture, obs.t_detect_done)
        self.assertLessEqual(obs.t_detect_done, time.perf_counter())
        self.assertEqual(obs.corners.shape, (4, 2))

    def test_reprojection_error_is_mean_corner_distance(self):
        obs = self.observation_at()
        projected, _ = cv2.projectPoints(self.perceiver.object_points, obs.rvec,
                                         obs.tvec, self.K, self.perceiver.dist)
        expected = np.mean(np.linalg.norm(projected.reshape(4, 2) - obs.corners, axis=1))
        self.assertAlmostEqual(obs.reproj_err_px, expected, places=7)

    def test_two_indistinguishable_solutions_are_ambiguous(self):
        rvec, tvec = pose_rotation(25), np.array([[4.], [0.], [50.]])
        with patch('perception.cv2.solvePnPGeneric', return_value=(2, [rvec, rvec], [tvec, tvec], None)):
            self.assertTrue(self.observation_at().ambiguous)

    def test_invalid_and_behind_camera_solutions_are_rejected(self):
        rvec = pose_rotation(25)
        for r, t in ((rvec, np.array([[0.], [0.], [-50.]])),
                     (np.full((3, 1), np.nan), np.array([[0.], [0.], [50.]]))):
            with patch('perception.cv2.solvePnPGeneric', return_value=(1, [r], [t], None)):
                self.assertFalse(self.observation_at().found)

    def test_pnp_error_is_a_missing_observation(self):
        with patch('perception.cv2.solvePnPGeneric', side_effect=cv2.error('test failure')):
            self.assertFalse(self.observation_at().found)

    def test_uniform_resize_preserves_geometry_and_axes_matrix(self):
        frame = cv2.resize(self.rendered_marker(), (640, 360), interpolation=cv2.INTER_NEAREST)
        obs = self.perceiver.process(frame, time.perf_counter())
        self.assertTrue(obs.found)
        self.assertAlmostEqual(obs.z_cm, 50, delta=1.5)
        self.assertAlmostEqual(self.perceiver.K[0, 0], 450)
        self.perceiver.process(self.frame, time.perf_counter())
        np.testing.assert_array_equal(self.perceiver.K, self.K)

    def test_aspect_ratio_change_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'aspect ratio'):
            self.perceiver.process(np.zeros((480, 640), np.uint8), time.perf_counter())

    def test_distortion_is_used(self):
        dist = np.array([0.15, -0.1, 0.003, -0.002, 0.01])
        save_calibration(self.path, self.K, dist, 0.1, (1280, 720))
        self.perceiver = Perceiver(self.path)
        points = self.projected(x=20, dist=dist).astype(np.float32).reshape(1, 4, 2)
        with patch.object(self.perceiver, 'detector') as detector:
            detector.detectMarkers.return_value = ([points], np.array([[7]]), [])
            obs = self.perceiver.process(self.frame, time.perf_counter())
        self.assertAlmostEqual(obs.z_cm, 50, delta=0.01)
        self.assertAlmostEqual(obs.x_cm, 20, delta=0.01)

    def test_bad_configuration_is_rejected(self):
        for side in (0, -6, np.nan):
            with self.assertRaises(ValueError):
                Perceiver(self.path, marker_side_cm=side)
        with self.assertRaises(ValueError):
            Perceiver(self.path, marker_id=50)
        save_calibration(self.path, np.zeros((3, 3)), np.zeros(5), 0, (1280, 720))
        with self.assertRaises(ValueError):
            Perceiver(self.path)

    def test_fov_fallback_metadata_and_formula(self):
        K = approximate_calibration(68, (1280, 720), self.path)
        self.assertAlmostEqual(K[0, 0], 1280 / (2 * np.tan(np.deg2rad(34))))
        with self.assertWarns(RuntimeWarning):
            perceiver = Perceiver(self.path)
        self.assertTrue(perceiver.approximate)
        with np.load(self.path) as data:
            self.assertTrue(np.isnan(data['rms']))
        with self.assertRaises(ValueError):
            approximate_calibration(180, (1280, 720), self.path)

    def test_calibration_from_synthetic_chessboard_views(self):
        rng = np.random.default_rng(7)
        views = []
        for _ in range(18):
            rvec = rng.uniform(-0.35, 0.35, 3)
            tvec = np.array([rng.uniform(-12, -4), rng.uniform(-9, -3), rng.uniform(55, 95)])
            points, _ = cv2.projectPoints(board_points(), rvec, tvec, self.K, np.zeros(5))
            points += rng.normal(0, 0.03, points.shape).astype(np.float32)
            views.append(points)
        rms, K, _ = calibrate_views(views, (1280, 720), 25, self.path)
        self.assertLess(rms, 0.1)
        self.assertAlmostEqual(K[0, 0], 900, delta=8)
        with np.load(self.path) as data:
            self.assertEqual(len(data['per_view_rms']), 18)
            self.assertEqual(tuple(data['image_size']), (1280, 720))
        with self.assertRaises(ValueError):
            calibrate_views(views[:14], (1280, 720), 25, self.path)

    def test_print_patterns_are_detectable(self):
        generate_patterns(self.root)
        marker = cv2.imread(str(self.root / 'marker_7.png'))
        corners, ids, _ = self.perceiver.detector.detectMarkers(marker)
        np.testing.assert_array_equal(ids, [[7]])
        self.assertEqual(len(corners), 1)
        board = cv2.imread(str(self.root / 'checkerboard_9x6.png'))
        self.assertIsNotNone(find_corners(board))


def live(args):
    perceiver = Perceiver(args.calib, args.marker_id, args.marker_side_cm)
    source = int(args.source) if args.source.isdecimal() else args.source
    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError('Cannot open source. Close other camera apps or change --source.')
    samples, count, last_print = [], 0, float('-inf')
    try:
        if isinstance(source, int):
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, perceiver.image_size[0])
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, perceiver.image_size[1])
            capture.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        print('Q: quit | unmirrored view: +x is camera-right | terminal output at most 10 Hz')
        while not args.max_frames or count < args.max_frames:
            if not capture.grab():
                if isinstance(source, int):
                    raise RuntimeError('Webcam stopped delivering frames.')
                break
            t_capture = time.perf_counter()
            ok, frame = capture.retrieve()
            if not ok or frame is None:
                raise RuntimeError('Could not retrieve frame.')
            obs = perceiver.process(frame, t_capture)
            count += 1
            if obs.found:
                samples.append(obs.z_cm)
                line = (f'x={obs.x_cm:+.2f} cm | z={obs.z_cm:.2f} cm | '
                        f'yaw={obs.yaw_deg:+.2f} deg | err={obs.reproj_err_px:.3f} px | '
                        f'ambiguous={obs.ambiguous}')
                cv2.polylines(frame, [np.rint(obs.corners).astype(np.int32)], True, (0, 255, 0), 2)
                cv2.drawFrameAxes(frame, perceiver.K, perceiver.dist, obs.rvec, obs.tvec,
                                  args.marker_side_cm / 2)
            else:
                line = 'KHONG THAY MARKER DUNG ID'
            now = time.perf_counter()
            if now - last_print >= 0.1:
                print(line, flush=True)
                last_print = now
            if not args.headless:
                cv2.putText(frame, line, (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 180, 255), 2)
                if perceiver.approximate:
                    cv2.putText(frame, 'K UOC LUONG - CHUA KIEM CHUNG DO CHINH XAC', (15, 65),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                if not isinstance(source, int):
                    cv2.putText(frame, 'VIDEO DA GHI - KHONG PHAI LIVE', (15, 95),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                cv2.imshow('P1 - Perception check', frame)
                if cv2.waitKey(1) & 0xFF in (ord('q'), ord('Q'), 27):
                    break
    finally:
        capture.release()
        if not args.headless:
            cv2.destroyAllWindows()
    print(f'Frames={count}, target detections={len(samples)}')
    if args.gt_z is not None:
        if len(samples) < 30:
            print('NOT VERIFIED: collect at least 30 target detections at a fixed ruler distance.')
            return 1
        median = float(np.median(samples))
        error = abs(median - args.gt_z)
        print(f'User-supplied GT z={args.gt_z:.2f} cm; median={median:.2f} cm; '
              f'absolute median error={error:.2f} cm; std={np.std(samples):.2f} cm')
        print('PASS (<1 cm median error)' if error < 1 else 'FAIL (>=1 cm median error)')
        return int(error >= 1)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--source', default='0')
    parser.add_argument('--calib', default='calib.npz')
    parser.add_argument('--marker-id', type=int, default=7)
    parser.add_argument('--marker-side-cm', type=float, default=6.0)
    parser.add_argument('--gt-z', type=float, help='User-measured fixed distance, in cm')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--max-frames', type=int, default=0, help='0 means unlimited')
    args = parser.parse_args()
    if args.max_frames < 0 or (args.gt_z is not None and
                               (not np.isfinite(args.gt_z) or args.gt_z <= 0)):
        parser.error('max-frames must be >=0; gt-z must be positive and finite.')
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PerceptionTests))
        return 0 if result.wasSuccessful() else 1
    try:
        return live(args)
    except (OSError, KeyError, ValueError, RuntimeError, cv2.error) as error:
        parser.exit(1, f'Perception check error: {error}\n')
    except KeyboardInterrupt:
        parser.exit(130, 'Stopped.\n')


if __name__ == '__main__':
    raise SystemExit(main())
