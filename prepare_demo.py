"""Build an offline ArUco video for the actual detector/PnP/filter demo.

Every frame is visibly labelled SYNTHETIC. K and ground truth describe a
virtual camera, not a measured physical camera. No printing or webcam needed.
"""

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np

from calibrate import save_calibration


ROOT = Path(__file__).resolve().parent
ASSET_DIR = ROOT / 'demo_assets'
VERSION = 2
FPS = 30
FRAME_COUNT = 28 * FPS
IMAGE_SIZE = (1280, 720)
K = np.array([[900., 0., 640.], [0., 900., 360.], [0., 0., 1.]])
OBJECT_POINTS = np.array([[-3., 3., 0.], [3., 3., 0.],
                          [3., -3., 0.], [-3., -3., 0.]])


def scenario(index):
    seconds = index / FPS
    if seconds < 6:
        u = seconds / 6
        u = u * u * (3 - 2 * u)
        return 'approach', 8 * (1-u), 80 - 66*u, 25*(1-u), 7
    if seconds < 9:
        return 'aligned', 0., 14., 0., 7
    if seconds < 12:
        return 'rapid_move', -8., 50., -25., 7
    if seconds < 14:
        return 'wrong_id', -8., 50., -25., 8
    if seconds < 16:
        return 'occluded', 4., 50., 20., 7
    if seconds < 18:
        return 'motion_blur', 4., 50., 20., 7
    if seconds < 20:
        return 'glare', 4., 50., 20., 7
    if seconds < 23:
        return 'distant_tilt', 0., 100., 20., 7
    return 'aligned_final', 0., 14., 0., 7


def render_frame(index, markers, rng):
    case, x, z, yaw, marker_id = scenario(index)
    facing = np.diag([1., -1., -1.])
    turn, _ = cv2.Rodrigues(np.array([0., -np.deg2rad(yaw), 0.]))
    rotation, _ = cv2.Rodrigues(turn @ facing)
    corners, _ = cv2.projectPoints(OBJECT_POINTS, rotation, np.array([x, 0., z]), K, np.zeros(5))
    source = np.array([[0, 0], [599, 0], [599, 599], [0, 599]], np.float32)
    H = cv2.getPerspectiveTransform(source, corners.reshape(4, 2).astype(np.float32))
    frame = cv2.warpPerspective(markers[marker_id], H, IMAGE_SIZE,
                                flags=cv2.INTER_LINEAR, borderValue=220)
    # Pixel noise is seeded, so the video is reproducible; Observation is NOT faked.
    frame = np.clip(frame.astype(np.float32) + rng.normal(0, 2, frame.shape), 0, 255).astype(np.uint8)
    if case == 'occluded':
        corner = corners.reshape(4, 2)[0].astype(int)
        cv2.rectangle(frame, tuple(corner-25), tuple(corner+25), 220, -1)
    elif case == 'motion_blur':
        frame = cv2.blur(frame, (81, 1))
    elif case == 'glare':
        points = corners.reshape(4, 2)
        center = points.mean(axis=0)
        glare = center + 0.85 * (points - center)
        cv2.fillConvexPoly(frame, glare.astype(np.int32), 255)
    frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    # Keep this label outside every marker's bounding box. It remains in raw recordings.
    cv2.rectangle(frame, (12, 190), (410, 350), (25, 30, 38), -1)
    lines = ['MO PHONG - KHONG PHAI WEBCAM', f'CASE: {case}',
             f'GT model: x={x:+.1f} z={z:.1f} cm', f'yaw={yaw:+.1f} deg | ID {marker_id}',
             'GT TU MO HINH, KHONG DO BANG THUOC']
    for row, line in enumerate(lines):
        cv2.putText(frame, line, (22, 217 + row*28), cv2.FONT_HERSHEY_SIMPLEX,
                    0.49, (230, 235, 245) if row else (80, 190, 255), 1, cv2.LINE_AA)
    return frame


def prepare_assets(directory=ASSET_DIR):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {name: directory / filename for name, filename in (
        ('video', 'marker_demo_render.mp4'), ('calib', 'calibration_render.npz'),
        ('truth', 'ground_truth_render.csv'), ('manifest', 'manifest.json'))}
    if paths['manifest'].is_file():
        try:
            manifest = json.loads(paths['manifest'].read_text(encoding='utf-8'))
            if manifest.get('version') == VERSION and all(path.is_file() and path.stat().st_size
                                                         for path in paths.values()):
                return paths
        except (ValueError, OSError):
            pass
    print('Preparing SYNTHETIC ArUco demo video (no physical accuracy claim)...', flush=True)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)
    markers = {marker_id: cv2.aruco.generateImageMarker(dictionary, marker_id, 600)
               for marker_id in (7, 8)}
    pending = directory / 'marker_demo_render.partial.mp4'
    writer = cv2.VideoWriter(str(pending), cv2.VideoWriter_fourcc(*'mp4v'), FPS, IMAGE_SIZE)
    if not writer.isOpened():
        writer.release()
        raise OSError('MP4 writer unavailable. Check OpenCV video codecs.')
    rng = np.random.default_rng(7)
    try:
        with paths['truth'].open('w', newline='', encoding='utf-8') as handle:
            output = csv.writer(handle)
            output.writerow(['frame_index', 'model_time_s', 'case', 'gt_x', 'gt_z', 'gt_yaw', 'marker_id'])
            for index in range(FRAME_COUNT):
                writer.write(render_frame(index, markers, rng))
                case, x, z, yaw, marker_id = scenario(index)
                output.writerow([index, index/FPS, case, x, z, yaw, marker_id])
    finally:
        writer.release()
    pending.replace(paths['video'])
    save_calibration(paths['calib'], K, np.zeros(5), np.nan, IMAGE_SIZE, method='synthetic_render')
    paths['manifest'].write_text(json.dumps({
        'version': VERSION, 'kind': 'SYNTHETIC_RENDER', 'fps': FPS, 'frames': FRAME_COUNT,
        'physical_measurement': False,
        'description': 'Rendered pixels processed by real ArUco, IPPE and Kalman. GT is virtual geometry.',
    }, indent=2), encoding='utf-8')
    print(f'Ready: {paths["video"]}', flush=True)
    return paths


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ASSET_DIR)
    args = parser.parse_args()
    prepare_assets(args.output_dir)
