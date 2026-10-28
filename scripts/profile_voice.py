"""Prueba real de Piper: WAV, pico RSS del worker y latencia, sin llamadas externas."""

import argparse
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import wave

SAMPLE = (
    'Con diez grados, llevá una campera ligera y pantalón cómodo. '
    'Por la tarde sube la temperatura: podés quitarte una capa y mantener calzado cómodo para tus planes.'
)

WRAPPER = r'''
import ctypes, ctypes.wintypes as w, json, runpy, sys
sys.argv = sys.argv[1:]
try:
    runpy.run_path(sys.argv[0], run_name='__main__')
finally:
    if sys.platform == 'win32':
        class Memory(ctypes.Structure):
            _fields_ = [('cb', w.DWORD), ('faults', w.DWORD)] + [(name, ctypes.c_size_t) for name in (
                'peak', 'rss', 'paged_peak', 'paged', 'nonpaged_peak', 'nonpaged', 'commit', 'commit_peak')]
        memory = Memory()
        memory.cb = ctypes.sizeof(memory)
        kernel = ctypes.WinDLL('kernel32')
        kernel.GetCurrentProcess.restype = w.HANDLE
        psapi = ctypes.WinDLL('psapi')
        psapi.GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.POINTER(Memory), w.DWORD]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(memory), memory.cb):
            raise OSError('No se pudo medir la memoria')
        peak = memory.peak / 1048576
    else:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1048576 if sys.platform == 'darwin' else 1024)
    print('ISA_PROFILE ' + json.dumps({'worker_peak_rss_mib': round(peak, 1)}), file=sys.stderr)
'''


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--text', default=SAMPLE)
    parser.add_argument('--output', type=Path, default=root / 'tmp' / 'isa-piper-female-sample.wav')
    parser.add_argument('--model-dir', type=Path, default=root / 'models' / 'piper-sharvard')
    parser.add_argument('--runs', type=int, default=1)
    args = parser.parse_args()
    if not 1 <= len(args.text.strip()) <= 600:
        parser.error('El texto debe tener entre 1 y 600 caracteres.')
    if not 1 <= args.runs <= 50:
        parser.error('--runs debe estar entre 1 y 50.')
    results = []
    for _ in range(args.runs):
        measurements = profile_once(root, args)
        if measurements is None:
            return 1
        results.append(measurements)
    durations = sorted(row['elapsed_seconds'] for row in results)
    print(json.dumps({'ok': True, 'runs': args.runs,
                      'worker_peak_rss_mib': max(row.get('worker_peak_rss_mib', 0) for row in results),
                      'p50_seconds': durations[math.ceil(len(durations) * .5) - 1],
                      'p95_seconds': durations[math.ceil(len(durations) * .95) - 1],
                      'audio_seconds': results[-1]['audio_seconds'], 'characters': len(args.text),
                      'output': str(args.output)}, ensure_ascii=False))
    return 0


def profile_once(root, args):
    started = time.monotonic()
    try:
        result = subprocess.run(
            [sys.executable, '-X', 'utf8', '-c', WRAPPER,
             str(root / 'api' / 'services' / 'voice_worker.py'), str(args.model_dir)],
            input=args.text.encode('utf-8'), capture_output=True, timeout=45,
        )
    except subprocess.TimeoutExpired:
        print(json.dumps({'ok': False, 'error': 'timeout_45_seconds'}))
        return None
    measurements = next((json.loads(line.removeprefix('ISA_PROFILE '))
                         for line in result.stderr.decode('utf-8', errors='replace').splitlines()
                         if line.startswith('ISA_PROFILE ')), {})
    if result.returncode:
        print(json.dumps({'ok': False, **measurements}))
        return None
    with wave.open(io.BytesIO(result.stdout), 'rb') as audio:
        seconds = audio.getnframes() / audio.getframerate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result.stdout)
    return {**measurements, 'elapsed_seconds': round(time.monotonic() - started, 2),
            'audio_seconds': round(seconds, 2), 'wav_bytes': len(result.stdout)}


if __name__ == '__main__':
    raise SystemExit(main())
