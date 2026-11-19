"""Validación de coordenadas y país para alertas."""
from django import forms

class AlertsQueryForm(forms.Form):
    latitud = forms.FloatField(min_value=-90, max_value=90)
    longitud = forms.FloatField(min_value=-180, max_value=180)
    pais = forms.RegexField(regex=r"^[A-Za-z]{2}$", max_length=2)

    def clean(self):
        cleaned = super().clean()
        if any(key not in self.fields for key in self.data):
            self.add_error(None, 'Parámetros no admitidos.')
        if hasattr(self.data, 'getlist') and any(len(self.data.getlist(key)) > 1 for key in self.fields):
            self.add_error(None, 'Parámetros repetidos.')
        return cleaned
