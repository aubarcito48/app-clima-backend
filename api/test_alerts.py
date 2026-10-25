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
        self.assertEqual(self.query(pais='UY').json()['estado'], 'fuera_cobertura')
        for values in ({'latitud': 91}, {'longitud': 'nan'}, {'pais': 'ARG'}, {'latitud': ''}, {'url': 'https://bad.invalid'}):
            self.assertEqual(self.query(**values).status_code, 400)
        self.assertEqual(self.client.get('/api/v1/alertas/?latitud=1&latitud=2&longitud=3&pais=AR').status_code, 400)
        self.assertEqual(self.client.post('/api/v1/alertas/').status_code, 405)
        self.download.assert_not_called()

    def test_download_does_not_follow_redirects_and_enforces_size_limit(self):
        # The low-level transport is exercised with an in-memory httpx response.
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(302, headers={'location': 'https://bad.invalid'})), follow_redirects=False)
        with client, self.assertRaises(httpx.HTTPStatusError): DOWNLOAD(client, alerts.FEED)
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b'x'*(alerts.MAX_BYTES+1))))
        with client, self.assertRaises(ValueError): DOWNLOAD(client, alerts.FEED)
