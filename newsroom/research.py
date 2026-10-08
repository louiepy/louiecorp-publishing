import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from .http import request, extract_text


def _clean(value):
    return ' '.join((value or '').split())


def _domain(url):
    try:
        return urllib.parse.urlparse(url).netloc.lower().replace('www.', '')
    except Exception:
        return ''


def _add_source(sources, seen_urls, title, url, description='', published='', publisher=''):
    url = _clean(url)

    if not url or url in seen_urls:
        return

    seen_urls.add(url)

    sources.append({
        'title': _clean(title) or 'Related source',
        'url': url,
        'description': _clean(description),
        'published': published or '',
        'track': 'news',
        'feed': _clean(publisher) or _domain(url) or 'News source'
    })


def _resolve_url(url):
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; LouieCorp-Newsroom/1.0)',
                'Accept': 'text/html,application/xhtml+xml,*/*'
            }
        )

        with urllib.request.urlopen(req, timeout=20) as response:
            return response.geturl()

    except Exception:
        return url


def _usable_text(html):
    try:
        text, title = extract_text(
            html.decode('utf-8', 'replace')
        )
        text = _clean(text)

        if len(text) >= 500:
            return text, title

    except Exception:
        pass

    return '', ''


def research(candidate, max_sources=6):
    sources = []
    seen_urls = set()

    candidate_url = candidate.get('url', '')

    if candidate_url:
        _add_source(
            sources,
            seen_urls,
            candidate.get('title', ''),
            candidate_url,
            candidate.get('description', ''),
            candidate.get('published', ''),
            candidate.get('feed', '')
        )

    query = urllib.parse.quote(candidate.get('title', ''))

    # Google News RSS
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
                description = _clean(
                    re.sub(
                        '<[^>]+>',
                        ' ',
                        item.findtext('description') or ''
                    )
                )
                published = _clean(item.findtext('pubDate'))

                source_node = item.find(
                    '{http://search.yahoo.com/mrss/}source'
                )

                publisher = (
                    _clean(source_node.text)
                    if source_node is not None
                    else ''
                )

                _add_source(
                    sources,
                    seen_urls,
                    title,
                    url,
                    description,
                    published,
                    publisher
                )

                if len(sources) >= max_sources:
                    break

    except Exception as exc:
        print(f'Google News discovery warning: {exc}')

    # GDELT
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

    for src in sources:
        if len(packet) >= max_sources:
            break

        original_url = src['url']
        resolved_url = _resolve_url(original_url)

        candidates = [resolved_url]

        if resolved_url != original_url:
            candidates.append(original_url)

        article_text = ''
        article_title = ''

        for url in candidates:
            try:
                status, _, body = request(
                    url,
                    timeout=20
                )

                if status >= 400:
                    continue

                article_text, article_title = _usable_text(body)

                if article_text:
                    break

            except Exception as exc:
                print(
                    f'Source fetch warning for {url}: {exc}'
                )

        domain = _domain(resolved_url)

        # Prefer genuinely extracted publisher text.
        if article_text:
            if domain in seen_domains:
                continue

            seen_domains.add(domain)

            packet.append({
                'title': article_title or src['title'],
                'url': resolved_url,
                'publisher': src.get('feed') or domain or 'Source',
                'retrieved_at': datetime.now(
                    timezone.utc
                ).isoformat(),
                'text': article_text[:9000]
            })

            continue

        # Some publishers block automated article retrieval.
        # A substantial RSS description can still provide a
        # second independent source for the research packet.
        fallback = _clean(src.get('description', ''))

        if len(fallback) >= 300:
            if domain in seen_domains:
                continue

            seen_domains.add(domain)

            packet.append({
                'title': src['title'],
                'url': resolved_url,
                'publisher': src.get('feed') or domain or 'News source',
                'retrieved_at': datetime.now(
                    timezone.utc
                ).isoformat(),
                'text': fallback[:9000]
            })

    return packet