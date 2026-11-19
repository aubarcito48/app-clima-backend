"""Synthesize the fixed local corpus; no calls to AI or weather APIs."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from narration import app_performance, advice_spans

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def validate_plan(plan):
    rows = plan['recordings']
    ids, texts = set(), set()
    owners = {}
    for row in rows:
        key = (row['language'], ' '.join(row['text'].casefold().split()))
        paired = plan.get('augmentation_profile') == 'paired-rate-v1'
        previous = owners.get(key)
        allowed_pair = (paired and previous is not None and row.get('group_id')
                        and row['group_id'] == previous.get('group_id') and row['split'] == previous['split']
                        and {row.get('variant'), previous.get('variant')} == {'baseline', 'automatic'})
        if (row['language'] not in {'es', 'en'} or row['split'] not in {'train', 'dev', 'test'}
                or not row['id'].replace('-', '').isalnum() or row['id'] in ids or (key in texts and not allowed_pair)
                or not 1 <= len(row['text']) <= 280):
            raise ValueError('Invalid or duplicate corpus item')
        ids.add(row['id'])
        texts.add(key)
        if previous is None:
            owners[key] = row
        elif allowed_pair:
            owners[key] = {**previous, 'variant': 'pair-complete'}
    for language in ('es', 'en'):
        for split in ('train', 'dev', 'test'):
            if not any(r['language'] == language and r['split'] == split for r in rows):
                raise ValueError('Every language needs train, dev and test recordings')
    return rows


def replace_manifest(temporary, target):
    # Windows indexers may briefly hold the previous manifest open. Retain the
    # atomic rename and retry only that transient failure, with a bounded delay.
    for attempt in range(6):
        try:
            temporary.replace(target)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(.1 * (attempt + 1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=Path(__file__).with_name('corpus_plan.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan_bytes = args.plan.read_bytes()
    plan = json.loads(plan_bytes)
    rows = validate_plan(plan)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    import django
    django.setup()
    from django.conf import settings
    from api.services.assistant.voice.voice import synthesize
    from api.services.assistant.direction.isa_local_director import direct_locally
    from classifier import labels_at, read_recording
    if not Path(settings.ISA_RHUBARB_PATH).is_file():
        parser.error('A local Rhubarb binary is needed to bootstrap weak labels')
    settings.ISA_LIP_SYNC = 'rhubarb'  # This CLI process only; no env/config changes.
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {'version': 1, 'reference': 'weak-rhubarb', 'narration_profile': plan.get('narration_profile', 'legacy-plain'),
                'plan_sha256': hashlib.sha256(plan_bytes).hexdigest(), 'recordings': []}
    target = args.output / 'corpus.json'
    if target.exists():
        old = json.loads(target.read_text(encoding='utf8'))
        if old['plan_sha256'] != manifest['plan_sha256']:
            parser.error('Use a new output directory for a changed corpus plan')
    else:
        old = {'recordings': []}
    for row in rows:
        wav = args.output / (row['id'] + '.wav')
        previous = next((r for r in old['recordings'] if r['id'] == row['id']), None)
        started = time.monotonic()
        if plan.get('narration_profile') == 'app-greeting-v1':
            spoken, performance = app_performance(row['advice'], row['language'], direct_locally)
            if spoken != row['text']:
                raise ValueError('The corpus narration differs from the app greeting/advice/farewell')
        else:
            performance = direct_locally(row['text'], language=row['language'])
        if not wav.exists():
            audio = synthesize(row['text'], language=row['language'],
                               segments=performance)
            wav.write_bytes(audio)
        samples, rate, cues, fingerprint = read_recording(wav)
        labels_at(cues, [], len(samples) / rate)
        if previous and previous['sha256_pcm'] != fingerprint:
            parser.error('Existing corpus PCM changed; use a new output directory')
        extra = {'advice_spans': advice_spans(wav.read_bytes(), len(samples) / rate)} if 'advice' in row else {}
        manifest['recordings'].append({**row, **extra, 'file': wav.name, 'sha256_pcm': fingerprint,
            'duration': len(samples) / rate, 'shapes': sorted({c['value'] for c in cues})})
        temporary = target.with_suffix('.building')
        temporary.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf8')
        replace_manifest(temporary, target)
        print(json.dumps({'id': row['id'], 'seconds': round(len(samples) / rate, 2),
                          'elapsed': round(time.monotonic() - started, 2)}), flush=True)


if __name__ == '__main__':
    main()
