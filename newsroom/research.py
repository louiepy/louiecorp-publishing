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


def add_source(sources, seen, title, url, description='', published='', publisher=''):
    title = clean(title)
    url = clean(url)
    description = clean(description)
    publisher = clean(publisher)

    if not url or url in seen:
        return

    seen.add(url)

    sources.append({
        'title': title or 'Related report',
        'url': url,
        'description': description,
        'published': clean(published),
        'publisher': publisher or domain(url) or 'News source'
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

        if len(text) >= 400:
            return text, clean(title)

    except Exception:
        pass

    return '', ''


def research(candidate, max_sources=6):
    sources = []
    seen = set()

    # Candidate itself.
    add_source(
        sources,
        seen,
        candidate.get('title', ''),
        candidate.get('url', ''),
        candidate.get('description', ''),
        candidate.get('published', ''),
        candidate.get('feed', '')
    )

    query = urllib.parse.quote(candidate.get('title', ''))

    # Pull related coverage from Google News RSS.
    google_url = (
        'https://news.google.com/rss/search?q='
        + query
        + '&hl=en-US&gl=UG&ceid=UG:en'
    )

    try:
        status, _, body = request(
            google_url,
            timeout=20
        )

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

                source_node = item.find(
                    '{http://search.yahoo.com/mrss/}source'
                )

                if source_node is not None:
                    publisher = clean(source_node.text)

                if not publisher:
                    source_node = item.find('source')
                    if source_node is not None:
                        publisher = clean(source_node.text)

                # Google News sometimes embeds the publisher
                # in the title as "Headline - Publisher".
                if not publisher and ' - ' in title:
                    possible = title.rsplit(' - ', 1)[-1].strip()
                    if 1 < len(possible) < 100:
                        publisher = possible

                add_source(
                    sources,
                    seen,
                    title,
                    url,
                    description,
                    item.findtext('pubDate') or '',
                    publisher
                )

    except Exception:
        pass

    # Try GDELT only as an additional source pool.
    if len(sources) < max_sources:
        try:
            gdelt_url = (
                'https://api.gdeltproject.org/api/v2/doc/doc?query='
                + query
                + '&mode=ArtList&maxrecords=20&format=json&sort=HybridRel'
            )

            status, _, body = request(
                gdelt_url,
                timeout=20
            )

            if status < 400:
                import json

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
                        item.get('domain', '')
                    )

                    if len(sources) >= max_sources:
                        break

        except Exception:
            pass

    packet = []
    seen_publishers = set()

    # First use full publisher articles whenever possible.
    for src in sources:
        if len(packet) >= max_sources:
            break

        publisher = clean(src.get('publisher', ''))
        publisher_key = publisher.lower()

        if not publisher_key:
            publisher_key = domain(src['url'])

        if publisher_key in seen_publishers:
            continue

        text, title = fetch_article(src['url'])

        if text:
            seen_publishers.add(publisher_key)

            packet.append({
                'title': title or src['title'],
                'url': src['url'],
                'publisher': publisher or domain(src['url']) or 'News source',
                'retrieved_at': datetime.now(
                    timezone.utc
                ).isoformat(),
                'text': text[:9000]
            })

    # Then use independent RSS/GDELT reports when direct article
    # retrieval is blocked. Require meaningful snippets.
    for src in sources:
        if len(packet) >= max_sources:
            break

        fallback = clean(src.get('description', ''))

        if len(fallback) < 120:
            continue

        publisher = clean(src.get('publisher', ''))
        publisher_key = publisher.lower()

        if not publisher_key:
            publisher_key = domain(src['url'])

        if not publisher_key or publisher_key in seen_publishers:
            continue

        seen_publishers.add(publisher_key)

        packet.append({
            'title': src['title'],
            'url': src['url'],
            'publisher': publisher,
            'retrieved_at': datetime.now(
                timezone.utc
            ).isoformat(),
            'text': fallback[:9000]
        })

    print(f'Research produced {len(packet)} usable sources.')

    for source in packet:
        print(
            f'Research source: {source["publisher"]} '
            f'({len(source["text"])} chars)'
        )

    return packet
