"""Regresión HTTP con servicios reales y solo los transportes simulados."""

from copy import deepcopy
import json
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from django.test import SimpleTestCase, override_settings
import httpx
from jsonschema import Draft202012Validator

from .services.recommendations import generate_recommendation
from .test_contract import CONTRACTS, date_formats, read_json


GEO = [{"name": "Cordoba", "country": "AR", "state": "Córdoba", "lat": -31.42, "lon": -64.18}]
CURRENT = {"dt": 1792861200, "timezone": -10800, "main": {"temp": 0, "humidity": 0}, "wind": {"speed": 2.5}}
FORECAST = {"cod": "200", "cnt": 1, "list": [{"dt": 1792872000, "main": {"temp": -2}}]}
PATHS = ["/geo/1.0/direct", "/data/2.5/weather", "/data/2.5/forecast"]


@override_settings(
    ALLOWED_HOSTS=["testserver"], DEBUG=False,
    OPENWEATHER_API_KEY="TEST-WEATHER-KEY", GROQ_API_KEY="TEST-GROQ-KEY", GROQ_MODEL="test-model",
    CORS_ALLOWED_ORIGINS=["http://localhost:4200", "http://127.0.0.1:4200"],
)
class TransportRegressionTests(SimpleTestCase):
    def setUp(self):
        self.responses = dict(zip(PATHS, [deepcopy(GEO), deepcopy(CURRENT), deepcopy(FORECAST)]))
        self.failures = {}
        self.connections = []
        self.requests = []
        self.groq_requests = []
        self.groq_status = 200
        self.validator = Draft202012Validator(
            read_json(CONTRACTS / "response-v1.schema.json"), format_checker=date_formats,
        )
        for target, effect in (
            ("socket.socket.connect", AssertionError("Red externa prohibida")),
            ("sqlite3.connect", AssertionError("SQLite prohibido")),
            ("django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection", AssertionError("BD prohibida")),
            ("api.services.openweather.http.client.HTTPSConnection", self.connection),
            ("api.services.climate.generate_recommendation", self.recommendation),
        ):
            patcher = patch(target, side_effect=effect)
            patcher.start()
            self.addCleanup(patcher.stop)

    def connection(self, host, **kwargs):
        self.assertEqual(host, "api.openweathermap.org")
        connection = Mock()
        self.connections.append(connection)

        def request(method, target, **options):
            self.assertEqual(method, "GET")
            parsed = urlsplit(target)
            self.requests.append((parsed.path, parse_qs(parsed.query)))
            status_or_error = self.failures.get(parsed.path, 200)
            if isinstance(status_or_error, Exception):
                raise status_or_error
            response = connection.getresponse.return_value
            response.status = status_or_error
            body = self.responses[parsed.path]
            response.read.return_value = body if isinstance(body, bytes) else json.dumps(body).encode()

        connection.request.side_effect = request
        return connection

    def recommendation(self, snapshot):
        return generate_recommendation(snapshot, transport=httpx.MockTransport(self.groq))

    def groq(self, request):
        self.groq_requests.append(request)
        self.assertEqual(str(request.url), "https://api.groq.com/openai/v1/chat/completions")
        return httpx.Response(self.groq_status, json={
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": "Llevá abrigo para esta temperatura."
            }}],
        })

    def get(self, params=None, status=200, origin="http://localhost:4200"):
        response = self.client.get("/api/v1/clima/", params or {"ciudad": "Córdoba", "pais": "AR"}, HTTP_ORIGIN=origin)
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.validator.validate(response.json())
        for secret in ("TEST-WEATHER-KEY", "TEST-GROQ-KEY", "PRIVATE-PROVIDER"):
            self.assertNotIn(secret, response.content.decode())
        for connection in self.connections:
            connection.close.assert_called_once_with()
        return response

    def reset_calls(self):
        self.connections.clear()
        self.requests.clear()
        self.groq_requests.clear()

    def test_full_transport_chain_for_every_availability_combination_and_angular_origin(self):
        for origin in ("http://localhost:4200", "http://127.0.0.1:4200"):
            for forecast_ok, ai_ok in ((True, True), (True, False), (False, True), (False, False)):
                with self.subTest(origin=origin, forecast=forecast_ok, ai=ai_ok):
                    self.reset_calls()
                    self.failures = {} if forecast_ok else {PATHS[2]: 429}
                    self.groq_status = 200 if ai_ok else 503
                    response = self.get(origin=origin)
                    payload = response.json()
                    self.assertEqual(response.headers["Access-Control-Allow-Origin"], origin)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertEqual(payload["actual"]["temperatura_c"], 0)
                    self.assertEqual(payload["actual"]["viento_kmh"], 9)
                    self.assertEqual(payload["pronostico"]["estado"], "disponible" if forecast_ok else "no_disponible")
                    self.assertEqual(payload["recomendacion"]["estado"], "disponible" if ai_ok else "no_disponible")
                    self.assertEqual([path for path, _ in self.requests], PATHS)
                    for _, params in self.requests:
                        self.assertEqual(params["appid"], ["TEST-WEATHER-KEY"])
                    for _, params in self.requests[1:]:
                        self.assertEqual((params["lat"], params["lon"]), (["-31.42"], ["-64.18"]))
                    self.assertEqual(len(self.groq_requests), 1)

    def test_geocoding_and_current_transport_failures_stop_downstream_requests(self):
        for index in (0, 1):
            for failure, status in ((429, 429), (401, 503), (503, 503), (TimeoutError("PRIVATE-PROVIDER"), 503)):
                with self.subTest(stage=index, failure=str(failure)):
                    self.reset_calls()
                    self.failures = {PATHS[index]: failure}
                    self.get(status=status)
                    self.assertEqual([path for path, _ in self.requests], PATHS[:index + 1])
                    self.assertEqual(self.groq_requests, [])

    def test_bad_provider_json_is_an_error_for_required_data_and_partial_for_forecast(self):
        for index in range(3):
            with self.subTest(stage=index):
                self.reset_calls()
                self.responses = dict(zip(PATHS, [deepcopy(GEO), deepcopy(CURRENT), deepcopy(FORECAST)]))
                self.responses[PATHS[index]] = b'{"PRIVATE-PROVIDER": NaN}'
                payload = self.get(status=200 if index == 2 else 503).json()
                if index == 2:
                    self.assertEqual(payload["pronostico"], {"estado": "no_disponible", "intervalos": []})
                else:
                    self.assertEqual(self.groq_requests, [])

    def test_ambiguity_can_be_refined_with_a_returned_region_before_fetching_weather(self):
        self.responses[PATHS[0]].append({**GEO[0], "state": "Otra región", "lat": -32})
        ambiguous = self.get(status=409).json()
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.groq_requests, [])
        self.reset_calls()
        candidate = ambiguous["candidatos"][0]
        payload = self.get({"ciudad": candidate["nombre"], "pais": candidate["pais"], "region": candidate["region"]}).json()
        self.assertEqual(payload["ubicacion"]["latitud"], candidate["latitud"])
        self.assertEqual([path for path, _ in self.requests], PATHS)

    def test_invalid_query_matrix_never_opens_a_provider_transport(self):
        for query in ("", "ciudad=", "ciudad=%20", "ciudad=A&pais=Argentina", "ciudad=A&ciudad=B", "ciudad=A&extra=x", "ciudad=A&region=" + "x" * 101):
            with self.subTest(query=query):
                response = self.client.get("/api/v1/clima/?" + query)
                self.assertEqual(response.status_code, 400)
                self.validator.validate(response.json())
        self.assertEqual(self.connections, [])
        self.assertEqual(self.groq_requests, [])
