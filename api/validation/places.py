"""Validación de búsqueda de lugares."""
from django import forms
from api.validation.fields import NormalizedTextField

class PlaceSearchForm(forms.Form):
    q = NormalizedTextField(min_length=3, max_length=206)

    def clean(self):
        cleaned = super().clean()
        if any(name != 'q' for name in self.data) or (hasattr(self.data, 'getlist') and len(self.data.getlist('q')) > 1):
            self.add_error(None, 'Enviá únicamente un parámetro q.')
        return cleaned
