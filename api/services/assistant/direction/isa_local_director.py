"""Stable public entry point for independent Spanish and English directors."""
from api.services.assistant.direction.isa_director_es import direct_spanish
from api.services.assistant.direction.isa_director_en import direct_english


def direct_locally(text, *, language='es'):
    if language == 'es':
        return direct_spanish(text)
    if language == 'en':
        return direct_english(text)
    raise ValueError('Unsupported language')
