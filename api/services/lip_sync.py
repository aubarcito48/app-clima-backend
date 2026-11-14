"""Optional Rhubarb probe after Piper exits; never replaces the spoken audio."""

import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import wave

from .voice_memory import memory_snapshot

MAX_CUE_BYTES = 65536
MAX_CUES = 1500
SHAPES = frozenset('ABCDEFGHX')


def read_mouth_cues(data, duration):
    """Only bounded, contiguous audio-relative times and real Rhubarb shapes."""
    rows = data.get('mouthCues') if isinstance(data, dict) else None
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_CUES:
        raise ValueError('Invalid mouth cues')
    result, previous = [], 0.0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'start', 'end', 'value'}:
            raise ValueError('Invalid mouth cue')
        start, end, shape = row['start'], row['end'], row['value']
        if (any(isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) for value in (start, end))
                or not isinstance(shape, str) or shape not in SHAPES
                or not 0 <= start < end <= duration + .011
                or abs(start - previous) > .011):
            raise ValueError('Invalid mouth cue timing')
        result.append({'start': start, 'end': end, 'value': shape})
        previous = end
    if abs(previous - duration) > .021:
        raise ValueError('Incomplete mouth timeline')
    payload = json.dumps(result, separators=(',', ':'), allow_nan=False).encode('ascii')
    if len(payload) > MAX_CUE_BYTES:
        raise ValueError('Mouth timeline too large')
    return result


def append_mouth_cues(audio, cues):
    # Separate from isac: existing consumers continue reading segment timings.
    payload = json.dumps(cues, separators=(',', ':'), allow_nan=False).encode('ascii')
    chunk = b'isav' + len(payload).to_bytes(4, 'little') + payload
    chunk += b'\x00' * (len(payload) % 2)
    result = audio + chunk
    return result[:4] + (len(result) - 8).to_bytes(4, 'little') + result[8:]


def _log(stage, started, peak, *, cues=0):
    if sys.platform != 'linux':
        return
    event = {'event': 'isa_memory', 'engine': 'rhubarb', 'stage': stage,
             'elapsed_seconds': round(time.monotonic() - started, 3),
             'mouth_cues': cues, **memory_snapshot(), **peak}
    try:
        print(json.dumps(event), file=sys.__stderr__, flush=True)
    except OSError:
        pass


def add_lip_sync(audio, executable, *, timeout):
    """Return original WAV on any optional failure. No model remains resident.

    A 50 ms cgroup sampler observes the whole container during the recognizer,
    rather than treating the Django process's RSS as Rhubarb's memory usage.
    No filenames, text, recognizer output or credentials enter application logs.
    """
    started = time.monotonic()
    peak, stopped = {'timeout_seconds': round(max(0, timeout), 3)}, threading.Event()
    def sample():
        while not stopped.is_set():
            current = memory_snapshot().get('cgroup_current_mib')
            if current is not None:
                peak['peak_cgroup_observed_mib'] = max(current, peak.get('peak_cgroup_observed_mib', 0))
            stopped.wait(.05)
    monitor = threading.Thread(target=sample, daemon=True)
    process = None
    try:
        if timeout <= 0:
            _log('skipped_budget', started, peak)
            return audio
        executable = Path(executable)
        if not executable.is_file():
            _log('missing_binary', started, peak)
            return audio
        with wave.open(io.BytesIO(audio)) as source:
            duration = source.getnframes() / source.getframerate()
            if not 0 < duration <= 90:
                raise ValueError('Invalid audio duration')
        with tempfile.TemporaryDirectory(prefix='isa-lips-') as folder:
            folder = Path(folder)
            wav_path, output = folder / 'speech.wav', folder / 'mouth.json'
            # WAV is temporary; the JSON metadata soundFile path is never returned.
            wav_path.write_bytes(audio)
            _log('processing_start', started, peak)
            monitor.start()
            process = subprocess.Popen([
                str(executable), '-r', 'phonetic', '-f', 'json', '--threads', '1',
                '--extendedShapes', 'GHX', '-q', '-o', str(output), str(wav_path),
            ], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                _log('timeout', started, peak)
                return audio
            if process.returncode or not output.is_file() or output.stat().st_size > MAX_CUE_BYTES:
                raise ValueError('Invalid recognizer output')
            cues = read_mouth_cues(json.loads(output.read_text(encoding='utf8')), duration)
            _log('complete', started, peak, cues=len(cues))
            return append_mouth_cues(audio, cues)
    except (OSError, ValueError, TypeError, OverflowError, wave.Error):
        _log('failed', started, peak)
        return audio
    finally:
        stopped.set()
        if monitor.is_alive():
            monitor.join(timeout=1)
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
