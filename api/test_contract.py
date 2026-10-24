from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from unittest.mock import patch

from django.http import QueryDict
from django.test import SimpleTestCase, override_settings
from jsonschema import Draft202012Validator, FormatChecker

from .responses import json_response
from .validation import ClimateQuery, ClimateQueryForm
from .services.geocoding import GeoLocation


CONTRACTS = Path(__file__).with_name("contracts")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


date_formats = FormatChecker()


@date_formats.checks("date-time", raises=ValueError)
def valid_datetime(value):
    if not isinstance(value, str):
        return True
    return datetime.fromisoformat(value).tzinfo is not None


@override_settings(ALLOWED_HOSTS=["testserver"])
class ApiEntryTests(SimpleTestCase):
    def setUp(self):
        resolver = patch(
            "api.views.resolve_location",
            return_value=GeoLocation("Córdoba", "AR", "Córdoba", -31.42, -64.18),
        )
        self.resolver = resolver.start()
        self.addCleanup(resolver.stop)
        # Si un endpoint intenta acceder a red o BD, la prueba falla.
        for target in (
            "socket.create_connection", "socket.socket.connect",
            "django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection",
        ):
            patcher = patch(target, side_effect=AssertionError("TK03 no debe acceder a red o BD"))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.validator = Draft202012Validator(
            read_json(CONTRACTS / "response-v1.schema.json"), format_checker=date_formats
        )

    def assert_contract(self, response, status, code=None):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        payload = response.json()
        self.validator.validate(payload)
        if code:
            self.assertEqual(payload["codigo"], code)
        return payload

    @override_settings(OPENWEATHER_API_KEY="", GROQ_API_KEY="")
    def test_health_is_application_liveness_without_providers_or_database(self):
        response = self.client.get("/api/v1/health/")
        self.assertEqual(self.assert_contract(response, 200), {"estado": "ok"})
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.resolver.assert_not_called()

    def test_missing_or_blank_city_is_a_structured_400(self):
        for city in [None, "", "   ", "\t\n", "\u00a0\u2003"]:
            with self.subTest(city=city):
                params = {} if city is None else {"ciudad": city}
                payload = self.assert_contract(
                    self.client.get("/api/v1/clima/", params), 400, "ENTRADA_INVALIDA"
                )
                self.assertIn("ciudad", payload["errores"])
        self.resolver.assert_not_called()

    def test_lengths_are_checked_after_normalizing_spaces(self):
        for field in ["ciudad", "region"]:
            with self.subTest(field=field):
                params = {"ciudad": "Córdoba", field: "x" * 101}
                response = self.client.get("/api/v1/clima/", params)
                self.assertIn(field, self.assert_contract(response, 400, "ENTRADA_INVALIDA")["errores"])
                params[field] = "  " + "x" * 100 + "  "
                self.assert_contract(self.client.get("/api/v1/clima/", params), 503, "SERVICIO_NO_DISPONIBLE")

    def test_country_must_be_two_ascii_letters_when_provided(self):
        for country in ["Argentina", "A", "123", "A1", "ÁR", "ß", "A R"]:
            with self.subTest(country=country):
                payload = self.assert_contract(
                    self.client.get("/api/v1/clima/", {"ciudad": "Córdoba", "pais": country}),
                    400, "ENTRADA_INVALIDA",
                )
                self.assertIn("pais", payload["errores"])

    def test_valid_queries_return_an_honest_503_until_provider_integration(self):
        for params in [
            {"ciudad": "Mendoza"},
            {"ciudad": "  Córdoba  ", "pais": " ar ", "region": "  Córdoba  "},
            {"ciudad": "São Tomé & Príncipe + #1/2?", "pais": "ST"},
        ]:
            with self.subTest(params=params):
                payload = self.assert_contract(
                    self.client.get("/api/v1/clima/", params), 503, "SERVICIO_NO_DISPONIBLE"
                )
                self.assertEqual(set(payload), {"codigo", "mensaje"})

    def test_repeated_and_unknown_parameters_are_rejected(self):
        for query, field in [
            ("ciudad=A&ciudad=B", "ciudad"),
            ("ciudad=A&pais=AR&pais=ES", "pais"),
            ("ciudad=A&region=A&region=B", "region"),
            ("ciudad=A&url=https%3A%2F%2Fexample.invalid", "consulta"),
        ]:
            with self.subTest(query=query):
                payload = self.assert_contract(
                    self.client.get("/api/v1/clima/?" + query), 400, "ENTRADA_INVALIDA"
                )
                self.assertIn(field, payload["errores"])

    def test_invisible_and_control_characters_are_rejected(self):
        for field in ["ciudad", "pais", "region"]:
            for value in ["a\x00b", "a\u200bb"]:
                with self.subTest(field=field, value=repr(value)):
                    params = {"ciudad": "Córdoba", field: value}
                    response = self.client.get("/api/v1/clima/", params)
                    self.assertIn(field, self.assert_contract(response, 400, "ENTRADA_INVALIDA")["errores"])

    def test_unsupported_methods_return_json_405_and_allow_header(self):
        for path in ["/api/v1/health/", "/api/v1/clima/"]:
            for method in ["POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "HEAD"]:
                with self.subTest(path=path, method=method):
                    response = self.client.generic(method, path)
                    self.assertEqual(response.headers["Allow"], "GET")
                    if method == "HEAD":
                        self.assertEqual(response.status_code, 405)
                        self.assertEqual(response.content, b"")
                    else:
                        self.assert_contract(response, 405, "METODO_NO_PERMITIDO")

    def test_authorized_cors_preflight_still_returns_200(self):
        with override_settings(CORS_ALLOWED_ORIGINS=["http://localhost:4200"]):
            response = self.client.options(
                "/api/v1/clima/",
                HTTP_ORIGIN="http://localhost:4200",
                HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "http://localhost:4200")

    @override_settings(SECRET_KEY="SECRET-FOR-TESTS", OPENWEATHER_API_KEY="WEATHER-TEST-KEY", GROQ_API_KEY="GROQ-TEST-KEY")
    def test_json_responses_never_include_private_configuration_or_user_values(self):
        for path in ["/api/v1/health/", "/api/v1/clima/", "/api/v1/clima/?ciudad=Mendoza"]:
            body = self.client.get(path).content.decode()
            self.assertNotIn("SECRET-FOR-TESTS", body)
            self.assertNotIn("WEATHER-TEST-KEY", body)
            self.assertNotIn("GROQ-TEST-KEY", body)


class ClimateQueryValidationTests(SimpleTestCase):
    def test_normalizes_unicode_spaces_country_and_region_without_modifying_input(self):
        raw = {"ciudad": "  Co\u0301rdoba  ", "pais": " ar ", "region": "  San\t Miguel\n de  Tucumán  "}
        form = ClimateQueryForm(raw)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.query(), ClimateQuery("Córdoba", "AR", "San Miguel de Tucumán"))
        self.assertEqual(raw["pais"], " ar ")

    def test_optional_blank_parameters_become_none(self):
        form = ClimateQueryForm({"ciudad": "Mendoza", "pais": " ", "region": " "})
        self.assertEqual(form.query(), ClimateQuery("Mendoza"))

    def test_encoded_parameters_round_trip_without_becoming_extra_fields(self):
        params = QueryDict("ciudad=S%C3%A3o+Tom%C3%A9+%26+Pr%C3%ADncipe+%2B+%231%2F2%3F&pais=st")
        form = ClimateQueryForm(params)
        self.assertEqual(form.query(), ClimateQuery("São Tomé & Príncipe + #1/2?", "ST"))

    def test_invalid_forms_cannot_construct_a_query(self):
        with self.assertRaises(ValueError):
            ClimateQueryForm({}).query()


class ResponseSchemaTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.schema = read_json(CONTRACTS / "response-v1.schema.json")
        cls.validator = Draft202012Validator(cls.schema, format_checker=date_formats)

    def test_schema_is_valid_and_all_versioned_examples_conform(self):
        Draft202012Validator.check_schema(self.schema)
        for path in (CONTRACTS / "examples").glob("*.json"):
            with self.subTest(example=path.name):
                self.validator.validate(read_json(path))

    def test_zero_negative_and_optional_null_weather_values_are_valid(self):
        payload = read_json(CONTRACTS / "examples" / "success.json")
        payload["actual"].update(temperatura_c=0, sensacion_c=-5, humedad_pct=None, viento_kmh=0, descripcion=None)
        payload["pronostico"]["intervalos"][0]["temperatura_c"] = -2
        self.validator.validate(payload)

    def test_forecast_and_ai_can_each_be_unavailable_without_losing_current_weather(self):
        for forecast_unavailable, ai_unavailable in [(True, False), (False, True), (True, True)]:
            with self.subTest(forecast=forecast_unavailable, ai=ai_unavailable):
                payload = read_json(CONTRACTS / "examples" / "success.json")
                if forecast_unavailable:
                    payload["pronostico"] = {"estado": "no_disponible", "intervalos": []}
                if ai_unavailable:
                    payload["recomendacion"] = {"estado": "no_disponible", "texto": None}
                self.validator.validate(payload)

    def test_contradictory_or_incomplete_payloads_are_rejected(self):
        original = read_json(CONTRACTS / "examples" / "success.json")
        changes = [
            lambda p: p.pop("ubicacion"),
            lambda p: p["meta"]["unidades"].update(viento="m/s"),
            lambda p: p["actual"].update(fecha_utc="2026-02-30T00:00:00Z"),
            lambda p: p["actual"].update(fecha_utc="2026-10-24T14:00:00-03:00"),
            lambda p: p["actual"].update(humedad_pct=101),
            lambda p: p["actual"].update(viento_kmh=-1),
            lambda p: p.update(recomendacion={"estado": "no_disponible", "texto": "inventado"}),
            lambda p: p.update(pronostico={"estado": "disponible", "intervalos": []}),
            lambda p: p.update(secret="no debe existir en el contrato"),
        ]
        for index, change in enumerate(changes):
            with self.subTest(case=index):
                payload = deepcopy(original)
                change(payload)
                self.assertTrue(list(self.validator.iter_errors(payload)))

    def test_ambiguity_requires_candidates_and_invalid_input_requires_field_errors(self):
        for payload in [
            {"codigo": "CIUDAD_AMBIGUA", "mensaje": "Precisá la ubicación."},
            {"codigo": "ENTRADA_INVALIDA", "mensaje": "Revisá los parámetros."},
        ]:
            with self.subTest(code=payload["codigo"]):
                self.assertTrue(list(self.validator.iter_errors(payload)))

    def test_non_finite_numbers_cannot_be_serialized_as_json(self):
        for value in [float("nan"), float("inf"), float("-inf")]:
            with self.subTest(value=str(value)), self.assertRaises(ValueError):
                json_response({"temperatura_c": value})
