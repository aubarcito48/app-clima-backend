"""Instala Kokoro INT8 y Dora con tamaño y SHA256 verificados."""

import argparse
import hashlib
from pathlib import Path
import shutil
import urllib.request


ASSETS = (
    ('kokoro-v1.0.int8.onnx', 92361271, '6e742170d309016e5891a994e1ce1559c702a2ccd0075e67ef7157974f6406cb'),
    ('voices-v1.0.bin', 28214398, 'bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d'),
)
BASE_URL = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'


def verified(path, size, digest):
    if not path.is_file() or path.stat().st_size != size:
        return False
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() == digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-dir', type=Path)
    parser.add_argument('--target', type=Path, default=Path(__file__).resolve().parents[1] / 'models' / 'kokoro-v1.0')
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
    print('Dora instalada. Reiniciá Django para usar la voz de Isa.')


if __name__ == '__main__':
    main()
