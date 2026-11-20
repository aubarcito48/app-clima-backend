"""One bounded request delivers independently playable WAV phrases in order."""

import base64
import io
import json
from pathlib import Path
import subprocess
import sys
from time import monotonic
import wave

from django.conf import settings

from api.services.assistant.alignment.own_lip_sync import classify_after_synthesis
from api.services.assistant.direction.isa_performance import read_segments
from api.services.assistant.voice.voice import _gate, VoiceBusy, VoiceUnavailable
from api.services.assistant.voice.voice_chunks import stream_voice_parts
from api.services.assistant.voice.voice_process import render_parts, reuse_status


def _event(value):
    return (json.dumps(value, separators=(',', ':')) + '\n').encode('ascii')


class PreparedStream:
    """Prefetch before HTTP headers; Django calls close even on disconnect."""

    def __init__(self, iterator):
        self.iterator = iterator
        self.first = next(iterator)

    def __iter__(self):
        return self

    def __next__(self):
        if self.first is not None:
            first, self.first = self.first, None
            return first
        return next(self.iterator)

    def close(self):
        self.iterator.close()


def synthesize_stream(text, language='es', *, segments=None):
    if language not in ('es', 'en'):
        raise VoiceUnavailable()
    if segments is not None:
        segments = read_segments(segments, text, max_segments=6)
    payload = {'texto': text, **({'segmentos': segments} if segments else {})}
    groups = stream_voice_parts(payload)
    if not _gate.acquire(blocking=False):
        raise VoiceBusy()
    worker = None
    sent = 0
    started = monotonic()
    duration = 0
    try:
        own_lips = settings.ISA_LIP_SYNC in ('own', 'rhubarb')
        command = [sys.executable, '-X', 'utf8', str(Path(__file__).with_name('voice_worker.py')),
                   str(settings.ISA_MODEL_DIR), language, '--performance', '--stream',
                   *(['--own-lip-sync'] if own_lips else [])]
        worker = render_parts(command, json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                              timeout=45, keepalive=settings.ISA_VOICE_KEEPALIVE_SECONDS)
        for index, audio in enumerate(worker):
            if index >= len(groups) or monotonic() - started > 110:
                raise VoiceUnavailable()
            if own_lips:
                audio = classify_after_synthesis(audio, language,
                    timeout=min(30, max(.1, 110 - (monotonic() - started))))
            with wave.open(io.BytesIO(audio)) as wav:
                duration += wav.getnframes() / wav.getframerate()
            if duration > 90 or len(audio) > 4_038_676:
                raise VoiceUnavailable()
            yield _event({'type': 'audio', 'index': index, 'total': len(groups),
                          'audio': base64.b64encode(audio).decode('ascii'),
                          'segments': groups[index]['segmentos'],
                          'model_reused': reuse_status()['model_reused'],
                          'elapsed_ms': round((monotonic() - started) * 1000)})
            sent += 1
        if sent != len(groups):
            raise VoiceUnavailable()
        yield _event({'type': 'done', 'total': sent, **reuse_status()})
    except (OSError, ValueError, wave.Error, subprocess.TimeoutExpired, VoiceUnavailable) as exc:
        if not sent:
            raise VoiceUnavailable() from exc
        yield _event({'type': 'error', 'code': 'VOZ_NO_DISPONIBLE'})
    finally:
        if worker is not None:
            worker.close()
        _gate.release()
