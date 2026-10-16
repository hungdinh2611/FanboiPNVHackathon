"""Verify a no-print recording against VIRTUAL ground truth, write a labelled report.

python verify_demo.py --log demo_assets/final_log_render.csv
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from prepare_demo import ASSET_DIR, FPS, FRAME_COUNT, prepare_assets


def verify(log, output):
    paths = prepare_assets()
    truth = pd.read_csv(paths['truth'])
    recorded = pd.read_csv(log)
    if (len(recorded) != FRAME_COUNT or
            recorded.frame_index.tolist() != list(range(FRAME_COUNT))):
        raise ValueError(f'Need exactly {FRAME_COUNT} consecutive frames from --no-print --once.')
    if not (recorded.source_kind == 'SYNTHETIC_RENDER').all():
        raise ValueError('Recording must retain the SYNTHETIC_RENDER label.')
    data = recorded.merge(truth, on='frame_index', validate='one_to_one')
    rows = []
    for case, group in data.groupby('case', sort=False):
        found = group[group.found == 1]
        raw_z = (found.raw_z_cm - found.gt_z).abs().mean()
        yaw_err = (found.raw_yaw_deg - found.gt_yaw + 180) % 360 - 180
        rows.append((case, len(group), 100*group.found.mean(),
                     100*(group.status == 'GOOD').mean(), 100*group.aligned.mean(),
                     raw_z, yaw_err.abs().mean()))
    results = pd.DataFrame(rows, columns=['case', 'frames', 'found_%', 'GOOD_%', 'aligned_%',
                                         'MAE_raw_z_cm', 'MAE_raw_yaw_deg'])
    checks = []
    checks.append(('Every frame is explicitly synthetic', True))
    for case in ('wrong_id', 'occluded', 'motion_blur', 'glare'):
        group = data[data['case'] == case]
        checks.append((f'{case}: no target observation', bool(len(group) and (group.found == 0).all())))
        checks.append((f'{case}: ends LOST', bool(len(group) and (group.tail(10).status == 'LOST').all())))
    final = data[(data['case'] == 'aligned_final') & (data.model_time_s >= 24)]
    checks.append(('Final stable pose: >=90% aligned and GOOD', bool(len(final) and
                   ((final.aligned == 1) & (final.status == 'GOOD')).mean() >= .9)))
    rapid = data[data['case'] == 'rapid_move']
    recovered = rapid[(rapid.status == 'GOOD') & ((rapid.z_cm-rapid.gt_z).abs() < 2) &
                      ((rapid.yaw_deg-rapid.gt_yaw).abs() < 5)]
    recovery_frames = None if recovered.empty else int(recovered.frame_index.iloc[0] - rapid.frame_index.iloc[0])
    checks.append(('Rapid move recovered within 6 model frames', recovery_frames is not None and recovery_frames <= 6))
    checks.append(('Capture timestamps increase', bool(np.all(np.diff(data.t_capture) > 0))))
    header = '| ' + ' | '.join(results.columns) + ' |'
    table = [header, '|' + ' --- |' * len(results.columns)]
    for row in results.itertuples(index=False, name=None):
        table.append('| ' + ' | '.join(f'{value:.3f}' if isinstance(value, float) else str(value)
                                      for value in row) + ' |')
    lines = ['# Kiem tra demo KHONG CAN IN', '',
             '**DU LIEU MO PHONG. K va GT tu camera ao; KHONG phai do webcam/thuoc.**', '',
             'Video pixels -> ArUco -> IPPE -> Kalman -> HUD -> recording.', '', *table, '',
             '## Checks', '', *[f'- {"PASS" if ok else "FAIL"}: {name}' for name, ok in checks], '',
             f'Rapid recovery: {recovery_frames} frames at {FPS} model FPS.', '',
             'Latency in the CSV measures playback software work, not sensor-to-screen latency.',
             'Known limitation: distant planar markers can still flip yaw; passing this clip does not',
             'prove physical accuracy. P4 render test P08 (z100/yaw20) retains this failure case.', '']
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines), encoding='utf-8')
    print('\n'.join(lines))
    print(f'Report: {output}')
    return all(ok for _, ok in checks)


def export_hud(video, log, output):
    """Bake HUD into a standalone labelled backup, without rerunning estimation."""
    import cv2
    import main as app
    from perception import Perceiver

    if Path(output).resolve() in (Path(video).resolve(), Path(log).resolve()):
        raise ValueError('HUD output must differ from input video and CSV.')
    paths = prepare_assets()
    perceiver = Perceiver(paths['calib'])
    replay = app.Replay(log)
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        capture.release()
        raise OSError(f'Cannot read {video}')
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*'mp4v'), FPS, (1280, 720))
    try:
        if not writer.isOpened():
            raise OSError(f'Cannot write {output}')
        for index in range(len(replay.rows)):
            ok, frame = capture.read()
            if not ok:
                raise ValueError('Recorded video ends before the CSV.')
            obs, state, enabled, kind = replay.at(index)
            canvas = app.render(app.Packet(index, frame, obs.t_capture, 0), obs, state,
                                perceiver, FPS, state.latency_ms['total'], 'VIDEO', enabled,
                                False, False, replay=True, recorded_kind=kind)
            writer.write(canvas)
        if capture.read()[0]:
            raise ValueError('Recorded video has more frames than the CSV.')
    finally:
        capture.release()
        writer.release()
    print(f'Standalone SYNTHETIC HUD backup: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', type=Path, default=ASSET_DIR / 'final_log_render.csv')
    parser.add_argument('--out', type=Path, default=ASSET_DIR / 'validation_render.md')
    parser.add_argument('--video', type=Path, default=ASSET_DIR / 'final_recording_render.mp4')
    parser.add_argument('--export-video', nargs='?', type=Path,
                        const=ASSET_DIR / 'demo_hud_render.mp4')
    args = parser.parse_args()
    passed = verify(args.log, args.out)
    if passed and args.export_video is not None:
        export_hud(args.video, args.log, args.export_video)
    raise SystemExit(0 if passed else 1)
