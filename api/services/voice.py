"""Piper local: una síntesis por proceso, sin red y con tiempo máximo."""

from pathlib import Path
import subprocess
import sys
import threading

from django.conf import settings
from .voice_memory import trace_voice_memory


_gate = threading.Lock()
MAX_TEXT = 600
MAX_AUDIO_BYTES = 3_969_044  # 90 segundos, mono PCM16 a 22.050 Hz.


class VoiceUnavailable(Exception):
    pass


class VoiceBusy(VoiceUnavailable):
    pass


def synthesize(text, language='es'):
    if language not in {'es', 'en'}:
        raise VoiceUnavailable()
    if not _gate.acquire(blocking=False):
        raise VoiceBusy()
    try:
        trace_voice_memory('request_start')
        result = subprocess.run(
            [sys.executable, '-X', 'utf8', str(Path(__file__).with_name('voice_worker.py')),
             str(settings.ISA_MODEL_DIR), language],
            input=text.encode('utf-8'), stdout=subprocess.PIPE, timeout=45,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        audio = result.stdout
        if (result.returncode != 0 or not 44 < len(audio) <= MAX_AUDIO_BYTES
                or audio[:4] != b'RIFF' or audio[8:12] != b'WAVE'):
            trace_voice_memory('worker_failed')
            raise VoiceUnavailable()
        return audio
    except (OSError, subprocess.TimeoutExpired) as exc:
        trace_voice_memory('timeout' if isinstance(exc, subprocess.TimeoutExpired) else 'worker_failed')
        raise VoiceUnavailable() from exc
    finally:
        _gate.release()
