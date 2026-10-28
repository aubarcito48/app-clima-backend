"""Diagnóstico Linux: solo medidas numéricas, sin texto, credenciales ni rutas."""

import json
from pathlib import Path
import sys


def _read(path):
    try:
        return Path(path).read_text(encoding='ascii')
    except (OSError, UnicodeError):
        return ''


def memory_snapshot():
    measurements = {}
    for line in _read('/proc/self/status').splitlines():
        key, _, value = line.partition(':')
        if key in ('VmRSS', 'VmHWM'):
            parts = value.split()
            if parts and parts[0].isdigit():
                measurements['rss_mib' if key == 'VmRSS' else 'peak_rss_mib'] = round(int(parts[0]) / 1024, 1)
    for name, paths in {
        'cgroup_current_mib': ('/sys/fs/cgroup/memory.current', '/sys/fs/cgroup/memory/memory.usage_in_bytes'),
        'cgroup_limit_mib': ('/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory/memory.limit_in_bytes'),
    }.items():
        for path in paths:
            value = _read(path).strip()
            if value.isdigit():
                measurements[name] = round(int(value) / 1048576, 1)
                break
    for line in _read('/sys/fs/cgroup/memory.stat').splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] in ('anon', 'file') and parts[1].isdigit():
            measurements[f'cgroup_{parts[0]}_mib'] = round(int(parts[1]) / 1048576, 1)
    return measurements


def trace_voice_memory(stage, chunk=None, tokens=None):
    if sys.platform != 'linux':
        return
    # Lista cerrada: ningún argumento del usuario puede convertirse en un campo.
    if stage not in ('request_start', 'worker_start', 'libraries_loaded', 'model_loading',
                     'phonemizing', 'phonemes_ready', 'inference_start', 'inference_done',
                     'model_ready', 'chunk_done', 'complete', 'worker_failed', 'timeout'):
        return
    event = {'event': 'isa_memory', 'engine': 'piper', 'stage': stage, **memory_snapshot()}
    if type(chunk) is int and chunk >= 0:
        event['chunk'] = chunk
    if type(tokens) is int and tokens >= 0:
        event['tokens'] = tokens
    try:
        print(json.dumps(event), file=sys.__stderr__, flush=True)
    except OSError:
        pass
