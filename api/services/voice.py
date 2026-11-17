"""Piper local: una síntesis por proceso, sin red y con tiempo máximo."""

from pathlib import Path
import json
import subprocess
import sys
import threading

from django.conf import settings
from .voice_memory import trace_voice_memory
from .isa_performance import read_segments
from .own_lip_sync import classify_after_synthesis, MAX_INTERNAL_AUDIO_BYTES


_gate = threading.Lock()
MAX_TEXT = 600
MAX_AUDIO_BYTES = 3_973_140  # 90 segundos PCM16 + hasta 4 KiB de tiempos de Isa.


class VoiceUnavailable(Exception):
    pass


class VoiceBusy(VoiceUnavailable):
    pass


def synthesize(text, language='es', *, segments=None):
    if language not in {'es', 'en'}:
        raise VoiceUnavailable()
    if segments is not None:
        segments = read_segments(segments, text, max_segments=6)
    if not _gate.acquire(blocking=False):
        raise VoiceBusy()
    try:
        trace_voice_memory('request_start')
        result = subprocess.run(
            [sys.executable, '-X', 'utf8', str(Path(__file__).with_name('voice_worker.py')),
             str(settings.ISA_MODEL_DIR), language, *(['--performance'] if segments else []),
             *(['--own-lip-sync'] if settings.ISA_LIP_SYNC in ('own', 'rhubarb') else [])],
            input=(json.dumps({'texto': text, 'segmentos': segments}, ensure_ascii=False).encode('utf-8')
                   if segments else text.encode('utf-8')), stdout=subprocess.PIPE, timeout=45,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        audio = result.stdout
        if (result.returncode != 0 or not 44 < len(audio) <= MAX_INTERNAL_AUDIO_BYTES
                or audio[:4] != b'RIFF' or audio[8:12] != b'WAVE'):
            trace_voice_memory('worker_failed')
            raise VoiceUnavailable()
        if settings.ISA_LIP_SYNC in ('own', 'rhubarb'):
            audio = classify_after_synthesis(audio, language)
        if len(audio) > MAX_AUDIO_BYTES + 65536:
            raise VoiceUnavailable()
        return audio
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        trace_voice_memory('timeout' if isinstance(exc, subprocess.TimeoutExpired) else 'worker_failed')
        raise VoiceUnavailable() from exc
    finally:
        _gate.release()
