from copy import deepcopy
import http.client
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from jsonschema import Draft202012Validator

from config.settings.environment import env_timeout
from .services.geocoding import (
    AmbiguousLocation, GeoLocation, GeocodingFailure, GeocodingRateLimited,
    IncompleteLocationSearch, LocationNotFound, MAX_RESPONSE_BYTES,
    OpenWeatherGeocoding, resolve_location,
)
from .validation import ClimateQuery


FIRST = {"name": "Cordoba", "local_names": {"es": "Córdoba"}, "country": "AR", "state": "Córdoba", "lat": -31.42, "lon": -64.18}
SECOND = {"name": "Cordoba", "country": "ES", "state": "Andalucía", "lat": 37.88, "lon": -4.78}


class IsolatedGeocodingTests(SimpleTestCase):
    def setUp(self):
        for name in [
            "socket.create_connection", "socket.socket.connect",
            "django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection",
        ]:
            blocker = patch(name, side_effect=AssertionError("Las pruebas no deben usar red ni BD"))
            blocker.start()
            self.addCleanup(blocker.stop)


@override_settings(
    OPENWEATHER_API_KEY="DUMMY-GEOCODING-KEY",
    OPENWEATHER_CONNECT_TIMEOUT_SECONDS=3,
    OPENWEATHER_READ_TIMEOUT_SECONDS=5,
)
class GeocodingTransportTests(IsolatedGeocodingTests):
    def setUp(self):
        super().setUp()
        factory = patch("api.services.geocoding.http.client.HTTPSConnection")
        self.factory = factory.start()
        self.addCleanup(factory.stop)
        self.connection = self.factory.return_value
        self.response = self.connection.getresponse.return_value
        self.response.status = 200
        self.response.read.return_value = b"[]"

    def test_https_host_path_and_each_query_parameter_are_fixed_or_encoded(self):
        query = ClimateQuery("São Tomé & Príncipe + #1/2?", "ST", "Región de prueba")
        with override_settings(OPENWEATHER_API_KEY="DUMMY key&+?#"):
            self.assertEqual(OpenWeatherGeocoding().search(query), [])
        self.factory.assert_called_once_with("api.openweathermap.org", timeout=3)
        self.connection.connect.assert_called_once_with()
        self.connection.sock.settimeout.assert_called_once_with(5)
        args, kwargs = self.connection.request.call_args
        self.assertEqual(args[0], "GET")
        target = urlsplit(args[1])
        self.assertEqual(target.path, "/geo/1.0/direct")
        self.assertEqual(target.netloc, "")
        self.assertEqual(parse_qs(target.query), {
            "q": [query.ciudad + ",ST"], "limit": ["5"], "appid": ["DUMMY key&+?#"],
        })
        self.assertEqual(kwargs["headers"], {"Accept": "application/json"})
        self.response.read.assert_called_once_with(MAX_RESPONSE_BYTES + 1)
        self.connection.close.assert_called_once_with()

    def test_region_is_not_inserted_as_a_us_state_code_for_another_country(self):
        OpenWeatherGeocoding().search(ClimateQuery("Córdoba", "AR", "Córdoba"))
        target = self.connection.request.call_args.args[1]
        self.assertEqual(parse_qs(urlsplit(target).query)["q"], ["Córdoba,AR"])

    @override_settings(OPENWEATHER_API_KEY=" ")
    def test_missing_key_does_not_create_a_connection(self):
        with self.assertRaises(GeocodingFailure):
            OpenWeatherGeocoding().search(ClimateQuery("Córdoba"))
        self.factory.assert_not_called()

    def test_upstream_errors_are_sanitized_and_redirects_are_not_followed(self):
        for status in [301, 302, 307, 400, 401, 403, 404, 500, 503]:
            with self.subTest(status=status):
                self.connection.request.reset_mock()
                self.response.read.reset_mock()
                self.response.status = status
                self.response.read.return_value = b"private upstream body appid=DUMMY-GEOCODING-KEY"
                with self.assertRaises(GeocodingFailure) as failure:
                    OpenWeatherGeocoding().search(ClimateQuery("Córdoba"))
                self.assertEqual(failure.exception.status, 503)
                self.assertNotIn("DUMMY-GEOCODING-KEY", str(failure.exception))
                self.response.read.assert_not_called()
                self.connection.request.assert_called_once()

    def test_rate_limit_is_mapped_to_429_without_copying_its_body(self):
        self.response.status = 429
        with self.assertRaises(GeocodingRateLimited) as failure:
            OpenWeatherGeocoding().search(ClimateQuery("Córdoba"))
        self.assertEqual(failure.exception.code, "LIMITE_ALCANZADO")
        self.response.read.assert_not_called()
        self.connection.close.assert_called_once_with()

    def test_connect_request_headers_and_read_failures_close_the_connection_without_retry(self):
        for phase in ["connect", "request", "getresponse", "read"]:
            with self.subTest(phase=phase):
                target = self.response.read if phase == "read" else getattr(self.connection, phase)
                target.side_effect = TimeoutError("https://example.invalid/?appid=DUMMY-GEOCODING-KEY")
                self.connection.close.reset_mock()
                with self.assertRaises(GeocodingFailure) as failure:
                    OpenWeatherGeocoding().search(ClimateQuery("Córdoba"))
                self.assertNotIn("DUMMY-GEOCODING-KEY", str(failure.exception))
                self.assertTrue(failure.exception.__suppress_context__)
                self.connection.close.assert_called_once_with()
                target.side_effect = None

    def test_protocol_errors_are_controlled(self):
        self.connection.getresponse.side_effect = http.client.BadStatusLine("private body")
        with self.assertRaises(GeocodingFailure):
            OpenWeatherGeocoding().search(ClimateQuery("Córdoba"))
        self.connection.close.assert_called_once_with()

    def test_non_json_non_list_non_finite_and_oversized_payloads_are_rejected(self):
        for body in [b"not json", b"{}", b"null", b"[NaN]", b"\xff", b"x" * (MAX_RESPONSE_BYTES + 1), b"[{}, {}, {}, {}, {}, {}]"]:
            with self.subTest(body_type=body[:20]):
                self.response.read.return_value = body
                with self.assertRaises(GeocodingFailure):
                    OpenWeatherGeocoding().search(ClimateQuery("Córdoba"))


class LocationResolutionTests(IsolatedGeocodingTests):
    def resolve(self, rows, query=None):
        client = Mock()
        client.search.return_value = rows
        return resolve_location(query or ClimateQuery("Córdoba"), client=client)

    def test_one_location_returns_normalized_name_country_region_and_coordinates(self):
        result = self.resolve([deepcopy(FIRST)], ClimateQuery("Córdoba", "AR"))
        self.assertEqual(result, GeoLocation("Córdoba", "AR", "Córdoba", -31.42, -64.18))
        self.assertEqual(set(result.as_candidate()), {"nombre", "pais", "region", "latitud", "longitud"})

    def test_region_can_be_absent_and_zero_coordinates_are_valid(self):
        result = self.resolve([{"name": "Example", "country": "AR", "lat": 0, "lon": 0}])
        self.assertIsNone(result.region)
        self.assertEqual((result.latitud, result.longitud), (0, 0))

    def test_no_matches_returns_not_found(self):
        with self.assertRaises(LocationNotFound):
            self.resolve([])

    def test_multiple_locations_are_never_resolved_by_selecting_the_first(self):
        with self.assertRaises(AmbiguousLocation) as result:
            self.resolve([deepcopy(FIRST), deepcopy(SECOND)])
        self.assertEqual(len(result.exception.candidates), 2)
        self.assertEqual(result.exception.status, 409)

    def test_country_filter_resolves_a_previously_ambiguous_search(self):
        result = self.resolve([deepcopy(FIRST), deepcopy(SECOND)], ClimateQuery("Córdoba", "AR"))
        self.assertEqual(result.pais, "AR")
        with self.assertRaises(LocationNotFound):
            self.resolve([deepcopy(SECOND)], ClimateQuery("Córdoba", "AR"))

    def test_region_filter_handles_accents_case_and_spaces(self):
        another_region = {**FIRST, "state": "Buenos Aires", "lat": -34.5}
        result = self.resolve([deepcopy(FIRST), another_region], ClimateQuery("Córdoba", "AR", "  CORDOBA  "))
        self.assertEqual(result.region, "Córdoba")
        with self.assertRaises(LocationNotFound):
            self.resolve([deepcopy(FIRST)], ClimateQuery("Córdoba", "AR", "Mendoza"))

    def test_country_or_region_does_not_hide_remaining_ambiguity(self):
        same_region = {**FIRST, "lat": -32}
        with self.assertRaises(AmbiguousLocation):
            self.resolve([deepcopy(FIRST), same_region], ClimateQuery("Córdoba", "AR", "Córdoba"))

    def test_duplicate_coordinates_do_not_create_false_ambiguity(self):
        result = self.resolve([deepcopy(FIRST), {**FIRST, "name": "Alias"}])
        self.assertEqual(result.nombre, "Córdoba")

    def test_a_malformed_row_is_not_discarded_to_force_a_unique_match(self):
        for item in [None, "bad", {}, {**FIRST, "lat": None}]:
            with self.subTest(item_type=type(item).__name__), self.assertRaises(GeocodingFailure):
                self.resolve([deepcopy(FIRST), item], ClimateQuery("Córdoba", "AR"))

    def test_invalid_fields_and_coordinates_are_controlled(self):
        changes = [
            {"lat": True}, {"lat": "1"}, {"lat": float("nan")}, {"lat": 91},
            {"lat": 10**500}, {"lon": -181}, {"lon": float("inf")},
            {"name": ""}, {"name": "A\u200bB"}, {"country": "Argentina"},
            {"state": 123}, {"local_names": {"es": ["not text"]}},
        ]
        for change in changes:
            with self.subTest(fields=list(change)), self.assertRaises(GeocodingFailure):
                self.resolve([{**FIRST, **change}])

    def test_saturated_results_cannot_claim_uniqueness_or_absence_after_filtering(self):
        for country in ["AR", "ES"]:
            with self.subTest(country=country), self.assertRaises(IncompleteLocationSearch):
                self.resolve([deepcopy(FIRST) for _ in range(5)], ClimateQuery("Córdoba", country))

    def test_five_different_locations_still_return_candidates(self):
        rows = [{**FIRST, "lat": -30 - index} for index in range(5)]
        with self.assertRaises(AmbiguousLocation) as failure:
            self.resolve(rows)
        self.assertEqual(len(failure.exception.candidates), 5)


@override_settings(ALLOWED_HOSTS=["testserver"])
class GeocodingEndpointTests(IsolatedGeocodingTests):
    def setUp(self):
        super().setUp()
        schema = Path(__file__).with_name("contracts") / "response-v1.schema.json"
        self.validator = Draft202012Validator(json.loads(schema.read_text(encoding="utf-8")))

    def request_with_rows(self, rows, params=None):
        with patch("api.services.geocoding.OpenWeatherGeocoding.search", return_value=rows) as search:
            response = self.client.get("/api/v1/clima/", params or {"ciudad": "Córdoba"})
        self.validator.validate(response.json())
        search.assert_called_once()
        return response

    def test_empty_geocoding_results_are_exposed_as_404(self):
        response = self.request_with_rows([])
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["codigo"], "CIUDAD_NO_ENCONTRADA")

    def test_ambiguity_is_exposed_as_409_with_only_public_candidate_fields(self):
        rows = [{**FIRST, "appid": "PRIVATE-UPSTREAM-DATA"}, deepcopy(SECOND)]
        response = self.request_with_rows(rows)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["codigo"], "CIUDAD_AMBIGUA")
        self.assertEqual(len(response.json()["candidatos"]), 2)
        self.assertNotIn("PRIVATE-UPSTREAM-DATA", response.content.decode())

    def test_refined_query_resolves_location_but_does_not_pretend_to_return_weather(self):
        response = self.request_with_rows([deepcopy(FIRST), deepcopy(SECOND)], {"ciudad": "Córdoba", "pais": "AR", "region": "Córdoba"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(set(response.json()), {"codigo", "mensaje"})

    def test_provider_rate_limit_and_failure_use_the_agreed_http_contract(self):
        for failure in [GeocodingRateLimited(), GeocodingFailure()]:
            with self.subTest(code=failure.code), patch("api.views.resolve_location", side_effect=failure):
                response = self.client.get("/api/v1/clima/", {"ciudad": "Córdoba"})
                self.assertEqual(response.status_code, failure.status)
                self.assertEqual(response.json()["codigo"], failure.code)
                self.validator.validate(response.json())

    def test_invalid_input_health_and_unsupported_methods_never_call_geocoding(self):
        with patch("api.services.geocoding.OpenWeatherGeocoding.search") as search:
            self.assertEqual(self.client.get("/api/v1/clima/", {"ciudad": " "}).status_code, 400)
            self.assertEqual(self.client.get("/api/v1/health/").status_code, 200)
            self.assertEqual(self.client.post("/api/v1/clima/").status_code, 405)
        search.assert_not_called()

    @override_settings(OPENWEATHER_API_KEY="")
    def test_missing_key_returns_safe_503_without_network(self):
        response = self.client.get("/api/v1/clima/", {"ciudad": "Córdoba"})
        self.assertEqual(response.status_code, 503)
        self.validator.validate(response.json())


class TimeoutConfigurationTests(SimpleTestCase):
    def test_timeouts_must_be_finite_positive_and_bounded(self):
        for value in ["0", "-1", "NaN", "inf", "31", "not a number"]:
            with self.subTest(value=value), patch.dict(os.environ, {"TEST_TIMEOUT": value}):
                with self.assertRaises(ImproperlyConfigured):
                    env_timeout("TEST_TIMEOUT", 3)
        with patch.dict(os.environ, {"TEST_TIMEOUT": " 2.5 "}):
            self.assertEqual(env_timeout("TEST_TIMEOUT", 3), 2.5)
