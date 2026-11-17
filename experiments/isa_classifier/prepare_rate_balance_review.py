"""Attach newly trained and previous predictions to identical rate-demo audio."""
import argparse
import json
import base64
from pathlib import Path
import temporal
from classifier import read_recording, timeline
from analyze_timing import analyze
from automatic_voice_rate import rate_plan
from rhythm_features import features_for_model
from narration import performance_rows
from pause_labels import verified_intervals


def verified_timing(timing, samples, rate, wav, info):
    intervals = verified_intervals(samples, rate, performance_rows(wav.read_bytes(), len(samples)/rate), info['phonemes'])
    return {**timing, 'inserted_pauses': [
        {'start': p['start'], 'end': p['end'], 'duration_ms': (p['end']-p['start'])*1000,
         'kind': p['source'], 'verified': True} for p in intervals]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--models', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--corpus', type=Path)
    p.add_argument('--previous-models', type=Path)
    p.add_argument('--model-label', default='Nuevo · datos ampliados y balanceo')
    p.add_argument('--evaluation', type=Path)
    p.add_argument('--verified-pauses', action='store_true')
    p.add_argument('--pause-roles', type=Path)
    args = p.parse_args()
    data = json.loads((args.source / 'comparison.json').read_text(encoding='utf8'))
    data['models'] = {'balanced': args.model_label, 'previous': 'Modelo anterior congelado'}
    data['verified_pauses'] = args.verified_pauses
    roles = json.loads(args.pause_roles.read_text()) if args.pause_roles else None
    if args.evaluation:
        evaluation = json.loads(args.evaluation.read_text(encoding='utf8'))
        data['metrics'] = {}
        for language, result in evaluation['languages'].items():
            new = result.get('boosted', result.get('hybrid'))
            old = result.get('identity', result.get('previous_hybrid'))
            data['metrics'][language] = {'groups': new['grouped_advice']['phrase_groups'],
                'agreement': [old['grouped_advice']['mean_group_agreement'], new['grouped_advice']['mean_group_agreement']],
                'f1': [old['grouped_advice']['mean_group_macro_f1'], new['grouped_advice']['mean_group_macro_f1']],
                'false_closure': [old['advice_only']['closed_while_reference_open_rate'], new['advice_only']['closed_while_reference_open_rate']],
                'dev_guardrails_passed': result.get('dev_guardrails_passed')}
            if 'pause_details' in new:
                data['metrics'][language]['pause_interior'] = [old['pause_details']['verified_interior']['closed_rate'], new['pause_details']['verified_interior']['closed_rate']]
            if roles:
                data['metrics'][language]['advice_pause_interior'] = [roles[f'{language}-previous-advice_interior']['closed_rate'], roles[f'{language}-new-advice_interior']['closed_rate']]
                data['metrics'][language]['advice_all_pause'] = [roles[f'{language}-previous-advice_all_pause']['closed_rate'], roles[f'{language}-new-advice_all_pause']['closed_rate']]
    for case in data['cases']:
        case['id'] = case['language'] + '-original'
        case['label'] = 'Prueba anterior · lluvia'
    for case in data['cases']:
        language = case['language']
        model = json.loads((args.models / f'hybrid-{language}.json').read_text())
        previous_model = json.loads((args.previous_models / f'hybrid-{language}.json').read_text()) if args.previous_models else None
        for name in ('baseline', 'automatic'):
            variant = case[name]
            folder = args.source / language / name
            samples, rate, _, fingerprint = read_recording(folder / f'raw-{language}.wav')
            if fingerprint != variant['sha256_pcm']:
                raise ValueError('Review PCM changed')
            info = json.loads((folder / f'phones-{language}.json').read_text(encoding='utf8'))
            info['sha256_pcm'] = fingerprint
            if args.verified_pauses:
                variant['timing'] = verified_timing(variant['timing'], samples, rate, folder/f'raw-{language}.wav', info)
            features, _, hop = features_for_model(model, samples, rate, alignment=info)
            old_cues = variant['cues']
            if previous_model:
                old_features, _, old_hop = features_for_model(previous_model, samples, rate, alignment=info)
                old_cues = timeline(temporal.predict(previous_model, old_features), old_hop, variant['duration'])
            variant['model_cues'] = {'previous': old_cues,
                'balanced': timeline(temporal.predict(model, features), hop, variant['duration'])}
    if args.corpus:
        manifest = json.loads(args.corpus.read_text(encoding='utf8'))
        for language in ('es', 'en'):
            fresh = [r for r in manifest['recordings'] if r['language'] == language
                     and r['split'] == 'test' and r.get('evaluation') == 'fresh']
            paired = [r for r in fresh if r['variant'] == 'baseline'
                      and any(x['group_id'] == r['group_id'] and x['variant'] == 'automatic' for x in fresh)][:2]
            previous = json.loads((args.previous_models / f'hybrid-{language}.json').read_text())
            balanced = json.loads((args.models / f'hybrid-{language}.json').read_text())
            for number, baseline in enumerate(paired, 1):
                automatic = next(r for r in fresh if r['group_id'] == baseline['group_id'] and r['variant'] == 'automatic')
                case = {'language': language, 'id': baseline['group_id'], 'label': f'Consejo reservado nuevo {number}', 'text': baseline['text']}
                for name, row in [('baseline', baseline), ('automatic', automatic)]:
                    wav = args.corpus.parent / row['file']
                    samples, rate, _, fingerprint = read_recording(wav)
                    if fingerprint != row['sha256_pcm']:
                        raise ValueError('Novel review PCM changed')
                    info = json.loads((args.corpus.parent / row['phones_file']).read_text(encoding='utf8'))
                    info['sha256_pcm'] = fingerprint
                    model_cues = {}
                    for key, candidate in [('previous', previous), ('balanced', balanced)]:
                        features, _, hop = features_for_model(candidate, samples, rate, alignment=info)
                        model_cues[key] = timeline(temporal.predict(candidate, features), hop, row['duration'])
                    case[name] = {**{k: row[k] for k in ('text', 'advice', 'duration', 'sha256_pcm', 'language')},
                        'audio': 'data:audio/wav;base64,' + base64.b64encode(wav.read_bytes()).decode(),
                        'phonemes': info['phonemes'], 'cues': model_cues['previous'], 'model_cues': model_cues, 'timing': analyze(wav, row)}
                    if args.verified_pauses:
                        case[name]['timing'] = verified_timing(case[name]['timing'], samples, rate, wav, info)
                _, case['decisions'] = rate_plan(case['baseline']['timing'])
                data['cases'].append(case)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'comparison.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')


if __name__ == '__main__':
    main()
