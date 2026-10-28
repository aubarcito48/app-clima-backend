"""Audio opcional: el fallo de voz nunca modifica la consulta del clima."""

import json

from django.http import HttpResponse
from django.views.decorators.cache import never_cache

from .responses import error_response
from .services.voice import MAX_TEXT, VoiceBusy, VoiceUnavailable, synthesize


@never_cache
def voice(request):
    if request.method != 'POST':
        response = error_response('METODO_NO_PERMITIDO', 'Este endpoint admite únicamente POST.', status=405)
        response['Allow'] = 'POST'
        return response
    if request.content_type != 'application/json':
        return error_response('ENTRADA_INVALIDA', 'Enviá un objeto JSON con texto.', status=415)
    # No se admiten formularios ni voces/rutas elegidas desde el cliente.
    if len(request.body) > 8192:
        return error_response('ENTRADA_INVALIDA', 'El texto es demasiado largo.', status=413)
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        payload = None
    text = payload.get('texto') if isinstance(payload, dict) and set(payload) == {'texto'} else None
    if (not isinstance(text, str) or not 1 <= len(text.strip()) <= MAX_TEXT
            or len(text) > MAX_TEXT or any(ord(char) < 32 and char not in '\n\r\t' for char in text)):
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
