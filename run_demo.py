"""P1 bootstrap: one command to start the integrated demo on this machine.

python run_demo.py                         # webcam, measured K or labelled FOV fallback
python run_demo.py --synthetic             # camera-free demo, visibly labelled
python run_demo.py --check                 # P1/P2 and full integration checks
All other options are passed to main.py, e.g. --headless --max-frames 60.
"""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def main():
    options = sys.argv[1:]
    if '--check' in options:
        if options != ['--check']:
            print('Use --check alone. For demo options: python run_demo.py --help', file=sys.stderr)
            return 2
        for command in [('test_perception.py', '--self-test'), ('test_filter.py',),
                        ('test_integration.py',)]:
            result = subprocess.run([sys.executable, *command], cwd=ROOT)
            if result.returncode:
                return result.returncode
        print('PASS: P1, P2, P3 record/replay and P4 evaluation pipeline.', flush=True)
        print('Physical calibration/ruler validation is a separate check.', flush=True)
        return 0

    # Let main.py own argument validation; only supply a missing calibration.
    needs_calib = not any(arg in ('--synthetic', '--replay', '--help', '-h') or
                          arg.startswith('--replay=') for arg in options)
    explicit_calib = any(arg == '--calib' or arg.startswith('--calib=') for arg in options)
    if needs_calib and not explicit_calib:
        measured = ROOT / 'calib.npz'
        if measured.is_file():
            options += ['--calib', str(measured)]
        else:
            from calibrate import approximate_calibration
            fallback = ROOT / 'calib_approx.npz'
            if not fallback.is_file():
                approximate_calibration(68, (1280, 720), fallback)
            print('FOV 68 deg is an ASSUMPTION. Starting with approximate calibration; '
                  'cm accuracy has NOT been measured. Run calibrate.py for measured K.', flush=True)
            options += ['--calib', str(fallback)]
    return subprocess.run([sys.executable, str(ROOT / 'main.py'), *options], cwd=ROOT).returncode


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
