from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from django.test import SimpleTestCase, override_settings
from jsonschema import Draft202012Validator

from .services.geocoding import GeoLocation
from .services.openweather import (
    MAX_RESPONSE_BYTES, OpenWeatherRateLimited, OpenWeatherUnavailable, request_json,
)
from .services.weather import (
    OpenWeatherMeteorology, WeatherFailure, WeatherRateLimited,
    fetch_weather, normalize_current, normalize_forecast,
)


LOCATION = GeoLocation("Córdoba", "AR", "Córdoba", -31.42, -64.18)
# Mediciones ficticias: no dependen del clima real ni de una cuenta externa.
CURRENT = {
    "cod": 200, "dt": 0, "timezone": -10800,
    "main": {"temp": 0, "feels_like": -3, "humidity": 0},
    "wind": {"speed": 2.5}, "weather": [{"description": "  cielo   claro  "}],
}
FORECAST = {
    "cod": "200", "cnt": 3,
    "list": [
        {"dt": 10800, "main": {"temp": -2}, "weather": [{"description": "nublado"}]},
        {"dt": 0, "main": {"temp": 0}},
        {"dt": 21600, "main": {"temp": 5}, "weather": [{"description": "despejado"}]},
    ],
}


class IsolatedWeatherTests(SimpleTestCase):
    def setUp(self):
        for name in [
            "socket.create_connection", "socket.socket.connect",
            "django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection",
        ]:
            blocker = patch(name, side_effect=AssertionError("Las pruebas no deben usar red ni BD"))
            blocker.start()
            self.addCleanup(blocker.stop)


@override_settings(
    OPENWEATHER_API_KEY="DUMMY-WEATHER-KEY",
    OPENWEATHER_CONNECT_TIMEOUT_SECONDS=3,
    OPENWEATHER_READ_TIMEOUT_SECONDS=5,
)
class WeatherTransportTests(IsolatedWeatherTests):
    def setUp(self):
        super().setUp()
        factory = patch("api.services.openweather.http.client.HTTPSConnection")
        self.factory = factory.start()
        self.addCleanup(factory.stop)
        self.connection = self.factory.return_value
        self.response = self.connection.getresponse.return_value
        self.response.status = 200
        self.response.read.return_value = json.dumps(CURRENT).encode()

    def test_current_and_forecast_use_fixed_paths_resolved_coordinates_and_metric_spanish(self):
        client = OpenWeatherMeteorology()
        for method, path in [(client.current, "/data/2.5/weather"), (client.forecast, "/data/2.5/forecast")]:
            with self.subTest(path=path):
                self.factory.reset_mock()
                self.connection.request.reset_mock()
                method(LOCATION)
                self.factory.assert_called_once_with("api.openweathermap.org", timeout=3)
                target = urlsplit(self.connection.request.call_args.args[1])
                self.assertEqual(target.path, path)
                self.assertEqual(parse_qs(target.query), {
                    "lat": ["-31.42"], "lon": ["-64.18"],
                    "units": ["metric"], "lang": ["es"], "appid": ["DUMMY-WEATHER-KEY"],
                })
                self.connection.sock.settimeout.assert_called_with(5)
                self.connection.close.assert_called()

    @override_settings(OPENWEATHER_API_KEY="")
    def test_no_key_means_no_request(self):
        with self.assertRaises(WeatherFailure):
            OpenWeatherMeteorology().current(LOCATION)
        self.factory.assert_not_called()

    def test_unapproved_paths_are_rejected_before_connecting(self):
        with self.assertRaises(ValueError):
            request_json("https://other.example/steal", {})
        self.factory.assert_not_called()

    def test_invalid_coordinates_are_rejected_before_connecting(self):
        for latitude, longitude in [(91, 0), (0, -181), (True, 0), (float("nan"), 0)]:
            with self.subTest(latitude=str(latitude)), self.assertRaises(WeatherFailure):
                OpenWeatherMeteorology().current(GeoLocation("Example", "AR", None, latitude, longitude))
        self.factory.assert_not_called()

    def test_current_rate_limit_and_auth_failures_are_public_safe_errors(self):
        for status, error_type in [(429, WeatherRateLimited), (401, WeatherFailure), (403, WeatherFailure), (503, WeatherFailure)]:
            with self.subTest(status=status):
                self.response.status = status
                self.response.read.reset_mock()
                with self.assertRaises(error_type) as result:
                    OpenWeatherMeteorology().current(LOCATION)
                self.assertNotIn("DUMMY-WEATHER-KEY", str(result.exception))
                self.response.read.assert_not_called()

    def test_timeout_in_current_or_forecast_is_sanitized_and_connection_is_closed(self):
        self.response.read.side_effect = TimeoutError("private appid=DUMMY-WEATHER-KEY")
        for method in [OpenWeatherMeteorology().current, OpenWeatherMeteorology().forecast]:
            with self.subTest(method=method.__name__), self.assertRaises(WeatherFailure) as result:
                method(LOCATION)
            self.assertNotIn("DUMMY-WEATHER-KEY", str(result.exception))
            self.connection.close.assert_called()

    def test_http_200_with_embedded_provider_error_is_not_accepted_as_weather(self):
        for payload, error_type in [({"cod": 401, "message": "private"}, WeatherFailure), ({"cod": "429"}, WeatherRateLimited)]:
            with self.subTest(payload_type=payload["cod"]):
                with self.assertRaises(error_type):
                    normalize_current(payload)

    def test_body_limit_and_bad_json_apply_to_meteorological_requests(self):
        for body in [b"private upstream text", b"{bad-json}", b"x" * (MAX_RESPONSE_BYTES + 1)]:
            with self.subTest(body_size=len(body)), self.assertRaises(WeatherFailure):
                self.response.read.return_value = body
                OpenWeatherMeteorology().current(LOCATION)

    def test_shared_transport_errors_are_translated_to_meteorological_errors(self):
        for error, mapped in [(OpenWeatherUnavailable(), WeatherFailure), (OpenWeatherRateLimited(), WeatherRateLimited)]:
            with self.subTest(error=type(error).__name__), patch("api.services.weather.request_json", side_effect=error):
                with self.assertRaises(mapped):
                    OpenWeatherMeteorology().current(LOCATION)


class CurrentNormalizationTests(IsolatedWeatherTests):
    def test_zero_and_negative_temperature_and_wind_conversion_are_preserved(self):
        result = normalize_current(deepcopy(CURRENT))
        self.assertEqual(result.actual, {
            "fecha_utc": "1970-01-01T00:00:00Z", "temperatura_c": 0,
            "sensacion_c": -3, "humedad_pct": 0, "viento_kmh": 9.0, "descripcion": "cielo claro",
        })
        self.assertEqual(result.desplazamiento_horario_segundos, -10800)

    def test_zero_wind_and_zero_timezone_are_not_treated_as_absent(self):
        data = deepcopy(CURRENT)
        data.update(wind={"speed": 0}, timezone=0)
        result = normalize_current(data)
        self.assertEqual(result.actual["viento_kmh"], 0)
        self.assertEqual(result.desplazamiento_horario_segundos, 0)

    def test_wind_is_converted_once_and_rounded_to_three_decimal_places(self):
        data = deepcopy(CURRENT)
        data["wind"]["speed"] = 1.23456
        self.assertEqual(normalize_current(data).actual["viento_kmh"], 4.444)

    def test_optional_absent_fields_remain_null_without_fabricated_zeroes(self):
        result = normalize_current({"dt": 0, "timezone": 0, "main": {"temp": -8}})
        self.assertEqual(result.actual["temperatura_c"], -8)
        for field in ["sensacion_c", "humedad_pct", "viento_kmh", "descripcion"]:
            self.assertIsNone(result.actual[field])

    def test_empty_optional_descriptions_are_null(self):
        for weather in [None, [], [{}], [{"description": None}], [{"description": "   "}]]:
            with self.subTest(weather=weather):
                data = {**CURRENT, "weather": weather}
                self.assertIsNone(normalize_current(data).actual["descripcion"])

    def test_required_temperature_timestamp_and_offset_cannot_be_missing_or_invalid(self):
        changes = [
            {"main": {}}, {"main": []}, {"dt": None}, {"dt": True},
            {"dt": "0"}, {"dt": 10**30}, {"timezone": None},
            {"timezone": True}, {"timezone": 50401}, {"timezone": -50401},
        ]
        for change in changes:
            with self.subTest(fields=list(change)), self.assertRaises(WeatherFailure):
                normalize_current({**CURRENT, **change})

    def test_invalid_optional_numbers_do_not_turn_into_silent_null_values(self):
        for field, value in [
            ("temp", True), ("temp", "24"), ("temp", float("nan")),
            ("temp", 10**500), ("feels_like", float("inf")),
            ("humidity", -1), ("humidity", 101), ("humidity", False),
        ]:
            with self.subTest(field=field, value=str(value)[:20]), self.assertRaises(WeatherFailure):
                data = deepcopy(CURRENT)
                data["main"][field] = value
                normalize_current(data)

    def test_malformed_wind_weather_and_negative_speed_are_rejected(self):
        for change in [
            {"wind": []}, {"wind": {"speed": -1}}, {"wind": {"speed": float("inf")}},
            {"weather": {}}, {"weather": ["not a condition"]},
            {"weather": [{"description": 5}]}, {"weather": [{"description": "a\u200bb"}]},
        ]:
            with self.subTest(fields=list(change)), self.assertRaises(WeatherFailure):
                normalize_current({**CURRENT, **change})

    def test_normalization_does_not_mutate_provider_payload(self):
        data = deepcopy(CURRENT)
        normalize_current(data)
        self.assertEqual(data, CURRENT)


class ForecastNormalizationTests(IsolatedWeatherTests):
    def test_wind_direction_preserves_north_and_is_optional_for_both_sources(self):
        self.assertEqual(normalize_current({**CURRENT, "wind": {"speed": 2, "deg": 0}}).actual["direccion_viento_grados"], 0)
        data = deepcopy(FORECAST)
        data["list"][0]["wind"] = {"speed": 2, "deg": 360}
        rows = normalize_forecast(data)["intervalos"]
        self.assertEqual(rows[1]["direccion_viento_grados"], 360)
        self.assertNotIn("direccion_viento_grados", rows[0])
        for value in (-1, 361, True, "90", float("nan")):
            with self.subTest(value=value), self.assertRaises(WeatherFailure):
                normalize_current({**CURRENT, "wind": {"deg": value}})
            data["list"][0]["wind"]["deg"] = value
            with self.subTest(forecast=value), self.assertRaises(WeatherFailure):
                normalize_forecast(data)

    def test_interval_wind_is_converted_once_to_kmh_including_zero(self):
        data = deepcopy(FORECAST)
        data["list"][0]["wind"] = {"speed": 1.23456}
        data["list"][1]["wind"] = {"speed": 0}
        rows = normalize_forecast(data)["intervalos"]
        self.assertEqual(rows[0]["viento_kmh"], 0)
        self.assertEqual(rows[1]["viento_kmh"], 4.444)
        self.assertNotIn("viento_kmh", rows[2])

    def test_invalid_interval_wind_is_rejected(self):
        for wind in ([], {"speed": -1}, {"speed": True}, {"speed": float("nan")}):
            data = deepcopy(FORECAST)
            data["list"][0]["wind"] = wind
            with self.subTest(wind=wind), self.assertRaises(WeatherFailure):
                normalize_forecast(data)

    def test_optional_solar_times_and_icon_come_from_the_provider(self):
        data = {**deepcopy(CURRENT), "sys": {"sunrise": 0, "sunset": 43200}, "weather": [{"icon": "01n"}]}
        result = normalize_current(data).actual
        self.assertEqual(result["amanecer_utc"], "1970-01-01T00:00:00Z")
        self.assertEqual(result["atardecer_utc"], "1970-01-01T12:00:00Z")
        self.assertEqual(result["icono"], "01n")
        self.assertNotIn("amanecer_utc", normalize_current(CURRENT).actual)

    def test_optional_rain_probability_is_a_percentage_including_zero(self):
        data = deepcopy(FORECAST)
        data["list"][0].update(pop=0.2, weather=[{"icon": "10d"}])
        data["list"][1]["pop"] = 0
        rows = normalize_forecast(data)["intervalos"]
        self.assertEqual(rows[0]["precipitacion_pct"], 0)
        self.assertEqual(rows[1]["precipitacion_pct"], 20)
        self.assertEqual(rows[1]["icono"], "10d")
        self.assertNotIn("precipitacion_pct", rows[2])

    def test_invalid_probability_and_solar_timestamp_do_not_become_fake_values(self):
        for value in (-0.1, 1.1, True, "0.5"):
            data = deepcopy(FORECAST)
            data["list"][0]["pop"] = value
            with self.subTest(value=value), self.assertRaises(WeatherFailure):
                normalize_forecast(data)
        with self.assertRaises(WeatherFailure):
            normalize_current({**CURRENT, "sys": {"sunrise": True}})

    def test_forecast_is_sorted_by_utc_timestamp_without_daily_averages(self):
        result = normalize_forecast(deepcopy(FORECAST))
        self.assertEqual(result["estado"], "disponible")
        self.assertEqual([row["fecha_utc"] for row in result["intervalos"]], [
            "1970-01-01T00:00:00Z", "1970-01-01T03:00:00Z", "1970-01-01T06:00:00Z",
        ])
        self.assertEqual([row["temperatura_c"] for row in result["intervalos"]], [0, -2, 5])
        self.assertIsNone(result["intervalos"][0]["descripcion"])

    def test_forecast_day_boundaries_keep_utc_instead_of_using_local_dt_txt(self):
        data = {"list": [
            {"dt": 86400, "dt_txt": "ignored", "main": {"temp": 1}},
            {"dt": 75600, "dt_txt": "ignored", "main": {"temp": 2}},
        ]}
        dates = [row["fecha_utc"] for row in normalize_forecast(data)["intervalos"]]
        self.assertEqual(dates, ["1970-01-01T21:00:00Z", "1970-01-02T00:00:00Z"])

    def test_empty_forecast_is_explicitly_unavailable(self):
        self.assertEqual(normalize_forecast({"list": [], "cnt": 0}), {"estado": "no_disponible", "intervalos": []})

    def test_bad_envelopes_counts_and_rows_are_rejected(self):
        payloads = [
            None, [], {}, {"list": {}}, {"list": [None]}, {"list": [{"dt": 0}]},
            {"list": [{"dt": 0, "main": {}}]}, {"list": [], "cnt": True},
            {**FORECAST, "cnt": 4}, {**FORECAST, "cod": "500"},
            {"list": [FORECAST["list"][0]] * 41},
        ]
        for payload in payloads:
            with self.subTest(payload_type=type(payload).__name__), self.assertRaises(WeatherFailure):
                normalize_forecast(payload)

    def test_duplicate_timestamps_are_not_silently_chosen_or_averaged(self):
        with self.assertRaises(WeatherFailure):
            normalize_forecast({"list": [deepcopy(FORECAST["list"][0])] * 2})

    def test_a_single_malformed_interval_invalidates_forecast_instead_of_inventing_data(self):
        for bad in [None, {"dt": True, "main": {"temp": 3}}, {"dt": 1, "main": {"temp": float("nan")}}]:
            with self.subTest(row_type=type(bad).__name__), self.assertRaises(WeatherFailure):
                normalize_forecast({"list": [FORECAST["list"][0], bad]})

    def test_sorting_preserves_the_original_provider_order_and_values(self):
        data = deepcopy(FORECAST)
        normalize_forecast(data)
        self.assertEqual(data, FORECAST)


class WeatherSnapshotTests(IsolatedWeatherTests):
    def weather_client(self):
        client = Mock()
        client.current.return_value = deepcopy(CURRENT)
        client.forecast.return_value = deepcopy(FORECAST)
        return client

    def test_weather_and_forecast_share_the_resolved_location(self):
        client = self.weather_client()
        result = fetch_weather(LOCATION, client=client)
        client.current.assert_called_once_with(LOCATION)
        client.forecast.assert_called_once_with(LOCATION)
        self.assertEqual(result.ubicacion, {**LOCATION.as_candidate(), "desplazamiento_horario_segundos": -10800})
        self.assertEqual(result.actual["temperatura_c"], 0)
        self.assertEqual(result.pronostico["estado"], "disponible")

    def test_current_failure_prevents_a_forecast_request(self):
        client = self.weather_client()
        for error in [WeatherFailure(), WeatherRateLimited()]:
            with self.subTest(error_type=type(error).__name__):
                client.current.side_effect = error
                with self.assertRaises(type(error)):
                    fetch_weather(LOCATION, client=client)
                client.forecast.assert_not_called()

    def test_invalid_current_payload_also_prevents_a_forecast_request(self):
        client = self.weather_client()
        client.current.return_value = {"main": {"temp": None}}
        with self.assertRaises(WeatherFailure):
            fetch_weather(LOCATION, client=client)
        client.forecast.assert_not_called()

    def test_forecast_failures_and_rate_limits_keep_valid_current_weather(self):
        for error in [WeatherFailure(), WeatherRateLimited()]:
            with self.subTest(error_type=type(error).__name__):
                client = self.weather_client()
                client.forecast.side_effect = error
                result = fetch_weather(LOCATION, client=client)
                self.assertEqual(result.actual["temperatura_c"], 0)
                self.assertEqual(result.pronostico, {"estado": "no_disponible", "intervalos": []})

    def test_invalid_forecast_becomes_unavailable_without_losing_current_weather(self):
        client = self.weather_client()
        client.forecast.return_value = {"list": [{"dt": "bad", "main": {"temp": None}}]}
        result = fetch_weather(LOCATION, client=client)
        self.assertEqual(result.actual["viento_kmh"], 9)
        self.assertEqual(result.pronostico["estado"], "no_disponible")

    def test_blocks_conform_to_the_existing_contract_for_full_and_partial_results(self):
        schema_path = Path(__file__).with_name("contracts") / "response-v1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        for bad_forecast in [False, True]:
            with self.subTest(partial=bad_forecast):
                client = self.weather_client()
                if bad_forecast:
                    client.forecast.side_effect = WeatherFailure()
                snapshot = fetch_weather(LOCATION, client=client)
                for field in ["ubicacion", "actual", "pronostico"]:
                    block_schema = {"$ref": f"#/$defs/{field}", "$defs": schema["$defs"]}
                    Draft202012Validator(block_schema).validate(getattr(snapshot, field))
