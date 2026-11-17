"""Cache and visitor protections without disk, database or live provider calls."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponse
from django.test import SimpleTestCase, RequestFactory, override_settings
import httpx

from .request_limits import ApiRequestLimitsMiddleware, RequestBudget, visitor_key
from .services.climate import query_climate
from .services.groq_guard import AdviceCache, cache_key
from .services.recommendations import build_messages, generate_recommendation
from .test_recommendations import weather_snapshot, completion


@override_settings(GROQ_GUARD_ENABLED=True, GROQ_API_KEY='DUMMY', GROQ_MODEL='test-model',
                   GROQ_CACHE_TTL_SECONDS=300, GROQ_CACHE_MAX_ENTRIES=10)
class GuardTests(SimpleTestCase):
    def setUp(self):
        self.cache = AdviceCache()
        patcher = patch('api.services.groq_guard.advice_cache', self.cache)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.calls = []

    def generate(self, snapshot=None, language='es', status=200):
        def respond(request):
            self.calls.append(request)
            return httpx.Response(status, json=completion())
        return generate_recommendation(snapshot or weather_snapshot(), language=language,
                                       transport=httpx.MockTransport(respond))

    def test_valid_advice_is_reused_and_returned_as_a_copy(self):
        first = self.generate()
        self.assertEqual(first['estado'], 'disponible')
        text = first['texto']
        first['texto'] = 'Mutated caller'
        self.assertEqual(self.generate()['texto'], text)
        self.assertEqual(len(self.calls), 1)

    def test_language_weather_model_and_director_are_separate_keys(self):
        messages = build_messages(weather_snapshot())
        base = cache_key(messages, 'es', 'groq')
        self.assertNotEqual(base, cache_key(messages, 'en', 'groq'))
        self.assertNotEqual(base, cache_key(messages, 'es', 'local'))
        with override_settings(GROQ_MODEL='other'):
            self.assertNotEqual(base, cache_key(messages, 'es', 'groq'))
        changed = weather_snapshot()
        changed.actual['temperatura_c'] += 1
        self.assertNotEqual(base, cache_key(build_messages(changed), 'es', 'groq'))

    def test_success_expires_after_five_minutes(self):
        with patch('api.services.groq_guard.time.monotonic', return_value=1000):
            self.generate()
        with patch('api.services.groq_guard.time.monotonic', return_value=1299):
            self.generate()
        self.assertEqual(len(self.calls), 1)
        with patch('api.services.groq_guard.time.monotonic', return_value=1300):
            self.generate()
        self.assertEqual(len(self.calls), 2)

    def test_parallel_identical_work_has_one_reservation(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.cache.acquire('same')[1], range(20)))
        self.assertEqual(sum(token is not None for token in results), 1)

    def test_invalid_response_is_not_cached_as_success(self):
        def invalid(request):
            self.calls.append(request)
            return httpx.Response(200, json=completion('', finish='length'))
        result = generate_recommendation(weather_snapshot(), transport=httpx.MockTransport(invalid))
        self.assertEqual(result['estado'], 'no_disponible')
        self.assertEqual(self.generate()['estado'], 'no_disponible')
        self.assertEqual(len(self.calls), 1)

    def test_failure_cooldown_recovers_after_thirty_seconds(self):
        with patch('api.services.groq_guard.time.monotonic', return_value=1000):
            self.assertEqual(self.generate(status=429)['estado'], 'no_disponible')
        with patch('api.services.groq_guard.time.monotonic', return_value=1029):
            self.generate()
        self.assertEqual(len(self.calls), 1)
        with patch('api.services.groq_guard.time.monotonic', return_value=1030):
            self.assertEqual(self.generate()['estado'], 'disponible')
        self.assertEqual(len(self.calls), 2)

    def test_abandoned_reservation_expires(self):
        self.assertIsNotNone(self.cache.acquire('a', now=1000)[1])
        self.assertIsNone(self.cache.acquire('a', now=1119)[1])
        self.assertIsNotNone(self.cache.acquire('a', now=1120)[1])

    def test_late_completion_cannot_replace_newer_work(self):
        _, old = self.cache.acquire('a', now=1000)
        _, new = self.cache.acquire('a', now=1120)
        good = {'estado': 'disponible', 'texto': 'New advice'}
        with patch('api.services.groq_guard.time.monotonic', return_value=1121):
            self.cache.finish('a', new, good)
            self.cache.finish('a', old, {'estado': 'no_disponible', 'texto': None})
        self.assertEqual(self.cache.acquire('a', now=1122)[0], good)

    @override_settings(GROQ_CACHE_MAX_ENTRIES=1)
    def test_cache_capacity_is_bounded_and_pending_work_is_not_evicted(self):
        self.assertIsNotNone(self.cache.acquire('a', now=1000)[1])
        self.assertIsNone(self.cache.acquire('b', now=1001)[1])
        self.assertEqual(len(self.cache.entries), 1)
        self.assertIsNotNone(self.cache.acquire('b', now=1120)[1])

    def test_no_disk_or_database_is_needed_for_ai(self):
        with patch('sqlite3.connect', side_effect=AssertionError('No database')):
            self.assertEqual(self.generate()['estado'], 'disponible')

    def test_restart_only_clears_cache_and_does_not_disable_ai(self):
        self.generate()
        with patch('api.services.groq_guard.advice_cache', AdviceCache()):
            self.assertEqual(self.generate()['estado'], 'disponible')
        self.assertEqual(len(self.calls), 2)

    def test_weather_survives_provider_unavailable(self):
        snapshot = weather_snapshot()
        before = deepcopy(snapshot)
        with patch('api.services.climate.resolve_location'), patch(
                'api.services.climate.fetch_weather', return_value=snapshot), patch(
                'api.services.recommendations._generate_uncached',
                return_value={'estado': 'no_disponible', 'texto': None}):
            result = query_climate(SimpleNamespace(idioma='es'))
        self.assertEqual(result['actual'], before.actual)
        self.assertEqual(result['pronostico'], before.pronostico)
        self.assertEqual(result['recomendacion']['estado'], 'no_disponible')


@override_settings(API_RATE_LIMIT_ENABLED=True, API_TRUSTED_PROXY_HOPS=0,
                   API_REQUESTS_PER_MINUTE={'/api/v1/clima/': 30},
                   API_VISITOR_REQUESTS_PER_MINUTE={'/api/v1/clima/': 2})
class VisitorTests(SimpleTestCase):
    def test_abusive_visitor_is_blocked_without_consuming_everyones_allowance(self):
        worker = ApiRequestLimitsMiddleware(lambda request: HttpResponse('ok'))
        factory = RequestFactory()
        for i in range(5):
            response = worker(factory.get('/api/v1/clima/', REMOTE_ADDR='192.0.2.1',
                HTTP_X_FORWARDED_FOR=f'198.51.100.{i}'))
            self.assertEqual(response.status_code, 200 if i < 2 else 429)
        self.assertEqual(worker(factory.get('/api/v1/clima/', REMOTE_ADDR='192.0.2.2')).status_code, 200)
        self.assertEqual(response['Retry-After'], '60')

    def test_forwarded_headers_are_ignored_by_default(self):
        factory = RequestFactory()
        first = visitor_key(factory.get('/', REMOTE_ADDR='192.0.2.1', HTTP_X_FORWARDED_FOR='a'))
        second = visitor_key(factory.get('/', REMOTE_ADDR='192.0.2.1', HTTP_X_FORWARDED_FOR='b'))
        self.assertEqual(first, second)
        self.assertNotIn('192.0.2.1', first)

    @override_settings(API_TRUSTED_PROXY_HOPS=1)
    def test_verified_proxy_counts_from_right_and_ignores_spoofed_prefix(self):
        factory = RequestFactory()
        def key(prefix):
            return visitor_key(factory.get('/', HTTP_X_FORWARDED_FOR=f'{prefix}, 192.0.2.1'))
        self.assertEqual(key('a'), key('b'))

    def test_ipv6_privacy_addresses_share_a_network_allowance(self):
        factory = RequestFactory()
        a = visitor_key(factory.get('/', REMOTE_ADDR='2001:db8::1'))
        b = visitor_key(factory.get('/', REMOTE_ADDR='2001:db8::2'))
        self.assertEqual(a, b)

    def test_visitor_memory_is_bounded_and_expired_entries_are_reclaimed(self):
        budget = RequestBudget(capacity=2)
        budget.retry_after('a', 2, 100)
        budget.retry_after('b', 2, 100)
        self.assertEqual(budget.retry_after('c', 2, 100), 60)
        self.assertEqual(len(budget._requests), 2)
        self.assertEqual(budget.retry_after('c', 2, 160), 0)
