"""Predict from PCM alone with an already trained local JSON model."""

import argparse
import json
from pathlib import Path

from classifier import audio_features, classify, read_recording, smooth, timeline
import temporal
from rhythm_features import features_for_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--wav', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    model = json.loads(args.model.read_text(encoding='utf8'))
    if model.get('modality') != 'audio' or model.get('language') not in {'es', 'en'}:
        parser.error('Use an audio model trained for es or en')
    samples, rate, _, _ = read_recording(args.wav)
    features, _, hop = features_for_model(model, samples, rate)
    if model['version'] in (temporal.VERSION, temporal.NONLINEAR_VERSION):
        predicted = temporal.predict(model, features)
    else:
        predicted, _ = classify(model, features)
        predicted = smooth(predicted)
    cues = timeline(predicted, hop, len(samples) / rate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'engine': model['version'],
        'language': model['language'], 'experimental': True, 'mouthCues': cues}, indent=2), encoding='utf8')
    print(json.dumps({'output': str(args.output), 'cues': len(cues)}))


if __name__ == '__main__':
    main()
