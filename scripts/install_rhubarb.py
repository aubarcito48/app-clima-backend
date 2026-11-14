"""Install the pinned official runtime and its license, without demos or tests."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import tempfile
import urllib.request
import zipfile

VERSION = '1.14.0'
ARCHIVES = {
    'Windows': (87374842, '62fa416a8d5e382a3828ee4bef358ce520d0b4cabdeaea75a7ac266d098d1fe3'),
    'Linux': (87225003, 'a9a9074862cff47b2d59b8bf399a678a3b0b74f9452ad6ad94cb292913dd8667'),
}
DEFAULT_TARGET = Path(__file__).resolve().parents[1] / 'models/rhubarb/runtime'


def install(*, target=DEFAULT_TARGET, from_zip=None):
    system = platform.system()
    if system not in ARCHIVES or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise RuntimeError('The pinned Rhubarb binaries require Windows/Linux x86-64')
    target = Path(target).resolve()
    target.mkdir(parents=True, exist_ok=True)
    size, digest = ARCHIVES[system]
    name = f'Rhubarb-Lip-Sync-{VERSION}-{system}'
    executable = 'rhubarb.exe' if system == 'Windows' else 'rhubarb'
    marker = target / 'installed.json'
    if marker.is_file():
        installed = json.loads(marker.read_text(encoding='utf8'))
        if (installed == {'version': VERSION, 'archive_sha256': digest}
                and (target / executable).is_file() and (target / 'res').is_dir()
                and (target / 'LICENSE.md').is_file()):
            print(f'Rhubarb {VERSION}: runtime already installed')
            return
    with tempfile.TemporaryDirectory(prefix='isa-rhubarb-install-') as folder:
        archive = Path(from_zip) if from_zip else Path(folder) / 'release.zip'
        if from_zip is None:
            url = f'https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v{VERSION}/{name}.zip'
            with urllib.request.urlopen(url, timeout=60) as response, archive.open('wb') as output:
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > size:
                        raise RuntimeError('Rhubarb download exceeds pinned size')
                    output.write(chunk)
        with archive.open('rb') as stream:
            if archive.stat().st_size != size or hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                raise RuntimeError('Rhubarb archive failed SHA256 verification')
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                if member.is_dir() or not member.filename.startswith(name + '/'):
                    continue
                relative = PurePosixPath(member.filename).relative_to(name)
                if relative.parts[0] != 'res' and relative.as_posix() not in (
                        executable, 'LICENSE.md', 'README.adoc', 'CHANGELOG.md'):
                    continue
                destination = target.joinpath(*relative.parts).resolve()
                if not destination.is_relative_to(target):
                    raise RuntimeError('Invalid archive path')
                destination.parent.mkdir(parents=True, exist_ok=True)
                partial = destination.with_suffix(destination.suffix + '.partial')
                with package.open(member) as source, partial.open('wb') as output:
                    shutil.copyfileobj(source, output)
                partial.replace(destination)
        binary = target / executable
        if not binary.is_file() or not (target / 'res').is_dir() or not (target / 'LICENSE.md').is_file():
            raise RuntimeError('Incomplete Rhubarb runtime')
        if os.name != 'nt':
            binary.chmod(binary.stat().st_mode | 0o111)
        marker.write_text(json.dumps({'version': VERSION, 'archive_sha256': digest}) + '\n', encoding='utf8')
    print(f'Rhubarb {VERSION}: verified runtime installed (license included)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-zip', type=Path)
    parser.add_argument('--target', type=Path, default=DEFAULT_TARGET)
    options = parser.parse_args()
    install(target=options.target, from_zip=options.from_zip)
