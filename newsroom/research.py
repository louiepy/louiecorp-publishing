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
    print(f'DIAGNOSTIC FETCH: {url}')

    try:
        status, headers, body = request(url, timeout=20)

        print(f'DIAGNOSTIC HTTP: {status} | {len(body)} bytes')

        if status >= 400:
            print('DIAGNOSTIC RESULT: HTTP failure')
            return '', ''

        text, title = extract_text(
            body.decode('utf-8', 'replace')
        )

        text = clean(text)

        print(
            f'DIAGNOSTIC TEXT: {len(text)} chars | '
            f'title={clean(title)[:120]}'
        )

        if len(text) >= 500:
            print('DIAGNOSTIC RESULT: ARTICLE TEXT ACCEPTED')
            return text, title

        print('DIAGNOSTIC RESULT: ARTICLE TEXT TOO SHORT')

    except Exception as exc:
        print(f'DIAGNOSTIC FETCH ERROR: {type(exc).__name__}: {exc}')

    return '', ''


def research(candidate, max_sources=6):
    print('========== RESEARCH DIAGNOSTICS ==========')
    print(f"CANDIDATE TITLE: {candidate.get('title', '')}")
    print(f"CANDIDATE URL: {candidate.get('url', '')}")
    print(f"CANDIDATE PUBLISHER: {candidate.get('feed', '')}")
    print(
        f"CANDIDATE DESCRIPTION: "
        f"{len(candidate.get('description', ''))} chars"
    )

    sources = []
    seen = set()

    add_source(
        sources,
        seen,
        candidate.get('title', ''),
        candidate.get('url', ''),
        candidate.get('description', ''),
        candidate.get('published', ''),
        candidate.get('feed', '')
    )

    print(f'INITIAL SOURCES: {len(sources)}')

    query = urllib.parse.quote(candidate.get('title', ''))

    google_url = (
        'https://news.google.com/rss/search?q='
        + query
        + '&hl=en-US&gl=UG&ceid=UG:en'
    )

    print(f'GOOGLE RSS QUERY: {candidate.get("title", "")}')

    try:
        status, _, body = request(google_url, timeout=20)

        print(
            f'GOOGLE RSS HTTP: {status} | '
            f'{len(body)} bytes'
        )

        if status < 400:
            root = ET.fromstring(body)
            items = root.findall('.//item')

            print(f'GOOGLE RSS ITEMS: {len(items)}')

            for item in items[:20]:
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

                print(
                    f'GOOGLE SOURCE: {publisher} | '
                    f'{title[:100]} | '
                    f'description={len(description)} chars'
                )

                add_source(
                    sources,
                    seen,
                    title,
                    url,
                    description,
                    item.findtext('pubDate') or '',
                    publisher
                )

                if len(sources) >= max_sources:
                    break

    except Exception as exc:
        print(
            f'GOOGLE RSS ERROR: '
            f'{type(exc).__name__}: {exc}'
        )

    print(f'SOURCES AFTER GOOGLE: {len(sources)}')

    if len(sources) < max_sources:
        try:
            gdelt_url = (
                'https://api.gdeltproject.org/api/v2/doc/doc?query='
                + query
                + '&mode=ArtList&maxrecords=20&format=json&sort=HybridRel'
            )

            print('GDELT QUERY START')

            status, _, body = request(
                gdelt_url,
                timeout=20
            )

            print(
                f'GDELT HTTP: {status} | '
                f'{len(body)} bytes'
            )

            if status < 400:
                data = json.loads(
                    body.decode('utf-8', 'replace')
                )

                articles = data.get('articles', [])

                print(
                    f'GDELT ARTICLES: {len(articles)}'
                )

                for item in articles:
                    print(
                        f'GDELT SOURCE: '
                        f'{item.get("domain", "")} | '
                        f'{str(item.get("title", ""))[:100]}'
                    )

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

        except Exception as exc:
            print(
                f'GDELT ERROR: '
                f'{type(exc).__name__}: {exc}'
            )

    print(f'TOTAL DISCOVERED SOURCES: {len(sources)}')

    packet = []
    seen_publishers = set()

    for number, src in enumerate(sources, 1):
        if len(packet) >= max_sources:
            break

        url = src['url']
        publisher = clean(src.get('feed', ''))
        publisher_key = publisher.lower() or domain(url)

        print(
            f'SOURCE {number}: '
            f'publisher={publisher} | '
            f'domain={domain(url)} | '
            f'fallback={len(src.get("description", ""))} chars'
        )

        text, title = fetch_article(url)

        if text:
            if publisher_key in seen_publishers:
                print(
                    f'SOURCE {number}: SKIPPED duplicate publisher '
                    f'{publisher_key}'
                )
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

            print(
                f'SOURCE {number}: ACCEPTED ARTICLE TEXT'
            )
            continue

        fallback = clean(src.get('description', ''))

        if len(fallback) >= 250:
            if publisher_key in seen_publishers:
                print(
                    f'SOURCE {number}: SKIPPED duplicate publisher '
                    f'{publisher_key}'
                )
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

            print(
                f'SOURCE {number}: ACCEPTED RSS/GDELT FALLBACK'
            )
        else:
            print(
                f'SOURCE {number}: REJECTED '
                f'fallback only {len(fallback)} chars'
            )

    print(f'FINAL USABLE SOURCES: {len(packet)}')

    for number, src in enumerate(packet, 1):
        print(
            f'FINAL SOURCE {number}: '
            f'{src["publisher"]} | '
            f'{src["url"]} | '
            f'{len(src["text"])} chars'
        )

    print('========== END RESEARCH DIAGNOSTICS ==========')

    return packet