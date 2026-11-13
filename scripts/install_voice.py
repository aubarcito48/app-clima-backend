"""Instala Piper Sharvard y su configuración con tamaño y SHA256 verificados."""

import argparse
import hashlib
from pathlib import Path
import shutil
import urllib.request


ASSETS = (
    ('es_ES-sharvard-medium.onnx', 76733615, '40febfb1679c69a4505ff311dc136e121e3419a13a290ef264fdf43ddedd0fb1'),
    ('es_ES-sharvard-medium.onnx.json', 4903, '7438c9b699c72b0c3388dae1b68d3f364dc66a2150fe554a1c11f03372957b2c'),
    ('MODEL_CARD', 392, '37655314d08fe8a0900abc628d3bcbee48ffbdd8fad9306b89525a0ada20fefc'),
    ('en_US-lessac-medium.onnx', 63201294, '5efe09e69902187827af646e1a6e9d269dee769f9877d17b16b1b46eeaaf019f'),
    ('en_US-lessac-medium.onnx.json', 4885, 'efe19c417bed055f2d69908248c6ba650fa135bc868b0e6abb3da181dab690a0'),
    ('MODEL_CARD.en', 351, 'ce49eb457742208166d399a40cdec2c7fa9db77960930031564ab56f12882645'),
)
BASE_URL = ('https://huggingface.co/rhasspy/piper-voices/resolve/'
            '5041a7a49ae5b3a0f30e6837769eb03fdbb231bd/es/es_ES/sharvard/medium/')


def verified(path, size, digest):
    if not path.is_file() or path.stat().st_size != size:
        return False
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() == digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-dir', type=Path)
    parser.add_argument('--target', type=Path, default=Path(__file__).resolve().parents[1] / 'models' / 'piper-sharvard')
    args = parser.parse_args()
    args.target.mkdir(parents=True, exist_ok=True)
    for name, size, digest in ASSETS:
        target = args.target / name
        if verified(target, size, digest):
            continue
        partial = target.with_suffix(target.suffix + '.partial')
        try:
            if args.from_dir:
                source = args.from_dir / name
                if not verified(source, size, digest):
                    raise RuntimeError('El modelo de origen no coincide con la versión verificada.')
                shutil.copyfile(source, partial)
            else:
                base = BASE_URL.replace('es/es_ES/sharvard/medium/', 'en/en_US/lessac/medium/') if name.startswith('en_') or name == 'MODEL_CARD.en' else BASE_URL
                remote_name = 'MODEL_CARD' if name == 'MODEL_CARD.en' else name
                with urllib.request.urlopen(base + remote_name, timeout=30) as response, partial.open('wb') as output:
                    total = 0
                    while chunk := response.read(1024 * 1024):
                        total += len(chunk)
                        if total > size:
                            raise RuntimeError('El modelo excede el tamaño esperado.')
                        output.write(chunk)
            if not verified(partial, size, digest):
                raise RuntimeError('El modelo no supera la verificación SHA256.')
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
    print('Piper instalado: Sharvard (es) y Lessac (en). Reiniciá Django para usar las voces de Isa.')


if __name__ == '__main__':
    main()
