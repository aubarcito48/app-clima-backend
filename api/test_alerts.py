"""Synthetic CAP fixtures; no provider or database is contacted."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
import httpx

from .services import alerts
DOWNLOAD = alerts._download

NOW = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
PREFIX = 'https://ssl.smn.gob.ar/feeds/CAP/xml_generados/'
POLYGON = '<polygon>-33,-66 -30,-66 -30,-62 -33,-62 -33,-66</polygon>'


def cap(identifier='first', geometry=POLYGON, kind='Alert', references='', status='Actual', scope='Public', expires='2026-10-26T12:00:00Z'):
    return f'''<alert xmlns="{alerts.NS['c']}">
    <identifier>{identifier}</identifier><sender>smn@smn.gob.ar</sender>
    <sent>2026-10-25T10:00:00Z</sent><status>{status}</status><scope>{scope}</scope>
    <msgType>{kind}</msgType><references>{references}</references><info>
    <language>es-AR</language><event>Tormentas de prueba</event><severity>Moderate</severity>
    <urgency>Future</urgency><certainty>Likely</certainty><onset>2026-10-25T13:00:00Z</onset>
    <expires>{expires}</expires><description>Aviso ficticio, no es una alerta real.</description>
    <instruction>Recomendación oficial ficticia.</instruction><area><areaDesc>Zona de prueba</areaDesc>{geometry}</area>
    </info></alert>'''.encode()


def feed(*names, published='Sun, 25 Oct 2026 12:00:00 GMT'):
    items = ''.join(f'<item><link>{PREFIX}{name}.xml</link></item>' for name in names)
    return f'<rss><channel><lastBuildDate>{published}</lastBuildDate>{items}</channel></rss>'.encode()


@override_settings(ALLOWED_HOSTS=['testserver'])
class OfficialAlertsTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.clock = patch('api.services.alerts.timezone.now', return_value=NOW).start()
        self.download = patch('api.services.alerts._download').start()
        self.documents = {alerts.FEED: feed('notice'), PREFIX + 'notice.xml': cap()}
        self.download.side_effect = lambda client, url: self.documents[url]
        self.addCleanup(patch.stopall)
        self.addCleanup(cache.clear)

    def query(self, **params):
        return self.client.get('/api/v1/alertas/', {'latitud': -31.4, 'longitud': -64.2, 'pais': 'AR', **params})

    @patch('api.services.climate.query_climate')
    @patch('api.services.recommendations.generate_recommendation')
    def test_location_matched_official_notice_and_future_period(self, groq, weather):
        response = self.query()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['estado'], 'disponible')
        self.assertEqual(body['alertas'][0]['fenomeno'], 'Tormentas de prueba')
        self.assertEqual(body['alertas'][0]['severidad'], 'Moderate')
        self.assertEqual(body['alertas'][0]['recomendaciones'], 'Recomendación oficial ficticia.')
        self.assertNotIn('shapes', body['alertas'][0])
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(body['fuente']['publicado_en_utc'], '2026-10-25T12:00:00Z')
        groq.assert_not_called(); weather.assert_not_called()

    def test_polygon_boundary_and_outside_and_cache_are_location_specific(self):
        self.assertEqual(len(self.query().json()['alertas']), 1)
        self.assertEqual(len(self.query(latitud=-33, longitud=-64).json()['alertas']), 1)
        outside = self.query(latitud=-40).json()
        self.assertEqual(outside['estado'], 'disponible')
        self.assertEqual(outside['alertas'], [])
        self.assertEqual(self.download.call_count, 2)

    def test_circle_geometry_and_invalid_coordinates(self):
        self.documents[PREFIX + 'notice.xml'] = cap(geometry='<circle>-31.4,-64.2 10</circle>')
        self.assertEqual(len(self.query().json()['alertas']), 1)
        self.assertEqual(self.query(latitud=-32).json()['alertas'], [])
        for geometry in ('<polygon>NaN,-64 -31,-64 -31,-63 NaN,-64</polygon>', '<polygon>-31,-64 -31,-63</polygon>', '<circle>-31,-64 -1</circle>'):
            cache.clear(); self.documents[PREFIX+'notice.xml'] = cap(geometry=geometry)
            self.assertEqual(self.query().json()['estado'], 'parcial')

    def test_short_term_official_path_is_accepted_without_loosening_host_validation(self):
        url = 'https://ssl.smn.gob.ar/feeds/CAP/avisocortoplazo/2026_10_25_cap_es.xml'
        self.documents[alerts.FEED] = feed('notice').replace((PREFIX+'notice.xml').encode(), url.encode())
        self.documents[url] = cap()
        self.assertEqual(self.query().json()['estado'], 'disponible')
        self.assertEqual(alerts._cap_url(url), url)

    def test_more_than_thirty_two_documents_are_checked_and_cached(self):
        names = [f'notice{i}' for i in range(40)]
        self.documents = {alerts.FEED: feed(*names), **{
            PREFIX + name + '.xml': cap(identifier=name) for name in names}}
        self.assertEqual(self.query().json()['estado'], 'disponible')
        self.assertEqual(len(self.query().json()['alertas']), 40)
        self.assertEqual(self.download.call_count, 41)

    def test_truly_incomplete_catalog_remains_partial_and_refreshes_after_thirty_seconds(self):
        self.documents[alerts.FEED] = feed('notice', 'broken')
        self.documents[PREFIX+'broken.xml'] = b'not XML'
        self.assertEqual(self.query().json()['estado'], 'parcial')
        self.documents[PREFIX+'broken.xml'] = cap(identifier='recovered')
        self.clock.return_value = NOW + timedelta(seconds=31)
        self.assertEqual(self.query().json()['estado'], 'disponible')

    def test_expired_test_private_and_cancelled_notices_are_not_current_alerts(self):
        for document in (cap(expires='2026-10-25T11:00:00Z').replace(b'2026-10-25T13:00:00Z', b'2026-10-25T09:00:00Z'), cap(status='Test'), cap(scope='Private')):
            cache.clear(); self.documents[PREFIX+'notice.xml'] = document
            self.assertEqual(self.query().json()['alertas'], [])
        cache.clear()
        self.documents = {alerts.FEED: feed('notice', 'cancel'), PREFIX+'notice.xml': cap(), PREFIX+'cancel.xml': cap('cancel', kind='Cancel', references='smn@smn.gob.ar,first,2026-10-25T10:00:00Z')}
        self.assertEqual(self.query().json()['alertas'], [])

    def test_update_supersedes_old_notice_and_duplicate_links_do_not_duplicate_results(self):
        self.documents = {alerts.FEED: feed('notice', 'notice', 'update'), PREFIX+'notice.xml': cap(), PREFIX+'update.xml': cap('second', kind='Update', references='smn@smn.gob.ar,first,2026-10-25T10:00:00Z')}
        body = self.query().json()
        self.assertEqual([row['identificador'] for row in body['alertas']], ['second'])
        self.assertEqual(self.download.call_count, 3)

    def test_missing_geography_or_failed_documents_are_partial_not_an_all_clear(self):
        self.documents[alerts.FEED] = feed('notice', 'broken')
        self.documents[PREFIX+'broken.xml'] = cap('broken', geometry='<geocode><value>unknown</value></geocode>')
        body = self.query().json()
        self.assertEqual(body['estado'], 'parcial'); self.assertEqual(len(body['alertas']), 1)
        cache.clear()
        self.download.side_effect = httpx.ReadTimeout('private transport details')
        body = self.query().json()
        self.assertEqual(body['estado'], 'no_disponible'); self.assertEqual(body['alertas'], [])
        self.assertNotIn('private', str(body))

    def test_stale_feed_and_unsafe_xml_are_unavailable(self):
        for payload in (feed('notice', published='Fri, 23 Oct 2026 12:00:00 GMT'), b'<!DOCTYPE rss [<!ENTITY x "unsafe">]><rss/>', b'<html/>', b'x'*(alerts.MAX_BYTES+1)):
            cache.clear(); self.documents[alerts.FEED] = payload
            self.assertEqual(self.query().json()['estado'], 'no_disponible')
        cache.clear(); self.documents[alerts.FEED] = feed()
        self.assertEqual(self.query().json()['estado'], 'disponible')

    def test_untrusted_feed_links_are_never_requested(self):
        self.documents[alerts.FEED] = b'<rss><channel><pubDate>Sun, 25 Oct 2026 12:00:00 GMT</pubDate><item><link>http://127.0.0.1/private</link></item></channel></rss>'
        self.assertEqual(self.query().json()['estado'], 'parcial')
        self.assertEqual(self.download.call_count, 1)
        for url in ('https://ssl.smn.gob.ar.evil/feeds/CAP/xml_generados/x.xml', 'https://ssl.smn.gob.ar:443/feeds/CAP/xml_generados/x.xml', PREFIX+'x.xml?redirect=1', 'https://ssl.smn.gob.ar/private.xml'):
            with self.assertRaises(ValueError): alerts._cap_url(url)

    def test_expiry_is_rechecked_when_catalog_is_cached(self):
        self.assertEqual(len(self.query().json()['alertas']), 1)
        self.clock.return_value = NOW + timedelta(hours=24)
        self.assertEqual(self.query().json()['alertas'], [])

    def test_outside_coverage_and_invalid_input_do_not_contact_smn(self):
        self.assertEqual(self.query(pais='PE').json()['estado'], 'fuera_cobertura')
        for values in ({'latitud': 91}, {'longitud': 'nan'}, {'pais': 'ARG'}, {'latitud': ''}, {'url': 'https://bad.invalid'}):
            self.assertEqual(self.query(**values).status_code, 400)
        self.assertEqual(self.client.get('/api/v1/alertas/?latitud=1&latitud=2&longitud=3&pais=AR').status_code, 400)
        self.assertEqual(self.client.post('/api/v1/alertas/').status_code, 405)
        self.download.assert_not_called()

    def test_partial_retry_reuses_documents_already_verified(self):
        self.documents[alerts.FEED] = feed('notice', 'slow')
        attempts = []
        def download(client, url):
            attempts.append(url)
            if url == PREFIX+'slow.xml' and attempts.count(url) == 1:
                raise httpx.ReadTimeout('private details must not be exposed')
            return cap('second') if url == PREFIX+'slow.xml' else self.documents[url]
        self.download.side_effect = download
        first = self.query().json()
        self.assertEqual(first['estado'], 'parcial')
        self.assertEqual(first['fuente']['verificacion']['fallos'], {'documento_timeout': 1})
        self.clock.return_value = NOW + timedelta(seconds=31)
        second = self.query().json()
        self.assertEqual(second['estado'], 'disponible')
        self.assertEqual(len(second['alertas']), 2)
        self.assertEqual(attempts.count(PREFIX+'notice.xml'), 1)
        self.assertEqual(attempts.count(PREFIX+'slow.xml'), 2)

    def test_source_http_failure_has_a_safe_diagnostic(self):
        response = httpx.Response(403, request=httpx.Request('GET', alerts.FEED))
        self.download.side_effect = httpx.HTTPStatusError('private marker', request=response.request, response=response)
        body = self.query().json()
        self.assertEqual(body['estado'], 'no_disponible')
        self.assertEqual(body['fuente']['verificacion']['fallos'], {'indice_http_403': 1})
        self.assertNotIn('private marker', str(body))

    def test_download_does_not_follow_redirects_and_enforces_size_limit(self):
        # The low-level transport is exercised with an in-memory httpx response.
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(302, headers={'location': 'https://bad.invalid'})), follow_redirects=False)
        with client, self.assertRaises(httpx.HTTPStatusError): DOWNLOAD(client, alerts.FEED)
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b'x'*(alerts.MAX_BYTES+1))))
        with client, self.assertRaises(ValueError): DOWNLOAD(client, alerts.FEED)

    def test_source_rate_limit_stops_additional_downloads_during_backoff(self):
        calls = []
        def reply(request):
            calls.append(request)
            return httpx.Response(429, headers={'Retry-After': '90'})
        with httpx.Client(transport=httpx.MockTransport(reply)) as client:
            with self.assertRaises(alerts.SMNRateLimited):
                DOWNLOAD(client, alerts.FEED)
            with self.assertRaises(alerts.SMNRateLimited):
                DOWNLOAD(client, PREFIX+'notice.xml')
        self.assertEqual(len(calls), 1)

    def test_backoff_preserves_previously_verified_notices_as_partial(self):
        first = self.query().json()
        self.assertEqual(first['estado'], 'disponible')
        self.clock.return_value = NOW + timedelta(seconds=181)
        cache.set(alerts.BACKOFF_KEY, True, 90)
        second = self.query().json()
        self.assertEqual(second['estado'], 'parcial')
        self.assertEqual(len(second['alertas']), 1)
        self.assertEqual(self.download.call_count, 2)

    def test_http_date_retry_after_is_respected(self):
        response = lambda request: httpx.Response(429, headers={
            'Retry-After': 'Sun, 25 Oct 2026 12:01:30 GMT'})
        with httpx.Client(transport=httpx.MockTransport(response)) as client:
            with patch.object(alerts.cache, 'set', wraps=cache.set) as remember:
                with self.assertRaises(alerts.SMNRateLimited):
                    DOWNLOAD(client, alerts.FEED)
                remember.assert_called_once_with(alerts.BACKOFF_KEY, True, 90)

    def test_background_recovery_completes_missing_documents_without_a_new_visitor(self):
        complete = alerts._load_catalog(NOW)
        from copy import deepcopy
        incomplete = deepcopy(complete)
        incomplete['partial'] = True
        incomplete['verification']['pendientes'] = 1
        cache.set(alerts.CACHE_KEY, incomplete, 900)
        alerts._recovery_lock.acquire()
        with patch.object(alerts, '_load_catalog', return_value=complete) as load, patch.object(alerts.time, 'sleep'):
            alerts._recover_catalog()
        load.assert_called_once()
        self.assertFalse(alerts._recovery_lock.locked())
        self.assertEqual(self.query().json()['estado'], 'disponible')

    def test_background_recovery_waits_for_the_provider_and_stops_at_its_budget(self):
        incomplete = {'partial': True, 'verification': {'pendientes': 1}}
        cache.set(alerts.CACHE_KEY, incomplete, 900)
        cache.set(alerts.BACKOFF_KEY, True, 90)
        alerts._recovery_lock.acquire()
        with patch.object(alerts.time, 'monotonic', side_effect=[0, 1, 241]), patch.object(
                alerts.time, 'sleep') as sleep, patch.object(alerts, '_load_catalog') as load:
            alerts._recover_catalog()
        load.assert_not_called()
        sleep.assert_called_once_with(5)
        self.assertFalse(alerts._recovery_lock.locked())

    @override_settings(SMN_BACKGROUND_RECOVERY=True)
    def test_concurrent_visitors_schedule_only_one_recovery_worker(self):
        incomplete = {'partial': True, 'verification': {'pendientes': 1}}
        try:
            with patch.object(alerts.threading, 'Thread') as worker:
                alerts._schedule_recovery(incomplete)
                alerts._schedule_recovery(incomplete)
                worker.assert_called_once_with(target=alerts._recover_catalog, name='smn-recovery', daemon=True)
                worker.return_value.start.assert_called_once()
        finally:
            if alerts._recovery_lock.locked():
                alerts._recovery_lock.release()
