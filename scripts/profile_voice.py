"""Prueba real de Dora: WAV y pico RSS del worker, sin Django ni llamadas externas."""

import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import wave

SAMPLE = (
    'Hoy en Córdoba hace diez grados y la sensación térmica es de nueve grados. '
    'El cielo está despejado, con viento suave y bastante humedad. Para salir por '
    'la mañana te recomiendo una campera ligera, una camiseta de manga larga y un '
    'pantalón cómodo. Al mediodía la temperatura va a subir, así que podés quitarte '
    'una capa. No hay lluvia prevista para las próximas horas y no hace falta llevar paraguas.'
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
    parser.add_argument('--output', type=Path, default=root / 'tmp' / 'isa-int8-sample.wav')
    parser.add_argument('--model-dir', type=Path, default=root / 'models' / 'kokoro-v1.0')
    args = parser.parse_args()
    if not 1 <= len(args.text.strip()) <= 600:
        parser.error('El texto debe tener entre 1 y 600 caracteres.')
    started = time.monotonic()
    try:
        result = subprocess.run(
            [sys.executable, '-X', 'utf8', '-c', WRAPPER,
             str(root / 'api' / 'services' / 'voice_worker.py'), str(args.model_dir)],
            input=args.text.encode('utf-8'), capture_output=True, timeout=45,
        )
    except subprocess.TimeoutExpired:
        print(json.dumps({'ok': False, 'error': 'timeout_45_seconds'}))
        return 1
    measurements = next((json.loads(line.removeprefix('ISA_PROFILE '))
                         for line in result.stderr.decode('utf-8', errors='replace').splitlines()
                         if line.startswith('ISA_PROFILE ')), {})
    if result.returncode:
        print(json.dumps({'ok': False, **measurements}))
        return 1
    with wave.open(io.BytesIO(result.stdout), 'rb') as audio:
        seconds = audio.getnframes() / audio.getframerate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result.stdout)
    print(json.dumps({'ok': True, **measurements, 'elapsed_seconds': round(time.monotonic() - started, 2),
                      'audio_seconds': round(seconds, 2), 'wav_bytes': len(result.stdout),
                      'characters': len(args.text), 'output': str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
