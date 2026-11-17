"""Create one isolated Piper-phoneme synthesis per language, preserving voices."""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import wave
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from phonetic_alignment import grouped_durations, phone_shapes, append_cue, expand_diphthongs
from narration import app_performance
from prepare_demo import TEXTS, replace_cues


@lru_cache(maxsize=1)
def load_aligned_voice(model):
    import onnx
    import onnxruntime as rt
    from piper import PiperVoice
    from piper.config import PiperConfig
    from piper.patch_voice_with_alignment import add_alignment_output
    config = PiperConfig.from_dict(json.loads(Path(str(model) + '.json').read_text(encoding='utf8')))
    graph = onnx.load(str(model))
    add_alignment_output(graph)  # In-memory graph only. Original model stays intact.
    options = rt.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    options.execution_mode = rt.ExecutionMode.ORT_SEQUENTIAL
    options.enable_cpu_mem_arena = options.enable_mem_pattern = False
    options.add_session_config_entry('session.disable_prepacking', '1')
    voice = PiperVoice(session=rt.InferenceSession(graph.SerializeToString(), sess_options=options,
                                                 providers=['CPUExecutionProvider']), config=config)
    del graph
    return voice, config


def synthesize_case(language, folder, advice=None, speed_factors=None):
    import numpy as np
    from piper import SynthesisConfig
    from django.conf import settings
    from api.services.voice_chunks import prepare_voice_chunks
    from api.services.voice_worker import VOICES
    from api.services.isa_local_director import direct_locally
    from api.services.isa_performance import append_timeline
    name, speaker, _ = VOICES[language]
    model = Path(settings.ISA_MODEL_DIR) / name
    def fingerprint():
        with model.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    before = fingerprint()
    voice, config = load_aligned_voice(model)
    text, segments = app_performance(advice if advice is not None else TEXTS[language], language, direct_locally)
    if speed_factors is not None:
        if (len(speed_factors) != len(segments) or speed_factors[0] != 1 or speed_factors[-1] != 1
                or any(not isinstance(v, (int, float)) or isinstance(v, bool) or not np.isfinite(v)
                       or not .85 <= v <= 1 for v in speed_factors)):
            raise ValueError('Invalid bounded automatic voice rates')
        segments = [{**s, 'speed': s['speed'] * factor} for s, factor in zip(segments, speed_factors)]
    cues, phones, performance, frames = [], [], [], 0
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(config.sample_rate)
        def pause(size):
            nonlocal frames
            if size:
                wav.writeframesraw(b'\0\0' * size)
                append_cue(cues, frames / config.sample_rate, (frames + size) / config.sample_rate, 'X')
                frames += size
        for segment in segments:
            start, previous = frames / config.sample_rate, []
            syn = SynthesisConfig(speaker_id=speaker,
                length_scale=config.length_scale * (1.08 if language == 'en' else 1) / segment['speed'])
            for chunk in prepare_voice_chunks(voice, segment['text'], language):
                if previous:
                    pause(config.sample_rate * (80 if previous[-1] in '.!?;:' else 20) // 1000)
                ids = voice.phonemes_to_ids(chunk)
                audio, counts = voice.phoneme_ids_to_audio(ids, syn, include_alignments=True)
                if counts is None or not len(audio) or not np.isfinite(audio).all():
                    raise ValueError('Missing alignments or invalid audio')
                rows = expand_diphthongs(grouped_durations(chunk, config.phoneme_id_map, ids, counts, len(audio)))
                shapes = phone_shapes(rows, language)
                cursor = frames
                for row, shape in zip(rows, shapes):
                    end = cursor + row['samples']
                    phones.append({**row, 'start': cursor / config.sample_rate, 'end': end / config.sample_rate,
                                   'shape': shape, 'segment': len(performance)})
                    append_cue(cues, cursor / config.sample_rate, end / config.sample_rate, shape)
                    cursor = end
                wav.writeframesraw((np.clip(audio * segment['energy'], -1, 1) * 32767).astype('<i2').tobytes())
                frames += len(audio)
                previous = chunk
            speech_end = frames / config.sample_rate
            pause(config.sample_rate * segment['pause_ms'] // 1000)
            performance.append({'from': start, 'speech_end': speech_end, 'until': frames / config.sample_rate,
                                'gesture': segment['gesture']})
    if fingerprint() != before:
        raise ValueError('Source voice changed')
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f'raw-{language}.wav').write_bytes(append_timeline(output.getvalue(), performance))
    (folder / f'phones-{language}.json').write_text(json.dumps({'language': language, 'text': text,
        'voice_sha256': before, 'voice_unchanged': True, 'phonemes': phones, 'cues': cues,
        'speed_factors': speed_factors,
        'alignment_source': 'Piper internal duration prediction; not human-verified'}, ensure_ascii=False), encoding='utf8')
    print(json.dumps({'language': language, 'seconds': frames / config.sample_rate,
                      'phones': len(phones), 'unknown_symbols': 0}), flush=True)


def build_demo(folder):
    import temporal
    from classifier import read_recording, timeline
    from rhythm_features import features_for_model
    from django.conf import settings
    from api.services.lip_sync import add_lip_sync, read_mouth_cues
    cases = []
    for language in ('es', 'en'):
        info = json.loads((folder / f'phones-{language}.json').read_text(encoding='utf8'))
        audio = add_lip_sync((folder / f'raw-{language}.wav').read_bytes(), settings.ISA_RHUBARB_PATH, timeout=45)
        wav = folder / f'demo-{language}.wav'
        wav.write_bytes(audio)
        samples, rate, reference, fingerprint = read_recording(wav)
        duration = len(samples) / rate
        read_mouth_cues({'mouthCues': reference}, duration)
        model = json.loads((ROOT / f'tmp/isa-own-classifier/v7/audio-{language}.json').read_text())
        features, _, hop = features_for_model(model, samples, rate)
        versions = {}
        for version, cues in [('v8', info['cues']), ('v7', timeline(temporal.predict(model, features), hop, duration))]:
            read_mouth_cues({'mouthCues': cues}, duration)
            result = replace_cues(audio, cues)
            target = folder / f'demo-{language}-{version}.wav'
            target.write_bytes(result)
            if read_recording(target)[3] != fingerprint:
                raise ValueError('Comparison PCM changed')
            versions[version] = {'audio': 'data:audio/wav;base64,' + base64.b64encode(result).decode(), 'cues': cues}
        cases.append({'language': language, 'text': info['text'], 'advice': TEXTS[language],
            'phonemes': info['phonemes'],
            'narration_profile': 'app-greeting-v1', 'duration': duration, 'sha256_pcm': fingerprint,
            'audio': 'data:audio/wav;base64,' + base64.b64encode(audio).decode(),
            'reference': reference, 'versions': versions})
    (folder / 'demo.json').write_text(json.dumps({'cases': cases,
        'purpose': 'Piper phonetic experiment, no retraining; visual review only'}, ensure_ascii=False), encoding='utf8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--language', choices=('es', 'en'))
    args = parser.parse_args()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    import django
    django.setup()
    if args.language:
        synthesize_case(args.language, args.output)
    else:
        for language in ('es', 'en'):
            subprocess.run([sys.executable, '-X', 'utf8', __file__, '--output', str(args.output),
                            '--language', language], check=True, timeout=90)
        build_demo(args.output)


if __name__ == '__main__':
    main()
