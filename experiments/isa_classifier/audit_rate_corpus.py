"""Audit grouped augmentation, real timing and audio identities before training."""
import argparse
import json
from pathlib import Path
from classifier import read_recording
from narration import performance_rows
from generate_corpus import validate_plan


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('corpus', type=Path)
    args = p.parse_args()
    manifest = json.loads(args.corpus.read_text(encoding='utf8'))
    validate_plan(manifest)
    groups, hashes = {}, set()
    for row in manifest['recordings']:
        wav = args.corpus.parent / row['file']
        _, _, _, fingerprint = read_recording(wav)
        if fingerprint != row['sha256_pcm'] or fingerprint in hashes:
            raise ValueError('Changed or duplicate PCM')
        hashes.add(fingerprint)
        group = groups.setdefault((row['language'], row['group_id']), {})
        if group and any(r['split'] != row['split'] or r['text'] != row['text'] for r in group.values()):
            raise ValueError('Augmented group crosses text or split')
        group[row['variant']] = row
    checked = 0
    for variants in groups.values():
        if 'automatic' not in variants:
            continue
        a, b = variants['baseline'], variants['automatic']
        before = performance_rows((args.corpus.parent / a['file']).read_bytes(), a['duration'])
        after = performance_rows((args.corpus.parent / b['file']).read_bytes(), b['duration'])
        for i, (x, y) in enumerate(zip(before, after)):
            if abs((x['until'] - x['speech_end']) - (y['until'] - y['speech_end'])) > 1e-8:
                raise ValueError('Inserted pause changed')
            if b['speed_factors'][i] < 1 and y['speech_end'] - y['from'] <= x['speech_end'] - x['from']:
                raise ValueError('Reduced speed did not increase actual phrase duration')
        checked += 1
    report = {'recordings': len(hashes), 'phrase_groups': len(groups), 'automatic_pairs_checked': checked,
              'groups_disjoint_between_splits': True, 'languages': {}}
    for language in ('es', 'en'):
        rows = [r for r in manifest['recordings'] if r['language'] == language]
        report['languages'][language] = {'recordings': len(rows), 'seconds': sum(r['duration'] for r in rows),
            'train': sum(r['split'] == 'train' for r in rows), 'dev': sum(r['split'] == 'dev' for r in rows),
            'fresh_test_recordings': sum(r['split'] == 'test' and r.get('evaluation') == 'fresh' for r in rows),
            'fresh_test_groups': len({r['group_id'] for r in rows if r['split'] == 'test' and r.get('evaluation') == 'fresh'})}
    (args.corpus.parent / 'audit.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
