"""P1 integration handoff checks; all images/GT are SYNTHETIC, never evidence.

Exercises the actual P1 -> P2 -> P3 video/CSV/replay and P2 -> P4 pipelines.
Uses temporary files only; does not open or record the webcam.
"""

import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from calibrate import save_calibration
from contract import Observation
from filter import AlignmentKF
import main as app
from perception import Perceiver
from test_perception import pose_rotation


ROOT = Path(__file__).resolve().parent


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def command(self, *args):
        result = subprocess.run([sys.executable, *map(str, args)], cwd=ROOT,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_perception_filter_hud_record_and_replay(self):
        K = np.array([[900., 0, 640], [0, 900., 360], [0, 0, 1]])
        calibration = self.root / 'synthetic_camera.npz'
        save_calibration(calibration, K, np.zeros(5), np.nan, (1280, 720), method='synthetic_test')
        perceiver = Perceiver(calibration)
        corners, _ = cv2.projectPoints(perceiver.object_points, pose_rotation(25),
                                       np.array([4., 0., 50.]), K, np.zeros(5))
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)
        square = np.array([[0, 0], [599, 0], [599, 599], [0, 599]], np.float32)
        H = cv2.getPerspectiveTransform(square, corners.reshape(4, 2).astype(np.float32))

        def frame(marker_id):
            marker = cv2.aruco.generateImageMarker(dictionary, marker_id, 600)
            gray = cv2.warpPerspective(marker, H, (1280, 720),
                                       flags=cv2.INTER_NEAREST, borderValue=255)
            return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        source = self.root / 'synthetic_marker.avi'
        writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'MJPG'), 30, (1280, 720))
        self.assertTrue(writer.isOpened())
        try:
            for image in (frame(7), frame(8), np.full((720, 1280, 3), 255, np.uint8), frame(7)):
                for _ in range(12):
                    writer.write(image)
        finally:
            writer.release()

        video, log = self.root / 'record.mp4', self.root / 'log.csv'
        args = app.build_parser().parse_args([
            '--source', str(source), '--calib', str(calibration), '--headless',
            '--record', '--video-out', str(video), '--log-out', str(log),
        ])
        self.assertEqual(app.run(args), 48)
        with log.open(newline='', encoding='utf-8') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 48)
        self.assertEqual([int(row['found']) for row in rows], [1] * 12 + [0] * 24 + [1] * 12)
        self.assertTrue(all(row['source_kind'] == 'VIDEO' for row in rows))
        self.assertTrue(any(row['status'] == 'LOST' for row in rows[12:36]))
        self.assertTrue(all(float(row['total_ms']) >= 0 for row in rows))
        for row in rows[:12] + rows[-12:]:
            self.assertAlmostEqual(float(row['raw_z_cm']), 50, delta=1)
            self.assertGreater(float(row['raw_yaw_deg']), 0)
        replay = app.Replay(log)
        for index, row in enumerate(rows):
            obs, state, enabled, kind = replay.at(index)
            self.assertEqual(obs.t_capture, float(row['t_capture']))
            self.assertEqual(state.status, row['status'])
            self.assertEqual(state.guidance, row['guidance'])
            self.assertEqual(enabled, bool(int(row['filter_enabled'])))
            self.assertEqual(kind, 'VIDEO')
        replay_args = app.build_parser().parse_args([
            '--source', str(video), '--replay', str(log), '--headless',
        ])
        self.assertEqual(app.run(replay_args), 48)
        # An unavailable camera must switch to the supplied video, without crash.
        fallback_args = app.build_parser().parse_args([
            '--source', '999', '--fallback', str(source), '--calib', str(calibration),
            '--headless', '--max-frames', '5',
        ])
        self.assertEqual(app.run(fallback_args), 5)
        loop_args = app.build_parser().parse_args([
            '--source', str(source), '--calib', str(calibration),
            '--loop', '--headless', '--max-frames', '55', '--record',
            '--video-out', str(self.root / 'loop_raw.mp4'),
            '--log-out', str(self.root / 'loop_raw.csv'),
        ])
        instances = []

        def load_raw_initially():
            estimator = AlignmentKF(filter_enabled=bool(instances))
            instances.append(estimator)
            return estimator, False

        with patch.object(app, 'load_filter', side_effect=load_raw_initially):
            self.assertEqual(app.run(loop_args), 55)
        with (self.root / 'loop_raw.csv').open(newline='', encoding='utf-8') as handle:
            loop_rows = list(csv.DictReader(handle))
        self.assertTrue(all(row['filter_enabled'] == '0' for row in loop_rows),
                        'Looping must preserve the presenter\'s F / RAW selection.')

    def test_p4_collection_and_evaluation(self):
        path = self.root / 'gt_runs_synthetic.csv'
        output = self.root / 'evaluation'
        self.command('collect_gt.py', '--synthetic', '--out', path)
        with path.open(newline='', encoding='utf-8') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 360)
        self.assertEqual(len({row['pose_id'] for row in rows}), 12)
        self.assertTrue(all(row['case'] == 'grid' for row in rows))
        self.command('evaluate.py', '--csv', path, '--out', output)
        metrics = (output / 'metrics_synthetic.md').read_text(encoding='utf-8')
        self.assertIn('DU LIEU GIA', metrics)
        self.assertIn('KHONG dung lam bang chung', metrics)
        self.assertIn('Tong 360 frame', metrics)
        for name in ('error_vs_z_synthetic.png', 'error_vs_yaw_synthetic.png'):
            image = cv2.imread(str(output / name))
            self.assertIsNotNone(image)
            self.assertGreater(image.shape[0], 100)

    def test_recording_existing_files_starts_a_new_session(self):
        for occupied in ('video', 'log', 'both', 'collision'):
            with self.subTest(occupied=occupied):
                directory = self.root / occupied
                directory.mkdir()
                video, log = directory / 'my_demo.mp4', directory / 'my_demo.csv'
                if occupied in ('video', 'both', 'collision'):
                    video.write_bytes(b'keep old video')
                if occupied in ('log', 'both', 'collision'):
                    log.write_text('keep old log', encoding='utf-8')
                if occupied == 'collision':
                    (directory / 'my_demo_20261016_170000.mp4').write_bytes(b'keep previous session')
                args = app.build_parser().parse_args([
                    '--synthetic', '--headless', '--max-frames', '3', '--record',
                    '--video-out', str(video), '--log-out', str(log),
                ])
                with patch('main.time.strftime', return_value='20261016_170000'):
                    self.assertEqual(app.run(args), 3)
                if occupied in ('video', 'both', 'collision'):
                    self.assertEqual(video.read_bytes(), b'keep old video')
                if occupied in ('log', 'both', 'collision'):
                    self.assertEqual(log.read_text(encoding='utf-8'), 'keep old log')
                serial = '_1' if occupied == 'collision' else ''
                new_video = directory / f'my_demo_20261016_170000{serial}.mp4'
                new_log = directory / f'my_demo_20261016_170000{serial}.csv'
                self.assertGreater(new_video.stat().st_size, 0)
                with new_log.open(newline='', encoding='utf-8') as handle:
                    self.assertEqual(len(list(csv.DictReader(handle))), 3)
                if occupied == 'collision':
                    self.assertEqual((directory / 'my_demo_20261016_170000.mp4').read_bytes(),
                                     b'keep previous session')

    def test_ambiguous_measurement_never_confirms_alignment(self):
        from collect_gt import make_row

        import time
        estimator = AlignmentKF()
        stamp = time.perf_counter()
        obs = Observation(stamp, stamp, True, x_cm=0, z_cm=15, yaw_deg=0,
                          reproj_err_px=0.2, ambiguous=True)
        state = estimator.update(obs)
        self.assertNotEqual(state.status, 'GOOD')
        self.assertFalse(state.aligned)
        self.assertNotIn('SAN SANG', state.guidance)
        row = make_row(('synthetic_ambiguous', 0., 15., 0.), 'synthetic_test', obs, state)
        self.assertEqual(row['ambiguous'], 1)
        self.assertEqual(row['status'], state.status)


if __name__ == '__main__':
    unittest.main(verbosity=2)
