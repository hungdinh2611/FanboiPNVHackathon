"""Regressions for rapid movement: recover from a new stable pose, reject bad runs."""

import unittest

from contract import Observation
from filter import AlignmentKF


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.kf = AlignmentKF()
        self.frame = 0
        for _ in range(90):
            self.sample()

    def sample(self, z=30., found=True, ambiguous=False, reproj=0.2):
        self.frame += 1
        stamp = self.frame / 30.
        return self.kf.update(Observation(stamp, stamp + .002, found,
                                          z_cm=z, ambiguous=ambiguous, reproj_err_px=reproj))

    def test_consistent_new_pose_recovers_within_six_frames(self):
        states = [self.sample(z=60) for _ in range(6)]
        self.assertEqual(states[-1].status, 'GOOD')
        self.assertAlmostEqual(states[-1].z_cm, 60, delta=1)

    def test_one_outlier_cannot_reinitialize(self):
        self.assertAlmostEqual(self.sample(z=100).z_cm, 30, delta=1)
        self.assertAlmostEqual(self.sample().z_cm, 30, delta=1)

    def test_bad_reprojection_cannot_arm_a_reset(self):
        for _ in range(6):
            self.sample(z=60, reproj=5)
        self.assertAlmostEqual(self.sample(z=60).z_cm, 30, delta=1)

    def test_ambiguous_run_cannot_arm_a_reset(self):
        for _ in range(6):
            self.sample(z=60, ambiguous=True)
        self.assertAlmostEqual(self.sample(z=60).z_cm, 30, delta=1)

    def test_missing_frame_breaks_consecutive_rejections(self):
        for _ in range(4):
            self.sample(z=60)
        self.sample(found=False)
        for _ in range(2):
            state = self.sample(z=60)
        self.assertAlmostEqual(state.z_cm, 30, delta=1)

    def test_inconsistent_outliers_do_not_reinitialize(self):
        for z in [60, 100] * 5:
            state = self.sample(z=z)
            self.assertAlmostEqual(state.z_cm, 30, delta=1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
