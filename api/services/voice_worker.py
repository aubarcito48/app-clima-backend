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
from api.services.voice_chunks import prepare_voice_chunks
from api.services.voice_memory import trace_voice_memory


def main():
    trace_voice_memory('worker_start')
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
        from kokoro_onnx.tokenizer import Tokenizer
        trace_voice_memory('libraries_loaded')

        # Convertir una sola vez, antes de sumar los pesos de ONNX a la memoria.
        trace_voice_memory('phonemizing')
        tokenizer = Tokenizer()
        chunks = prepare_voice_chunks(tokenizer, text)
        if not chunks:
            return 1
        trace_voice_memory('phonemes_ready')

        options = rt.SessionOptions()
        options.intra_op_num_threads = options.inter_op_num_threads = 1
        options.execution_mode = rt.ExecutionMode.ORT_SEQUENTIAL
        options.enable_cpu_mem_arena = False
        options.enable_mem_pattern = False
        options.add_session_config_entry('session.disable_prepacking', '1')
        trace_voice_memory('model_loading')
        session = rt.InferenceSession(str(model), sess_options=options,
                                      providers=['CPUExecutionProvider'])
        engine = Kokoro.from_session(session, str(voices))
        trace_voice_memory('model_ready')
        output = io.BytesIO()
        frames = 0
        previous_chunk = ''
        with wave.open(output, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            for index, chunk in enumerate(chunks):
                trace_voice_memory('chunk_start', index)
                trace_voice_memory('inference_start', index, tokens=len(tokenizer.tokenize(chunk)))
                samples, sample_rate = engine.create(chunk, voice='ef_dora', speed=.95,
                                                     lang='es', is_phonemes=True)
                trace_voice_memory('inference_done', index)
                if sample_rate != 24000 or not len(samples) or not np.isfinite(samples).all():
                    return 1
                # Pausa mínima entre palabras; 80 ms al terminar una frase.
                pause_frames = (1920 if previous_chunk.endswith(('.', '!', '?', ';', ':')) else 480) if frames else 0
                frames += pause_frames + len(samples)
                if frames > 24000 * 90:
                    return 1
                if pause_frames:
                    wav.writeframesraw(b'\x00\x00' * pause_frames)
                pcm = (np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes()
                wav.writeframesraw(pcm)
                del samples, pcm
                trace_voice_memory('chunk_done', index)
                previous_chunk = chunk
    trace_voice_memory('complete')
    sys.stdout.buffer.write(output.getvalue())
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        # El proceso padre solo recibe el resultado, sin texto ni rutas privadas.
        raise SystemExit(1)
