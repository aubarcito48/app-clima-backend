"""Audio opcional: el fallo de voz nunca modifica la consulta del clima."""

import json
import unicodedata

from django.http import HttpResponse, StreamingHttpResponse
from django.conf import settings
from django.views.decorators.cache import never_cache

from api.responses import error_response
from api.services.assistant.voice.voice import MAX_TEXT
from api.services.assistant.voice.voice import VoiceBusy
from api.services.assistant.voice.voice import VoiceUnavailable
from api.services.assistant.voice.voice import synthesize
from api.services.assistant.direction.isa_performance import read_segments
from api.services.assistant.voice.voice_stream import PreparedStream, synthesize_stream


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


@never_cache
def voice(request):
    if request.method != 'POST':
        response = error_response('METODO_NO_PERMITIDO', 'Este endpoint admite únicamente POST.', status=405)
        response['Allow'] = 'POST'
        return response
    if request.content_type != 'application/json':
        return error_response('ENTRADA_INVALIDA', 'Enviá un objeto JSON con texto.', status=415)
    # No se admiten formularios ni voces/rutas elegidas desde el cliente.
    body = request.read(8193)
    if len(body) > 8192:
        return error_response('ENTRADA_INVALIDA', 'El texto es demasiado largo.', status=413)
    try:
        payload = json.loads(body, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeDecodeError, RecursionError):
        payload = None
    valid = isinstance(payload, dict) and 'texto' in payload and set(payload) <= {'texto', 'idioma', 'segmentos'}
    text = payload.get('texto') if valid else None
    language = payload.get('idioma', 'es') if valid else None
    if not isinstance(language, str) or language not in {'es', 'en'}:
        return error_response('ENTRADA_INVALIDA', 'Idioma no admitido.', status=400)
    if (not isinstance(text, str) or not 1 <= len(text.strip()) <= MAX_TEXT
            or len(text) > MAX_TEXT or any(unicodedata.category(char) in {'Cc', 'Cf', 'Cs'}
                                         and char not in '\n\r\t' for char in text)):
        return error_response('ENTRADA_INVALIDA', 'Enviá entre 1 y 600 caracteres de texto.', status=400)
    options = {} if language == 'es' else {'language': 'en'}
    if 'segmentos' in payload:
        try:
            options['segments'] = read_segments(payload['segmentos'], text, max_segments=6)
        except (ValueError, TypeError, OverflowError):
            return error_response('ENTRADA_INVALIDA', 'Interpretación de Isa inválida.', status=400)
    try:
        if (settings.ISA_VOICE_STREAM_ENABLED
                and 'application/x-ndjson' in request.headers.get('Accept', '').split(',')):
            stream = PreparedStream(synthesize_stream(text, **options))
            response = StreamingHttpResponse(stream, content_type='application/x-ndjson')
            response['X-Accel-Buffering'] = 'no'
            response['X-Content-Type-Options'] = 'nosniff'
            response['Cache-Control'] = 'no-store, no-transform'
            return response
        audio = synthesize(text, **options)
    except VoiceBusy:
        response = error_response('VOZ_OCUPADA', 'Isa está ocupada. Volvé a intentar en unos segundos.', status=429)
        response['Retry-After'] = '5'
        return response
    except VoiceUnavailable:
        return error_response('VOZ_NO_DISPONIBLE', 'La voz de Isa no está disponible por el momento.', status=503)
    response = HttpResponse(audio, content_type='audio/wav')
    response['X-Content-Type-Options'] = 'nosniff'
    return response
