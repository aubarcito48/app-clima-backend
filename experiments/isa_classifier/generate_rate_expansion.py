"""New grouped advice and automatic-rate augmentation; previous audio preserved."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from probe_phonetic import synthesize_case, load_aligned_voice
from rate_expansion_plan import make_plan
from automatic_voice_rate import rate_plan
from classifier import read_recording
from narration import advice_spans, performance_rows
from analyze_timing import analyze
from generate_corpus import validate_plan


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--previous', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--language', choices=('es', 'en'))
    p.add_argument('--plan', type=Path)
    p.add_argument('--parallel-languages', action='store_true', help='Isolated ES/EN worker processes')
    args = p.parse_args()
    old = json.loads(args.previous.read_text(encoding='utf8'))
    plan = json.loads(args.plan.read_text(encoding='utf8')) if args.plan else make_plan()
    known = {(r['language'], r['advice'].strip().casefold()) for r in old['recordings']}
    if any((r['language'], r['advice'].strip().casefold()) in known for r in plan):
        raise ValueError('New advice already appeared in prior corpus')
    args.output.mkdir(parents=True, exist_ok=True)
    plan_hash = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    marker = args.output / 'plan-sha256.txt'
    if marker.exists() and marker.read_text() != plan_hash:
        raise ValueError('Changed plan needs a new directory')
    if not args.language:
        marker.write_text(plan_hash)
    if not args.language:
        previous_rows = []
        for row in old['recordings']:
            source = args.previous.parent / row['file']
            if read_recording(source)[3] != row['sha256_pcm']:
                raise ValueError('Old PCM changed')
            shutil.copy2(source, args.output / row['file'])
            info = args.previous.parent / row['phones_file']
            dest = args.output / row['id']
            dest.mkdir(exist_ok=True)
            shutil.copy2(info, dest / info.name)
            shutil.copy2(info.parent / f"raw-{row['language']}.wav", dest / f"raw-{row['language']}.wav")
            previous_rows.append({**row, 'group_id': row.get('group_id', row['id']),
                                  'variant': row.get('variant', 'baseline'), 'evaluation': 'legacy'})
        def run_language(language):
            subprocess.run([sys.executable, '-X', 'utf8', __file__, '--previous', str(args.previous),
                            '--output', str(args.output), '--language', language,
                            *(['--plan', str(args.plan)] if args.plan else [])], check=True)
        if args.parallel_languages:
            with ThreadPoolExecutor(max_workers=2) as workers:
                list(workers.map(run_language, ('es', 'en')))
        else:
            for language in ('es', 'en'):
                run_language(language)
        rows = previous_rows + sum([json.loads((args.output / f'new-{lang}.json').read_text(encoding='utf8')) for lang in ('es', 'en')], [])
        manifest = {'version': 1, 'reference': 'weak-rhubarb', 'narration_profile': 'app-greeting-v1',
                    'augmentation_profile': 'paired-rate-v1', 'plan_sha256': plan_hash,
                    'warning': 'Fresh test groups separate from legacy reevaluation; rate variants are not independent phrases',
                    'recordings': rows}
        validate_plan(manifest)
        (args.output / 'corpus.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
        print(json.dumps({'total_recordings': len(rows), 'new_advice_groups': len(plan)}), flush=True)
        return
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    import django
    django.setup()
    import onnxruntime as rt
    from django.conf import settings
    from api.services.lip_sync import add_lip_sync, read_mouth_cues
    rows = []
    language = args.language
    for group in [r for r in plan if r['language'] == language]:
        def generate(variant, factors=None):
            item_id = group['id'] + '-' + variant
            folder, wav = args.output / item_id, args.output / (item_id + '.wav')
            if not wav.exists():
                load_aligned_voice.cache_clear()
                rt.set_seed(20261116)
                synthesize_case(language, folder, group['advice'], speed_factors=factors)
                wav.write_bytes(add_lip_sync((folder / f'raw-{language}.wav').read_bytes(), settings.ISA_RHUBARB_PATH, timeout=45))
            samples, rate, cues, fingerprint = read_recording(wav)
            duration = len(samples) / rate
            read_mouth_cues({'mouthCues': cues}, duration)
            row = {**group, 'id': item_id, 'variant': variant, 'speed_factors': factors,
                'file': wav.name, 'phones_file': str((folder / f'phones-{language}.json').relative_to(args.output)),
                'duration': duration, 'sha256_pcm': fingerprint, 'advice_spans': advice_spans(wav.read_bytes(), duration)}
            rows.append(row)
            return row, analyze(wav, row)
        baseline, timing = generate('baseline')
        factors, _ = rate_plan(timing)
        if any(f < 1 for f in factors):
            automatic, _ = generate('automatic', factors)
            before = performance_rows((args.output / baseline['file']).read_bytes(), baseline['duration'])
            after = performance_rows((args.output / automatic['file']).read_bytes(), automatic['duration'])
            failures = [i for i, (a, b) in enumerate(zip(before, after)) if factors[i] < 1
                        and b['speech_end'] - b['from'] <= a['speech_end'] - a['from'] + 1e-8]
            if failures:
                rows.remove(automatic)
                (args.output / automatic['id'] / 'rejected-rate.json').write_text(json.dumps({
                    'reason': 'requested_slowdown_not_measured', 'segments': failures,
                    'preserved_audio': automatic['file'], 'excluded_from_corpus': True}), encoding='utf8')
        print(json.dumps({'group_complete': group['id'],
                          'variants': sum(r['group_id'] == group['group_id'] for r in rows)}), flush=True)
    (args.output / f'new-{language}.json').write_text(json.dumps(rows, ensure_ascii=False), encoding='utf8')


if __name__ == '__main__':
    main()
