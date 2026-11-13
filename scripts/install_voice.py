"""Instala Daniela argentina y Lessac con tamaño y SHA256 verificados."""

import argparse
import hashlib
from pathlib import Path
import shutil
import urllib.request


ASSETS = (
    ('es_AR-daniela-high.onnx', 114199011, '7ceb1fc0dab349418c5b54a639ae9ee595212d7c9ea422220d8419163d5cc985'),
    ('es_AR-daniela-high.onnx.json', 7248, 'aedbf69647e1d754c62ecf8e0366ca5f16af3e768e3c6b5329af6eb6bde3852b'),
    ('MODEL_CARD', 353, '39fda44bb85009b0bd7aabb455b113e50abf1f2a2013f3264c482691105e4e3b'),
    ('en_US-lessac-medium.onnx', 63201294, '5efe09e69902187827af646e1a6e9d269dee769f9877d17b16b1b46eeaaf019f'),
    ('en_US-lessac-medium.onnx.json', 4885, 'efe19c417bed055f2d69908248c6ba650fa135bc868b0e6abb3da181dab690a0'),
    ('MODEL_CARD.en', 351, 'ce49eb457742208166d399a40cdec2c7fa9db77960930031564ab56f12882645'),
)
BASE_URL = ('https://huggingface.co/rhasspy/piper-voices/resolve/'
            '2f358b6a560e3a913ebf509b2f3344f20b367f94/es/es_AR/daniela/high/')
ENGLISH_BASE_URL = ('https://huggingface.co/rhasspy/piper-voices/resolve/'
                    '5041a7a49ae5b3a0f30e6837769eb03fdbb231bd/en/en_US/lessac/medium/')


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
                base = ENGLISH_BASE_URL if name.startswith('en_') or name == 'MODEL_CARD.en' else BASE_URL
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
    print('Piper instalado: Daniela argentina (es) y Lessac (en). Reiniciá Django para usar las voces de Isa.')


if __name__ == '__main__':
    main()
