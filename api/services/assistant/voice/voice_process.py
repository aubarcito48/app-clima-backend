"""Optional bounded reuse of one Piper process, released after inactivity."""

import atexit
import queue
import struct
import subprocess
import threading
from time import monotonic

from api.services.assistant.alignment.own_lip_sync import MAX_INTERNAL_AUDIO_BYTES

_lock = threading.Lock()
_worker = None
_command = None
_replies = None
_idle = None


def _stop():
    global _worker, _command, _replies, _idle
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
    global _worker, _command, _replies, _idle
    if not 0 < len(payload) <= 8192:
        raise ValueError('Invalid voice payload size')
    with _lock:
        if _idle is not None:
            _idle.cancel()
            _idle = None
        if _worker is None or _worker.poll() is not None or _command != command:
            _stop()
            _worker = subprocess.Popen(
                [*command, '--persistent'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            _command = command
            _replies = queue.Queue(maxsize=8)
            threading.Thread(target=_read_replies, args=(_worker, _replies), daemon=True).start()
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
            if not finished or not keepalive:
                _stop()
            else:
                worker = _worker

                def expire():
                    with _lock:
                        if _worker is worker and _idle is timer:
                            _stop()

                timer = _idle = threading.Timer(keepalive, expire)
                timer.daemon = True
                timer.start()


def render(command, payload, *, timeout, keepalive):
    parts = list(render_parts(command, payload, timeout=timeout, keepalive=keepalive))
    if len(parts) != 1:
        raise ValueError('Unexpected multipart voice response')
    return parts[0]
