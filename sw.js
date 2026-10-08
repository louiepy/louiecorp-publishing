/* LouieCorp Publishing — public static service worker
   News-safe: static assets may be cached; dynamic news/API never is. */
const CACHE_VERSION = 'louiecorp-static-v1';
const OFFLINE_URL = '/offline.html';

const PRECACHE = [
  '/',
  '/index.html',
  '/offline.html',
  '/css/styles.css',
  '/js/config.js',
  '/js/script.js',
  '/js/pwa.js',
  '/manifest.webmanifest',
  '/icon.svg',
  '/og-default.png',
  '/fonts/unifrakturmaguntia.woff2',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/apple-touch-icon.png'
];

function isAdminPath(url) {
  try {
    const path = new URL(url).pathname;
    return path === '/admin' || path.startsWith('/admin/');
  } catch (e) {
    return false;
  }
}

function isSupabase(url) {
  try {
    const host = new URL(url).hostname;
    return host.includes('supabase.co') || host.includes('supabase.in');
  } catch (e) {
    return false;
  }
}

function isWorkerOrMedia(url) {
  try {
    const u = new URL(url);
    if (u.hostname.includes('workers.dev')) return true;
    if (u.pathname.startsWith('/media/')) return true;
    if (u.pathname.startsWith('/share/')) return true;
    return false;
  } catch (e) {
    return false;
  }
}

function isStaticAsset(url) {
  try {
    const path = new URL(url).pathname;
    return (
      path.startsWith('/css/') ||
      path.startsWith('/fonts/') ||
      path.startsWith('/icons/') ||
      path === '/icon.svg' ||
      path === '/og-default.png' ||
      path === '/manifest.webmanifest' ||
      path === '/js/config.js' ||
      path === '/js/script.js' ||
      path === '/js/pwa.js' ||
      path === '/js/supabase-client.js' ||
      path === '/js/articles.js' ||
      path === '/js/pdf.js' ||
      /\.(?:css|js|woff2?|png|svg|ico|webmanifest)$/i.test(path)
    );
  } catch (e) {
    return false;
  }
}

function isHtmlNavigation(request) {
  if (request.mode === 'navigate') return true;
  const accept = request.headers.get('accept') || '';
  return request.method === 'GET' && accept.includes('text/html');
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) =>
      cache.addAll(PRECACHE).catch(() => {
        /* individual failures are fine; install still completes */
      })
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_VERSION)
          .map((key) => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = request.url;

  // Never intercept admin, Supabase, or Worker/media
  if (isAdminPath(url) || isSupabase(url) || isWorkerOrMedia(url)) {
    return;
  }

  // Cross-origin: only handle same-origin
  try {
    if (new URL(url).origin !== self.location.origin) return;
  } catch (e) {
    return;
  }

  // HTML navigations: network-first, offline fallback
  if (isHtmlNavigation(request)) {
    event.respondWith(networkFirstHtml(request));
    return;
  }

  // Static assets: cache-first
  if (isStaticAsset(url)) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Everything else on-origin: network only (freshness for news shells that are not pure static)
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});

async function networkFirstHtml(request) {
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      const copy = response.clone();
      const cache = await caches.open(CACHE_VERSION);
      // Only cache known public shells, not arbitrary dynamic paths as "latest news"
      const path = new URL(request.url).pathname;
      const safeShell =
        path === '/' ||
        path === '/index.html' ||
        path === '/offline.html' ||
        path === '/about.html' ||
        path === '/contact.html' ||
        path === '/search.html' ||
        path === '/section.html' ||
        path === '/article.html' ||
        path === '/200.html' ||
        path === '/author.html' ||
        path === '/privacy.html' ||
        path === '/terms.html' ||
        path === '/submit.html' ||
        path === '/editorial-policy.html' ||
        path === '/advertising.html' ||
        path === '/corrections.html' ||
        path === '/sitemap.html';
      if (safeShell) {
        cache.put(request, copy).catch(() => {});
      }
      return response;
    }
  } catch (e) {
    /* network failed */
  }
  const cached = await caches.match(request);
  if (cached) return cached;
  const offline = await caches.match(OFFLINE_URL);
  if (offline) return offline;
  return new Response('You are offline.', {
    status: 503,
    statusText: 'Offline',
    headers: { 'Content-Type': 'text/plain; charset=utf-8' }
  });
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      const cache = await caches.open(CACHE_VERSION);
      cache.put(request, response.clone()).catch(() => {});
    }
    return response;
  } catch (e) {
    if (request.url.includes('offline.html')) {
      return new Response('Offline', { status: 503 });
    }
    throw e;
  }
}
