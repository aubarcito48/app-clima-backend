"""Automatic sentence pacing, fresh synthesis alignments and frozen hybrid inference."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
from probe_phonetic import ROOT, synthesize_case, load_aligned_voice
from automatic_voice_rate import rate_plan
from classifier import read_recording, timeline
from phonetic_features import hybrid_features
import temporal
from analyze_timing import analyze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--language', choices=('es', 'en'))
    args = parser.parse_args()
    data = json.loads((args.source / 'timing.json').read_text(encoding='utf8'))
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.language:
        for language in ('es', 'en'):
            subprocess.run([sys.executable, '-X', 'utf8', __file__, '--source', str(args.source),
                            '--output', str(args.output), '--language', language], check=True, timeout=90)
        cases = [json.loads((args.output / f'case-{lang}.json').read_text(encoding='utf8')) for lang in ('es', 'en')]
        (args.output / 'comparison.json').write_text(json.dumps({'cases': cases,
            'warning': 'Local two-pass heuristic; targets are experimental, not learned optimal rates. Fresh audio has synthesis variability.'}, ensure_ascii=False), encoding='utf8')
        return
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    import django
    django.setup()
    language = args.language
    sample = next(c for c in data['cases'] if c['language'] == language)
    model = json.loads((ROOT / f'tmp/isa-own-classifier/hybrid-phonetic-v1/hybrid-{language}.json').read_text())
    def render(name, factors=None):
        import onnxruntime as rt
        folder = args.output / language / name
        if (folder / f'raw-{language}.wav').exists():
            raise ValueError('Use a new output folder for another synthesis')
        # Restart the session's random sequence for a more controlled A/B.
        load_aligned_voice.cache_clear()
        rt.set_seed(20261116)
        synthesize_case(language, folder, sample['advice'], speed_factors=factors)
        raw = folder / f'raw-{language}.wav'
        samples, rate, _, fingerprint = read_recording(raw)
        info = json.loads((folder / f'phones-{language}.json').read_text(encoding='utf8'))
        info['sha256_pcm'] = fingerprint
        features, _, hop = hybrid_features(samples, rate, info)
        cues = timeline(temporal.predict(model, features), hop, len(samples) / rate)
        result = {k: sample[k] for k in ('language', 'text', 'advice', 'narration_profile')}
        result.update(audio='data:audio/wav;base64,' + base64.b64encode(raw.read_bytes()).decode(),
                      sha256_pcm=fingerprint, duration=len(samples) / rate, phonemes=info['phonemes'], cues=cues)
        result['timing'] = analyze(raw, result)
        return result
    baseline = render('baseline')
    factors, decisions = rate_plan(baseline['timing'])
    adapted = render('automatic', factors)
    (args.output / f'case-{language}.json').write_text(json.dumps({'language': language,
        'text': sample['text'], 'decisions': decisions, 'baseline': baseline, 'automatic': adapted}, ensure_ascii=False), encoding='utf8')
    print(json.dumps({'language': language, 'factors': factors, 'before_seconds': baseline['duration'],
                      'after_seconds': adapted['duration']}), flush=True)


if __name__ == '__main__':
    main()
