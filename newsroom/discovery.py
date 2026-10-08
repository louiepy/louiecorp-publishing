import re
import urllib.parse
import xml.etree.ElementTree as ET

from .config import RSS_FEEDS
from .http import request


def clean(value):
    return ' '.join((value or '').split())


def discover():
    out = []

    # Use the configured Google News RSS feeds as the primary
    # discovery source. Do not depend on GDELT being available.
    for publisher, url, track in RSS_FEEDS:
        try:
            status, _, body = request(url, timeout=20)

            if status >= 400:
                print(
                    f'Discovery warning: {publisher} returned HTTP {status}'
                )
                continue

            root = ET.fromstring(body)

            for item in root.findall('.//item')[:25]:
                title = clean(item.findtext('title'))
                link = clean(item.findtext('link'))

                description = clean(
                    re.sub(
                        r'<[^>]+>',
                        ' ',
                        item.findtext('description') or ''
                    )
                )

                pub = clean(item.findtext('pubDate'))

                source_node = item.find(
                    '{http://search.yahoo.com/mrss/}source'
                )

                source = (
                    clean(source_node.text)
                    if source_node is not None
                    else publisher
                )

                if not title or not link:
                    continue

                out.append({
                    'title': title,
                    'url': link,
                    'description': description[:2000],
                    'published': pub,
                    'track': track,
                    'feed': source or publisher
                })

        except ET.ParseError as error:
            print(
                f'Discovery warning: {publisher} returned invalid RSS: {error}'
            )
        except Exception as error:
            print(
                f'Discovery warning: {publisher}: '
                f'{type(error).__name__}: {error}'
            )

    # Remove duplicate headlines.
    seen = set()
    unique = []

    for item in out:
        key = re.sub(
            r'[^a-z0-9]+',
            ' ',
            item['title'].lower()
        ).strip()

        if not key or key in seen:
            continue

        seen.add(key)
        unique.append(item)

    print(f'Discovered {len(unique)} unique candidates.')

    return unique
