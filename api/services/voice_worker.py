"""Piper worker: fixed female speaker, bounded inference and WAV on stdout."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import wave

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from api.services.voice_chunks import prepare_voice_chunks
from api.services.voice_memory import trace_voice_memory

MODEL_NAME = 'es_ES-sharvard-medium.onnx'
SAMPLE_RATE = 22050
FEMALE_SPEAKER = 1


def main():
    trace_voice_memory('worker_start')
    model_dir = Path(sys.argv[1])
    model = model_dir / MODEL_NAME
    config_path = model_dir / (MODEL_NAME + '.json')
    if not model.is_file() or not config_path.is_file():
        return 1
    text = sys.stdin.buffer.read(2401).decode('utf-8')
    if not 1 <= len(text.strip()) <= 600 or '\x00' in text:
        return 1
    with redirect_stdout(sys.stderr):
        import numpy as np
        import onnxruntime as rt
        from piper import PiperVoice, SynthesisConfig
        from piper.config import PiperConfig
        trace_voice_memory('libraries_loaded')

        config = PiperConfig.from_dict(json.loads(config_path.read_text(encoding='utf-8')))
        if (config.speaker_id_map.get('F') != FEMALE_SPEAKER
                or config.num_speakers != 2 or config.sample_rate != SAMPLE_RATE):
            return 1
        options = rt.SessionOptions()
        options.intra_op_num_threads = options.inter_op_num_threads = 1
        options.execution_mode = rt.ExecutionMode.ORT_SEQUENTIAL
        options.enable_cpu_mem_arena = False
        options.enable_mem_pattern = False
        options.add_session_config_entry('session.disable_prepacking', '1')
        trace_voice_memory('model_loading')
        voice = PiperVoice(session=rt.InferenceSession(
            str(model), sess_options=options, providers=['CPUExecutionProvider']), config=config)
        trace_voice_memory('model_ready')
        trace_voice_memory('phonemizing')
        chunks = prepare_voice_chunks(voice, text)
        if not chunks:
            return 1
        trace_voice_memory('phonemes_ready')

        output = io.BytesIO()
        frames = 0
        previous_chunk = []
        synthesis = SynthesisConfig(speaker_id=FEMALE_SPEAKER)
        with wave.open(output, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            for index, chunk in enumerate(chunks):
                ids = voice.phonemes_to_ids(chunk)
                trace_voice_memory('inference_start', index, tokens=len(ids))
                samples = voice.phoneme_ids_to_audio(ids, synthesis)
                trace_voice_memory('inference_done', index)
                if not len(samples) or not np.isfinite(samples).all():
                    return 1
                pause_ms = 80 if previous_chunk and previous_chunk[-1] in '.!?;:' else 20
                pause_frames = SAMPLE_RATE * pause_ms // 1000 if frames else 0
                frames += pause_frames + len(samples)
                if frames > SAMPLE_RATE * 90:
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
        raise SystemExit(1)
