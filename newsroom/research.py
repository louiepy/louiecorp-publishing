import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from .http import request, extract_text


def _clean(value):
    return ' '.join((value or '').split())


def _publisher_from_url(url):
    try:
        return urllib.parse.urlparse(url).netloc.lower().replace('www.', '')
    except Exception:
        return ''


def _add_source(sources, seen_urls, title, url, description='', published='', feed=''):
    if not url:
        return

    url = url.strip()

    if url in seen_urls:
        return

    domain = _publisher_from_url(url)

    # Avoid adding multiple copies from the same publisher when possible.
    if domain and any(_publisher_from_url(x['url']) == domain for x in sources):
        return

    seen_urls.add(url)

    sources.append({
        'title': _clean(title) or 'Related source',
        'url': url,
        'description': _clean(description),
        'published': published or '',
        'track': 'news',
        'feed': _clean(feed) or domain or 'News source'
    })


def research(candidate, max_sources=6):
    sources = []
    seen_urls = set()

    candidate_url = candidate.get('url', '')
    candidate_domain = _publisher_from_url(candidate_url)

    if candidate_url:
        _add_source(
            sources,
            seen_urls,
            candidate.get('title', ''),
            candidate_url,
            candidate.get('description', ''),
            candidate.get('published', ''),
            candidate.get('feed', '') or candidate_domain
        )

    query = urllib.parse.quote(candidate.get('title', ''))

    # Google News RSS discovery.
    feed_url = (
        'https://news.google.com/rss/search?q='
        + query
        + '&hl=en-US&gl=UG&ceid=UG:en'
    )

    try:
        status, _, body = request(feed_url, timeout=20)

        if status < 400:
            root = ET.fromstring(body)

            for item in root.findall('.//item'):
                title = _clean(item.findtext('title'))
                url = _clean(item.findtext('link'))
                desc = _clean(
                    re.sub(
                        '<[^>]+>',
                        ' ',
                        item.findtext('description') or ''
                    )
                )

                source_node = item.find(
                    '{http://search.yahoo.com/mrss/}source'
                )

                publisher = (
                    source_node.text.strip()
                    if source_node is not None and source_node.text
                    else ''
                )

                _add_source(
                    sources,
                    seen_urls,
                    title,
                    url,
                    desc,
                    item.findtext('pubDate') or '',
                    publisher
                )

                if len(sources) >= max_sources:
                    break

    except Exception as exc:
        print(f'Google News discovery warning: {exc}')

    # GDELT provides another independent discovery path.
    if len(sources) < max_sources:
        try:
            gd = (
                'https://api.gdeltproject.org/api/v2/doc/doc?query='
                + query
                + '&mode=ArtList&maxrecords=20&format=json&sort=HybridRel'
            )

            status, _, body = request(gd, timeout=20)

            if status < 400:
                data = json.loads(
                    body.decode('utf-8', 'replace')
                )

                for item in data.get('articles', []):
                    _add_source(
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
            print(f'GDELT discovery warning: {exc}')

    packet = []
    seen_domains = set()

    # Fetch article pages and keep only genuinely usable sources.
    for src in sources:
        if len(packet) >= max_sources:
            break

        try:
            status, headers, body = request(
                src['url'],
                timeout=20
            )

            if status >= 400:
                continue

            text, title = extract_text(
                body.decode('utf-8', 'replace')
            )

            text = _clean(text)

            if len(text) < 500:
                continue

            domain = _publisher_from_url(src['url'])

            if domain in seen_domains:
                continue

            seen_domains.add(domain)

            packet.append({
                'title': title or src['title'],
                'url': src['url'],
                'publisher': src.get('feed') or domain or 'Source',
                'retrieved_at': datetime.now(
                    timezone.utc
                ).isoformat(),
                'text': text[:9000]
            })

        except Exception as exc:
            print(
                f'Source fetch warning for {src.get("url", "")}: {exc}'
            )
            continue

    return packet