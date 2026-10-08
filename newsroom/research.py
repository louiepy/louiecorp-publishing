import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

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

    if value and value.lower() not in {
        'google news',
        'google news uganda',
        'google news africa',
        'google news world',
        'google news science',
        'news source',
    }:
        return value

    return domain(url) or 'News source'


def add_source(sources, seen, title, url, description='', published='', publisher=''):
    url = clean(url)

    if not url or url in seen:
        return

    seen.add(url)

    sources.append({
        'title': clean(title) or 'Related source',
        'url': url,
        'description': clean(description),
        'published': clean(published),
        'track': 'news',
        'feed': publisher_name(publisher, url),
    })


def fetch_article(url):
    try:
        status, _, body = request(url, timeout=20)

        if status >= 400:
            return '', ''

        text, title = extract_text(
            body.decode('utf-8', 'replace')
        )

        text = clean(text)

        if len(text) >= 500:
            return text, title

    except Exception:
        pass

    return '', ''


def research(candidate, max_sources=6):
    sources = []
    seen = set()

    add_source(
        sources,
        seen,
        candidate.get('title', ''),
        candidate.get('url', ''),
        candidate.get('description', ''),
        candidate.get('published', ''),
        candidate.get('feed', ''),
    )

    query = urllib.parse.quote(candidate.get('title', ''))

    # Google News related coverage
    google_url = (
        'https://news.google.com/rss/search?q='
        + query
        + '&hl=en-US&gl=UG&ceid=UG:en'
    )

    try:
        status, _, body = request(google_url, timeout=20)

        if status < 400:
            root = ET.fromstring(body)

            for item in root.findall('.//item')[:20]:
                title = clean(item.findtext('title'))
                url = clean(item.findtext('link'))

                description = clean(
                    re.sub(
                        r'<[^>]+>',
                        ' ',
                        item.findtext('description') or '',
                    )
                )

                source_node = item.find(
                    '{http://search.yahoo.com/mrss/}source'
                )

                publisher = (
                    clean(source_node.text)
                    if source_node is not None
                    else ''
                )

                # Google News sometimes exposes the real publisher
                # in a normal <source> element without the MRSS namespace.
                if not publisher:
                    source_node = item.find('source')
                    if source_node is not None:
                        publisher = clean(source_node.text)

                add_source(
                    sources,
                    seen,
                    title,
                    url,
                    description,
                    item.findtext('pubDate') or '',
                    publisher,
                )

                if len(sources) >= max_sources:
                    break

    except Exception:
        pass

    # GDELT provides an independent pool of sources.
    if len(sources) < max_sources:
        try:
            gdelt_url = (
                'https://api.gdeltproject.org/api/v2/doc/doc?query='
                + query
                + '&mode=ArtList&maxrecords=30&format=json&sort=HybridRel'
            )

            status, _, body = request(gdelt_url, timeout=20)

            if status < 400:
                data = json.loads(
                    body.decode('utf-8', 'replace')
                )

                for item in data.get('articles', []):
                    add_source(
                        sources,
                        seen,
                        item.get('title', ''),
                        item.get('url', ''),
                        item.get('snippet', ''),
                        item.get('seendate', ''),
                        item.get('domain', ''),
                    )

                    if len(sources) >= max_sources:
                        break

        except Exception:
            pass

    packet = []
    seen_publishers = set()

    # First pass: use full article text where available.
    for src in sources:
        if len(packet) >= max_sources:
            break

        url = src['url']
        publisher = publisher_name(src.get('feed', ''), url)
        publisher_key = publisher.lower()

        text, title = fetch_article(url)

        if text and publisher_key not in seen_publishers:
            seen_publishers.add(publisher_key)

            packet.append({
                'title': title or src['title'],
                'url': url,
                'publisher': publisher,
                'retrieved_at': datetime.now(
                    timezone.utc
                ).isoformat(),
                'text': text[:9000],
            })

    # Second pass: if publisher pages block the runner,
    # use substantial RSS/GDELT descriptions as source evidence.
    for src in sources:
        if len(packet) >= max_sources:
            break

        fallback = clean(src.get('description', ''))

        if len(fallback) < 250:
            continue

        publisher = publisher_name(
            src.get('feed', ''),
            src.get('url', ''),
        )
        publisher_key = publisher.lower()

        if publisher_key in seen_publishers:
            continue

        seen_publishers.add(publisher_key)

        packet.append({
            'title': src['title'],
            'url': src['url'],
            'publisher': publisher,
            'retrieved_at': datetime.now(
                timezone.utc
            ).isoformat(),
            'text': fallback[:9000],
        })

    return packet
