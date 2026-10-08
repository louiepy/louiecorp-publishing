import re
import urllib.parse
import xml.etree.ElementTree as ET

from .config import RSS_FEEDS
from .http import request


def clean(value):
    return ' '.join((value or '').split())


def extract_publisher(item_title, source_text, url, fallback=''):
    """
    Extract the actual publisher without allowing Google News feed
    names to become the publisher identity.
    """
    source = clean(source_text)

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

    if source and source.lower() not in invalid:
        return source

    title = clean(item_title)

    # Google News commonly formats:
    # Headline - Publisher
    if ' - ' in title:
        possible = title.rsplit(' - ', 1)[-1].strip()

        if 1 < len(possible) < 100:
            if possible.lower() not in invalid:
                return possible

    try:
        host = urllib.parse.urlparse(
            clean(url)
        ).netloc.lower().replace('www.', '')

        if (
            host
            and host != 'news.google.com'
            and not host.endswith('.google.com')
        ):
            return host
    except Exception:
        pass

    return clean(fallback)


def discover():
    out = []

    for feed_name, url, track in RSS_FEEDS:
        try:
            status, _, body = request(
                url,
                timeout=20,
            )

            if status >= 400:
                print(
                    f'Discovery warning: {feed_name} '
                    f'returned HTTP {status}'
                )
                continue

            root = ET.fromstring(body)

            items = root.findall('.//item')

            for item in items[:30]:
                title = clean(
                    item.findtext('title')
                )

                link = clean(
                    item.findtext('link')
                )

                description = clean(
                    re.sub(
                        r'<[^>]+>',
                        ' ',
                        item.findtext('description') or '',
                    )
                )

                published = clean(
                    item.findtext('pubDate')
                )

                source_node = item.find(
                    '{http://search.yahoo.com/mrss/}source'
                )

                source = ''

                if source_node is not None:
                    source = clean(
                        source_node.text
                    )

                if not source:
                    source_node = item.find('source')

                    if source_node is not None:
                        source = clean(
                            source_node.text
                        )

                publisher = extract_publisher(
                    title,
                    source,
                    link,
                    feed_name,
                )

                if not title or not link:
                    continue

                out.append({
                    'title': title,
                    'url': link,
                    'description': description[:3000],
                    'published': published,
                    'track': track,
                    'feed': publisher,
                    'publisher': publisher,
                })

        except ET.ParseError as error:
            print(
                f'Discovery warning: {feed_name} '
                f'returned invalid RSS: {error}'
            )

        except Exception as error:
            print(
                f'Discovery warning: {feed_name}: '
                f'{type(error).__name__}: {error}'
            )

    # Remove duplicate headlines while preserving candidates
    # from genuinely different stories.
    seen_titles = set()
    unique = []

    for item in out:
        key = re.sub(
            r'[^a-z0-9]+',
            ' ',
            item['title'].lower(),
        ).strip()

        if not key:
            continue

        if key in seen_titles:
            continue

        seen_titles.add(key)
        unique.append(item)

    print(
        f'Discovered {len(unique)} unique candidates '
        f'from {len(out)} feed items.'
    )

    # Helpful visibility for Actions logs.
    by_track = {}

    for item in unique:
        track = item.get('track') or 'unknown'
        by_track[track] = by_track.get(track, 0) + 1

    for track, count in sorted(
        by_track.items()
    ):
        print(
            f'Discovery track: {track} = {count}'
        )

    return unique
