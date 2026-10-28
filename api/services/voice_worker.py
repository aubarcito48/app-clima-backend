"""Worker aislado: WAV por stdout; nunca reproduce sonido en el servidor."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import wave


def main():
    model_dir = Path(sys.argv[1])
    model = model_dir / 'kokoro-v1.0.onnx'
    voices = model_dir / 'voices-v1.0.bin'
    if not model.is_file() or not voices.is_file():
        return 1
    text = sys.stdin.buffer.read(2401).decode('utf-8')
    if not 1 <= len(text.strip()) <= 600 or '\x00' in text:
        return 1
    with redirect_stdout(sys.stderr):
        import numpy as np
        from kokoro_onnx import Kokoro

        engine = Kokoro(str(model), str(voices))
        samples, sample_rate = engine.create(text, voice='ef_dora', speed=.95, lang='es')
        if sample_rate != 24000 or not 0 < len(samples) <= sample_rate * 90 or not np.isfinite(samples).all():
            return 1
        pcm = (np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes()
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    sys.stdout.buffer.write(output.getvalue())
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        # El proceso padre solo recibe el resultado, sin texto ni rutas privadas.
        raise SystemExit(1)
