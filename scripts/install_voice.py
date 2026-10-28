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
                with urllib.request.urlopen(BASE_URL + name, timeout=30) as response, partial.open('wb') as output:
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
    print('Piper Sharvard instalado (voz femenina F). Reiniciá Django para usar la voz de Isa.')


if __name__ == '__main__':
    main()
