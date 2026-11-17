"""No live requests: concurrent reservations, cache isolation and safe degradation."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.http import HttpResponse
from django.test import SimpleTestCase, RequestFactory, override_settings
import httpx

from .request_limits import ApiRequestLimitsMiddleware, RequestBudget, visitor_key
from .services.climate import query_climate
from .services.groq_guard import AdviceBudget, cache_key
from .services.recommendations import build_messages, generate_recommendation
from .test_recommendations import weather_snapshot, completion


@override_settings(GROQ_GUARD_ENABLED=True, GROQ_API_KEY='DUMMY', GROQ_MODEL='test-model',
                   GROQ_DAILY_REQUEST_LIMIT=2, GROQ_CACHE_TTL_SECONDS=300, GROQ_CACHE_MAX_ENTRIES=10)
class GuardTests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=os.getenv('GROQ_BUDGET_TEST_ROOT'))
        self.addCleanup(self.directory.cleanup)
        self.path = str(Path(self.directory.name) / 'budget.sqlite3')
        config = override_settings(GROQ_BUDGET_PATH=self.path)
        config.enable()
        self.addCleanup(config.disable)
        self.calls = []

    def generate(self, snapshot=None, language='es', status=200):
        def respond(request):
            self.calls.append(request)
            return httpx.Response(status, json=completion())
        return generate_recommendation(snapshot or weather_snapshot(), language=language,
                                       transport=httpx.MockTransport(respond))

    def test_identical_valid_advice_is_reused_and_returned_as_a_copy(self):
        first = self.generate()
        self.assertEqual(first['estado'], 'disponible')
        text = first['texto']
        first['texto'] = 'Mutated caller'
        self.assertEqual(self.generate()['texto'], text)
        self.assertEqual(len(self.calls), 1)

    def test_language_weather_model_and_director_are_separate_cache_keys(self):
        messages = build_messages(weather_snapshot())
        base = cache_key(messages, 'es', 'groq')
        self.assertNotEqual(base, cache_key(messages, 'en', 'groq'))
        self.assertNotEqual(base, cache_key(messages, 'es', 'local'))
        with override_settings(GROQ_MODEL='other'):
            self.assertNotEqual(base, cache_key(messages, 'es', 'groq'))
        changed = weather_snapshot()
        changed.actual['temperatura_c'] += 1
        self.assertNotEqual(base, cache_key(build_messages(changed), 'es', 'groq'))

    def test_budget_denies_new_calls_but_keeps_valid_cached_advice(self):
        self.generate()
        self.generate(language='en')
        changed = weather_snapshot()
        changed.actual['temperatura_c'] += 1
        self.assertEqual(self.generate(changed)['estado'], 'no_disponible')
        self.assertEqual(self.generate()['estado'], 'disponible')
        self.assertEqual(len(self.calls), 2)

    def test_success_cache_expires_and_gets_a_fresh_allowance(self):
        with patch('api.services.groq_guard.time.time', return_value=1763337600):
            self.generate()
        with patch('api.services.groq_guard.time.time', return_value=1763337899):
            self.generate()
        self.assertEqual(len(self.calls), 1)
        with patch('api.services.groq_guard.time.time', return_value=1763337900):
            self.generate()
        self.assertEqual(len(self.calls), 2)

    def test_simultaneous_identical_work_has_one_reservation(self):
        with closing(AdviceBudget(self.path).connect()):
            pass
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: AdviceBudget(self.path).acquire('same')[1], range(20)))
        self.assertEqual(results.count(True), 1)

    def test_invalid_response_is_not_cached_as_advice_and_still_consumes_attempt(self):
        def invalid(request):
            self.calls.append(request)
            return httpx.Response(200, json=completion('', finish='length'))
        result = generate_recommendation(weather_snapshot(), transport=httpx.MockTransport(invalid))
        self.assertEqual(result['estado'], 'no_disponible')
        self.assertEqual(self.generate()['estado'], 'no_disponible')
        self.assertEqual(len(self.calls), 1)

    def test_failed_call_counts_and_same_failure_has_a_cooldown(self):
        self.assertEqual(self.generate(status=429)['estado'], 'no_disponible')
        self.generate(status=429)
        self.assertEqual(len(self.calls), 1)
        self.generate(language='en', status=500)
        changed = weather_snapshot()
        changed.actual['temperatura_c'] += 2
        self.generate(changed)
        self.assertEqual(len(self.calls), 2)

    def test_no_counter_or_broken_storage_never_contacts_groq(self):
        for path in ['', 'relative.sqlite3', self.directory.name]:
            with self.subTest(path=path), override_settings(GROQ_BUDGET_PATH=path):
                self.assertEqual(self.generate()['estado'], 'no_disponible')
        self.assertEqual(self.calls, [])

    @override_settings(GROQ_DAILY_REQUEST_LIMIT=0)
    def test_zero_budget_is_a_kill_switch(self):
        self.assertEqual(self.generate()['estado'], 'no_disponible')
        self.assertEqual(self.calls, [])

    def test_independent_store_instances_share_a_durable_daily_allowance(self):
        self.assertTrue(AdviceBudget(self.path).acquire('a', now=1763337600)[1])
        self.assertTrue(AdviceBudget(self.path).acquire('b', now=1763337600)[1])
        self.assertFalse(AdviceBudget(self.path).acquire('c', now=1763337600)[1])

    def test_parallel_unique_calls_cannot_overspend(self):
        # Initialize schema before simultaneous writers; transaction handles the allowance.
        with closing(AdviceBudget(self.path).connect()) as db:
            db.commit()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda i: AdviceBudget(self.path).acquire(str(i))[1], range(20)))
        self.assertEqual(sum(results), 2)

    def test_same_pending_key_is_coalesced_across_workers(self):
        store = AdviceBudget(self.path)
        self.assertTrue(store.acquire('same')[1])
        self.assertEqual(AdviceBudget(self.path).acquire('same'), (None, False))

    def test_midnight_resets_budget_but_clock_rollback_does_not(self):
        store = AdviceBudget(self.path)
        today = 1763337600
        store.acquire('a', now=today)
        store.acquire('b', now=today)
        self.assertFalse(store.acquire('c', now=today + 200)[1])
        self.assertTrue(store.acquire('c', now=today + 86400)[1])
        self.assertFalse(store.acquire('d', now=today)[1])

    def test_expiry_permits_new_attempt_without_refunding_previous_one(self):
        store = AdviceBudget(self.path)
        store.acquire('a', now=1000)
        self.assertFalse(store.acquire('a', now=1119)[1])
        self.assertTrue(store.acquire('a', now=1120)[1])
        self.assertFalse(store.acquire('a', now=1240)[1])

    @override_settings(GROQ_CACHE_MAX_ENTRIES=1)
    def test_cache_capacity_is_bounded_and_pending_work_is_not_evicted(self):
        store = AdviceBudget(self.path)
        self.assertTrue(store.acquire('a', now=1000)[1])
        self.assertFalse(store.acquire('b', now=1001)[1])
        self.assertTrue(store.acquire('b', now=1120)[1])

    def test_database_contains_no_prompt_or_credential(self):
        self.generate()
        raw = Path(self.path).read_bytes()
        self.assertNotIn(b'DUMMY', raw)
        self.assertNotIn(b'role', raw)
        self.assertNotIn(b'api.groq.com', raw)

    @override_settings(GROQ_BUDGET_PATH='')
    def test_weather_survives_ai_budget_unavailable(self):
        snapshot = weather_snapshot()
        before = deepcopy(snapshot)
        with patch('api.services.climate.resolve_location'), patch(
                'api.services.climate.fetch_weather', return_value=snapshot):
            # Use the public query shape used by the existing weather orchestration.
            from types import SimpleNamespace
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
