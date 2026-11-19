"""Synthesize a fixed local sample and export an audio/cue inspection page."""

import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--language', choices=('es', 'en'), default='es')
    parser.add_argument('--text')
    parser.add_argument('--output', type=Path, default=ROOT / 'tmp/isa-rhubarb/probe.wav')
    args = parser.parse_args()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    import django
    django.setup()
    from django.conf import settings
    from api.services.assistant.direction.isa_local_director import direct_locally
    from api.services.assistant.voice.voice import synthesize
    from preview_lip_sync import build_preview
    if settings.ISA_LIP_SYNC != 'rhubarb':
        parser.error('Set ISA_LIP_SYNC=rhubarb in the local backend environment first')
    text = args.text or (
        'Usá una campera liviana. Más tarde evitá el calzado abierto si llueve.' if args.language == 'es'
        else 'Wear a light jacket. Later, avoid open shoes if it rains.'
    )
    if not 1 <= len(text.strip()) <= 280 or len(text.split()) > 40:
        parser.error('Use at most 280 characters and 40 words of advice')
    start = time.monotonic()
    audio = synthesize(text, language=args.language, segments=direct_locally(text, language=args.language))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(audio)
    try:
        page = build_preview(audio)
    except ValueError:
        print(json.dumps({'audio_ok': True, 'mouth_cues': False,
                          'elapsed_seconds': round(time.monotonic() - start, 3),
                          'fallback': 'original Piper WAV retained'}))
        return 1
    args.output.with_suffix('.html').write_text(page, encoding='utf8')
    print(json.dumps({'audio_ok': True, 'mouth_cues': True,
                      'elapsed_seconds': round(time.monotonic() - start, 3),
                      'output': str(args.output), 'preview': str(args.output.with_suffix('.html'))}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
