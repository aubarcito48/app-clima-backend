"""Dora local: una síntesis por proceso, sin red y con tiempo máximo."""

from pathlib import Path
import subprocess
import sys
import threading

from django.conf import settings


_gate = threading.Lock()
MAX_TEXT = 600
MAX_AUDIO_BYTES = 4_320_044  # 90 segundos, mono PCM16 a 24 kHz.


class VoiceUnavailable(Exception):
    pass


class VoiceBusy(VoiceUnavailable):
    pass


def synthesize(text):
    if not _gate.acquire(blocking=False):
        raise VoiceBusy()
    try:
        result = subprocess.run(
            [sys.executable, '-X', 'utf8', str(Path(__file__).with_name('voice_worker.py')),
             str(settings.ISA_MODEL_DIR)],
            input=text.encode('utf-8'), capture_output=True, timeout=45,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        audio = result.stdout
        if (result.returncode != 0 or not 44 < len(audio) <= MAX_AUDIO_BYTES
                or audio[:4] != b'RIFF' or audio[8:12] != b'WAVE'):
            raise VoiceUnavailable()
        return audio
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VoiceUnavailable() from exc
    finally:
        _gate.release()
