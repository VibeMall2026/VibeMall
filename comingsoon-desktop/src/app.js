const root = document.getElementById('app');

const state = {
  apiBase: '',
  layout: { header: '', footer: '' },
  page: null,
};

bootstrap();

async function bootstrap() {
  root.innerHTML = '<div class="loading">Loading coming soon desktop view...</div>';
  try {
    const layoutDoc = await fetchDocument('/shop/?bypass=true');
    const pageDoc = await fetchDocument('/coming-soon/?bypass=true');
    state.layout.header = extractOuterHTML(layoutDoc, ['header.vm-copy-header', '.vm-copy-header', 'header']);
    state.layout.footer = extractOuterHTML(layoutDoc, ['footer.vm-copy-footer', '.vm-copy-footer', 'footer']);
    state.page = parseComingSoon(pageDoc);
    render();
    bind();
    startCountdown();
  } catch (error) {
    root.innerHTML = `<div class="error-box"><div><h1>Unable to load page</h1><p>${escapeHtml(error.message)}</p><button id="retryBtn">Retry</button></div></div>`;
    document.getElementById('retryBtn')?.addEventListener('click', bootstrap);
  }
}

function render() {
  const page = state.page;
  root.innerHTML = `
    <div class="cs-page">
      <div class="layout-slot">${state.layout.header || ''}</div>
      <main class="cs-main">
        <section class="cs-shell">
          <section class="cs-copy">
            <p class="cs-kicker">${escapeHtml(page.kicker)}</p>
            <h1 class="cs-title">${escapeHtml(page.title)}</h1>
            <p class="cs-subtitle">${escapeHtml(page.subtitle)}</p>
            <div class="cs-highlights">
              ${page.highlights.map((item) => `<article class="cs-highlight"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.text)}</span></article>`).join('')}
            </div>
          </section>
          <aside class="cs-panel">
            <p class="cs-panel-label">Join the Private Viewing</p>
            <h2 class="cs-date">${escapeHtml(page.launchDateDisplay)}</h2>
            <p class="cs-launch-line">${escapeHtml(page.panelText)}</p>
            <div class="cs-countdown" id="countdownGrid">
              ${['Days', 'Hours', 'Minutes', 'Seconds'].map((label) => `<div class="cs-countdown-card"><strong>00</strong><span>${label}</span></div>`).join('')}
            </div>
            <form class="cs-form" id="notifyForm">
              <div class="cs-input-row">
                <input id="emailInput" type="email" name="email" placeholder="Enter your email address" required>
                <button id="notifyBtn" type="submit">Notify Me</button>
              </div>
              <p class="cs-status" id="notifyStatus" aria-live="polite"></p>
            </form>
            <div class="cs-meta">
              <span>Live admin updates appear here after every reload.</span>
              <span>Source: ${escapeHtml(state.apiBase)}</span>
            </div>
          </aside>
        </section>
      </main>
      <div class="layout-slot">${state.layout.footer || ''}</div>
    </div>
  `;
}

function bind() {
  document.getElementById('notifyForm')?.addEventListener('submit', submitNewsletter);
}

async function submitNewsletter(event) {
  event.preventDefault();
  const emailInput = document.getElementById('emailInput');
  const button = document.getElementById('notifyBtn');
  const status = document.getElementById('notifyStatus');
  const email = emailInput.value.trim();

  if (!email) {
    setStatus('Please enter a valid email address.', true);
    return;
  }

  button.disabled = true;
  button.textContent = 'Sending...';
  setStatus('');

  const csrf = getCookie('csrftoken');
  const body = new URLSearchParams({
    email,
    source_page: 'comingsoon-desktop',
    csrfmiddlewaretoken: csrf || '',
  });

  try {
    const response = await fetch(new URL('/newsletter/subscribe/', state.apiBase), {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': csrf || '',
      },
      body: body.toString(),
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
      throw new Error(data.message || 'Unable to subscribe right now.');
    }
    emailInput.value = '';
    setStatus(data.message || 'Subscribed successfully.');
  } catch (error) {
    setStatus(error.message || 'Unable to subscribe right now.', true);
  } finally {
    button.disabled = false;
    button.textContent = 'Notify Me';
  }
}

function startCountdown() {
  const grid = document.getElementById('countdownGrid');
  if (!grid || !state.page.launchDateIso) return;
  const cards = Array.from(grid.querySelectorAll('strong'));
  const launchAt = new Date(state.page.launchDateIso).getTime();
  const update = () => {
    const diff = Math.max(launchAt - Date.now(), 0);
    const values = [
      Math.floor(diff / 86400000),
      Math.floor((diff % 86400000) / 3600000),
      Math.floor((diff % 3600000) / 60000),
      Math.floor((diff % 60000) / 1000),
    ];
    values.forEach((value, index) => {
      if (cards[index]) cards[index].textContent = String(value).padStart(2, '0');
    });
  };
  update();
  window.clearInterval(window.__vmComingSoonDesktopTimer);
  window.__vmComingSoonDesktopTimer = window.setInterval(update, 1000);
}

function parseComingSoon(doc) {
  const title = doc.querySelector('.vm-cs-title')?.textContent?.trim() || 'Coming Soon';
  const kicker = doc.querySelector('.vm-cs-kicker')?.textContent?.trim() || 'Private Preview';
  const subtitle = doc.querySelector('.vm-cs-sub')?.textContent?.trim() || 'A new era of VibeMall is arriving.';
  const launchDateDisplay = doc.getElementById('vmLaunchDate')?.textContent?.trim() || 'Soon';
  const launchDateIso = doc.querySelector('[data-launch-date]')?.getAttribute('data-launch-date') || '';
  const panelText = doc.querySelector('.vm-cs-card p:not(.vm-cs-date):not(.vm-cs-msg)')?.textContent?.trim() || 'Subscribe for early access and launch alerts.';
  const highlights = Array.from(doc.querySelectorAll('.vm-cs-grid > div')).map((node, index) => ({
    title: ['Dispatch', 'Catalog', 'Checkout', 'Offers'][index] || `Update ${index + 1}`,
    text: node.textContent.replace(/\s+/g, ' ').trim(),
  }));
  return {
    title,
    kicker,
    subtitle,
    launchDateDisplay,
    launchDateIso,
    panelText,
    highlights: highlights.length ? highlights : [
      { title: 'Dispatch', text: 'Fast dispatch and live status tracking.' },
      { title: 'Catalog', text: 'Fresh catalog and real-time stock updates.' },
      { title: 'Checkout', text: 'Secure checkout and order timeline.' },
      { title: 'Offers', text: 'Early launch offers for subscribers.' },
    ],
  };
}

async function fetchDocument(path) {
  const candidates = getApiBaseCandidates();
  let lastError = new Error('Request failed.');
  for (const base of candidates) {
    try {
      const response = await fetch(new URL(path, base), { credentials: 'include' });
      const text = await response.text();
      if (!response.ok && response.status >= 500) throw new Error(`Server error ${response.status}`);
      state.apiBase = base;
      return new DOMParser().parseFromString(text, 'text/html');
    } catch (error) {
      lastError = error;
    }
  }
  throw new Error(`${lastError.message} Use ?apiBase=http://127.0.0.1:8000 if the backend is on another port.`);
}

function getApiBaseCandidates() {
  const url = new URL(window.location.href);
  const explicit = url.searchParams.get('apiBase') || localStorage.getItem('vmApiBase') || '';
  const current = `${url.protocol}//${url.host}`;
  const fallback = ['localhost', '127.0.0.1'].includes(url.hostname) ? `${url.protocol}//${url.hostname}:8000` : '';
  return [...new Set([explicit, current, fallback].filter(Boolean))];
}

function extractOuterHTML(doc, selectors) {
  for (const selector of selectors) {
    const node = doc.querySelector(selector);
    if (node) return node.outerHTML;
  }
  return '';
}

function getCookie(name) {
  return document.cookie.split('; ').find((part) => part.startsWith(`${name}=`))?.split('=')[1] || '';
}

function setStatus(message, isError = false) {
  const node = document.getElementById('notifyStatus');
  if (!node) return;
  node.textContent = message;
  node.classList.toggle('is-error', isError);
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
