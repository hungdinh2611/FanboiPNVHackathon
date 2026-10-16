"""P3 demo app. Run with the project's Python environment:

    python main.py --synthetic
    python main.py --source 0 --calib calib.npz
    python main.py --source video.mp4 --replay log.csv
    python main.py --synthetic --headless --max-frames 90 --record

R: record raw video + CSV, F: toggle P2 Kalman, SPACE: freeze, Q/ESC: quit.
Synthetic mode and the temporary raw adapter are visibly labelled. No camera
calibration or P2 filter is invented. All processing timestamps use perf_counter.

Thiet ke P3: capture chay rieng, webcam chi giu frame moi nhat de tranh tre.
Video/replay doc tung frame theo FPS, log gan voi frame_index cua video da ghi.
Sigma la do lech chuan tu P2; khi chua co P2 hien '--', khong bia do tin cay.
Minimap nhin tu tren: x duong sang phai, z duong ra xa; elip la +/-2 sigma.
"""

import argparse
import csv
import importlib
import json
import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path
import threading
import time

import cv2
import numpy as np

from contract import Observation, State


WIDTH, HEIGHT = 1280, 720
COLORS = {'GOOD': (90, 220, 100), 'DEGRADED': (0, 200, 255), 'LOST': (75, 75, 255)}
LOG_FIELDS = [
    'frame_index', 'video_time_s', 't_capture', 't_detect_done', 'found',
    'raw_x_cm', 'raw_z_cm', 'raw_yaw_deg', 'reproj_err_px', 'ambiguous',
    'x_cm', 'z_cm', 'yaw_deg', 'sigma_x', 'sigma_z', 'sigma_yaw',
    'status', 'guidance', 'aligned', 'filter_enabled', 'source_kind',
    'capture_ms', 'detect_ms', 'filter_ms', 'display_ms', 'total_ms',
    'corners', 'rvec', 'tvec',
]


@dataclass
class Packet:
    index: int
    frame: np.ndarray
    t_capture: float
    capture_ms: float


class Capture:
    """One-slot mailbox. Camera overwrites stale frames; video waits for consumer.

    The worker owns VideoCapture including release, avoiding release/read races.
    A driver stuck in read cannot stall the UI or prevent fallback (daemon thread).
    """

    def __init__(self, source, synthetic=False):
        self.source = source
        self.synthetic = synthetic
        self.live = isinstance(source, int) and not synthetic
        self.kind = 'SYNTHETIC' if synthetic else ('LIVE' if self.live else 'VIDEO')
        self.condition = threading.Condition()
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.latest = None
        self.done = False
        self.error = ''
        self.fps = 30.0
        self.thread = threading.Thread(target=self._run, daemon=True, name='capture')
        self.thread.start()

    def _run(self):
        cap = None
        try:
            if not self.synthetic:
                cap = cv2.VideoCapture(self.source)
                if not cap.isOpened():
                    raise OSError(f'Cannot open source: {self.source}')
                if self.live:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                fps = cap.get(cv2.CAP_PROP_FPS)
                self.fps = float(fps) if math.isfinite(fps) and 1 <= fps <= 240 else 30.0
            self.ready.set()
            index = 0
            deadline = time.perf_counter()
            while not self.stop.is_set():
                if not self.live:
                    with self.condition:
                        self.condition.wait_for(lambda: self.latest is None or self.stop.is_set())
                    if self.stop.is_set():
                        break
                    self.stop.wait(max(0, deadline - time.perf_counter()))
                    if self.stop.is_set():
                        break
                start = time.perf_counter()
                if self.synthetic:
                    frame = np.full((HEIGHT, WIDTH, 3), (30, 24, 20), np.uint8)
                    t_capture = time.perf_counter()
                else:
                    ok = cap.grab()
                    t_capture = time.perf_counter()
                    if not ok:
                        if self.live:
                            self.error = 'Camera disconnected'
                        break
                    ok, frame = cap.retrieve()
                    if not ok or frame is None:
                        raise OSError('Frame retrieval failed')
                packet = Packet(index, frame, t_capture, (t_capture - start) * 1000)
                with self.condition:
                    self.latest = packet
                    self.condition.notify_all()
                index += 1
                # Never burst through old video frames after a pause/slow detector.
                deadline = max(deadline + 1 / self.fps, time.perf_counter())
        except (OSError, cv2.error) as exc:
            self.error = str(exc)
        finally:
            if cap is not None:
                cap.release()
            with self.condition:
                self.done = True
                self.ready.set()
                self.condition.notify_all()

    def read(self, timeout=0.05):
        with self.condition:
            self.condition.wait_for(lambda: self.latest is not None or self.done, timeout)
            packet = self.latest
            self.latest = None
            self.condition.notify_all()
            return packet

    def close(self):
        self.stop.set()
        with self.condition:
            self.condition.notify_all()
        self.thread.join(timeout=0.5)


class RawAdapter:
    """P3-only temporary stub until P2 arrives. Unknown sigma stays unknown."""

    filter_enabled = False

    def update(self, obs):
        status = ('DEGRADED' if obs.ambiguous else 'GOOD') if obs.found else 'LOST'
        guidance = 'KHONG THAY MARKER'
        if obs.found:
            parts = []
            if abs(obs.x_cm) >= 1:
                parts.append(f"SANG {'PHAI' if obs.x_cm > 0 else 'TRAI'} {abs(obs.x_cm):.1f} cm")
            if abs(obs.yaw_deg) >= 5:
                parts.append(f'CHINH GOC {obs.yaw_deg:+.0f} deg')
            parts.append(f'TIEN {obs.z_cm - 15:.1f} cm' if obs.z_cm > 15 else 'DUNG LAI')
            guidance = ' | '.join(parts)
        return State(obs.t_capture, obs.x_cm, obs.z_cm, obs.yaw_deg,
                     math.nan, math.nan, math.nan, status, guidance, False)


def load_filter():
    try:
        module = importlib.import_module('filter')
    except ModuleNotFoundError as exc:
        if exc.name != 'filter':
            raise
        print('P2 filter.py missing: temporary RAW adapter, sigma unavailable.')
        return RawAdapter(), True
    return module.AlignmentKF(), False


def synthetic_observation(packet, sequence=None):
    """Deterministic demo motion, dropouts and ambiguous frames; NOT measurements."""
    if sequence is not None:
        obs = next(sequence)
        # P2's generator precomputes future timestamps; the UI must rebase them
        # to actual capture/detection time rather than logging negative latency.
        obs.t_capture = packet.t_capture
        if obs.found and obs.corners is not None:
            cv2.fillConvexPoly(packet.frame, np.asarray(obs.corners).astype(np.int32), (160, 155, 140))
        obs.t_detect_done = time.perf_counter()
        return obs
    phase = packet.index / 30.0
    x = 12 * math.sin(phase * 0.8)
    z = 48 + 30 * math.cos(phase * 0.35)
    yaw = 18 * math.sin(phase * 0.5)
    found = packet.index % 240 < 215
    cx, cy = int(WIDTH / 2 + x * 9), HEIGHT // 2
    side = int(2000 / z)
    corners = np.array([[cx-side, cy-side], [cx+side, cy-side],
                        [cx+side, cy+side], [cx-side, cy+side]], np.float32)
    if found:
        cv2.fillConvexPoly(packet.frame, corners.astype(np.int32), (160, 155, 140))
    return Observation(packet.t_capture, time.perf_counter(), found, x, z, yaw,
                       0.3, packet.index % 150 > 135, corners if found else None)


def load_synthetic():
    try:
        module = importlib.import_module('synthetic')
    except ModuleNotFoundError as exc:
        if exc.name != 'synthetic':
            raise
        return None
    return module.stream_synthetic(realtime=False)


def array_json(value):
    return '' if value is None else json.dumps(np.asarray(value).tolist(), separators=(',', ':'))


class Recorder:
    """One CSV row for each saved raw frame; frame_index guarantees replay pairing.

    MP4 has constant FPS; video_time_s is the media timeline, t_capture retains
    the original sample timing for analysis. Video and CSV are never overwritten.
    """

    def __init__(self, video, log, fps, frame_size):
        if Path(video).resolve() == Path(log).resolve():
            raise ValueError('Video and CSV paths must differ')
        if Path(video).exists() or Path(log).exists():
            raise FileExistsError('Recording exists; choose new --video-out / --log-out paths')
        self.writer = None
        self.file = None
        self.index = 0
        self.fps = fps
        self.size = frame_size
        try:
            self.file = Path(log).open('x', newline='', encoding='utf-8')
            self.csv = csv.DictWriter(self.file, fieldnames=LOG_FIELDS)
            self.csv.writeheader()
            self.writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'mp4v'), fps, frame_size)
            if not self.writer.isOpened():
                raise OSError('MP4 writer could not open; check path/codec')
        except Exception:
            self.close()
            raise

    def write(self, packet, obs, state, enabled, kind):
        row = dict(frame_index=self.index, video_time_s=self.index / self.fps,
                   t_capture=obs.t_capture, t_detect_done=obs.t_detect_done,
                   found=int(obs.found), raw_x_cm=obs.x_cm, raw_z_cm=obs.z_cm,
                   raw_yaw_deg=obs.yaw_deg, reproj_err_px=obs.reproj_err_px,
                   ambiguous=int(obs.ambiguous), status=state.status,
                   guidance=state.guidance, aligned=int(state.aligned),
                   filter_enabled=int(enabled), source_kind=kind,
                   corners=array_json(obs.corners), rvec=array_json(obs.rvec), tvec=array_json(obs.tvec))
        for name in ('x_cm', 'z_cm', 'yaw_deg', 'sigma_x', 'sigma_z', 'sigma_yaw'):
            row[name] = getattr(state, name)
        for name in ('capture', 'detect', 'filter', 'display', 'total'):
            row[name + '_ms'] = state.latency_ms.get(name, 0.0)
        frame = packet.frame
        if (frame.shape[1], frame.shape[0]) != self.size:
            frame = cv2.resize(frame, self.size)
        self.writer.write(frame)
        self.csv.writerow(row)
        self.file.flush()
        self.index += 1

    def close(self):
        if self.writer is not None:
            self.writer.release()
        if self.file is not None:
            self.file.close()


class Replay:
    def __init__(self, path):
        with Path(path).open(newline='', encoding='utf-8-sig') as handle:
            reader = csv.DictReader(handle)
            if not set(LOG_FIELDS).issubset(reader.fieldnames or []):
                raise ValueError('Replay requires a P3 log.csv with frame_index and raw/filtered fields')
            self.rows = list(reader)
        if not self.rows:
            raise ValueError('Replay CSV is empty')
        for index, row in enumerate(self.rows):
            if int(row['frame_index']) != index:
                raise ValueError('Replay frame_index must be consecutive from zero')

    def at(self, index):
        if index >= len(self.rows):
            raise ValueError('Video has more frames than replay CSV')
        row = self.rows[index]
        def arr(name):
            return np.array(json.loads(row[name]), dtype=np.float64) if row[name] else None
        obs = Observation(float(row['t_capture']), float(row['t_detect_done']), bool(int(row['found'])),
                          float(row['raw_x_cm']), float(row['raw_z_cm']), float(row['raw_yaw_deg']),
                          float(row['reproj_err_px']), bool(int(row['ambiguous'])),
                          arr('corners'), arr('rvec'), arr('tvec'))
        state = State(obs.t_capture, *(float(row[name]) for name in
                      ('x_cm', 'z_cm', 'yaw_deg', 'sigma_x', 'sigma_z', 'sigma_yaw')),
                      row['status'], row['guidance'], bool(int(row['aligned'])),
                      {name: float(row[name + '_ms']) for name in
                       ('capture', 'detect', 'filter', 'display', 'total')})
        if state.status not in COLORS:
            raise ValueError(f'Invalid replay status: {state.status}')
        return obs, state, bool(int(row['filter_enabled'])), row['source_kind']


def put(frame, text, xy, scale=0.6, color=(235, 235, 235), thickness=1):
    # OpenCV's built-in font supports ASCII only. Fit long P2 guidance on screen.
    text = str(text).encode('ascii', errors='replace').decode('ascii')
    available = max(50, frame.shape[1] - xy[0] - 18)
    width = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)[0][0]
    if width > available:
        scale *= available / width
    cv2.putText(frame, text, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def number(value):
    return f'{value:.1f}' if math.isfinite(value) else '--'


def minimap(canvas, state):
    left, top, width, height = 1000, 218, 255, 300
    cv2.rectangle(canvas, (left, top), (left+width, top+height), (24, 29, 38), -1)
    put(canvas, 'TOP VIEW / cm', (left+12, top+25), 0.5)
    origin = (left + width//2, top + height - 30)
    # Scale expands to keep the current target visible. Same scale for both axes.
    distance = max(100.0, abs(state.x_cm)*2.4, state.z_cm*1.15) if state.status != 'LOST' else 100.0
    scale = 210.0 / distance
    cv2.line(canvas, (origin[0], top+40), origin, (100, 100, 100))
    cv2.line(canvas, (left+15, origin[1]), (left+width-15, origin[1]), (100, 100, 100))
    put(canvas, f'z: 0..{distance:.0f}', (left+8, top+47), 0.4)
    put(canvas, '+x ->', (left+width-72, origin[1]+18), 0.4)
    cv2.circle(canvas, origin, 6, (255, 210, 90), -1)
    if state.status == 'LOST':
        put(canvas, 'NO TARGET', (left+65, top+140), 0.5, COLORS['LOST'])
        return
    if not all(math.isfinite(v) for v in (state.x_cm, state.z_cm)):
        return
    target = (int(origin[0]+state.x_cm*scale), int(origin[1]-state.z_cm*scale))
    target = (max(left+10, min(left+width-10, target[0])), max(top+55, min(origin[1], target[1])))
    color = COLORS[state.status]
    has_sigma = all(math.isfinite(v) and v >= 0 for v in (state.sigma_x, state.sigma_z))
    if has_sigma:
        axes = (max(1, min(90, int(2*state.sigma_x*scale))),
                max(1, min(90, int(2*state.sigma_z*scale))))
        overlay = canvas[top:top+height, left:left+width].copy()
        cv2.ellipse(overlay, (target[0]-left, target[1]-top), axes, 0, 0, 360, color, 1)
        canvas[top:top+height, left:left+width] = overlay
    cv2.circle(canvas, target, 5, color, -1)
    put(canvas, 'ellipse: +/-2 sigma' if has_sigma else 'SIGMA CHUA CO',
        (left+10, top+height-8), 0.4)


def render(packet, obs, state, perceiver, fps, latency, kind, enabled, stub, recording,
           frozen=False, replay=False, notice='', recorded_kind=''):
    frame = packet.frame.copy()
    color = COLORS.get(state.status, COLORS['LOST'])
    if obs.corners is not None:
        points = np.asarray(obs.corners).reshape(4, 2).astype(np.int32)
        cv2.polylines(frame, [points], True, color, 2)
    if (perceiver is not None and obs.found and obs.rvec is not None and obs.tvec is not None):
        cv2.drawFrameAxes(frame, perceiver.K, perceiver.dist, obs.rvec, obs.tvec, 3.0)
    # Letterboxing preserves camera geometry (overlays drawn before resizing).
    ratio = min(WIDTH/frame.shape[1], HEIGHT/frame.shape[0])
    small = cv2.resize(frame, (round(frame.shape[1]*ratio), round(frame.shape[0]*ratio)))
    canvas = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    y, x = (HEIGHT-small.shape[0])//2, (WIDTH-small.shape[1])//2
    canvas[y:y+small.shape[0], x:x+small.shape[1]] = small
    cv2.rectangle(canvas, (0, 0), (WIDTH-1, HEIGHT-1), color, 6)
    cv2.rectangle(canvas, (6, 6), (WIDTH-7, 177), (22, 26, 34), -1)
    banner = ('DU LIEU GIA - KHONG PHAI LIVE' if kind == 'SYNTHETIC'
              else 'VIDEO DA GHI - KHONG PHAI LIVE' if kind == 'VIDEO' else 'CAMERA LIVE')
    if getattr(perceiver, 'synthetic_calibration', False) or recorded_kind == 'SYNTHETIC_RENDER':
        banner = 'VIDEO MO PHONG - ARUCO/PNP THAT - KHONG PHAI LIVE'
    put(canvas, banner + (' | REPLAY CSV' if replay else ''), (20, 35), 0.72,
        (80, 80, 255) if kind != 'LIVE' else color, 2)
    mode = 'RAW TAM - CHUA CO P2 / SIGMA KHONG CO' if stub else ('KALMAN ON' if enabled else 'RAW / KALMAN OFF')
    if replay:
        mode = ('RECORDED KALMAN ON' if enabled else 'RECORDED RAW') + f' | ORIGINAL: {recorded_kind}'
    put(canvas, f'{state.status} | {mode}', (20, 68), 0.6, color, 2)
    guidance = state.guidance
    if state.status == 'LOST':
        guidance = 'KHONG THAY MARKER - DUNG LAI'
    elif state.aligned and state.status != 'GOOD':
        guidance = 'TIN HIEU KEM - CHUA XAC NHAN CAN CHINH'
    put(canvas, guidance, (20, 115), 0.95, color, 2)
    values = '   '.join(f'{label} = {number(getattr(state, val))} +- {number(getattr(state, sigma))} {unit}'
                        for label, val, sigma, unit in [('x', 'x_cm', 'sigma_x', 'cm'),
                        ('z', 'z_cm', 'sigma_z', 'cm'), ('yaw', 'yaw_deg', 'sigma_yaw', 'deg')])
    put(canvas, values, (20, 156), 0.65)
    minimap(canvas, state)
    if state.status != 'LOST' and ('SANG PHAI' in guidance or 'SANG TRAI' in guidance):
        direction = 1 if 'SANG PHAI' in guidance else -1
        cv2.arrowedLine(canvas, (640, 540), (640 + direction*110, 540), color, 6, tipLength=0.3)
    if state.status != 'LOST' and ('TIEN ' in guidance or 'LUI ' in guidance):
        end_y = 440 if 'TIEN ' in guidance else 580
        cv2.arrowedLine(canvas, (640, 510), (640, end_y), color, 4, tipLength=0.3)
    if state.aligned and state.status == 'GOOD':
        put(canvas, 'DA CAN CHINH', (480, 580), 0.9, color, 2)
    cv2.rectangle(canvas, (6, 596), (WIDTH-7, HEIGHT-7), (22, 26, 34), -1)
    put(canvas, f'FPS {fps:.1f} | latency p50 {number(latency)} ms'
        + (' (recorded)' if replay else ' (capture -> HUD)'), (20, 625), 0.58)
    put(canvas, 'R: record | F: Kalman | SPACE: freeze | Q: quit', (20, 658), 0.58)
    flags = ('REC ' if recording else '') + ('FROZEN ' if frozen else '')
    put(canvas, flags + notice, (20, 692), 0.55, (90, 180, 255))
    if perceiver is not None and getattr(perceiver, 'approximate', False):
        cv2.rectangle(canvas, (12, 184), (670, 218), (22, 26, 34), -1)
        put(canvas, 'CALIB FOV UOC LUONG - CHUA KIEM CHUNG', (20, 210), 0.62, COLORS['DEGRADED'], 2)
    return canvas


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--source', default='0', help='Camera index or video path')
    parser.add_argument('--calib', default='calib.npz')
    parser.add_argument('--marker-id', type=int, default=7)
    parser.add_argument('--marker-side-cm', type=float, default=6.0)
    parser.add_argument('--fallback', default='video.mp4', help='Backup video on webcam failure')
    parser.add_argument('--replay', help='P3 CSV paired with --source video')
    parser.add_argument('--synthetic', action='store_true', help='Explicit synthetic UI demo, not real evidence')
    parser.add_argument('--loop', action='store_true', help='Repeat video until Q (requires a video source)')
    parser.add_argument('--record', action='store_true', help='Start recording immediately')
    parser.add_argument('--video-out', default='video.mp4')
    parser.add_argument('--log-out', default='log.csv')
    parser.add_argument('--headless', action='store_true', help='No window, for smoke/soak checks')
    parser.add_argument('--max-frames', type=int, help='Stop after N processed frames')
    parser.add_argument('--snapshot', help='Write final 1280x720 HUD to image')
    return parser


def run(args):
    source = int(args.source) if args.source.isdigit() else args.source
    if args.replay and (isinstance(source, int) or args.synthetic):
        raise ValueError('--replay requires --source video.mp4, without --synthetic')
    if args.loop and (args.replay or args.synthetic or isinstance(source, int)):
        raise ValueError('--loop requires a video source without --replay/--synthetic')
    if args.headless and args.max_frames is None and (args.synthetic or isinstance(source, int) or args.loop):
        raise ValueError('Use --max-frames with a headless live/synthetic source')
    if args.max_frames is not None and args.max_frames <= 0:
        raise ValueError('--max-frames must be positive')
    replay = Replay(args.replay) if args.replay else None
    estimator, stub = (None, False) if replay else load_filter()
    synthetic_sequence = load_synthetic() if args.synthetic else None
    perceiver = None
    if not args.synthetic and replay is None:
        from perception import Perceiver
        if not Path(args.calib).is_file():
            raise FileNotFoundError(f'Calibration missing: {args.calib}. Run P1 calibrate.py first, '
                                    'or use --synthetic for a labelled UI demo.')
        perceiver = Perceiver(args.calib, marker_id=args.marker_id,
                              marker_side_cm=args.marker_side_cm)
    capture = Capture(source, args.synthetic)
    recorder = None
    canvas = None
    want_record = args.record
    frozen = False
    count = 0
    cycle_start_count = 0
    latencies = deque(maxlen=300)
    completions = deque(maxlen=120)
    last_packet_at = time.perf_counter()
    notice = ''
    fallback_used = False
    recorded_kind = ''
    enabled = False
    window = 'Charge-Port Alignment Assist / P3'
    try:
        if not args.headless:
            cv2.namedWindow(window, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window, WIDTH, HEIGHT)
        while True:
            packet = None if frozen else capture.read()
            if packet is None and not frozen:
                if capture.done or time.perf_counter() - last_packet_at > 3:
                    if capture.live:
                        capture.close()
                        # Finalize MP4 before it can be used as a backup. Never append
                        # backup frames to the live recording or mix source geometry.
                        if recorder is not None:
                            recorder.close()
                            recorder = None
                        want_record = False
                        if not fallback_used and Path(args.fallback).is_file():
                            print('Webcam unavailable; switching to recorded backup:', args.fallback)
                            capture = Capture(args.fallback)
                            fallback_used = True
                            notice = 'WEBCAM LOI -> VIDEO DU PHONG'
                            last_packet_at = time.perf_counter()
                            # A fresh estimator must not carry old live velocities into video.
                            estimator, stub = load_filter()
                            latencies.clear()
                            completions.clear()
                            continue
                        raise OSError((capture.error or 'Webcam timed out') + '; no backup video available')
                    if capture.error:
                        raise OSError(capture.error)
                    if capture.done:
                        if args.loop:
                            if count == cycle_start_count:
                                raise OSError('Cannot loop an empty video')
                            cycle_start_count = count
                            repeat_source = capture.source
                            capture.close()
                            capture = Capture(repeat_source)
                            reset = getattr(estimator, 'reset', None)
                            if reset is not None:
                                reset()  # Preserve the presenter's F / RAW choice.
                            last_packet_at = time.perf_counter()
                            latencies.clear()
                            completions.clear()
                            notice = 'VIDEO LAP LAI / Q DE THOAT'
                            continue
                        if replay and count != len(replay.rows):
                            raise ValueError('Video ended before all replay CSV rows were consumed')
                        print('End of video.')
                        break
                    raise OSError('Video source timed out')
            if packet is not None:
                last_packet_at = time.perf_counter()
                if replay:
                    obs, state, enabled, recorded_kind = replay.at(packet.index)
                else:
                    obs = (synthetic_observation(packet, synthetic_sequence) if capture.synthetic
                           else perceiver.process(packet.frame, packet.t_capture))
                    state = estimator.update(obs)
                    filtered_at = time.perf_counter()
                    enabled = bool(estimator.filter_enabled)
                    state.latency_ms.update(capture=packet.capture_ms,
                                            detect=(obs.t_detect_done-obs.t_capture)*1000,
                                            filter=(filtered_at-obs.t_detect_done)*1000)
                now = time.perf_counter()
                completions.append(now)
                fps = (len(completions)-1)/(completions[-1]-completions[0]) if len(completions) > 1 else 0
                if replay:
                    latencies.append(state.latency_ms['total'])
                else:
                    latencies.append((now-packet.t_capture)*1000)
                canvas = render(packet, obs, state, perceiver, fps, float(np.median(latencies)),
                                capture.kind, enabled, stub, recorder is not None or want_record,
                                replay=bool(replay), notice=notice, recorded_kind=recorded_kind)
                if not replay:
                    rendered_at = time.perf_counter()
                    state.latency_ms['display'] = (rendered_at-filtered_at)*1000
                    state.latency_ms['total'] = (rendered_at-packet.t_capture)*1000
                    latencies[-1] = state.latency_ms['total']
                    state.latency_ms['p50_ms'] = float(np.median(latencies))
                    state.latency_ms['p95_ms'] = float(np.percentile(latencies, 95))
                    tracker = getattr(estimator, 'latency_tracker', None)
                    if tracker is not None:
                        tracker.record_display_stage(rendered_at)
                if want_record and recorder is None:
                    # Cannot replace or feed back into the active source/fallback.
                    protected = [source] if isinstance(source, str) else []
                    if fallback_used:
                        protected.append(args.fallback)
                    if any(Path(p).resolve() == Path(args.video_out).resolve() for p in protected):
                        raise ValueError('Recording output is also the active input video')
                    try:
                        recorder = Recorder(args.video_out, args.log_out, capture.fps,
                                            (packet.frame.shape[1], packet.frame.shape[0]))
                        print(f'Recording: {args.video_out} + {args.log_out}')
                    except (OSError, ValueError, cv2.error) as exc:
                        if args.headless:
                            raise
                        notice = 'KHONG GHI DUOC: ' + str(exc)
                        print(notice)
                    want_record = False
                if recorder is not None:
                    original_kind = ('SYNTHETIC_RENDER' if getattr(perceiver, 'synthetic_calibration', False)
                                     else capture.kind)
                    recorder.write(packet, obs, state, enabled, recorded_kind if replay else original_kind)
                count += 1
                if args.max_frames and count >= args.max_frames:
                    break
            if not args.headless:
                if canvas is not None:
                    shown = canvas.copy()
                    if frozen:
                        put(shown, 'FROZEN / SPACE TO RESUME', (380, 390), 0.85, COLORS['DEGRADED'], 2)
                    cv2.imshow(window, shown)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord('q'), ord('Q'), 27) or cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                    break
                if key == 32:
                    frozen = not frozen
                    last_packet_at = time.perf_counter()
                    if not frozen and not replay:
                        reset = getattr(estimator, 'reset', None)
                        if reset is not None:
                            reset()
                if key in (ord('f'), ord('F')):
                    if replay:
                        notice = 'REPLAY: GIU NGUYEN KET QUA DA GHI'
                    elif stub:
                        notice = 'CHUA CO P2: KHONG THE BAT KALMAN'
                    else:
                        new_enabled = not estimator.filter_enabled
                        # P2's RAW path freezes its internal motion state. Reinitialize
                        # when returning to Kalman instead of gating against stale pose.
                        reset = getattr(estimator, 'reset', None)
                        if new_enabled and reset is not None:
                            reset()
                        estimator.filter_enabled = new_enabled
                        notice = 'KALMAN ON' if estimator.filter_enabled else 'KALMAN OFF'
                if key in (ord('r'), ord('R')):
                    if recorder is not None:
                        recorder.close()
                        recorder = None
                        # Continue into a new segment; never silently overwrite prior evidence.
                        stamp = time.strftime('%Y%m%d_%H%M%S') + f'_{count}'
                        args.video_out = str(Path(args.video_out).with_name('video_' + stamp + '.mp4'))
                        args.log_out = str(Path(args.log_out).with_name('log_' + stamp + '.csv'))
                        notice = 'DA LUU VIDEO + CSV'
                    else:
                        want_record = not want_record
        if canvas is not None and args.snapshot:
            if not cv2.imwrite(args.snapshot, canvas):
                raise OSError(f'Cannot write snapshot: {args.snapshot}')
        print(f'Processed {count} frames; total latency p50={np.median(latencies) if latencies else 0:.1f} ms, '
              f'p95={np.percentile(latencies, 95) if latencies else 0:.1f} ms'
              + (' (recorded timing)' if replay else ' (software capture-to-HUD only)'))
        return count
    finally:
        capture.close()
        if recorder is not None:
            recorder.close()
        if not args.headless:
            cv2.destroyAllWindows()


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        run(args)
    except (OSError, ValueError, RuntimeError, ImportError, cv2.error) as exc:
        parser.exit(1, f'P3 error: {exc}\n')
    except KeyboardInterrupt:
        parser.exit(130, 'Stopped.\n')


if __name__ == '__main__':
    main()
