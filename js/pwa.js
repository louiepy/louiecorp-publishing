(function initLouieCorpPwa() {
  if (typeof window === 'undefined') return;

  const DISMISS_KEY = 'lc_pwa_dismissed_at';
  const DISMISS_MS = 14 * 24 * 60 * 60 * 1000;
  const ENGAGE_DELAY_MS = 60000;
  const BANNER_ID = 'lc-pwa-banner';

  function isAdminPath() {
    const path = window.location.pathname || '';
    return path === '/admin' || path.indexOf('/admin/') === 0 || /\/admin(?:\.html)?$/i.test(path);
  }

  function isStandalone() {
    if (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) return true;
    if (window.navigator.standalone === true) return true;
    return false;
  }

  function isIos() {
    const ua = window.navigator.userAgent || '';
    return /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  }

  function isSafari() {
    const ua = window.navigator.userAgent || '';
    return /Safari/i.test(ua) && !/Chrome|CriOS|FxiOS|EdgiOS|OPiOS|Android/i.test(ua);
  }

  function wasDismissedRecently() {
    try {
      const raw = localStorage.getItem(DISMISS_KEY);
      if (!raw) return false;
      const ts = parseInt(raw, 10);
      if (!Number.isFinite(ts)) return false;
      return Date.now() - ts < DISMISS_MS;
    } catch (e) {
      return false;
    }
  }

  function markDismissed() {
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    } catch (e) {
      /* ignore */
    }
  }

  function removeBanner() {
    const el = document.getElementById(BANNER_ID);
    if (el) el.remove();
  }

  function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return;
    if (isAdminPath()) return;
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/', updateViaCache: 'none' }).catch(() => {
        /* registration failure is non-fatal */
      });
    });
  }

  function buildBanner(mode, deferredPrompt) {
    if (document.getElementById(BANNER_ID)) return;

    const banner = document.createElement('div');
    banner.id = BANNER_ID;
    banner.className = 'lc-pwa-banner';
    banner.setAttribute('role', 'dialog');
    banner.setAttribute('aria-label', 'Install LouieCorp');

    if (mode === 'install') {
      banner.innerHTML =
        '<div class="lc-pwa-banner-inner">' +
        '<div class="lc-pwa-copy">' +
        '<p class="lc-pwa-title">Install LouieCorp</p>' +
        '<p class="lc-pwa-text">Get faster access to LouieCorp Publishing from your home screen.</p>' +
        '</div>' +
        '<div class="lc-pwa-actions">' +
        '<button type="button" class="lc-pwa-btn lc-pwa-btn-primary" data-lc-pwa="install">Install</button>' +
        '<button type="button" class="lc-pwa-btn lc-pwa-btn-ghost" data-lc-pwa="dismiss">Not now</button>' +
        '</div></div>';
    } else {
      banner.innerHTML =
        '<div class="lc-pwa-banner-inner">' +
        '<div class="lc-pwa-copy">' +
        '<p class="lc-pwa-title">Add LouieCorp to your Home Screen</p>' +
        '<p class="lc-pwa-text">On iPhone or iPad, tap Share, then choose Add to Home Screen.</p>' +
        '</div>' +
        '<div class="lc-pwa-actions">' +
        '<button type="button" class="lc-pwa-btn lc-pwa-btn-ghost" data-lc-pwa="dismiss">Got it</button>' +
        '</div></div>';
    }

    banner.addEventListener('click', (event) => {
      const btn = event.target.closest('[data-lc-pwa]');
      if (!btn) return;
      const action = btn.getAttribute('data-lc-pwa');
      if (action === 'dismiss') {
        markDismissed();
        removeBanner();
        return;
      }
      if (action === 'install' && deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(() => {
          removeBanner();
        }).catch(() => {
          removeBanner();
        });
        window.__lcDeferredInstall = null;
      }
    });

    document.body.appendChild(banner);
  }

  function shouldOffer() {
    if (isAdminPath()) return false;
    if (isStandalone()) return false;
    if (wasDismissedRecently()) return false;
    return true;
  }

  function setupInstallPrompt() {
    if (!shouldOffer()) return;

    let deferredPrompt = null;
    let engaged = false;
    let timerDone = false;
    let shown = false;

    function tryShow() {
      if (shown || !shouldOffer()) return;
      if (!(engaged || timerDone)) return;

      if (deferredPrompt) {
        shown = true;
        buildBanner('install', deferredPrompt);
        return;
      }
      // iOS Safari guidance (no beforeinstallprompt)
      if (isIos() && isSafari()) {
        shown = true;
        buildBanner('ios', null);
      }
    }

    window.addEventListener('beforeinstallprompt', (event) => {
      event.preventDefault();
      deferredPrompt = event;
      window.__lcDeferredInstall = event;
      tryShow();
    });

    window.addEventListener('appinstalled', () => {
      markDismissed();
      removeBanner();
      deferredPrompt = null;
      window.__lcDeferredInstall = null;
    });

    window.setTimeout(() => {
      timerDone = true;
      tryShow();
    }, ENGAGE_DELAY_MS);

    const markEngaged = () => {
      engaged = true;
      tryShow();
    };

    let scrollTicks = 0;
    window.addEventListener('scroll', () => {
      scrollTicks += 1;
      if (scrollTicks >= 3) markEngaged();
    }, { passive: true });

    document.addEventListener('click', (event) => {
      const a = event.target.closest('a');
      if (a && a.href) markEngaged();
    });
  }

  registerServiceWorker();
  setupInstallPrompt();
}());
