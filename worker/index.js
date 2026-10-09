const ALLOWED_FOLDERS = new Set(['covers', 'authors', 'pdfs', 'sources']);
const BOT_MAX_UPLOAD_BYTES = 12 * 1024 * 1024;
// The newsroom only selects photographs through Wikimedia Commons and Unsplash.
// Permit their documented image hosts/subdomains, not arbitrary user-supplied hosts.
const BOT_IMAGE_HOSTS = new Set([
  'commons.wikimedia.org',
  'upload.wikimedia.org',
  'wikimedia.org',
  'wikipedia.org',
  'images.unsplash.com',
  'plus.unsplash.com'
]);

export function isApprovedBotImageSource(value) {
  try {
    const source = new URL(String(value || '').trim());
    if (source.protocol !== 'https:' || source.username || source.password) return false;
    const host = source.hostname.toLowerCase();
    return BOT_IMAGE_HOSTS.has(host) ||
      host.endsWith('.wikimedia.org') ||
      host.endsWith('.wikipedia.org') ||
      host.endsWith('.unsplash.com');
  } catch (_) {
    return false;
  }
}
const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
const SITE_ORIGIN = 'https://louiecorp.com';
const PUBLISHER_NAME = 'LouieCorp Publishing';
const DEFAULT_AUTHOR = 'Sentongo. R. Louis';
const PRODUCTION_ORIGINS = new Set([
  'https://louiecorp.com',
  'https://www.louiecorp.com',
  'http://louiecorp.com',
  'http://www.louiecorp.com'
]);

function json(body, status, extraHeaders) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      ...(extraHeaders || {})
    }
  });
}

function isLocalDevOrigin(origin) {
  return /^https?:\/\/(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$/i.test(String(origin || '').trim());
}

function isAllowedOrigin(origin) {
  const value = String(origin || '').trim().replace(/\/+$/, '');
  if (!value || value === 'null') return false;
  if (PRODUCTION_ORIGINS.has(value) || isLocalDevOrigin(value)) return true;
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase();
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return false;
    if (host === 'louiecorp.com' || host === 'www.louiecorp.com' || host.endsWith('.louiecorp.com')) return true;
    if (host === 'surge.sh' || host.endsWith('.surge.sh')) return true;
    if (host === 'monkeycode-ai.live' || host.endsWith('.monkeycode-ai.live')) return true;
    return false;
  } catch (error) {
    return false;
  }
}

function requestOrigin(request) {
  return String(request.headers.get('Origin') || '').trim();
}

function corsHeaders(request, publicResource) {
  const origin = requestOrigin(request);
  const requested = request.headers.get('Access-Control-Request-Headers');
  const headers = {
    'Access-Control-Allow-Methods': 'GET, PUT, DELETE, HEAD, OPTIONS',
    'Access-Control-Allow-Headers': requested || 'Authorization, Content-Type, Cache-Control, Accept',
    'Access-Control-Expose-Headers': 'ETag, Content-Length, Content-Type, Cache-Control',
    'Access-Control-Max-Age': '86400',
    Vary: 'Origin'
  };
  if (publicResource) {
    headers['Access-Control-Allow-Origin'] = '*';
    return headers;
  }
  if (isAllowedOrigin(origin)) {
    headers['Access-Control-Allow-Origin'] = origin;
  }
  return headers;
}

function mediaKeyFromPath(pathname) {
  const match = String(pathname || '').match(/^\/media\/(.+)$/);
  if (!match) return '';
  let key = '';
  try {
    key = decodeURIComponent(match[1]);
  } catch (error) {
    return '';
  }
  key = key.replace(/^\/+/, '').replace(/\\/g, '');
  if (key.includes('..')) return '';
  const parts = key.split('/');
  if (parts.length !== 2) return '';
  const folder = parts[0];
  const name = parts[1];
  if (!ALLOWED_FOLDERS.has(folder)) return '';
  if (!/^[a-zA-Z0-9._-]+$/.test(name)) return '';
  if (name.length > 180) return '';
  return `${folder}/${name}`;
}

async function requireEditor(request, env) {
  const cors = corsHeaders(request, false);
  const header = request.headers.get('Authorization') || '';
  const token = header.replace(/^Bearer\s+/i, '').trim();
  if (!token) {
    return json({ error: 'Sign in required.' }, 401, cors);
  }
  const supabaseUrl = String(env.SUPABASE_URL || '').replace(/\/+$/, '');
  const anonKey = env.SUPABASE_ANON_KEY || '';
  if (!supabaseUrl || !anonKey) {
    return json({ error: 'Media worker is not configured.' }, 500, cors);
  }
  let response;
  try {
    response = await fetch(`${supabaseUrl}/auth/v1/user`, {
      headers: {
        Authorization: `Bearer ${token}`,
        apikey: anonKey
      }
    });
  } catch (error) {
    return json({ error: 'Could not validate the editor session.' }, 502, cors);
  }
  if (!response.ok) {
    return json({ error: 'Invalid or expired session.' }, 401, cors);
  }
  return null;
}

function looksLikePdf(bytes) {
  if (!bytes || bytes.byteLength < 5) return false;
  const header = new Uint8Array(bytes.slice(0, 5));
  return header[0] === 0x25 && header[1] === 0x50 && header[2] === 0x44 && header[3] === 0x46;
}

async function handleBotPdf(request, env, key) {
  const contentType = String(request.headers.get('Content-Type') || '').toLowerCase();
  if (!contentType.includes('pdf')) return json({ error: 'Source is not a PDF.' }, 415);
  const length = Number(request.headers.get('Content-Length') || 0);
  if (length && length > BOT_MAX_UPLOAD_BYTES) return json({ error: 'PDF is too large.' }, 413);
  const bytes = await request.arrayBuffer();
  if (!bytes.byteLength) return json({ error: 'Empty PDF.' }, 400);
  if (bytes.byteLength > BOT_MAX_UPLOAD_BYTES) return json({ error: 'PDF is too large.' }, 413);
  if (!looksLikePdf(bytes)) return json({ error: 'Source is not a PDF.' }, 415);
  if (!env.MEDIA_BUCKET) return json({ error: 'R2 bucket is not bound.' }, 500);
  await env.MEDIA_BUCKET.put(key, bytes, {
    httpMetadata: {
      contentType: 'application/pdf',
      cacheControl: 'public, max-age=31536000, immutable'
    }
  });
  return json({ ok: true, key, url: `${new URL(request.url).origin}/media/${key}` }, 200);
}

export function authenticateBot(env, authorizationHeader) {
  const secret = String((env && env.MEDIA_BOT_SECRET) || '').trim();
  const supplied = String(authorizationHeader || '').replace(/^Bearer\s+/i, '').trim();
  if (!secret) {
    return { ok: false, status: 500, error: 'MEDIA_BOT_SECRET is not configured on the Worker.' };
  }
  if (!supplied || supplied !== secret) {
    return { ok: false, status: 401, error: 'Bot authentication failed.' };
  }
  return { ok: true };
}

async function handleBotMedia(request, env, pathname) {
  if (request.method !== 'PUT') return json({ error: 'Method not allowed.' }, 405);
  const auth = authenticateBot(env, request.headers.get('Authorization'));
  if (!auth.ok) return json({ error: auth.error }, auth.status);
  const pdfMatch = String(pathname || '').match(/^\/bot-media\/(pdfs\/[a-zA-Z0-9._-]+)$/);
  if (pdfMatch) return handleBotPdf(request, env, pdfMatch[1]);
  const match = String(pathname || '').match(/^\/bot-media\/(covers\/[a-zA-Z0-9._-]+)$/);
  if (!match) return json({ error: 'Invalid bot media path.' }, 400);
  const source = String(request.headers.get('X-Image-Source') || '').trim();
  let sourceUrl;
  try { sourceUrl = new URL(source); } catch (_) { return json({ error: 'Invalid image source.' }, 400); }
  if (!isApprovedBotImageSource(sourceUrl.toString())) {
    return json({ error: `Image source is not an approved host: ${sourceUrl.hostname || 'unknown'}.` }, 400);
  }
  let upstream;
  try {
    upstream = await fetch(sourceUrl.toString(), {
      headers: { 'User-Agent': 'LouieCorp-Newsroom/1.0 (+https://louiecorp.com/editorial-policy.html)', 'Accept': 'image/avif,image/webp,image/*,*/*;q=0.8' },
      redirect: 'follow',
      signal: AbortSignal.timeout(20000)
    });
  } catch (error) {
    return json({ error: 'Could not reach the approved image source. The newsroom can retry this run.' }, 502);
  }
  if (upstream.url && !isApprovedBotImageSource(upstream.url)) {
    return json({ error: 'Image source redirected outside the approved photo hosts.' }, 400);
  }
  if (!upstream.ok) return json({ error: `Could not fetch the source image (HTTP ${upstream.status}).` }, 502);
  const contentType = String(upstream.headers.get('Content-Type') || '');
  if (!contentType.toLowerCase().startsWith('image/')) return json({ error: 'Source is not an image.' }, 415);
  const length = Number(upstream.headers.get('Content-Length') || 0);
  if (length && length > BOT_MAX_UPLOAD_BYTES) return json({ error: 'Source image is too large.' }, 413);
  const bytes = await upstream.arrayBuffer();
  if (bytes.byteLength > BOT_MAX_UPLOAD_BYTES) return json({ error: 'Source image is too large.' }, 413);
  if (!env.MEDIA_BUCKET) return json({ error: 'R2 bucket is not bound.' }, 500);
  const key = match[1];
  await env.MEDIA_BUCKET.put(key, bytes, { httpMetadata: { contentType, cacheControl: 'public, max-age=31536000, immutable' } });
  return json({ ok: true, key, url: `${new URL(request.url).origin}/media/${key}` }, 200);
}

function objectHeaders(object, request) {
  const headers = corsHeaders(request, true);
  headers['Content-Type'] = object.httpMetadata && object.httpMetadata.contentType
    ? object.httpMetadata.contentType
    : 'application/octet-stream';
  headers['Cache-Control'] = object.httpMetadata && object.httpMetadata.cacheControl
    ? object.httpMetadata.cacheControl
    : 'public, max-age=31536000, immutable';
  headers['ETag'] = object.httpEtag || object.etag;
  if (object.size != null) headers['Content-Length'] = String(object.size);
  return headers;
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function collapseText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function excerptFromArticle(article) {
  const excerpt = collapseText(article && article.excerpt);
  if (excerpt) return excerpt.slice(0, 180);
  const body = collapseText(String(article && article.content || '').replace(/<[^>]+>/g, ' '));
  return body ? `${body.slice(0, 179)}…` : 'A published article from LouieCorp Publishing.';
}

function publicImageUrl(value) {
  const url = String(value || '').trim();
  if (!url) return '';
  if (/^https:\/\//i.test(url)) return url;
  if (/^http:\/\//i.test(url)) return url.replace(/^http:\/\//i, 'https://');
  if (url.startsWith('//')) return `https:${url}`;
  if (url.startsWith('/')) return `${SITE_ORIGIN}${url}`;
  return url;
}

function displayAuthorName(name) {
  const value = String(name || '').trim();
  if (!value || /^(editorial desk|louiecorp editorial(?:\s+desk)?|ai writer|admin|louiecorp)$/i.test(value)) {
    return DEFAULT_AUTHOR;
  }
  return value;
}

function storyShareHtml(article) {
  const title = article.title || 'LouieCorp';
  const description = excerptFromArticle(article);
  const slug = article.slug || '';
  const url = `${SITE_ORIGIN}/story/${encodeURIComponent(slug)}`;
  const cover = publicImageUrl(article.cover_image_url);
  const image = cover || `${SITE_ORIGIN}/og-default.png`;
  const imageType = cover ? 'image/jpeg' : 'image/png';
  const author = displayAuthorName(article.authors && article.authors.name);
  const desk = article.categories && article.categories.name ? article.categories.name : '';
  const published = article.published_at || '';
  const modified = article.updated_at || published;
  const xml = escapeHtml;
  const imageTags = `
  <meta property="og:image" content="${xml(image)}">
  <meta property="og:image:secure_url" content="${xml(image)}">
  <meta property="og:image:type" content="${imageType}">
  <meta property="og:image:alt" content="${xml(title)}">
  <meta name="twitter:image" content="${xml(image)}">
  <meta name="twitter:image:alt" content="${xml(title)}">
  <meta name="twitter:card" content="summary_large_image">`;
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'NewsArticle',
    headline: title,
    description,
    image: image ? [image] : undefined,
    datePublished: published || undefined,
    dateModified: modified || undefined,
    author: { '@type': 'Person', name: author },
    publisher: {
      '@type': 'NewsMediaOrganization',
      name: PUBLISHER_NAME,
      url: `${SITE_ORIGIN}/`,
      logo: { '@type': 'ImageObject', url: `${SITE_ORIGIN}/icon.svg` }
    },
    mainEntityOfPage: { '@type': 'WebPage', '@id': url },
    articleSection: desk || undefined,
    url
  };
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>${xml(title)} — LouieCorp</title>
  <meta name="description" content="${xml(description)}">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <meta name="author" content="${xml(author)}">
  <link rel="canonical" href="${xml(url)}">
  <meta property="og:site_name" content="${xml(PUBLISHER_NAME)}">
  <meta property="og:title" content="${xml(title)}">
  <meta property="og:description" content="${xml(description)}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="${xml(url)}">
  ${imageTags}
  <meta property="article:publisher" content="${xml(PUBLISHER_NAME)}">
  <meta property="article:author" content="${xml(author)}">
  ${published ? `<meta property="article:published_time" content="${xml(published)}">` : ''}
  ${modified ? `<meta property="article:modified_time" content="${xml(modified)}">` : ''}
  ${desk ? `<meta property="article:section" content="${xml(desk)}">` : ''}
  <meta name="twitter:title" content="${xml(title)}">
  <meta name="twitter:description" content="${xml(description)}">
  <meta name="twitter:label1" content="Written by">
  <meta name="twitter:data1" content="${xml(author)}">
  <meta name="twitter:label2" content="Published by">
  <meta name="twitter:data2" content="${xml(PUBLISHER_NAME)}">
  <script type="application/ld+json">${JSON.stringify(jsonLd).replace(/</g, '\\u003c')}</script>
</head>
<body>
  <article>
    <p>${xml(desk)}</p>
    <h1>${xml(title)}</h1>
    ${description ? `<p>${xml(description)}</p>` : ''}
    <p>By ${xml(author)} · ${xml(PUBLISHER_NAME)}</p>
    ${image ? `<img src="${xml(image)}" alt="${xml(title)}">` : ''}
  </article>
</body>
</html>`;
}

function storySlugFromPath(pathname) {
  const match = String(pathname || '').match(/^\/(?:share\/)?story\/([^/?#]+)$/);
  if (!match) return '';
  try {
    return decodeURIComponent(match[1]);
  } catch (error) {
    return match[1];
  }
}

async function fetchPublishedArticle(env, slug) {
  const supabaseUrl = String(env.SUPABASE_URL || '').replace(/\/+$/, '');
  const anonKey = env.SUPABASE_ANON_KEY || '';
  if (!supabaseUrl || !anonKey || !slug) return null;
  const endpoint = `${supabaseUrl}/rest/v1/articles?slug=eq.${encodeURIComponent(slug)}&status=eq.published&select=slug,title,excerpt,content,cover_image_url,published_at,updated_at,categories(name),authors:byline_author_id(name)&limit=1`;
  const response = await fetch(endpoint, {
    headers: {
      apikey: anonKey,
      Authorization: `Bearer ${anonKey}`
    }
  });
  if (!response.ok) return null;
  const rows = await response.json();
  return Array.isArray(rows) && rows[0] ? rows[0] : null;
}

async function handleShareStory(request, env, slug) {
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    return json({ error: 'Method not allowed.' }, 405, corsHeaders(request, true));
  }
  const article = await fetchPublishedArticle(env, slug);
  if (!article) {
    return json({ error: 'Not found.' }, 404, corsHeaders(request, true));
  }
  const html = storyShareHtml(article);
  const headers = {
    'Content-Type': 'text/html; charset=utf-8',
    'Cache-Control': 'public, max-age=300',
    ...corsHeaders(request, true)
  };
  if (request.method === 'HEAD') {
    return new Response(null, { status: 200, headers });
  }
  return new Response(html, { status: 200, headers });
}

async function handleRequest(request, env) {
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders(request, false) });
  }

  const url = new URL(request.url);
  if (url.pathname.startsWith('/bot-media/')) return handleBotMedia(request, env, url.pathname);
  const shareSlug = storySlugFromPath(url.pathname);
  if (shareSlug) {
    return handleShareStory(request, env, shareSlug);
  }

  const mutating = request.method === 'PUT' || request.method === 'DELETE';
  const cors = corsHeaders(request, !mutating);

  if (!env.MEDIA_BUCKET) {
    return json({ error: 'R2 bucket is not bound.' }, 500, cors);
  }

  const key = mediaKeyFromPath(url.pathname);
  if (!key) {
    return json({ error: 'Not found.' }, 404, cors);
  }

  if (request.method === 'GET' || request.method === 'HEAD') {
    const object = await env.MEDIA_BUCKET.get(key);
    if (!object) return json({ error: 'Not found.' }, 404, cors);
    const headers = objectHeaders(object, request);
    if (request.method === 'HEAD') {
      return new Response(null, { status: 200, headers });
    }
    return new Response(object.body, { status: 200, headers });
  }

  if (mutating) {
    const origin = requestOrigin(request);
    if (origin && !isAllowedOrigin(origin)) {
      return json({ error: 'Origin not allowed.' }, 403, cors);
    }
    const authError = await requireEditor(request, env);
    if (authError) return authError;
  }

  if (request.method === 'PUT') {
    const bytes = await request.arrayBuffer();
    if (bytes.byteLength > MAX_UPLOAD_BYTES) {
      return json({ error: 'File is too large.' }, 413, cors);
    }
    const contentType = request.headers.get('Content-Type') || 'application/octet-stream';
    const cacheControl = request.headers.get('Cache-Control') || 'public, max-age=31536000, immutable';
    await env.MEDIA_BUCKET.put(key, bytes, {
      httpMetadata: {
        contentType,
        cacheControl
      }
    });
    const publicUrl = `${url.origin}/media/${key}`;
    return json({ url: publicUrl, key }, 200, cors);
  }

  if (request.method === 'DELETE') {
    await env.MEDIA_BUCKET.delete(key);
    return json({ ok: true, key }, 200, cors);
  }

  return json({ error: 'Method not allowed.' }, 405, cors);
}

export default {
  async fetch(request, env) {
    try {
      return await handleRequest(request, env);
    } catch (error) {
      return json({ error: 'Media worker error.' }, 500, corsHeaders(request, false));
    }
  }
};
