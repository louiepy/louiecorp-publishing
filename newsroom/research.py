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
        'feed': clean(publisher) or domain(url) or 'News source'
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
    seen_urls = set()

    add_source(
        sources,
        seen_urls,
        candidate.get('title', ''),
        candidate.get('url', ''),
        candidate.get('description', ''),
        candidate.get('published', ''),
        candidate.get('feed', '')
    )

    query = urllib.parse.quote(candidate.get('title', ''))

    google_url = (
        'https://news.google.com/rss/search?q='
        + query
        + '&hl=en-US&gl=UG&ceid=UG:en'
    )

    try:
        status, _, body = request(google_url, timeout=20)

        if status < 400:
            root = ET.fromstring(body)

            for item in root.findall('.//item'):
                title = clean(item.findtext('title'))
                url = clean(item.findtext('link'))
                description = clean(
                    re.sub(
                        r'<[^>]+>',
                        ' ',
                        item.findtext('description') or ''
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

                add_source(
                    sources,
                    seen_urls,
                    title,
                    url,
                    description,
                    item.findtext('pubDate') or '',
                    publisher
                )

                if len(sources) >= max_sources:
                    break

    except Exception as exc:
        print('Google News warning:', exc)

    if len(sources) < max_sources:
        try:
            gdelt_url = (
                'https://api.gdeltproject.org/api/v2/doc/doc?query='
                + query
                + '&mode=ArtList&maxrecords=20&format=json&sort=HybridRel'
            )

            status, _, body = request(gdelt_url, timeout=20)

            if status < 400:
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

        except Exception as exc:
            print('GDELT warning:', exc)

    packet = []
    seen_publishers = set()

    for src in sources:
        if len(packet) >= max_sources:
            break

        url = src['url']
        publisher = clean(src.get('feed', ''))

        text, title = fetch_article(url)

        # Use the publisher supplied by Google News/GDELT as the
        # identity of the source. Do NOT use news.google.com as
        # the publisher identity.
        publisher_key = publisher.lower()

        if not publisher_key:
            publisher_key = domain(url)

        if text:
            if publisher_key in seen_publishers:
                continue

            seen_publishers.add(publisher_key)

            packet.append({
                'title': title or src['title'],
                'url': url,
                'publisher': publisher or domain(url) or 'Source',
                'retrieved_at': datetime.now(
                    timezone.utc
                ).isoformat(),
                'text': text[:9000]
            })

            continue

        fallback = clean(src.get('description', ''))

        if len(fallback) >= 250:
            if publisher_key in seen_publishers:
                continue

            seen_publishers.add(publisher_key)

            packet.append({
                'title': src['title'],
                'url': url,
                'publisher': publisher or domain(url) or 'News source',
                'retrieved_at': datetime.now(
                    timezone.utc
                ).isoformat(),
                'text': fallback[:9000]
            })

    return packet