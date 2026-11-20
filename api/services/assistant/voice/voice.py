"""Piper local: una solicitud a la vez, sin red y con tiempo máximo."""

from pathlib import Path
import json
import subprocess
import sys
import threading

from django.conf import settings
from api.services.assistant.voice.voice_memory import trace_voice_memory
from api.services.assistant.direction.isa_performance import read_segments
from api.services.assistant.alignment.own_lip_sync import classify_after_synthesis
from api.services.assistant.alignment.own_lip_sync import MAX_INTERNAL_AUDIO_BYTES
from api.services.assistant.voice.voice_process import render


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
        command = [sys.executable, '-X', 'utf8', str(Path(__file__).with_name('voice_worker.py')),
             str(settings.ISA_MODEL_DIR), language, *(['--performance'] if segments else []),
             *(['--own-lip-sync'] if settings.ISA_LIP_SYNC in ('own', 'rhubarb') else [])]
        payload = (json.dumps({'texto': text, 'segmentos': segments}, ensure_ascii=False).encode('utf-8')
                   if segments else text.encode('utf-8'))
        keepalive = settings.ISA_VOICE_KEEPALIVE_SECONDS
        if keepalive:
            audio = render(command, payload, timeout=45, keepalive=keepalive)
            returncode = 0
        else:
            result = subprocess.run(
                command, input=payload, stdout=subprocess.PIPE, timeout=45,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            audio, returncode = result.stdout, result.returncode
        if (returncode != 0 or not 44 < len(audio) <= MAX_INTERNAL_AUDIO_BYTES
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
