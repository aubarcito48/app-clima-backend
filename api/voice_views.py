"""Audio opcional: el fallo de voz nunca modifica la consulta del clima."""

import json
import unicodedata

from django.http import HttpResponse
from django.views.decorators.cache import never_cache

from .responses import error_response
from .services.voice import MAX_TEXT, VoiceBusy, VoiceUnavailable, synthesize


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
    text = payload.get('texto') if isinstance(payload, dict) and set(payload) == {'texto'} else None
    if (not isinstance(text, str) or not 1 <= len(text.strip()) <= MAX_TEXT
            or len(text) > MAX_TEXT or any(unicodedata.category(char) in {'Cc', 'Cf', 'Cs'}
                                         and char not in '\n\r\t' for char in text)):
        return error_response('ENTRADA_INVALIDA', 'Enviá entre 1 y 600 caracteres de texto.', status=400)
    try:
        audio = synthesize(text)
    except VoiceBusy:
        response = error_response('VOZ_OCUPADA', 'Isa está ocupada. Volvé a intentar en unos segundos.', status=429)
        response['Retry-After'] = '5'
        return response
    except VoiceUnavailable:
        return error_response('VOZ_NO_DISPONIBLE', 'La voz de Isa no está disponible por el momento.', status=503)
    response = HttpResponse(audio, content_type='audio/wav')
    response['X-Content-Type-Options'] = 'nosniff'
    return response
