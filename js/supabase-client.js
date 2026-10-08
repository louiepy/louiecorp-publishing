(function initLouieCorpClient(global) {
const STORAGE_KEYS = {
  url: 'louiepy.supabaseUrl',
  key: 'louiepy.supabaseAnonKey'
};

function normalizeSupabaseUrl(url) {
  let value = String(url || '').trim();
  if (!value) return '';
  value = value.replace(/\/+$/, '');
  value = value.replace(/\/rest\/v1$/i, '');
  value = value.replace(/\/auth\/v1$/i, '');
  return value.replace(/\/+$/, '');
}

function normalizeAnonKey(key) {
  return String(key || '').trim();
}

function readFileConfig() {
  const defaults = window.LOUIECORP_DEFAULTS || {};
  return {
    url: normalizeSupabaseUrl(defaults.supabaseUrl),
    key: normalizeAnonKey(defaults.supabaseAnonKey)
  };
}

function readLocalConfig() {
  let storedUrl = '';
  let storedKey = '';
  try {
    storedUrl = localStorage.getItem(STORAGE_KEYS.url) || '';
    storedKey = localStorage.getItem(STORAGE_KEYS.key) || '';
  } catch (error) {
    storedUrl = '';
    storedKey = '';
  }
  return {
    url: normalizeSupabaseUrl(storedUrl),
    key: normalizeAnonKey(storedKey)
  };
}

function readStoredConfig() {
  const fileConfig = readFileConfig();
  const localConfig = readLocalConfig();
  return {
    url: fileConfig.url || localConfig.url || '',
    key: fileConfig.key || localConfig.key || ''
  };
}

function saveStoredConfig(url, key) {
  try {
    localStorage.setItem(STORAGE_KEYS.url, normalizeSupabaseUrl(url));
    localStorage.setItem(STORAGE_KEYS.key, normalizeAnonKey(key));
  } catch (error) {
    throw new Error('Could not save the project connection in this browser.');
  }
}

function isConfigured() {
  const { url, key } = readStoredConfig();
  return Boolean(url && key);
}

let cachedClient = null;
let cachedSignature = '';

function getClient() {
  if (!window.supabase) {
    throw new Error('Supabase library is not loaded.');
  }
  const { url, key } = readStoredConfig();
  if (!url || !key) {
    throw new Error('Add your Supabase URL and anon key in Admin setup.');
  }
  const signature = `${url}::${key}`;
  if (!cachedClient || cachedSignature !== signature) {
    cachedClient = window.supabase.createClient(url, key);
    cachedSignature = signature;
  }
  return cachedClient;
}

function mediaWorkerUrl() {
  const defaults = window.LOUIECORP_DEFAULTS || {};
  const value = String(defaults.mediaWorkerUrl || 'https://louiecorp.louievolt.workers.dev').trim();
  return value.replace(/\/+$/, '');
}

function mediaObjectUrl(key) {
  const clean = String(key || '').replace(/^\/+/, '');
  return `${mediaWorkerUrl()}/media/${clean}`;
}

function safeFileExt(file, fallbackType) {
  const fromName = String((file && file.name) || '').split('.').pop() || '';
  const cleaned = fromName.toLowerCase().replace(/[^a-z0-9]/g, '');
  if (cleaned && cleaned.length <= 8) return cleaned;
  const type = String((file && file.type) || fallbackType || '');
  if (type.includes('pdf')) return 'pdf';
  if (type.includes('png')) return 'png';
  if (type.includes('webp')) return 'webp';
  if (type.includes('gif')) return 'gif';
  if (type.includes('jpeg') || type.includes('jpg')) return 'jpg';
  return 'bin';
}

function uniqueMediaKey(folder, slug, file, fallbackType) {
  const prefix = String(folder || 'media').replace(/[^a-z0-9/_-]/gi, '');
  const base = slugify(slug || 'file').slice(0, 60);
  const ext = safeFileExt(file, fallbackType);
  const rand = Math.random().toString(36).slice(2, 8);
  return `${prefix}/${base}-${Date.now()}-${rand}.${ext}`;
}

async function uploadMediaFile(file, key, fallbackType) {
  if (!file) return '';
  const objectKey = String(key || '').replace(/^\/+/, '');
  if (!objectKey) throw new Error('A media object key is required.');
  const client = getClient();
  const { data } = await client.auth.getSession();
  const token = data && data.session && data.session.access_token;
  if (!token) throw new Error('Sign in before uploading files.');
  const url = mediaObjectUrl(objectKey);
  let response;
  try {
    response = await fetch(url, {
      method: 'PUT',
      mode: 'cors',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': file.type || fallbackType || 'application/octet-stream'
      },
      body: file
    });
  } catch (error) {
    throw new Error('Could not reach the media worker. Confirm it is deployed and allows this site origin.');
  }
  if (!response.ok) {
    let detail = '';
    try {
      const text = (await response.text()).trim();
      try {
        const parsed = JSON.parse(text);
        detail = parsed.error || parsed.message || text;
      } catch (error) {
        detail = text;
      }
    } catch (error) {
      detail = '';
    }
    throw new Error(detail || `Could not upload the file (${response.status}).`);
  }
  return url;
}

function slugify(value) {
  return String(value || '')
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80) || `story-${Date.now()}`;
}

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric'
  });
}

function formatDateTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const sameDay = date.toDateString() === new Date().toDateString();
  if (sameDay) {
    return date.toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit'
    });
  }
  return date.toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

const SITE_ORIGIN = 'https://louiecorp.com';
const PUBLISHER_NAME = 'LouieCorp Publishing';
const DEFAULT_AUTHOR_NAME = 'Sentongo. R. Louis';
const PLACEHOLDER_AUTHOR = /^(editorial desk|louiecorp editorial(?:\s+desk)?|ai writer|admin|louiecorp)$/i;

function siteUrl(path) {
  const clean = String(path || '').replace(/^\//, '');
  return clean ? `${SITE_ORIGIN}/${clean}` : `${SITE_ORIGIN}/`;
}

function articleHref(slug) {
  const clean = String(slug || '').replace(/^\/+/, '');
  return clean ? `story/${encodeURIComponent(clean)}` : 'article.html';
}

function readArticleSlug() {
  const params = new URLSearchParams(window.location.search);
  const querySlug = (params.get('slug') || '').trim();
  if (querySlug) return querySlug;
  const parts = window.location.pathname.split('/').filter(Boolean);
  if ((parts[0] === 'story' || parts[0] === 's') && parts[1]) {
    return decodeURIComponent(parts.slice(1).join('/').replace(/\.html$/, ''));
  }
  const last = (parts[parts.length - 1] || '').replace(/\.html$/, '');
  if (last && !['article', 'index', '200', 's', 'story'].includes(last.toLowerCase())) {
    return decodeURIComponent(last);
  }
  return '';
}

function readingTime(text) {
  const words = String(text || '').trim().split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / 220));
}

function shareCardUrl(slug) {
  const clean = String(slug || '').replace(/^\/+/, '');
  return clean ? `${mediaWorkerUrl()}/share/story/${encodeURIComponent(clean)}` : '';
}

function shareTargets(url, title, extras) {
  const encodedUrl = encodeURIComponent(url);
  const encodedTitle = encodeURIComponent(title || 'LouieCorp');
  const cardUrl = extras && extras.cardUrl ? encodeURIComponent(extras.cardUrl) : encodedUrl;
  return {
    x: `https://twitter.com/intent/tweet?url=${cardUrl}&text=${encodedTitle}`,
    facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}`,
    whatsapp: `https://api.whatsapp.com/send?text=${encodedTitle}%20${encodedUrl}`
  };
}

function articleCanonicalUrl(slug) {
  return siteUrl(articleHref(slug));
}

function authorHref(slug) {
  if (!slug) return '';
  return `author.html?slug=${encodeURIComponent(slug)}`;
}

function authorCanonicalUrl(slug) {
  return slug ? siteUrl(authorHref(slug)) : '';
}

function isoDate(value) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toISOString();
}

function plainText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function excerptFrom(article, maxLen) {
  const limit = maxLen || 160;
  const excerpt = plainText(article && article.excerpt);
  if (excerpt) {
    return excerpt.length > limit
      ? `${excerpt.slice(0, limit - 1).replace(/\s+\S*$/, '')}…`
      : excerpt;
  }
  const body = plainText(article && article.content)
    .replace(/^#+\s+/g, '')
    .replace(/^>\s+/g, '');
  if (!body) return 'A published article from LouieCorp Publishing.';
  return body.length > limit
    ? `${body.slice(0, limit - 1).replace(/\s+\S*$/, '')}…`
    : body;
}

function upsertMeta(attrName, key, value) {
  if (value == null || value === '') return;
  let el = document.querySelector(`meta[${attrName}="${key}"]`);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute(attrName, key);
    document.head.appendChild(el);
  }
  el.setAttribute('content', String(value));
}

function removeMeta(attrName, key) {
  document.querySelectorAll(`meta[${attrName}="${key}"]`).forEach((el) => el.remove());
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
  if (!value || PLACEHOLDER_AUTHOR.test(value)) return DEFAULT_AUTHOR_NAME;
  return value;
}

function upsertLink(rel, href) {
  if (!href) return;
  let el = document.querySelector(`link[rel="${rel}"]`);
  if (!el) {
    el = document.createElement('link');
    el.setAttribute('rel', rel);
    document.head.appendChild(el);
  }
  el.setAttribute('href', href);
}

function setJsonLd(id, data) {
  let el = document.getElementById(id);
  if (!el) {
    el = document.createElement('script');
    el.type = 'application/ld+json';
    el.id = id;
    document.head.appendChild(el);
  }
  el.textContent = JSON.stringify(data);
}

function applyArticleHead(article, author, extras) {
  const title = `${article.title} — LouieCorp`;
  const description = excerptFrom(article);
  const url = articleCanonicalUrl(article.slug);
  const cover = publicImageUrl(article.cover_image_url);
  const image = cover || siteUrl('og-default.png');
  const imageType = cover ? 'image/jpeg' : 'image/png';
  const published = isoDate(article.published_at);
  const modified = isoDate(article.updated_at) || published;
  const desk = extras && extras.desk;
  const tags = (extras && extras.tags) || [];
  const authorName = displayAuthorName(author && author.name);
  document.title = title;
  upsertMeta('name', 'description', description);
  upsertMeta('name', 'author', authorName);
  upsertMeta('name', 'robots', 'index,follow,max-image-preview:large');
  if (tags.length) upsertMeta('name', 'keywords', tags.join(', '));
  upsertLink('canonical', url);
  if (author && author.slug) {
    upsertLink('author', authorCanonicalUrl(author.slug));
  }
  upsertMeta('property', 'og:site_name', PUBLISHER_NAME);
  upsertMeta('property', 'og:title', article.title);
  upsertMeta('property', 'og:description', description);
  upsertMeta('property', 'og:type', 'article');
  upsertMeta('property', 'og:url', url);
  upsertMeta('property', 'og:locale', 'en_GB');
  upsertMeta('property', 'og:image', image);
  upsertMeta('property', 'og:image:secure_url', image);
  upsertMeta('property', 'og:image:type', imageType);
  upsertMeta('property', 'og:image:alt', article.title);
  upsertMeta('name', 'twitter:image', image);
  upsertMeta('name', 'twitter:image:alt', article.title);
  upsertMeta('name', 'twitter:card', 'summary_large_image');
  upsertMeta('property', 'article:publisher', PUBLISHER_NAME);
  upsertMeta('property', 'article:author', authorName);
  if (published) upsertMeta('property', 'article:published_time', published);
  if (modified) upsertMeta('property', 'article:modified_time', modified);
  if (desk) upsertMeta('property', 'article:section', desk);
  document.querySelectorAll('meta[property="article:tag"]').forEach((el) => el.remove());
  tags.forEach((tag) => {
    const el = document.createElement('meta');
    el.setAttribute('property', 'article:tag');
    el.setAttribute('content', tag);
    document.head.appendChild(el);
  });
  upsertMeta('name', 'twitter:title', article.title);
  upsertMeta('name', 'twitter:description', description);
  upsertMeta('name', 'twitter:label1', 'Written by');
  upsertMeta('name', 'twitter:data1', authorName);
  upsertMeta('name', 'twitter:label2', 'Published by');
  upsertMeta('name', 'twitter:data2', PUBLISHER_NAME);
  const authorEntity = {
    '@type': 'Person',
    name: authorName
  };
  if (author && author.slug) authorEntity.url = authorCanonicalUrl(author.slug);
  const payload = {
    '@context': 'https://schema.org',
    '@type': 'NewsArticle',
    headline: article.title,
    description,
    datePublished: published || undefined,
    dateModified: modified || undefined,
    author: authorEntity,
    publisher: {
      '@type': 'NewsMediaOrganization',
      name: PUBLISHER_NAME,
      url: siteUrl('/'),
      logo: {
        '@type': 'ImageObject',
        url: siteUrl('icon.svg')
      }
    },
    mainEntityOfPage: {
      '@type': 'WebPage',
      '@id': url
    },
    url
  };
  if (image) payload.image = [image];
  if (desk) payload.articleSection = desk;
  if (tags.length) payload.keywords = tags.join(', ');
  setJsonLd('articleJsonLd', payload);
}

function authorFromArticle(article) {
  const nested = article && (article.authors || article.byline_author);
  if (nested && nested.name) {
    return {
      id: nested.id,
      name: displayAuthorName(nested.name),
      slug: nested.slug || '',
      bio: nested.bio || '',
      photo: nested.photo_url || '',
      title: nested.title || ''
    };
  }
  return {
    id: null,
    name: DEFAULT_AUTHOR_NAME,
    slug: '',
    bio: '',
    photo: '',
    title: ''
  };
}

function authorInitials(name) {
  const parts = String(name || DEFAULT_AUTHOR_NAME).trim().split(/\s+/).filter(Boolean).slice(0, 2);
  return parts.map((part) => part.charAt(0).toUpperCase()).join('') || 'SL';
}

function articleDocumentUrl(article) {
  if (!article || typeof article !== 'object') return '';
  const keys = [
    'pdf_url',
    'document_url',
    'file_url',
    'attachment_url',
    'pdf',
    'document'
  ];
  for (const key of keys) {
    const value = article[key];
    if (typeof value === 'string' && /^https?:\/\//i.test(value.trim())) {
      return value.trim();
    }
  }
  return '';
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function looksLikeHtml(value) {
  return /<\/?(p|h[1-6]|blockquote|ul|ol|li|figure|img|div|br)\b/i.test(String(value || ''));
}

function sanitizeArticleHtml(html) {
  const wrap = document.createElement('div');
  wrap.innerHTML = String(html || '');
  wrap.querySelectorAll('script, style, iframe, object, embed, form, link, meta').forEach((el) => el.remove());
  wrap.querySelectorAll('*').forEach((el) => {
    [...el.attributes].forEach((attr) => {
      const name = attr.name.toLowerCase();
      const value = String(attr.value || '');
      if (name.startsWith('on') || /^(javascript|data):/i.test(value)) {
        el.removeAttribute(attr.name);
      }
    });
  });
  const firstP = wrap.querySelector('p');
  if (firstP && !firstP.classList.contains('dropcap')) {
    firstP.classList.add('dropcap');
  }
  return wrap.innerHTML;
}

function renderMarkdownBody(text) {
  const blocks = String(text || '').replace(/\r\n/g, '\n').split(/\n{2,}/);
  let firstParagraph = true;
  return blocks.map((block) => {
    const trimmed = block.trim();
    if (!trimmed) return '';
    if (trimmed.startsWith('## ')) {
      firstParagraph = false;
      return `<h2>${escapeHtml(trimmed.slice(3))}</h2>`;
    }
    if (trimmed.startsWith('# ')) {
      firstParagraph = false;
      return `<h2>${escapeHtml(trimmed.slice(2))}</h2>`;
    }
    if (trimmed.startsWith('> ')) {
      firstParagraph = false;
      const lines = trimmed.split('\n').map((line) => line.replace(/^>\s?/, ''));
      let cite = '';
      const last = lines[lines.length - 1] || '';
      if (lines.length > 1 && /^(—|--)\s+\S/.test(last)) {
        cite = last.replace(/^(—|--)\s+/, '');
        lines.pop();
      }
      const quote = escapeHtml(lines.join('\n')).replace(/\n/g, '<br>');
      const citeHtml = cite ? `<cite>${escapeHtml(cite)}</cite>` : '';
      return `<blockquote>${quote}${citeHtml}</blockquote>`;
    }
    const html = escapeHtml(trimmed).replace(/\n/g, '<br>');
    if (firstParagraph) {
      firstParagraph = false;
      return `<p class="dropcap">${html}</p>`;
    }
    return `<p>${html}</p>`;
  }).join('');
}

function renderBody(text) {
  const value = String(text || '');
  if (looksLikeHtml(value)) return sanitizeArticleHtml(value);
  return renderMarkdownBody(value);
}

function publicDesk(name) {
  if (!name) return 'Analysis';
  if (name === 'Christianity') return 'Faith';
  if (name === 'Ideas' || name === 'History') return 'Analysis';
  if (name === 'Law & Governance') return 'Governance';
  if (name === 'Public life' || name === 'Public Life') return 'Politics';
  return name;
}

global.LouieCorp = {
  STORAGE_KEYS,
  SITE_ORIGIN,
  PUBLISHER_NAME,
  DEFAULT_AUTHOR_NAME,
  publicImageUrl,
  displayAuthorName,
  readStoredConfig,
  saveStoredConfig,
  isConfigured,
  getClient,
  mediaWorkerUrl,
  mediaObjectUrl,
  uniqueMediaKey,
  uploadMediaFile,
  slugify,
  formatDate,
  formatDateTime,
  isoDate,
  siteUrl,
  articleHref,
  readArticleSlug,
  readingTime,
  shareTargets,
  shareCardUrl,
  articleCanonicalUrl,
  authorHref,
  authorCanonicalUrl,
  excerptFrom,
  applyArticleHead,
  upsertMeta,
  upsertLink,
  setJsonLd,
  articleDocumentUrl,
  authorFromArticle,
  authorInitials,
  escapeHtml,
  renderBody,
  publicDesk
};
}(window));
