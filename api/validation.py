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


class NormalizedTextField(forms.CharField):
    def to_python(self, value):
        text = unicodedata.normalize("NFC", " ".join(super().to_python(value).split()))
        if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in text):
            raise forms.ValidationError("No se admiten caracteres de control o invisibles.")
        return text


class ClimateQueryForm(forms.Form):
    ciudad = NormalizedTextField(
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

    def clean_pais(self):
        country = self.cleaned_data["pais"]
        if country and not re.fullmatch(r"[A-Za-z]{2}", country):
            raise forms.ValidationError("Usá un código de país de dos letras, por ejemplo AR.")
        return country.upper()

    def clean(self):
        cleaned = super().clean()
        if any(name not in self.fields for name in self.data):
            self.add_error(None, "Solo se admiten los parámetros ciudad, pais y region.")
        if hasattr(self.data, "getlist"):
            for name in self.fields:
                if len(self.data.getlist(name)) > 1:
                    self.add_error(name, "Enviá este parámetro una sola vez.")
        return cleaned

    def query(self):
        if not self.is_valid():
            raise ValueError("No se puede construir una consulta con parámetros inválidos.")
        return ClimateQuery(
            ciudad=self.cleaned_data["ciudad"],
            pais=self.cleaned_data["pais"] or None,
            region=self.cleaned_data["region"] or None,
        )

    def public_errors(self):
        return {
            "consulta" if name == "__all__" else name: [str(message) for message in messages]
            for name, messages in self.errors.items()
        }
