"""Generate new local speech for an A/B demo, not training or model selection."""

import argparse
import base64
import json
import os
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import temporal
from classifier import audio_features, read_recording, timeline
from narration import app_performance
from rhythm_features import features_for_model

TEXTS = {
    'es': 'Esta tarde puede llover. Llevá una campera liviana y cerrá las ventanas antes de salir.',
    'en': 'It may rain this afternoon. Bring a light jacket and close the windows before you leave.',
}


def replace_cues(audio, cues):
    chunks, offset = [], 12
    while offset + 8 <= len(audio):
        size = struct.unpack_from('<I', audio, offset + 4)[0]
        end = offset + 8 + size + size % 2
        if end > len(audio):
            raise ValueError('Truncated WAV')
        if audio[offset:offset + 4] != b'isav':
            chunks.append(audio[offset:end])
        offset = end
    if offset != len(audio):
        raise ValueError('Invalid WAV padding')
    payload = json.dumps(cues, separators=(',', ':')).encode('ascii')
    chunks.append(b'isav' + len(payload).to_bytes(4, 'little') + payload + b'\0' * (len(payload) % 2))
    data = b'WAVE' + b''.join(chunks)
    return b'RIFF' + len(data).to_bytes(4, 'little') + data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--versions', nargs='+', choices=('v3', 'v4', 'v5', 'v6', 'v7'), default=['v3', 'v4'])
    parser.add_argument('--reuse-demo', type=Path, help='Reuse identical spoken samples from an earlier demo')
    args = parser.parse_args()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    import django
    django.setup()
    from django.conf import settings
    from api.services.voice import synthesize
    from api.services.isa_local_director import direct_locally
    from api.services.lip_sync import read_mouth_cues
    settings.ISA_LIP_SYNC = 'rhubarb'
    args.output.mkdir(parents=True, exist_ok=True)
    cases = []
    for language, advice in TEXTS.items():
        text, performance = app_performance(advice, language, direct_locally)
        wav = args.output / f'demo-{language}.wav'
        if wav.exists() and (args.output / 'demo.json').exists():
            existing = json.loads((args.output / 'demo.json').read_text(encoding='utf8'))
            if next(c for c in existing['cases'] if c['language'] == language)['text'] != text:
                parser.error('Use a new demo folder for the greeting/advice/farewell profile')
        if not wav.exists() and args.reuse_demo:
            previous = json.loads((args.reuse_demo / 'demo.json').read_text(encoding='utf8'))
            sample = next(c for c in previous['cases'] if c['language'] == language)
            source = args.reuse_demo / wav.name
            if sample['text'] != text or read_recording(source)[3] != sample['sha256_pcm']:
                raise ValueError('Previous demo identity changed')
            wav.write_bytes(source.read_bytes())
        if not wav.exists():
            wav.write_bytes(synthesize(text, language=language, segments=performance))
        samples, rate, reference, fingerprint = read_recording(wav)
        duration = len(samples) / rate
        read_mouth_cues({'mouthCues': reference}, duration)
        versions = {}
        for version in args.versions:
            model = json.loads((ROOT / f'tmp/isa-own-classifier/{version}/audio-{language}.json').read_text())
            features, _, hop = features_for_model(model, samples, rate)
            cues = timeline(temporal.predict(model, features), hop, duration)
            read_mouth_cues({'mouthCues': cues}, duration)
            result = replace_cues(wav.read_bytes(), cues)
            target = args.output / f'demo-{language}-{version}.wav'
            target.write_bytes(result)
            if read_recording(target)[3] != fingerprint:
                raise ValueError('The A/B comparison must preserve identical PCM')
            versions[version] = {'audio': 'data:audio/wav;base64,' + base64.b64encode(result).decode(),
                                 'cues': cues}
        cases.append({'language': language, 'text': text, 'advice': advice, 'narration_profile': 'app-greeting-v1',
                      'duration': duration, 'sha256_pcm': fingerprint,
                      'audio': 'data:audio/wav;base64,' + base64.b64encode(wav.read_bytes()).decode(),
                      'reference': reference, 'versions': versions})
    (args.output / 'demo.json').write_text(json.dumps({'cases': cases,
        'purpose': 'visual review only; never included in training'}, ensure_ascii=False), encoding='utf8')
    print(json.dumps({'output': str(args.output / 'demo.json'),
                       'durations': {c['language']: c['duration'] for c in cases}}))


if __name__ == '__main__':
    main()
