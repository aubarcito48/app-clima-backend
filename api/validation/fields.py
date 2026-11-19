"""Normalización común de texto de entrada."""
import unicodedata
from django import forms

class NormalizedTextField(forms.CharField):
    def to_python(self, value):
        text = unicodedata.normalize("NFC", " ".join(super().to_python(value).split()))
        if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in text):
            raise forms.ValidationError("No se admiten caracteres de control o invisibles.")
        return text
