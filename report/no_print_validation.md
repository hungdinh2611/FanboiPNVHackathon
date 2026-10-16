# Kiem tra demo KHONG CAN IN

**DU LIEU MO PHONG. K va GT tu camera ao; KHONG phai do webcam/thuoc.**

Video pixels -> ArUco -> IPPE -> Kalman -> HUD -> recording.

| case | frames | found_% | GOOD_% | aligned_% | MAE_raw_z_cm | MAE_raw_yaw_deg |
| --- | --- | --- | --- | --- | --- | --- |
| approach | 180 | 100.000 | 97.222 | 5.556 | 0.161 | 0.822 |
| aligned | 90 | 100.000 | 100.000 | 100.000 | 0.031 | 0.417 |
| rapid_move | 90 | 100.000 | 95.556 | 0.000 | 0.095 | 0.384 |
| wrong_id | 60 | 0.000 | 0.000 | 0.000 | nan | nan |
| occluded | 60 | 0.000 | 0.000 | 0.000 | nan | nan |
| motion_blur | 60 | 0.000 | 0.000 | 0.000 | nan | nan |
| glare | 60 | 0.000 | 0.000 | 0.000 | nan | nan |
| distant_tilt | 90 | 100.000 | 100.000 | 0.000 | 0.430 | 0.796 |
| aligned_final | 150 | 100.000 | 97.333 | 97.333 | 0.031 | 0.343 |

## Checks

- PASS: Every frame is explicitly synthetic
- PASS: wrong_id: no target observation
- PASS: wrong_id: ends LOST
- PASS: occluded: no target observation
- PASS: occluded: ends LOST
- PASS: motion_blur: no target observation
- PASS: motion_blur: ends LOST
- PASS: glare: no target observation
- PASS: glare: ends LOST
- PASS: Final stable pose: >=90% aligned and GOOD
- PASS: Rapid move recovered within 6 model frames
- PASS: Capture timestamps increase

Rapid recovery: 4 frames at 30 model FPS.

Latency in the CSV measures playback software work, not sensor-to-screen latency.
Known limitation: distant planar markers can still flip yaw; passing this clip does not
prove physical accuracy. P4 render test P08 (z100/yaw20) retains this failure case.
