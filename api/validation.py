"""Validación de parámetros de la API, independiente de proveedores y persistencia."""

from dataclasses import dataclass
import re
import unicodedata

from django import forms


@dataclass(frozen=True)
class ClimateQuery:
    ciudad: str
    pais: str | None = None
    region: str | None = None
    idioma: str = 'es'


@dataclass(frozen=True)
class CoordinatesQuery:
    latitud: float
    longitud: float
    idioma: str = 'es'


class NormalizedTextField(forms.CharField):
    def to_python(self, value):
        text = unicodedata.normalize("NFC", " ".join(super().to_python(value).split()))
        if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in text):
            raise forms.ValidationError("No se admiten caracteres de control o invisibles.")
        return text


class PlaceSearchForm(forms.Form):
    q = NormalizedTextField(min_length=3, max_length=206)

    def clean(self):
        cleaned = super().clean()
        if any(name != 'q' for name in self.data) or (hasattr(self.data, 'getlist') and len(self.data.getlist('q')) > 1):
            self.add_error(None, 'Enviá únicamente un parámetro q.')
        return cleaned


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


class ClimateQueryForm(forms.Form):
    idioma = forms.ChoiceField(choices=[('es', 'Español'), ('en', 'English')], required=False)
    ciudad = NormalizedTextField(
        required=False,
        max_length=100,
        error_messages={
            "required": "La ciudad es obligatoria y no puede contener solo espacios.",
            "max_length": "La ciudad admite hasta 100 caracteres.",
        },
    )
    pais = NormalizedTextField(
        required=False,
        max_length=2,
        error_messages={"max_length": "Usá un código de país de dos letras, por ejemplo AR."},
    )
    region = NormalizedTextField(
        required=False,
        max_length=100,
        error_messages={"max_length": "La región admite hasta 100 caracteres."},
    )
    latitud = forms.FloatField(required=False, min_value=-90, max_value=90)
    longitud = forms.FloatField(required=False, min_value=-180, max_value=180)

    def clean_pais(self):
        country = self.cleaned_data["pais"]
        if country and not re.fullmatch(r"[A-Za-z]{2}", country):
            raise forms.ValidationError("Usá un código de país de dos letras, por ejemplo AR.")
        return country.upper()

    def clean(self):
        cleaned = super().clean()
        coordinates = any(name in self.data for name in ("latitud", "longitud"))
        if coordinates:
            for name in ("latitud", "longitud"):
                if cleaned.get(name) is None and name not in self.errors:
                    self.add_error(name, "Enviá latitud y longitud válidas juntas.")
            if any(cleaned.get(name) for name in ("ciudad", "pais", "region")):
                self.add_error(None, "Usá un nombre de lugar o coordenadas, sin mezclarlos.")
        elif not cleaned.get("ciudad") and "ciudad" not in self.errors:
            self.add_error("ciudad", "La ciudad es obligatoria y no puede contener solo espacios.")
        if any(name not in self.fields for name in self.data):
            self.add_error(None, "Solo se admiten ciudad, pais, region, latitud, longitud e idioma.")
        if hasattr(self.data, "getlist"):
            for name in self.fields:
                if len(self.data.getlist(name)) > 1:
                    self.add_error(name, "Enviá este parámetro una sola vez.")
        return cleaned

    def query(self):
        if not self.is_valid():
            raise ValueError("No se puede construir una consulta con parámetros inválidos.")
        if self.cleaned_data.get("latitud") is not None:
            return CoordinatesQuery(self.cleaned_data["latitud"], self.cleaned_data["longitud"], self.cleaned_data['idioma'] or 'es')
        return ClimateQuery(
            ciudad=self.cleaned_data["ciudad"],
            pais=self.cleaned_data["pais"] or None,
            region=self.cleaned_data["region"] or None,
            idioma=self.cleaned_data['idioma'] or 'es',
        )

    def public_errors(self):
        return {
            "consulta" if name == "__all__" else name: [str(message) for message in messages]
            for name, messages in self.errors.items()
        }
