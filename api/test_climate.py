from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
import httpx
from jsonschema import Draft202012Validator

from .services.openweather import OpenWeatherRateLimited, OpenWeatherUnavailable
from .services.recommendations import generate_recommendation


CONTRACTS = Path(__file__).with_name("contracts")
OBSERVED_AT = int(datetime(2026, 10, 24, 17, tzinfo=timezone.utc).timestamp())
CONSULTED_AT = datetime(2026, 10, 24, 17, 1, tzinfo=timezone.utc)
GEO_ROWS = [
    {"name": "Cordoba", "local_names": {"es": "Córdoba"}, "country": "AR", "state": "Córdoba", "lat": -31.42, "lon": -64.18},
    {"name": "Cordoba", "country": "ES", "state": "Andalucía", "lat": 37.88, "lon": -4.78},
]
CURRENT = {
    "cod": 200, "dt": OBSERVED_AT, "timezone": -10800,
    "main": {"temp": 0, "feels_like": -3, "humidity": 0},
    "wind": {"speed": 2.5}, "weather": [{"description": "cielo claro"}],
}
FORECAST = {
    "cod": "200", "cnt": 2,
    "list": [
        {"dt": OBSERVED_AT + 14400, "main": {"temp": -2}},
        {"dt": OBSERVED_AT + 3600, "main": {"temp": 1}, "weather": [{"description": "nublado"}]},
    ],
}


@override_settings(
    ALLOWED_HOSTS=["testserver"],
    CORS_ALLOWED_ORIGINS=["http://localhost:4200"],
    OPENWEATHER_API_KEY="DUMMY-WEATHER-KEY",
    GROQ_API_KEY="DUMMY-GROQ-KEY", GROQ_MODEL="test-chat-model",
)
class ClimateIntegrationTests(SimpleTestCase):
    def setUp(self):
        self.provider_requests = []
        self.groq_requests = []
        self.geo_rows = deepcopy(GEO_ROWS)
        self.current = deepcopy(CURRENT)
        self.forecast = deepcopy(FORECAST)
        self.current_error = None
        self.forecast_error = None
        self.groq_status = 200
        self.groq_error = None
        self.text = "Llevá un abrigo para salir con esta temperatura."
        self.finish_reason = "stop"
        for target in [
            "socket.create_connection", "socket.socket.connect",
            "django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection",
        ]:
            blocker = patch(target, side_effect=AssertionError("No debe usar red ni BD en las pruebas"))
            blocker.start()
            self.addCleanup(blocker.stop)
        for target, effect in [
            ("api.services.geocoding.request_json", self.openweather),
            ("api.services.weather.request_json", self.openweather),
            ("api.services.climate.generate_recommendation", self.recommendation),
        ]:
            mocked = patch(target, side_effect=effect)
            mocked.start()
            self.addCleanup(mocked.stop)
        clock = patch("api.services.climate.timezone.now", return_value=CONSULTED_AT)
        clock.start()
        self.addCleanup(clock.stop)
        schema = json.loads((CONTRACTS / "response-v1.schema.json").read_text(encoding="utf-8"))
        self.validator = Draft202012Validator(schema)

    def openweather(self, path, params):
        self.provider_requests.append((path, deepcopy(params)))
        if path == "/geo/1.0/direct":
            return deepcopy(self.geo_rows)
        if path == "/data/2.5/weather":
            if self.current_error:
                raise self.current_error
            return deepcopy(self.current)
        if path == "/data/2.5/forecast":
            if self.forecast_error:
                raise self.forecast_error
            return deepcopy(self.forecast)
        self.fail("Endpoint externo inesperado")

    def recommendation(self, snapshot):
        # SDK real con HTTP en memoria: no se reemplaza la lógica de recomendación.
        return generate_recommendation(snapshot, transport=httpx.MockTransport(self.groq))

    def groq(self, request):
        self.groq_requests.append(request)
        if self.groq_error:
            raise self.groq_error
        if self.groq_status != 200:
            return httpx.Response(self.groq_status, json={"error": {"message": "PRIVATE-UPSTREAM-BODY DUMMY-GROQ-KEY"}})
        return httpx.Response(200, json={
            "id": "test-completion", "object": "chat.completion", "created": 0,
            "model": "test-chat-model", "choices": [{
                "index": 0, "finish_reason": self.finish_reason,
                "message": {"role": "assistant", "content": self.text},
            }],
        })

    def request(self, params=None, expected_status=200):
        response = self.client.get(
            "/api/v1/clima/", params if params is not None else {"ciudad": "  Córdoba  ", "pais": " ar ", "region": " cordoba "},
            HTTP_ORIGIN="http://localhost:4200",
        )
        self.assertEqual(response.status_code, expected_status)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "http://localhost:4200")
        self.validator.validate(response.json())
        return response

    def test_success_composes_all_blocks_from_the_same_query_and_normalized_location(self):
        response = self.request()
        payload = response.json()
        self.assertEqual(set(payload), {"ubicacion", "actual", "pronostico", "recomendacion", "meta"})
        self.assertEqual(payload["ubicacion"]["nombre"], "Córdoba")
        self.assertEqual(payload["ubicacion"]["pais"], "AR")
        self.assertEqual(payload["ubicacion"]["latitud"], -31.42)
        self.assertEqual(payload["actual"]["temperatura_c"], 0)
        self.assertEqual(payload["actual"]["sensacion_c"], -3)
        self.assertEqual(payload["actual"]["viento_kmh"], 9)
        self.assertEqual(payload["actual"]["fecha_utc"], "2026-10-24T17:00:00Z")
        self.assertEqual([row["temperatura_c"] for row in payload["pronostico"]["intervalos"]], [1, -2])
        self.assertEqual(payload["recomendacion"], {"estado": "disponible", "texto": self.text})
        self.assertEqual(payload["meta"], {
            "fuente_meteorologica": "OpenWeather", "consultado_en_utc": "2026-10-24T17:01:00Z",
            "unidades": {"temperatura": "°C", "viento": "km/h", "humedad": "%", "fecha": "UTC"},
        })
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual([path for path, _ in self.provider_requests], ["/geo/1.0/direct", "/data/2.5/weather", "/data/2.5/forecast"])
        for _, params in self.provider_requests[1:]:
            self.assertEqual((params["lat"], params["lon"]), (-31.42, -64.18))
        context = json.loads(json.loads(self.groq_requests[0].content)["messages"][1]["content"])
        self.assertEqual(context["ubicacion"]["nombre"], payload["ubicacion"]["nombre"])
        self.assertEqual(context["actual"], payload["actual"])

    def test_groq_errors_empty_or_truncated_text_produce_200_with_current_weather(self):
        for failure in ["429", "503", "timeout", "empty", "truncated"]:
            with self.subTest(failure=failure):
                self.groq_status = int(failure) if failure.isdigit() else 200
                self.groq_error = httpx.ReadTimeout("private DUMMY-GROQ-KEY") if failure == "timeout" else None
                self.text = "" if failure == "empty" else "Consejo de prueba."
                self.finish_reason = "length" if failure == "truncated" else "stop"
                self.groq_requests.clear()
                payload = self.request().json()
                self.assertEqual(payload["recomendacion"], {"estado": "no_disponible", "texto": None})
                self.assertEqual(payload["actual"]["temperatura_c"], 0)
                self.assertEqual(payload["pronostico"]["estado"], "disponible")
                self.assertEqual(len(self.groq_requests), 1)

    def test_forecast_failure_keeps_current_weather_and_generates_advice_from_it(self):
        self.forecast_error = OpenWeatherUnavailable()
        payload = self.request().json()
        self.assertEqual(payload["pronostico"], {"estado": "no_disponible", "intervalos": []})
        self.assertEqual(payload["actual"]["viento_kmh"], 9)
        self.assertEqual(payload["recomendacion"]["estado"], "disponible")
        context = json.loads(json.loads(self.groq_requests[0].content)["messages"][1]["content"])
        self.assertEqual(context["pronostico"]["estado"], "no_disponible")
        self.assertEqual(context["pronostico"]["intervalos"], [])

    def test_forecast_and_ai_can_both_be_unavailable_with_http_200(self):
        self.forecast_error = OpenWeatherRateLimited()
        self.groq_status = 503
        payload = self.request().json()
        self.assertEqual(payload["actual"]["temperatura_c"], 0)
        self.assertEqual(payload["pronostico"]["estado"], "no_disponible")
        self.assertEqual(payload["recomendacion"], {"estado": "no_disponible", "texto": None})

    def test_invalid_forecast_payload_preserves_current_weather(self):
        self.forecast = {"cod": "200", "list": [{"dt": "bad", "main": {"temp": None}}]}
        self.assertEqual(self.request().json()["pronostico"]["estado"], "no_disponible")

    def test_current_weather_failure_stops_forecast_and_ai(self):
        for failure, status in [(OpenWeatherUnavailable(), 503), (OpenWeatherRateLimited(), 429)]:
            with self.subTest(status=status):
                self.current_error = failure
                self.provider_requests.clear()
                payload = self.request(expected_status=status).json()
                self.assertEqual(payload["codigo"], "LIMITE_ALCANZADO" if status == 429 else "SERVICIO_NO_DISPONIBLE")
                self.assertEqual([path for path, _ in self.provider_requests], ["/geo/1.0/direct", "/data/2.5/weather"])
                self.assertEqual(self.groq_requests, [])

    def test_invalid_current_weather_also_stops_before_forecast_and_ai(self):
        self.current["main"]["temp"] = None
        self.request(expected_status=503)
        self.assertEqual(len(self.provider_requests), 2)
        self.assertEqual(self.groq_requests, [])

    def test_no_location_or_ambiguous_location_stops_before_weather_and_ai(self):
        for rows, status in [([], 404), (deepcopy(GEO_ROWS), 409)]:
            with self.subTest(status=status):
                self.geo_rows = rows
                self.provider_requests.clear()
                payload = self.request({"ciudad": "Córdoba"}, expected_status=status).json()
                self.assertEqual(len(self.provider_requests), 1)
                self.assertEqual(self.groq_requests, [])
                if status == 409:
                    self.assertEqual(len(payload["candidatos"]), 2)

    def test_validation_health_and_method_errors_never_consult_providers(self):
        self.request({"ciudad": " "}, expected_status=400)
        self.assertEqual(self.client.get("/api/v1/health/").json(), {"estado": "ok"})
        self.assertEqual(self.client.post("/api/v1/clima/").status_code, 405)
        self.assertEqual(self.provider_requests, [])
        self.assertEqual(self.groq_requests, [])

    def test_missing_groq_configuration_is_a_partial_success_not_a_weather_failure(self):
        with override_settings(GROQ_API_KEY="", GROQ_MODEL=""):
            payload = self.request().json()
        self.assertEqual(payload["recomendacion"], {"estado": "no_disponible", "texto": None})
        self.assertEqual(payload["pronostico"]["estado"], "disponible")
        self.assertEqual(self.groq_requests, [])

    def test_optional_null_values_are_not_fabricated_in_full_response(self):
        self.current["main"] = {"temp": -4}
        self.current.pop("wind")
        self.current.pop("weather")
        payload = self.request().json()
        for field in ["sensacion_c", "humedad_pct", "viento_kmh", "descripcion"]:
            self.assertIsNone(payload["actual"][field])
        self.assertEqual(payload["actual"]["temperatura_c"], -4)

    def test_public_response_has_no_credentials_private_provider_fields_or_exceptions(self):
        self.geo_rows[0]["secret"] = "PRIVATE-UPSTREAM-BODY"
        self.current["secret"] = "PRIVATE-UPSTREAM-BODY"
        self.groq_status = 503
        response = self.request()
        for private in ["DUMMY-GROQ-KEY", "DUMMY-WEATHER-KEY", "PRIVATE-UPSTREAM-BODY", "Traceback"]:
            self.assertNotIn(private, response.content.decode())

    def test_sequential_queries_keep_their_own_location_measurements_and_ai_context(self):
        first = self.request().json()
        self.geo_rows = [{"name": "Mendoza", "country": "AR", "state": "Mendoza", "lat": -32.89, "lon": -68.84}]
        self.current["main"]["temp"] = 27
        self.text = "Consejo ficticio para Mendoza."
        second = self.request({"ciudad": "Mendoza", "pais": "AR"}).json()
        self.assertEqual(first["ubicacion"]["nombre"], "Córdoba")
        self.assertEqual(first["actual"]["temperatura_c"], 0)
        self.assertEqual(second["ubicacion"]["nombre"], "Mendoza")
        self.assertEqual(second["actual"]["temperatura_c"], 27)
        context = json.loads(json.loads(self.groq_requests[-1].content)["messages"][1]["content"])
        self.assertEqual(context["ubicacion"]["nombre"], "Mendoza")
        self.assertEqual(context["actual"]["temperatura_c"], 27)
