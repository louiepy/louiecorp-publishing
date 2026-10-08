import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from .config import RSS_FEEDS
from .http import request, extract_text


def clean(value):
    return ' '.join((value or '').split())


def domain(url):
    try:
        return urllib.parse.urlparse(url).netloc.lower().replace('www.', '')
    except Exception:
        return ''


def publisher_name(value, url=''):
    value = clean(value)
    d = domain(url)

    invalid = {
        'google news',
        'google news uganda',
        'google news africa',
        'google news world',
        'google news science',
        'news source',
        'news.google.com',
        'google.com',
    }

    if value and value.lower() not in invalid:
        return value

    if d and d not in {'news.google.com', 'google.com'} and not d.endswith('.google.com'):
        return d

    return ''


def add_source(
    sources,
    seen_urls,
    title,
    url,
    description='',
    published='',
    publisher=''
):
    title = clean(title)
    url = clean(url)
    description = clean(description)
    publisher = publisher_name(publisher, url)

    if not url or url in seen_urls:
        return

    seen_urls.add(url)

    sources.append({
        'title': title or 'Related report',
        'url': url,
        'description': description,
        'published': clean(published),
        'publisher': publisher,
    })


def fetch_article(url):
    """
    Try to retrieve readable article text from a publisher URL.

    Google News and other intermediary pages may not expose a useful
    article body. Those failures are intentionally treated as a normal
    research fallback condition rather than a fatal newsroom error.
    """
    try:
        status, headers, body = request(url, timeout=20)

        if status >= 400:
            return '', ''

        content_type = ''
        try:
            content_type = str(headers.get('Content-Type', '')).lower()
        except Exception:
            pass

        if content_type and 'html' not in content_type:
            return '', ''

        text, title = extract_text(
            body.decode('utf-8', 'replace')
        )

        text = clean(text)

        if len(text) >= 400:
            return text, clean(title)

    except Exception:
        pass

    return '', ''


def research(candidate, max_sources=6):
    sources = []
    seen_urls = set()

    # Candidate URLs are useful evidence, but the discovery feed name
    # must never be treated as the publisher.
    add_source(
        sources,
        seen_urls,
        candidate.get('title', ''),
        candidate.get('url', ''),
        candidate.get('description', ''),
        candidate.get('published', ''),
        ''
    )

    title_query = clean(candidate.get('title', ''))

    if not title_query:
        print('Research warning: candidate has no title.')
        return []

    query = urllib.parse.quote(title_query)

    # ------------------------------------------------------------
    # Google News RSS
    # ------------------------------------------------------------
    google_url = (
        'https://news.google.com/rss/search?q='
        + query
        + '&hl=en-US&gl=UG&ceid=UG:en'
    )

    try:
        status, _, body = request(google_url, timeout=20)

        if status < 400:
            root = ET.fromstring(body)

            for item in root.findall('.//item')[:30]:
                title = clean(item.findtext('title'))
                url = clean(item.findtext('link'))

                description = clean(
                    re.sub(
                        r'<[^>]+>',
                        ' ',
                        item.findtext('description') or ''
                    )
                )

                publisher = ''

                # RSS source metadata.
                source_node = item.find(
                    '{http://search.yahoo.com/mrss/}source'
                )

                if source_node is not None:
                    publisher = clean(source_node.text)

                if not publisher:
                    source_node = item.find('source')

                    if source_node is not None:
                        publisher = clean(source_node.text)

                # Google News commonly formats headlines as:
                #
                # Headline - Publisher
                #
                # Always prefer this publisher when available.
                if ' - ' in title:
                    possible = title.rsplit(' - ', 1)[-1].strip()

                    if 1 < len(possible) < 100:
                        publisher = possible

                add_source(
                    sources,
                    seen_urls,
                    title,
                    url,
                    description,
                    item.findtext('pubDate') or '',
                    publisher
                )

    except ET.ParseError as error:
        print(
            'Research warning: Google News returned invalid RSS:',
            error
        )
    except Exception as error:
        print(
            'Research warning: Google News:',
            type(error).__name__,
            error
        )

    # ------------------------------------------------------------
    # GDELT fallback
    # ------------------------------------------------------------
    if len(sources) < max_sources:
        try:
            gdelt_url = (
                'https://api.gdeltproject.org/api/v2/doc/doc?query='
                + query
                + '&mode=ArtList&maxrecords=30'
                + '&format=json&sort=HybridRel'
            )

            status, _, body = request(gdelt_url, timeout=20)

            if status < 400:
                import json

                data = json.loads(
                    body.decode('utf-8', 'replace')
                )

                for item in data.get('articles', []):
                    add_source(
                        sources,
                        seen_urls,
                        item.get('title', ''),
                        item.get('url', ''),
                        item.get('snippet', ''),
                        item.get('seendate', ''),
                        item.get('domain', '')
                    )

                    if len(sources) >= max_sources:
                        break

        except Exception as error:
            print(
                'Research warning: GDELT:',
                type(error).__name__,
                error
            )

    # ------------------------------------------------------------
    # Build usable evidence packet
    # ------------------------------------------------------------
    packet = []
    seen_publishers = set()

    # First priority: full article text from independent publishers.
    for src in sources:
        if len(packet) >= max_sources:
            break

        publisher = publisher_name(
            src.get('publisher', ''),
            src.get('url', '')
        )

        if not publisher:
            continue

        publisher_key = publisher.lower()

        if publisher_key in seen_publishers:
            continue

        text, article_title = fetch_article(
            src.get('url', '')
        )

        if not text:
            continue

        seen_publishers.add(publisher_key)

        packet.append({
            'title': article_title or src.get('title', ''),
            'url': src.get('url', ''),
            'publisher': publisher,
            'retrieved_at': datetime.now(
                timezone.utc
            ).isoformat(),
            'text': text[:9000],
        })

    # Second priority: meaningful RSS/GDELT descriptions.
    #
    # This is important because many legitimate publishers block
    # automated article retrieval while their RSS metadata remains
    # available.
    for src in sources:
        if len(packet) >= max_sources:
            break

        fallback = clean(
            src.get('description', '')
        )

        if len(fallback) < 120:
            continue

        publisher = publisher_name(
            src.get('publisher', ''),
            src.get('url', '')
        )

        if not publisher:
            continue

        publisher_key = publisher.lower()

        if publisher_key in seen_publishers:
            continue

        seen_publishers.add(publisher_key)

        packet.append({
            'title': src.get('title', ''),
            'url': src.get('url', ''),
            'publisher': publisher,
            'retrieved_at': datetime.now(
                timezone.utc
            ).isoformat(),
            'text': fallback[:9000],
        })

    # ------------------------------------------------------------
    # Research logging
    # ------------------------------------------------------------
    print(
        f'Research produced {len(packet)} usable sources.'
    )

    for source in packet:
        print(
            'Research source:',
            source['publisher'],
            f"({len(source['text'])} chars)"
        )

    if len(packet) < 2:
        print(
            'Research warning: fewer than two independent '
            'publishers were found for this candidate.'
        )

    return packet
