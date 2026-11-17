"""Reuse training only; never convert previously observed dev/test data to training."""

import argparse
import json
from pathlib import Path

from classifier import read_recording
from generate_corpus import validate_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--additions', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    previous = json.loads(args.previous.read_text(encoding='utf8'))
    additions = json.loads(args.additions.read_text(encoding='utf8'))
    reused = [r for r in previous['recordings'] if r['split'] == 'train']
    profile = additions.get('narration_profile', previous.get('narration_profile', 'legacy-plain'))
    if previous.get('narration_profile', 'legacy-plain') != profile:
        parser.error('Do not mix narration profiles when reusing training recordings')
    plan = {'version': 1, 'reference': 'weak-rhubarb', 'narration_profile': profile, 'recordings': [
        {key: r[key] for key in ('id', 'language', 'split', 'text', 'advice') if key in r}
        for r in reused] + additions['recordings']}
    validate_plan(plan)
    prior_texts = {(r['language'], ' '.join(r['text'].casefold().split())) for r in previous['recordings']}
    if any((r['language'], ' '.join(r['text'].casefold().split())) in prior_texts for r in additions['recordings']):
        parser.error('All added texts must be new relative to the previous corpus')
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / 'plan.json'
    if target.exists() and json.loads(target.read_text(encoding='utf8')) != plan:
        parser.error('Use a new output directory for a different plan')
    for row in reused:
        source = args.previous.parent / row['file']
        if source.resolve().parent != args.previous.parent.resolve():
            parser.error('Recording path leaves the corpus directory')
        if read_recording(source)[3] != row['sha256_pcm']:
            parser.error('Existing training recording changed')
        destination = args.output / row['file']
        if destination.exists():
            if read_recording(destination)[3] != row['sha256_pcm']:
                parser.error('Destination recording changed')
        else:
            destination.write_bytes(source.read_bytes())
    target.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding='utf8')
    print(json.dumps({'plan': str(target), 'reused_training': len(reused),
                       'new_recordings': len(additions['recordings'])}))


if __name__ == '__main__':
    main()
