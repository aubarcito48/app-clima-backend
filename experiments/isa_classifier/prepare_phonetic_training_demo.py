"""Compare trained hybrid vs V7/raw phonetics on the exact existing demo PCM."""
import argparse
import base64
import json
from pathlib import Path
import temporal
from classifier import read_recording, timeline
from prepare_demo import replace_cues
from phonetic_features import hybrid_features


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', type=Path, required=True)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    data = json.loads((args.demo / 'demo.json').read_text(encoding='utf8'))
    for case in data['cases']:
        language = case['language']
        audio = (args.demo / f'demo-{language}.wav').read_bytes()
        target = args.output / f'demo-{language}.wav'
        target.write_bytes(audio)
        samples, rate, _, fingerprint = read_recording(target)
        if read_recording(args.demo / f'raw-{language}.wav')[3] != fingerprint or fingerprint != case['sha256_pcm']:
            raise ValueError('Demo PCM differs from phonetic synthesis source')
        info = json.loads((args.demo / f'phones-{language}.json').read_text(encoding='utf8'))
        info['sha256_pcm'] = fingerprint
        features, _, hop = hybrid_features(samples, rate, info)
        model = json.loads((args.models / f'hybrid-{language}.json').read_text())
        cues = timeline(temporal.predict(model, features), hop, case['duration'])
        result = replace_cues(audio, cues)
        (args.output / f'demo-{language}-v9.wav').write_bytes(result)
        if read_recording(args.output / f'demo-{language}-v9.wav')[3] != fingerprint:
            raise ValueError('Hybrid comparison changed PCM')
        case['versions'] = {'v9': {'audio': 'data:audio/wav;base64,' + base64.b64encode(result).decode(), 'cues': cues},
                            **case['versions']}
    data['purpose'] = 'Trained phonetic/acoustic/timing hybrid; local visual evaluation only'
    (args.output / 'demo.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')


if __name__ == '__main__':
    main()
