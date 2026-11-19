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

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from api.services.assistant.voice.voice_chunks import prepare_voice_chunks
from api.services.assistant.voice.voice_memory import trace_voice_memory
from api.services.assistant.direction.isa_performance import append_timeline
from api.services.assistant.direction.isa_performance import read_segments

MODEL_NAME = 'es_ES-sharvard-medium.onnx'
SAMPLE_RATE = 22050
VOICES = {
    'es': (MODEL_NAME, 1, 2),
    'en': ('en_GB-cori-medium.onnx', 0, 1),
}


def main():
    trace_voice_memory('worker_start')
    model_dir = Path(sys.argv[1])
    language = sys.argv[2] if len(sys.argv) > 2 else 'es'
    if language not in VOICES:
        return 1
    model_name, speaker, speakers = VOICES[language]
    model = model_dir / model_name
    config_path = model_dir / (model_name + '.json')
    if not model.is_file() or not config_path.is_file():
        return 1
    performance = '--performance' in sys.argv[3:]
    own_lips = '--own-lip-sync' in sys.argv[3:]
    if own_lips:
        model = model_dir / (model_name + '.aligned.onnx')
        if not model.is_file():
            return 1
    phones, mouth_cues = [], []
    raw = sys.stdin.buffer.read(8193 if performance else 2401).decode('utf-8')
    payload = json.loads(raw) if performance else None
    text = payload['texto'] if performance else raw
    if not 1 <= len(text.strip()) <= 600 or '\x00' in text:
        return 1
    segments = read_segments(payload['segmentos'], text, max_segments=6) if performance else [
        {'text': text, 'gesture': 'isa-awake', 'speed': 1, 'energy': 1, 'pause_ms': 0},
    ]
    timeline = []
    with redirect_stdout(sys.stderr):
        import numpy as np
        import onnxruntime as rt
        from piper import PiperVoice, SynthesisConfig
        from piper.config import PiperConfig
        trace_voice_memory('libraries_loaded')

        config = PiperConfig.from_dict(json.loads(config_path.read_text(encoding='utf-8')))
        if (config.num_speakers != speakers or config.sample_rate != SAMPLE_RATE
                or language == 'es' and config.speaker_id_map.get('F') != speaker):
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
        output = io.BytesIO()
        frames = 0
        with wave.open(output, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            for segment in segments:
                chunks = prepare_voice_chunks(voice, segment['text'], language)
                if not chunks:
                    return 1
                trace_voice_memory('phonemes_ready')
                start = frames / SAMPLE_RATE
                previous_chunk = []
                synthesis = SynthesisConfig(speaker_id=speaker,
                    length_scale=config.length_scale * (1.08 if language == 'en' else 1) / segment['speed'])
                for index, chunk in enumerate(chunks):
                    ids = voice.phonemes_to_ids(chunk)
                    trace_voice_memory('inference_start', index, tokens=len(ids))
                    if own_lips:
                        from api.services.assistant.alignment.isa_ml.phonetic_alignment import grouped_durations
                        from api.services.assistant.alignment.isa_ml.phonetic_alignment import expand_diphthongs
                        from api.services.assistant.alignment.isa_ml.phonetic_alignment import phone_shapes
                        from api.services.assistant.alignment.isa_ml.phonetic_alignment import append_cue
                        samples, counts = voice.phoneme_ids_to_audio(ids, synthesis, include_alignments=True)
                        rows = expand_diphthongs(grouped_durations(chunk, config.phoneme_id_map, ids, counts, len(samples)))
                    else:
                        samples = voice.phoneme_ids_to_audio(ids, synthesis)
                    trace_voice_memory('inference_done', index)
                    if not len(samples) or not np.isfinite(samples).all():
                        return 1
                    pause_ms = 80 if previous_chunk and previous_chunk[-1] in '.!?;:' else 20
                    pause_frames = SAMPLE_RATE * pause_ms // 1000 if previous_chunk else 0
                    if frames + pause_frames + len(samples) > SAMPLE_RATE * 90:
                        return 1
                    if pause_frames:
                        wav.writeframesraw(b'\x00\x00' * pause_frames)
                        if own_lips:
                            append_cue(mouth_cues, frames / SAMPLE_RATE, (frames + pause_frames) / SAMPLE_RATE, 'X')
                    frames += pause_frames
                    if own_lips:
                        cursor = frames
                        for row, shape in zip(rows, phone_shapes(rows, language)):
                            end = cursor + row['samples']
                            phones.append({**row, 'start': cursor / SAMPLE_RATE, 'end': end / SAMPLE_RATE, 'shape': shape})
                            append_cue(mouth_cues, cursor / SAMPLE_RATE, end / SAMPLE_RATE, shape)
                            cursor = end
                    pcm = (np.clip(samples * segment['energy'], -1, 1) * 32767).astype('<i2').tobytes()
                    wav.writeframesraw(pcm)
                    frames += len(samples)
                    del samples, pcm
                    trace_voice_memory('chunk_done', index)
                    previous_chunk = chunk
                speech_end = frames / SAMPLE_RATE
                pause_frames = SAMPLE_RATE * segment['pause_ms'] // 1000
                frames += pause_frames
                if frames > SAMPLE_RATE * 90:
                    return 1
                if pause_frames:
                    wav.writeframesraw(b'\x00\x00' * pause_frames)
                    if own_lips:
                        append_cue(mouth_cues, speech_end, frames / SAMPLE_RATE, 'X')
                timeline.append({'from': start, 'speech_end': speech_end,
                                 'until': frames / SAMPLE_RATE, 'gesture': segment['gesture']})
    trace_voice_memory('complete')
    audio = output.getvalue()
    audio = append_timeline(audio, timeline) if performance else audio
    if own_lips:
        from api.services.assistant.alignment.own_lip_sync import attach_alignment
        if phones[-1]['end'] < frames / SAMPLE_RATE:
            phones.append({'phoneme': '.', 'start': phones[-1]['end'], 'end': frames / SAMPLE_RATE})
        audio = attach_alignment(audio, {'phonemes': phones, 'cues': mouth_cues})
    sys.stdout.buffer.write(audio)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(1)
