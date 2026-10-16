"""P1: chessboard calibration (9x6 inner corners, 25 mm squares).

SPACE saves a valid view, C calibrates after >=15 views, Q exits.
Fallback: python calibrate.py --approx-fov 68 --width 1280 --height 720
Print assets: python calibrate.py --generate-patterns
"""

import argparse
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


BOARD = (9, 6)
MIN_VIEWS = 15


def board_points(square_mm=25.0):
    points = np.zeros((BOARD[0] * BOARD[1], 3), np.float32)
    # Geometry is in cm throughout the project.
    points[:, :2] = np.mgrid[:BOARD[0], :BOARD[1]].T.reshape(-1, 2)
    points *= square_mm / 10.0
    return points


def find_corners(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    found, corners = cv2.findChessboardCorners(
        gray, BOARD, cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
    )
    if not found:
        return None
    return cv2.cornerSubPix(
        gray, corners, (11, 11), (-1, -1),
        (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001),
    )


def save_calibration(path, K, dist, rms, image_size, **metadata):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # A file handle prevents numpy silently appending '.npz' to a custom path.
    with path.open('wb') as output:
        np.savez(output, K=K, dist=dist, rms=float(rms),
                 image_size=np.asarray(image_size, dtype=np.int32), **metadata)
    print(f'Saved {path} | image_size={tuple(image_size)}')


def approximate_calibration(hfov_deg, image_size, output):
    width, height = image_size
    if not 0 < hfov_deg < 180 or min(width, height) <= 0:
        raise ValueError('FOV must be between 0 and 180; width/height must be positive.')
    # Assumes square pixels, principal point at image centre, no distortion.
    focal = width / (2.0 * np.tan(np.deg2rad(hfov_deg) / 2.0))
    K = np.array([[focal, 0, width / 2.0],
                  [0, focal, height / 2.0], [0, 0, 1]], dtype=np.float64)
    save_calibration(output, K, np.zeros(5), np.nan, image_size,
                     method='approx_fov', hfov_deg=hfov_deg)
    print('WARNING: APPROXIMATE K, not measured calibration; RMS is unknown.')
    print('Use the exact camera resolution above. Measure z=50 cm with a ruler.')
    return K


def calibrate_views(corners, image_size, square_mm, output):
    if len(corners) < MIN_VIEWS:
        raise ValueError(f'Need at least {MIN_VIEWS} valid, varied chessboard views.')
    objects = [board_points(square_mm) for _ in corners]
    rms, K, dist, rvecs, tvecs = cv2.calibrateCamera(
        objects, corners, image_size, None, None
    )
    if not np.isfinite(rms) or not np.isfinite(K).all() or not np.isfinite(dist).all():
        raise ValueError('Calibration failed: non-finite parameters. Capture new views.')
    errors = []
    for index, (obj, observed, rvec, tvec) in enumerate(zip(objects, corners, rvecs, tvecs)):
        predicted, _ = cv2.projectPoints(obj, rvec, tvec, K, dist)
        # RMS pixel distance per corner, consistent with calibrateCamera's RMS.
        error = float(np.sqrt(np.mean(np.sum((observed - predicted) ** 2, axis=2))))
        errors.append(error)
        print(f'View {index + 1:02d}: RMS={error:.4f} px')
    print(f'Overall RMS={rms:.4f} px | target <0.6 px')
    save_calibration(output, K, dist, rms, image_size, method='chessboard',
                     square_mm=square_mm, per_view_rms=np.asarray(errors),
                     views=len(corners), quality_ok=bool(rms < 0.6))
    if rms >= 0.6:
        print('WARNING: above target. Vary board tilt/position; remove blur/glare.')
        print('If time is short, use --approx-fov 68 and report the limitation.')
    return rms, K, dist


def generate_patterns(output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)
    # White quiet zone is outside the measured 6 cm black square.
    marker = cv2.aruco.generateImageMarker(dictionary, 7, 600)
    marker = cv2.copyMakeBorder(marker, 100, 100, 100, 100, cv2.BORDER_CONSTANT, value=255)
    square_px = 100
    board = np.full((7 * square_px + 200, 10 * square_px + 200), 255, np.uint8)
    for row in range(7):
        for col in range(10):
            if (row + col) % 2 == 0:
                y, x = 100 + row * square_px, 100 + col * square_px
                board[y:y + square_px, x:x + square_px] = 0
    for name, pixels in [('marker_7.png', marker), ('checkerboard_9x6.png', board)]:
        if not cv2.imwrite(str(output_dir / name), pixels):
            raise OSError(f'Could not write {name}')
    print('marker_7.png: print whole 800px image at 80 x 80 mm; black square = 60 mm.')
    print('checkerboard_9x6.png: print whole image at 300 x 225 mm (A3); each square = 25 mm.')
    print('A4 landscape: crop white margin, print board alone at 250 x 175 mm.')
    print('Disable fit-to-page. Measure actual marker edge and board squares after printing.')


def calibrate_images(paths, square_mm, output):
    views, image_size = [], None
    for path in paths:
        frame = cv2.imread(str(path))
        if frame is None:
            raise ValueError(f'Cannot read image: {path}')
        size = (frame.shape[1], frame.shape[0])
        if image_size is not None and size != image_size:
            raise ValueError('All calibration images must have the same resolution.')
        image_size = size
        corners = find_corners(frame)
        if corners is not None:
            views.append(corners)
        else:
            print(f'Skip (no 9x6 corners): {path}')
    return calibrate_views(views, image_size, square_mm, output)


def capture_calibration(args):
    capture = cv2.VideoCapture(args.source)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError('Cannot open webcam. Close other camera apps or change --source.')
    session = Path(args.frames_dir) / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    views, image_size = [], None
    try:
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        if capture.set(cv2.CAP_PROP_AUTOFOCUS, 0):
            print('Autofocus off requested; verify the board remains sharp.')
        else:
            print('Driver cannot lock autofocus. Keep focus fixed in camera settings if possible.')
        print('SPACE: save valid view | C: calibrate (>=15) | Q: quit')
        print('Move board across the image, vary distance and tilt; keep all corners visible.')
        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                raise RuntimeError('Camera stopped delivering frames.')
            size = (frame.shape[1], frame.shape[0])
            if image_size is not None and size != image_size:
                raise RuntimeError('Camera resolution changed; restart calibration.')
            image_size = size
            corners = find_corners(frame)
            preview = frame.copy()
            if corners is not None:
                cv2.drawChessboardCorners(preview, BOARD, corners, True)
            text = f'Views {len(views)}/{MIN_VIEWS} | SPACE save | C calibrate | Q quit'
            cv2.putText(preview, text, (15, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.65, (0, 255, 0) if corners is not None else (0, 150, 255), 2)
            cv2.imshow('P1 - Calibration', preview)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), ord('Q'), 27):
                break
            if key == 32:
                if corners is None:
                    print('Not saved: all 9x6 inner corners must be visible.')
                    continue
                if any(np.mean(np.linalg.norm(corners - old, axis=2)) < 5 for old in views):
                    print('Not saved: near-duplicate view. Move or tilt the board.')
                    continue
                session.mkdir(parents=True, exist_ok=True)
                path = session / f'view_{len(views) + 1:03d}.png'
                if not cv2.imwrite(str(path), frame):
                    raise OSError(f'Could not save {path}')
                views.append(corners.copy())
                print(f'Saved view {len(views)}: {path}')
            if key in (ord('c'), ord('C')):
                if len(views) < MIN_VIEWS:
                    print(f'Need {MIN_VIEWS - len(views)} more views.')
                    continue
                calibrate_views(views, image_size, args.square_mm, args.output)
                break
    finally:
        capture.release()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--approx-fov', type=float, metavar='DEGREES')
    mode.add_argument('--generate-patterns', action='store_true')
    mode.add_argument('--images', nargs='+', type=Path)
    parser.add_argument('--source', type=int, default=0)
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=720)
    parser.add_argument('--square-mm', type=float, default=25.0)
    parser.add_argument('--output', default='calib.npz')
    parser.add_argument('--frames-dir', default='calibration_frames')
    parser.add_argument('--patterns-dir', default='.')
    args = parser.parse_args()
    if not np.isfinite(args.square_mm) or min(args.width, args.height, args.square_mm) <= 0:
        parser.error('width, height and square-mm must be positive.')
    try:
        if args.generate_patterns:
            generate_patterns(args.patterns_dir)
        elif args.approx_fov is not None:
            approximate_calibration(args.approx_fov, (args.width, args.height), args.output)
        elif args.images:
            calibrate_images(args.images, args.square_mm, args.output)
        else:
            capture_calibration(args)
    except (ValueError, OSError, RuntimeError, cv2.error) as error:
        parser.exit(1, f'Calibration error: {error}\n')
    except KeyboardInterrupt:
        parser.exit(130, 'Stopped.\n')


if __name__ == '__main__':
    main()
