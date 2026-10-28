"""Worker aislado: WAV por stdout; nunca reproduce sonido en el servidor."""

from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import sys
import wave

# Límites antes de importar NumPy/ONNX: evita pools de CPU por cada consulta.
for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'

# El worker también se ejecuta directamente por ruta desde Django.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from api.services.voice_chunks import split_voice_text


def main():
    model_dir = Path(sys.argv[1])
    model = model_dir / 'kokoro-v1.0.int8.onnx'
    voices = model_dir / 'voices-v1.0.bin'
    if not model.is_file() or not voices.is_file():
        return 1
    text = sys.stdin.buffer.read(2401).decode('utf-8')
    if not 1 <= len(text.strip()) <= 600 or '\x00' in text:
        return 1
    with redirect_stdout(sys.stderr):
        import numpy as np
        import onnxruntime as rt
        from kokoro_onnx import Kokoro

        options = rt.SessionOptions()
        options.intra_op_num_threads = options.inter_op_num_threads = 1
        options.execution_mode = rt.ExecutionMode.ORT_SEQUENTIAL
        options.enable_cpu_mem_arena = False
        options.enable_mem_pattern = False
        session = rt.InferenceSession(str(model), sess_options=options,
                                      providers=['CPUExecutionProvider'])
        engine = Kokoro.from_session(session, str(voices))
        output = io.BytesIO()
        frames = 0
        with wave.open(output, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            for chunk in split_voice_text(text):
                samples, sample_rate = engine.create(chunk, voice='ef_dora', speed=.95, lang='es')
                if sample_rate != 24000 or not len(samples) or not np.isfinite(samples).all():
                    return 1
                pause_frames = 1920 if frames else 0  # 80 ms entre fragmentos.
                frames += pause_frames + len(samples)
                if frames > 24000 * 90:
                    return 1
                if pause_frames:
                    wav.writeframesraw(b'\x00\x00' * pause_frames)
                pcm = (np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes()
                wav.writeframesraw(pcm)
                del samples, pcm
    sys.stdout.buffer.write(output.getvalue())
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        # El proceso padre solo recibe el resultado, sin texto ni rutas privadas.
        raise SystemExit(1)
