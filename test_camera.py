"""Camera startup/stall regressions with a deterministic clock, no camera access."""

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from contract import Observation
import main as app


class CameraStartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.calib = Path(self.temp.name) / 'fake_calibration.npz'
        self.calib.touch()  # Perceiver is mocked; no real camera calibration is used.
        self.clock = [0.]
        self.sent_frame = False

        def read():
            self.clock[0] += .5
            if self.clock[0] >= 4 and not self.sent_frame:
                self.sent_frame = True
                return app.Packet(0, np.zeros((720, 1280, 3), np.uint8), self.clock[0], 0.)
            return None

        self.capture = SimpleNamespace(live=True, synthetic=False, kind='LIVE', source=0,
                                       fps=30., done=False, error='', read=read, close=lambda: None)

    def run_camera(self, *options):
        args = app.build_parser().parse_args([
            '--source', '0', '--calib', str(self.calib), '--headless',
            '--fallback', str(Path(self.temp.name) / 'missing.mp4'), *options,
        ])
        with patch.object(app, 'Capture', return_value=self.capture), \
                patch('main.time.perf_counter', side_effect=lambda: self.clock[0]), \
                patch('perception.Perceiver') as constructor:
            constructor.return_value.process.side_effect = lambda frame, stamp: Observation(stamp, stamp, False)
            return app.run(args)

    def test_camera_first_frame_after_three_seconds_is_accepted(self):
        self.assertEqual(self.run_camera('--max-frames', '1'), 1)
        self.assertEqual(self.clock[0], 4.)

    def test_running_camera_still_times_out_after_three_seconds_without_frames(self):
        with self.assertRaisesRegex(OSError, 'Webcam timed out'):
            self.run_camera('--max-frames', '2')
        self.assertTrue(self.sent_frame, 'Startup must finish before testing a running-camera stall.')
        self.assertLess(self.clock[0], 10.)


if __name__ == '__main__':
    unittest.main(verbosity=2)
