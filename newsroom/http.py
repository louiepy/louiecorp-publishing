import json
import urllib.error
import urllib.parse
import urllib.request
import zlib
from html.parser import HTMLParser

from .config import USER_AGENT


def decode_body(raw_body, headers=None):
    headers = headers or {}
    body = raw_body or b''
    encoding = str(
        headers.get('Content-Encoding')
        or headers.get('content-encoding')
        or ''
    ).lower().strip()

    try:
        if (
            encoding == 'gzip'
            or body.startswith(b'\x1f\x8b')
        ):
            body = zlib.decompress(
                body,
                16 + zlib.MAX_WBITS,
            )

        elif encoding == 'deflate':
            try:
                body = zlib.decompress(body)
            except zlib.error:
                body = zlib.decompress(
                    body,
                    -zlib.MAX_WBITS,
                )

    except zlib.error:
        return raw_body or b''

    return body


def body_text(raw_body, headers=None, limit=None):
    text = decode_body(
        raw_body,
        headers,
    ).decode(
        'utf-8',
        'replace',
    )

    if limit is not None:
        return text[:limit]

    return text


def request(
    url,
    method='GET',
    data=None,
    headers=None,
    timeout=25,
):
    hdr = {
        'User-Agent': USER_AGENT,
        'Accept': (
            'text/html,application/xhtml+xml,'
            'application/xml;q=0.9,'
            'application/json;q=0.9,'
            '*/*;q=0.8'
        ),
        'Accept-Language': 'en-US,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'close',
    }

    if headers:
        hdr.update(headers)

    body = None

    if data is not None:
        if isinstance(data, bytes):
            body = data
        else:
            body = json.dumps(data).encode('utf-8')

        hdr.setdefault(
            'Content-Type',
            'application/json',
        )

    try:
        req = urllib.request.Request(
            url,
            data=body,
            headers=hdr,
            method=method,
        )

        with urllib.request.urlopen(
            req,
            timeout=timeout,
        ) as response:
            status = response.status
            response_headers = response.headers
            raw_body = response.read()

            return (
                status,
                response_headers,
                decode_body(
                    raw_body,
                    response_headers,
                ),
            )

    except urllib.error.HTTPError as error:
        try:
            body = error.read()
        except Exception:
            body = b''

        return (
            error.code,
            error.headers,
            decode_body(
                body,
                error.headers,
            ),
        )

    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
        OSError,
    ) as error:
        print(
            f'HTTP warning: {type(error).__name__}: {error}'
        )

        return (
            0,
            {},
            b'',
        )

    except Exception as error:
        print(
            f'HTTP warning: {type(error).__name__}: {error}'
        )

        return (
            0,
            {},
            b'',
        )


def get_json(
    url,
    headers=None,
    timeout=25,
):
    status, _, body = request(
        url,
        headers=headers,
        timeout=timeout,
    )

    if status == 0:
        raise RuntimeError(
            f'Unable to reach {url}'
        )

    if status >= 400:
        raise RuntimeError(
            f'HTTP {status}: '
            f'{body_text(body, limit=500)}'
        )

    try:
        return json.loads(
            body_text(body)
        )
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f'Invalid JSON response from {url}: {error}'
        ) from error


class TextParser(HTMLParser):

    def __init__(self):
        super().__init__(
            convert_charrefs=True
        )

        self.skip = 0
        self.parts = []
        self.title = ''
        self.in_title = False

        self.skip_tags = {
            'script',
            'style',
            'noscript',
            'svg',
            'nav',
            'footer',
            'header',
            'form',
            'aside',
            'menu',
            'iframe',
            'template',
        }

    def handle_starttag(
        self,
        tag,
        attrs,
    ):
        tag = tag.lower()

        if tag in self.skip_tags:
            self.skip += 1

        if tag == 'title':
            self.in_title = True

    def handle_startendtag(
        self,
        tag,
        attrs,
    ):
        # Self-closing tags do not need normal skip-depth handling.
        pass

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag == 'title':
            self.in_title = False

        if (
            tag in self.skip_tags
            and self.skip
        ):
            self.skip -= 1

    def handle_data(self, data):
        if self.in_title:
            self.title += ' ' + data

        if (
            not self.skip
            and data
            and data.strip()
        ):
            self.parts.append(
                data.strip()
            )

    def handle_comment(self, data):
        pass

    def handle_entityref(self, name):
        pass

    def handle_charref(self, name):
        pass


def extract_text(
    html,
    limit=12000,
):
    if not html:
        return '', ''

    parser = TextParser()

    try:
        parser.feed(html)
        parser.close()
    except Exception:
        # A malformed publisher page should never crash
        # the entire newsroom run.
        pass

    text = ' '.join(
        parser.parts
    )

    title = ' '.join(
        parser.title.split()
    )

    text = ' '.join(
        text.split()
    )

    return (
        text[:limit],
        title[:300],
    )
