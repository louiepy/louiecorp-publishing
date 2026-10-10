import os
import unittest
import urllib.parse
from unittest.mock import patch

os.environ.setdefault(
    'SUPABASE_URL',
    'https://example.supabase.co',
)
os.environ.setdefault(
    'SUPABASE_SERVICE_ROLE_KEY',
    'dummy',
)

from newsroom import research


def long_html(text):
    return (
        '<html><head><title>Story</title></head>'
        '<body><p>'
        + (' '.join([text] * 220))
        + '</p></body></html>'
    ).encode('utf-8')


class ResearchTests(unittest.TestCase):

    def test_two_independent_publishers_required(self):
        rss = '''<?xml version="1.0"?>
        <rss xmlns:media="http://search.yahoo.com/mrss/">
          <channel>
            <item>
              <title>Uganda update - Daily Monitor</title>
              <link>https://news.google.com/rss/articles/abc1</link>
              <description><![CDATA[<a href="https://www.monitor.co.ug/news/a">Read</a> Parliament updates policy with verified context and long narrative detail for editorial evidence.]]></description>
              <media:source url="https://www.monitor.co.ug">Daily Monitor</media:source>
            </item>
            <item>
              <title>Uganda update follow-up - Daily Monitor</title>
              <link>https://news.google.com/rss/articles/abc2</link>
              <description><![CDATA[<a href="https://www.monitor.co.ug/news/b">Read</a> Additional context appears here with broad descriptive text that remains substantive and useful for fallback evidence.]]></description>
              <media:source url="https://www.monitor.co.ug">Daily Monitor</media:source>
            </item>
            <item>
              <title>Regional reaction - Reuters</title>
              <link>https://news.google.com/rss/articles/abc3</link>
              <description><![CDATA[<a href="https://www.reuters.com/world/reaction">Read</a> Reuters reports broad context and policy implications with detail and independent attribution for verification.]]></description>
              <media:source url="https://www.reuters.com">Reuters</media:source>
            </item>
          </channel>
        </rss>'''

        def fake_request(url, **kwargs):
            host = urllib.parse.urlparse(
                url
            ).netloc.lower()
            if 'news.google.com/rss/search' in url:
                return 200, {}, rss.encode('utf-8')
            if host in {
                'monitor.co.ug',
                'www.monitor.co.ug',
            }:
                return 200, {'Content-Type': 'text/html'}, long_html('Monitor reporting')
            if host in {
                'reuters.com',
                'www.reuters.com',
            }:
                return 200, {'Content-Type': 'text/html'}, long_html('Reuters reporting')
            if host == 'api.gdeltproject.org':
                return 200, {}, b'{"articles":[]}'
            return 404, {}, b''

        candidate = {
            'title': 'Uganda policy update',
            'url': 'https://news.google.com/rss/articles/start',
            'description': 'Initial report',
            'published': '',
            'publisher': '',
        }

        with patch(
            'newsroom.research.request',
            side_effect=fake_request,
        ):
            packet = research.research(
                candidate,
                max_sources=6,
            )

        self.assertEqual(2, len(packet))
        publishers = [
            item['publisher'].lower()
            for item in packet
        ]
        self.assertTrue(
            any(
                token in p
                for p in publishers
                for token in (
                    'daily monitor',
                    'monitor.co.ug',
                )
            )
        )
        self.assertTrue(
            any(
                token in p
                for p in publishers
                for token in (
                    'reuters',
                    'reuters.com',
                )
            )
        )
        self.assertFalse(
            any('google' in p for p in publishers)
        )

    def test_fallback_evidence_works_without_article_fetch(self):
        rss = '''<?xml version="1.0"?>
        <rss xmlns:media="http://search.yahoo.com/mrss/">
          <channel>
            <item>
              <title>Kampala transport bill - New Vision</title>
              <link>https://news.google.com/rss/articles/x1</link>
              <description><![CDATA[<a href="https://www.newvision.co.ug/story/transport-bill">Read</a> Lawmakers debated the transport bill in Kampala with details on costs, public hearings, opposition criticism, ministerial replies, and implementation timelines for local districts across Uganda.]]></description>
              <media:source url="https://www.newvision.co.ug">New Vision</media:source>
            </item>
            <item>
              <title>Fuel tax response - The EastAfrican</title>
              <link>https://news.google.com/rss/articles/x2</link>
              <description><![CDATA[<a href="https://www.theeastafrican.co.ke/story/fuel-tax">Read</a> Analysts and civil society groups described likely inflation effects, commuter burdens, and fiscal trade-offs while officials defended the measure as temporary and targeted to budget shortfalls.]]></description>
              <media:source url="https://www.theeastafrican.co.ke">The EastAfrican</media:source>
            </item>
          </channel>
        </rss>'''

        def fake_request(url, **kwargs):
            host = urllib.parse.urlparse(
                url
            ).netloc.lower()
            if 'news.google.com/rss/search' in url:
                return 200, {}, rss.encode('utf-8')
            if (
                host in {
                    'newvision.co.ug',
                    'www.newvision.co.ug',
                    'theeastafrican.co.ke',
                    'www.theeastafrican.co.ke',
                }
            ):
                return 403, {'Content-Type': 'text/html'}, b''
            if host == 'api.gdeltproject.org':
                return 200, {}, b'{"articles":[]}'
            return 404, {}, b''

        candidate = {
            'title': 'Uganda transport and fuel policy',
            'url': 'https://news.google.com/rss/articles/start',
            'description': 'Initial report',
            'published': '',
            'publisher': '',
        }

        with patch(
            'newsroom.research.request',
            side_effect=fake_request,
        ):
            packet = research.research(
                candidate,
                max_sources=6,
            )

        self.assertEqual(2, len(packet))
        self.assertTrue(
            all(len(item['text']) >= 140 for item in packet)
        )

    def test_homepage_url_is_not_an_article(self):
        self.assertTrue(
            research.is_homepage_url('https://www.softpower.ug/')
        )
        self.assertTrue(
            research.is_homepage_url('https://www.monitor.co.ug')
        )
        self.assertTrue(
            research.is_homepage_url('https://www.newvision.co.ug/news')
        )
        self.assertFalse(
            research.is_homepage_url(
                'https://www.monitor.co.ug/uganda/news/national/story-123'
            )
        )

    def test_rejects_publisher_homepage_as_source(self):
        rss = '''<?xml version="1.0"?>
        <rss xmlns:media="http://search.yahoo.com/mrss/">
          <channel>
            <item>
              <title>Uganda update - SoftPower News</title>
              <link>https://news.google.com/rss/articles/hp1</link>
              <description><![CDATA[<a href="https://www.softpower.ug/">Read</a> Homepage teaser copy about Uganda parliament with extra narrative padding so fallback length would otherwise pass editorial evidence checks for this source.]]></description>
              <media:source url="https://www.softpower.ug">SoftPower News</media:source>
            </item>
            <item>
              <title>Uganda update - Daily Monitor</title>
              <link>https://news.google.com/rss/articles/hp2</link>
              <description><![CDATA[<a href="https://www.monitor.co.ug">Read</a> Another homepage teaser about the same Uganda policy debate with enough padded descriptive text that fallback evidence would look usable if the URL were accepted.]]></description>
              <media:source url="https://www.monitor.co.ug">Daily Monitor</media:source>
            </item>
          </channel>
        </rss>'''

        def fake_request(url, **kwargs):
            host = urllib.parse.urlparse(url).netloc.lower()
            if 'news.google.com/rss/search' in url:
                return 200, {}, rss.encode('utf-8')
            if host == 'api.gdeltproject.org':
                return 200, {}, b'{"articles":[]}'
            return 200, {'Content-Type': 'text/html'}, long_html(
                'Homepage listing'
            )

        candidate = {
            'title': 'Uganda policy update',
            'url': 'https://www.softpower.ug/',
            'description': 'Initial report',
            'published': '',
            'publisher': 'SoftPower News',
        }

        with patch(
            'newsroom.research.request',
            side_effect=fake_request,
        ):
            packet = research.research(
                candidate,
                max_sources=6,
            )

        self.assertEqual(0, len(packet))

    def test_rejects_syndicated_copies_as_independent(self):
        shared = (
            'Parliament in Kampala approved the same policy measure '
            'after a lengthy debate covering costs, hearings, opposition '
            'criticism, ministerial replies, and district timelines '
            'across Uganda with identical wire copy repeated here. '
        )
        rss = f'''<?xml version="1.0"?>
        <rss xmlns:media="http://search.yahoo.com/mrss/">
          <channel>
            <item>
              <title>Uganda bill - Outlet One</title>
              <link>https://news.google.com/rss/articles/s1</link>
              <description><![CDATA[<a href="https://one.example/uganda/bill">Read</a> {shared}]]></description>
              <media:source url="https://one.example">Outlet One</media:source>
            </item>
            <item>
              <title>Uganda bill - Outlet Two</title>
              <link>https://news.google.com/rss/articles/s2</link>
              <description><![CDATA[<a href="https://two.example/uganda/bill">Read</a> {shared}]]></description>
              <media:source url="https://two.example">Outlet Two</media:source>
            </item>
          </channel>
        </rss>'''

        def fake_request(url, **kwargs):
            if 'news.google.com/rss/search' in url:
                return 200, {}, rss.encode('utf-8')
            if 'api.gdeltproject.org' in url:
                return 200, {}, b'{"articles":[]}'
            return 403, {'Content-Type': 'text/html'}, b''

        candidate = {
            'title': 'Uganda bill',
            'url': 'https://news.google.com/rss/articles/start',
            'description': 'Initial report',
            'published': '',
            'publisher': '',
        }

        with patch(
            'newsroom.research.request',
            side_effect=fake_request,
        ):
            packet = research.research(
                candidate,
                max_sources=6,
            )

        self.assertEqual(1, len(packet))


if __name__ == '__main__':
    unittest.main()
