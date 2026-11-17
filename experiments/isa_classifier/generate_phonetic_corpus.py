"""Regenerate V7 split-preserving speech, obtaining PCM and phones together."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from probe_phonetic import ROOT, synthesize_case, load_aligned_voice
from narration import advice_spans, app_text
from classifier import read_recording


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--language', choices=('es', 'en'))
    args = parser.parse_args()
    source_bytes = args.source.read_bytes()
    source = json.loads(source_bytes)
    args.output.mkdir(parents=True, exist_ok=True)
    plan_hash = hashlib.sha256(source_bytes).hexdigest()
    marker = args.output / 'source-sha256.txt'
    if marker.exists() and marker.read_text() != plan_hash:
        raise ValueError('Different source requires another folder')
    marker.write_text(plan_hash)
    if not args.language:
        for language in ('es', 'en'):
            subprocess.run([sys.executable, '-X', 'utf8', __file__, '--source', str(args.source),
                            '--output', str(args.output), '--language', language], check=True)
        rows = sum([json.loads((args.output / f'index-{lang}.json').read_text(encoding='utf8')) for lang in ('es', 'en')], [])
        (args.output / 'corpus.json').write_text(json.dumps({'version': 1, 'reference': 'weak-rhubarb',
            'narration_profile': 'app-greeting-v1', 'plan_sha256': plan_hash,
            'warning': 'V7 phrases regenerated; prior test phrases are not a fresh external holdout',
            'recordings': rows}, ensure_ascii=False, indent=2), encoding='utf8')
        return
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    import django
    django.setup()
    from django.conf import settings
    from api.services.lip_sync import add_lip_sync, read_mouth_cues
    from api.services.voice_worker import VOICES
    from api.services.voice_chunks import prepare_voice_chunks
    from phonetic_alignment import expand_diphthongs, phone_shapes
    language = args.language
    selected = [r for r in source['recordings'] if r['language'] == language]
    # Validate the whole phonetic inventory before spending time synthesizing.
    voice, _ = load_aligned_voice(Path(settings.ISA_MODEL_DIR) / VOICES[language][0])
    for row in selected:
        for chunk in prepare_voice_chunks(voice, app_text(row['advice'], language), language):
            phone_shapes(expand_diphthongs([{'phoneme': p, 'samples': 2} for p in chunk]), language)
    rows = []
    for row in selected:
        folder = args.output / row['id']
        wav = args.output / f"{row['id']}.wav"
        info_path = folder / f'phones-{language}.json'
        if not wav.exists():
            synthesize_case(language, folder, row['advice'])
            audio = add_lip_sync((folder / f'raw-{language}.wav').read_bytes(), settings.ISA_RHUBARB_PATH, timeout=45)
            wav.write_bytes(audio)
        samples, rate, cues, fingerprint = read_recording(wav)
        duration = len(samples) / rate
        read_mouth_cues({'mouthCues': cues}, duration)
        info = json.loads(info_path.read_text(encoding='utf8'))
        if info['text'] != row['text'] or abs(info['phonemes'][-1]['end'] - duration) > 1e-8:
            raise ValueError('Phone/audio mismatch')
        rows.append({**{k: row[k] for k in ('id', 'language', 'split', 'text', 'advice')},
                     'file': wav.name, 'phones_file': str(info_path.relative_to(args.output)),
                     'sha256_pcm': fingerprint, 'duration': duration,
                     'advice_spans': advice_spans(wav.read_bytes(), duration)})
    (args.output / f'index-{language}.json').write_text(json.dumps(rows, ensure_ascii=False), encoding='utf8')
    print(json.dumps({'complete': language, 'recordings': len(rows)}), flush=True)


if __name__ == '__main__':
    main()
