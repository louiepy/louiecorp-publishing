import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from .config import USER_AGENT
from .http import extract_text, request

INVALID_PUBLISHERS = {
    'google news',
    'google news uganda',
    'google news kampala',
    'google news uganda government',
    'google news uganda economy',
    'google news monitor uganda',
    'google news new vision',
    'google news nile post',
    'google news independent uganda',
    'google news chimpreports',
    'google news africa',
    'google news world',
    'google news science',
    'news source',
    'news.google.com',
    'google.com',
}

MIN_FALLBACK_TEXT = 140


def clean(value):
    return ' '.join((value or '').split())


def domain(url):
    try:
        host = urllib.parse.urlparse(
            clean(url)
        ).netloc.lower().strip()
        if host.startswith('www.'):
            host = host[4:]
        return host
    except Exception:
        return ''


def is_google_domain(host):
    host = clean(host).lower()
    return (
        host == 'google.com'
        or host.endswith('.google.com')
        or host.endswith('.googleusercontent.com')
    )


def normalize_publisher_text(value):
    text = clean(value).lower()
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    text = clean(text)

    if (
        not text
        or text in INVALID_PUBLISHERS
        or text.startswith('google news')
    ):
        return ''

    return text


def publisher_name(value, url='', source_url=''):
    label = clean(value)

    if normalize_publisher_text(label):
        return label

    for candidate in [source_url, url]:
        host = domain(candidate)

        if host and not is_google_domain(host):
            return host

    return ''


def publisher_key(publisher, url='', source_url=''):
    for candidate in [source_url, url]:
        host = domain(candidate)

        if host and not is_google_domain(host):
            return host

    normalized = normalize_publisher_text(
        publisher
    )

    if normalized:
        return f'name:{normalized}'

    return ''


def remove_tags(value):
    return clean(
        html.unescape(
            re.sub(
                r'<[^>]+>',
                ' ',
                str(value or ''),
            )
        )
    )


def normalize_url(url):
    value = clean(url)

    if not value:
        return ''

    try:
        parsed = urllib.parse.urlparse(value)

        if parsed.scheme not in {'http', 'https'}:
            return ''

        return urllib.parse.urlunparse(
            parsed._replace(fragment='')
        )
    except Exception:
        return ''


HOMEPAGE_SEGMENTS = {
    'index.html',
    'index.php',
    'home',
    'news',
    'en',
    'uk',
    'us',
    'africa',
    'world',
    'uganda',
    'latest',
    'headlines',
    'sport',
    'sports',
    'business',
    'politics',
    'opinion',
    'video',
    'videos',
    'photos',
    'live',
    'about',
    'contact',
}


def is_homepage_url(url):
    value = normalize_url(url)

    if not value:
        return False

    parsed = urllib.parse.urlparse(value)
    segments = [
        item
        for item in parsed.path.split('/')
        if item
    ]

    if not segments:
        return True

    if len(segments) == 1:
        seg = segments[0].lower()

        if seg in HOMEPAGE_SEGMENTS:
            return True

        if (
            '-' not in seg
            and '_' not in seg
            and not any(char.isdigit() for char in seg)
            and len(seg) < 24
        ):
            return True

    return False


def source_text_tokens(text):
    return set(
        re.findall(
            r'[a-z0-9]{4,}',
            clean(text).lower()[:2500],
        )
    )


def is_syndicated_copy(tokens, seen_token_sets):
    if len(tokens) < 24:
        return False

    for other in seen_token_sets:
        union = len(tokens | other)

        if union < 24:
            continue

        if len(tokens & other) / union >= 0.72:
            return True

    return False


def decode_google_query_url(url):
    value = normalize_url(url)

    if not value:
        return ''

    parsed = urllib.parse.urlparse(value)

    for key in ('url', 'u', 'q'):
        options = urllib.parse.parse_qs(
            parsed.query
        ).get(key)

        if not options:
            continue

        candidate = normalize_url(options[0])

        if candidate and not is_google_domain(
            domain(candidate)
        ):
            return candidate

    return ''


def extract_links(value):
    links = []

    for match in re.findall(
        r'href=["\']([^"\']+)["\']',
        str(value or ''),
        flags=re.I,
    ):
        candidate = normalize_url(
            html.unescape(match)
        )

        if not candidate:
            continue

        if candidate in links:
            continue

        links.append(candidate)

    return links


def follow_redirect(url):
    value = normalize_url(url)

    if not value:
        return ''

    try:
        req = urllib.request.Request(
            value,
            headers={
                'User-Agent': USER_AGENT,
                'Accept': (
                    'text/html,application/xhtml+xml,'
                    'application/xml;q=0.9,*/*;q=0.8'
                ),
            },
        )

        with urllib.request.urlopen(
            req,
            timeout=20,
        ) as response:
            final = normalize_url(
                response.geturl()
            )

            if final:
                return final

    except Exception:
        pass

    return ''


def resolve_source_url(source):
    url = normalize_url(
        source.get('url', '')
    )

    source_url = normalize_url(
        source.get('source_url', '')
    )

    related = [
        normalize_url(item)
        for item in source.get(
            'related_urls',
            [],
        )
    ]

    candidates = []

    decoded = decode_google_query_url(url)

    if decoded:
        candidates.append(decoded)

    candidates.extend(
        item
        for item in related
        if item
    )

    if source_url:
        candidates.append(source_url)

    if url:
        candidates.append(url)

    # Always keep deterministic order while deduplicating.
    ordered = []
    seen = set()

    for item in candidates:
        if not item or item in seen:
            continue

        seen.add(item)
        ordered.append(item)

    article_urls = [
        item
        for item in ordered
        if not is_google_domain(domain(item))
        and not is_homepage_url(item)
    ]

    for item in article_urls:
        return item

    if url and is_google_domain(domain(url)):
        redirected = follow_redirect(url)

        if (
            redirected
            and not is_google_domain(domain(redirected))
            and not is_homepage_url(redirected)
        ):
            return redirected

    return ''


def add_source(
    sources,
    seen_urls,
    title,
    url,
    description='',
    published='',
    publisher='',
    source_url='',
    related_urls=None,
):
    title = clean(title)
    url = normalize_url(url)
    source_url = normalize_url(source_url)
    description = clean(description)

    if source_url and is_homepage_url(source_url):
        source_url = ''

    if url and is_homepage_url(url):
        url = ''

    links = []

    for item in related_urls or []:
        normalized = normalize_url(item)

        if (
            not normalized
            or normalized in links
            or is_homepage_url(normalized)
        ):
            continue

        links.append(normalized)

    if not url and not source_url:
        if links:
            url = links[0]
        else:
            return

    dedupe_url = url or source_url

    if not dedupe_url or dedupe_url in seen_urls:
        return

    seen_urls.add(dedupe_url)

    sources.append({
        'title': title or 'Related report',
        'url': url,
        'description': description,
        'published': clean(published),
        'publisher': clean(publisher),
        'source_url': source_url,
        'related_urls': links,
    })


def fetch_article(url):
    target = normalize_url(url)

    if not target:
        return '', ''

    if is_google_domain(domain(target)):
        return '', ''

    try:
        status, headers, body = request(
            target,
            timeout=20,
        )

        if status >= 400:
            return '', ''

        content_type = ''

        try:
            content_type = str(
                headers.get('Content-Type', '')
            ).lower()
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


def fallback_text(source):
    text = remove_tags(
        source.get('description', '')
    )

    text = re.sub(
        r'view full coverage on google news\b',
        ' ',
        text,
        flags=re.I,
    )

    text = re.sub(
        r'\bgoogle news\b',
        ' ',
        text,
        flags=re.I,
    )

    text = clean(text)

    if len(text) < MIN_FALLBACK_TEXT:
        return ''

    words = re.findall(
        r'[a-z0-9]{3,}',
        text.lower(),
    )

    if len(set(words)) < 18:
        return ''

    return text


def source_from_google_item(item):
    title = clean(
        item.findtext('title')
    )

    url = clean(item.findtext('link'))
    description_html = item.findtext('description') or ''
    description = remove_tags(description_html)
    related_urls = extract_links(description_html)
    publisher = ''
    source_url = ''

    source_node = item.find(
        '{http://search.yahoo.com/mrss/}source'
    )

    if source_node is None:
        source_node = item.find('source')

    if source_node is not None:
        publisher = clean(source_node.text)
        source_url = clean(
            source_node.attrib.get('url', '')
        )

    if ' - ' in title:
        possible = title.rsplit(
            ' - ',
            1,
        )[-1].strip()

        if 1 < len(possible) < 100:
            publisher = possible

    return {
        'title': title,
        'url': url,
        'description': description,
        'published': clean(
            item.findtext('pubDate') or ''
        ),
        'publisher': publisher,
        'source_url': source_url,
        'related_urls': related_urls,
    }


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
        candidate.get('publisher', ''),
        candidate.get('publisher_url', ''),
    )

    title_query = clean(
        candidate.get('title', '')
    )

    if not title_query:
        print(
            'Research warning: candidate has no title.'
        )
        return []

    query = urllib.parse.quote(title_query)

    google_url = (
        'https://news.google.com/rss/search?q='
        + query
        + '&hl=en-US&gl=UG&ceid=UG:en'
    )

    try:
        status, _, body = request(
            google_url,
            timeout=20,
        )

        if status < 400:
            root = ET.fromstring(body)

            for item in root.findall('.//item')[:30]:
                source = source_from_google_item(
                    item
                )

                add_source(
                    sources,
                    seen_urls,
                    source['title'],
                    source['url'],
                    source['description'],
                    source['published'],
                    source['publisher'],
                    source['source_url'],
                    source['related_urls'],
                )

    except ET.ParseError as error:
        print(
            'Research warning: Google News '
            'returned invalid RSS:',
            error,
        )
    except Exception as error:
        print(
            'Research warning: Google News:',
            type(error).__name__,
            error,
        )

    if len(sources) < max_sources:
        try:
            gdelt_url = (
                'https://api.gdeltproject.org/api/v2/doc/doc?query='
                + query
                + '&mode=ArtList&maxrecords=30'
                + '&format=json&sort=HybridRel'
            )

            status, _, body = request(
                gdelt_url,
                timeout=20,
            )

            if status < 400:
                data = json.loads(
                    body.decode('utf-8', 'replace')
                )

                for item in data.get(
                    'articles',
                    [],
                ):
                    add_source(
                        sources,
                        seen_urls,
                        item.get('title', ''),
                        item.get('url', ''),
                        item.get('snippet', ''),
                        item.get('seendate', ''),
                        item.get('domain', ''),
                        item.get('url', ''),
                    )

                    if len(sources) >= max_sources * 4:
                        break

        except Exception as error:
            print(
                'Research warning: GDELT:',
                type(error).__name__,
                error,
            )

    packet = []
    seen_publishers = set()
    seen_texts = set()
    seen_token_sets = []

    for source in sources:
        if len(packet) >= max_sources:
            break

        resolved_url = resolve_source_url(source)

        if not resolved_url:
            print(
                'Research skipped: no article URL '
                '(homepage or Google link rejected).'
            )
            continue

        if is_homepage_url(resolved_url):
            print(
                'Research skipped: publisher homepage '
                'cannot count as an article source:',
                resolved_url,
            )
            continue

        publisher = publisher_name(
            source.get('publisher', ''),
            resolved_url,
            source.get('source_url', ''),
        )

        key = publisher_key(
            publisher,
            resolved_url,
            source.get('source_url', ''),
        )

        if not key:
            continue

        if key in seen_publishers:
            continue

        text, article_title = fetch_article(
            resolved_url
        )

        if not text:
            text = fallback_text(source)

        if not text:
            continue

        fingerprint = clean(
            text[:450]
        ).lower()

        if fingerprint in seen_texts:
            continue

        tokens = source_text_tokens(text)

        if is_syndicated_copy(tokens, seen_token_sets):
            print(
                'Research skipped: syndicated copy '
                'is not independent reporting:',
                resolved_url,
            )
            continue

        seen_texts.add(fingerprint)
        seen_publishers.add(key)
        seen_token_sets.append(tokens)

        packet.append({
            'title': article_title
            or source.get('title', ''),
            'url': resolved_url,
            'publisher': publisher,
            'retrieved_at': datetime.now(
                timezone.utc
            ).isoformat(),
            'text': text[:9000],
        })

    print(
        f'Research produced {len(packet)} usable sources.'
    )

    for source in packet:
        print(
            'Research source:',
            source['publisher'],
            source['url'],
            f"({len(source['text'])} chars)",
        )

    if len(packet) < 2:
        print(
            'Research warning: fewer than two '
            'independent publishers were found for '
            'this candidate.'
        )

    return packet
