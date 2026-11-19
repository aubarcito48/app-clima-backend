"""Official country routing and CAP safety, using synthetic documents only."""
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase
import httpx

from api.services.alerts import alerts as alerts
from api.services.alerts import international_alerts as international
from api.tests.alerts.test_alerts import NOW
from api.tests.alerts.test_alerts import cap


class InternationalAlertsTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.clock = patch('api.services.alerts.international_alerts.timezone.now', return_value=NOW).start()
        self.download = patch('api.services.alerts.international_alerts._download').start()
        self.addCleanup(patch.stopall)
        self.documents = {}
        self.download.side_effect = lambda client, country, url: self.documents[url]

    def setup_country(self, country, document=None):
        source = international.SOURCES[country]
        url = {'CL': 'https://archivos.meteochile.gob.cl/portaldmc/rss/meteochile_A1_2026_cap.xml',
               'UY': 'https://www.inumet.gub.uy/reportes/riesgo/cap_2026_10_25.xml',
               'BR': 'https://apiprevmet3.inmet.gov.br/avisos/rss/123'}[country]
        self.documents[source['feed']] = (
            '<rss><channel><pubDate>Sun, 25 Oct 2026 09:00:00 -0300</pubDate>'
            f'<item><link>{url}</link></item></channel></rss>').encode()
        self.documents[url] = document if document is not None else cap(country)
        return url

    def query(self, country, latitude=-31.4, longitude=-64.2):
        return alerts.query_alerts(latitude, longitude, country)

    def test_each_country_uses_own_official_feed_source_and_geographic_filter(self):
        with patch('api.services.alerts.alerts._download') as smn:
            for country in international.SOURCES:
                url = self.setup_country(country)
                response = self.query(country)
                self.assertEqual(response['estado'], 'disponible')
                self.assertEqual(response['alertas'][0]['url'], url)
                self.assertEqual(response['fuente']['nombre'], international.SOURCES[country]['nombre'])
                self.assertEqual(response['fuente']['publicado_en_utc'], '2026-10-25T12:00:00Z')
                self.assertNotIn('shapes', response['alertas'][0])
                self.assertEqual(self.query(country, latitude=0)['alertas'], [])
            smn.assert_not_called()
        self.assertEqual(self.download.call_count, 6)

    def test_portuguese_information_preferred_and_html_kept_literal(self):
        document = cap().replace(b'es-AR', b'pt-BR').replace(b'Aviso ficticio, no es una alerta real.', b'&lt;img src=x onerror=alert(1)&gt;')
        self.setup_country('BR', document)
        result = self.query('BR')
        self.assertEqual(result['estado'], 'disponible')
        self.assertEqual(result['alertas'][0]['descripcion'], '<img src=x onerror=alert(1)>')

    def test_untrusted_feed_links_are_not_fetched_and_never_mean_all_clear(self):
        for country in international.SOURCES:
            url = self.setup_country(country)
            self.documents[international.SOURCES[country]['feed']] = self.documents[international.SOURCES[country]['feed']].replace(url.encode(), b'http://127.0.0.1/private')
            result = self.query(country)
            self.assertEqual(result['estado'], 'parcial')
            self.assertEqual(result['alertas'], [])
        self.assertEqual(self.download.call_count, 3)

    def test_partial_catalog_preserves_verified_notices_and_retries_after_cooldown(self):
        url = self.setup_country('BR')
        feed = international.SOURCES['BR']['feed']
        other = url + '4'
        self.documents[feed] = self.documents[feed].replace(b'</channel>', f'<item><link>{other}</link></item></channel>'.encode())
        self.documents[other] = b'invalid XML'
        result = self.query('BR')
        self.assertEqual(result['estado'], 'parcial')
        self.assertEqual(len(result['alertas']), 1)
        self.assertEqual(result['fuente']['verificacion']['verificados'], 1)
        self.documents[other] = cap('second')
        self.clock.return_value = NOW + timedelta(seconds=61)
        self.assertEqual(self.query('BR')['estado'], 'disponible')

    def test_expired_test_cancelled_and_non_geographic_documents_do_not_leak(self):
        url = self.setup_country('UY', cap(expires='2026-10-25T11:00:00Z').replace(b'2026-10-25T13:00:00Z', b'2026-10-25T09:00:00Z'))
        self.assertEqual(self.query('UY')['alertas'], [])
        for document, state in [(cap(status='Test'), 'disponible'), (cap(geometry=''), 'parcial')]:
            cache.clear()
            self.documents[url] = document
            self.assertEqual(self.query('UY')['estado'], state)
            self.assertEqual(self.query('UY')['alertas'], [])
        cache.clear()
        feed = international.SOURCES['UY']['feed']
        cancel_url = url.replace('25.xml', '26.xml')
        self.documents[url] = cap()
        self.documents[cancel_url] = cap('cancel', kind='Cancel', references='official,first,2026-10-25T10:00:00Z')
        self.documents[feed] = self.documents[feed].replace(b'</channel>', f'<item><link>{cancel_url}</link></item></channel>'.encode())
        self.assertEqual(self.query('UY')['alertas'], [])

    def test_stale_or_missing_feed_date_unavailable_not_zero_alerts(self):
        for published in [b'', b'Sun, 18 Oct 2026 12:00:00 GMT', b'Sun, 25 Oct 2026 15:00:00 GMT']:
            cache.clear()
            self.setup_country('CL')
            feed = international.SOURCES['CL']['feed']
            self.documents[feed] = self.documents[feed].replace(b'Sun, 25 Oct 2026 09:00:00 -0300', published)
            self.assertEqual(self.query('CL')['estado'], 'no_disponible')

    def test_provider_failure_cached_and_isolated_from_other_countries(self):
        self.setup_country('CL'); self.setup_country('BR')
        original = self.download.side_effect
        def fail_chile(client, country, url):
            if country == 'CL':
                raise httpx.ConnectError('not exposed')
            return original(client, country, url)
        self.download.side_effect = fail_chile
        self.assertEqual(self.query('CL')['estado'], 'no_disponible')
        self.assertEqual(self.query('CL')['estado'], 'no_disponible')
        self.assertEqual(self.download.call_count, 1)
        self.assertEqual(self.query('BR')['estado'], 'disponible')

    def test_429_honors_retry_after_and_is_country_specific(self):
        def handler(request):
            return httpx.Response(429, headers={'Retry-After': '300'})
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with patch.object(international, '_download', wraps=DOWNLOAD) as download:
                for _ in range(2):
                    with self.assertRaises(international.ProviderRateLimited):
                        download(client, 'BR', international.SOURCES['BR']['feed'])
        self.assertTrue(cache.get(international._key('BR', 'backoff')))
        self.assertIsNone(cache.get(international._key('UY', 'backoff')))

    def test_unsupported_country_never_contacts_a_provider(self):
        self.assertEqual(self.query('PE')['estado'], 'fuera_cobertura')
        self.download.assert_not_called()


DOWNLOAD = international._download
