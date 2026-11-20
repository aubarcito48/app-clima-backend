"""Optional bounded reuse of one Piper process, released after inactivity."""

import atexit
import queue
import struct
import subprocess
import threading
from time import monotonic

from api.services.assistant.alignment.own_lip_sync import MAX_INTERNAL_AUDIO_BYTES
from api.services.assistant.voice.voice_memory import can_retain_voice, trace_voice_memory

_lock = threading.Lock()
_worker = None
_command = None
_replies = None
_idle = None
_uses = 0
_last_reused = False
_last_retained = False


def _stop():
    global _worker, _command, _replies, _idle, _uses, _last_retained
    if _idle is not None:
        _idle.cancel()
        _idle = None
    if _worker is not None:
        if _worker.poll() is None:
            _worker.kill()
        _worker.wait()
        _worker.stdin.close()
        _worker.stdout.close()
    _worker = _command = _replies = None
    _uses = 0
    _last_retained = False


def close():
    with _lock:
        _stop()


atexit.register(close)


def _read_replies(worker, replies):
    try:
        while True:
            header = worker.stdout.read(4)
            if len(header) != 4:
                raise ValueError('Voice worker closed')
            size = struct.unpack('<I', header)[0]
            if size != 0 and not 44 < size <= MAX_INTERNAL_AUDIO_BYTES:
                raise ValueError('Invalid voice response size')
            audio = worker.stdout.read(size)
            if len(audio) != size:
                raise ValueError('Truncated voice response')
            replies.put_nowait(audio)
    except (OSError, ValueError, queue.Full):
        try:
            replies.put_nowait(None)
        except queue.Full:
            pass


def render_parts(command, payload, *, timeout, keepalive):
    global _worker, _command, _replies, _idle, _uses, _last_reused, _last_retained
    if not 0 < len(payload) <= 8192:
        raise ValueError('Invalid voice payload size')
    with _lock:
        if _idle is not None:
            _idle.cancel()
            _idle = None
        _last_reused = _last_retained = False
        if _worker is not None and not can_retain_voice():
            trace_voice_memory('memory_release')
            _stop()
        if _worker is None or _worker.poll() is not None or _command != command:
            _stop()
            _worker = subprocess.Popen(
                [*command, '--persistent'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            _command = command
            _replies = queue.Queue(maxsize=8)
            threading.Thread(target=_read_replies, args=(_worker, _replies), daemon=True).start()
        _last_reused = _uses > 0
        if _last_reused:
            trace_voice_memory('model_reused')
        _uses += 1
        finished = False
        started = monotonic()
        try:
            _worker.stdin.write(struct.pack('<I', len(payload)) + payload)
            _worker.stdin.flush()
            count = 0
            while True:
                remaining = 110 - (monotonic() - started)
                if remaining <= 0:
                    raise queue.Empty()
                audio = _replies.get(timeout=min(timeout, remaining))
                if audio is None:
                    raise ValueError('Voice worker failed')
                if audio == b'':
                    if count == 0:
                        raise ValueError('Empty voice response')
                    finished = True
                    break
                count += 1
                if count > 6:
                    raise ValueError('Too many voice parts')
                yield audio
        except queue.Empty as exc:
            _stop()
            raise subprocess.TimeoutExpired(command, timeout) from exc
        except (OSError, ValueError):
            _stop()
            raise
        finally:
            # Recycle after one reuse to bound allocator growth across requests.
            if not finished or not keepalive or _uses >= 2:
                if finished and keepalive and _uses >= 2:
                    trace_voice_memory('reuse_limit_release')
                _stop()
            elif not can_retain_voice():
                trace_voice_memory('memory_release')
                _stop()
            else:
                worker = _worker
                expires = monotonic() + keepalive

                def expire():
                    nonlocal timer
                    global _idle
                    with _lock:
                        if _worker is worker and _idle is timer:
                            if not can_retain_voice():
                                trace_voice_memory('memory_release')
                                _stop()
                            elif monotonic() >= expires:
                                trace_voice_memory('idle_release')
                                _stop()
                            else:
                                timer = _idle = threading.Timer(min(5, expires - monotonic()), expire)
                                timer.daemon = True
                                timer.start()

                timer = _idle = threading.Timer(min(5, keepalive), expire)
                timer.daemon = True
                timer.start()
                _last_retained = True
                trace_voice_memory('model_retained')


def reuse_status():
    """Only aggregate booleans; never expose memory sizes, PIDs or model paths."""
    return {'model_reused': _last_reused, 'model_retained': _last_retained}


def render(command, payload, *, timeout, keepalive):
    parts = list(render_parts(command, payload, timeout=timeout, keepalive=keepalive))
    if len(parts) != 1:
        raise ValueError('Unexpected multipart voice response')
    return parts[0]
