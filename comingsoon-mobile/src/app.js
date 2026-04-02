const root = document.getElementById('app');
const state = { apiBase: '', layout: { header: '', footer: '', bottomNav: '' }, page: null };
bootstrap();

async function bootstrap() {
  root.innerHTML = '<div class="loading">Loading coming soon mobile view...</div>';
  try {
    const layoutDoc = await fetchDocument('/shop/?bypass=true');
    const pageDoc = await fetchDocument('/coming-soon/?bypass=true');
    state.layout.header = pick(layoutDoc, ['.vm-mobile-alt-header', '.vm-login-m-header', 'header']);
    state.layout.footer = pick(layoutDoc, ['.vm-mobile-alt-footer', '.vm-copy-footer', 'footer']);
    state.layout.bottomNav = pick(layoutDoc, ['#mobileBottomNavShell', '.vm-mobile-bottom-nav', '.mobile-bottom-nav-shell']);
    state.page = parseComingSoon(pageDoc);
    render();
    bind();
    startCountdown();
  } catch (error) {
    root.innerHTML = `<div class="error"><div><h1>Unable to load page</h1><p>${safe(error.message)}</p><button id="retry">Retry</button></div></div>`;
    document.getElementById('retry')?.addEventListener('click', bootstrap);
  }
}

function render() {
  const p = state.page;
  root.innerHTML = `<div class="page"><div class="slot">${state.layout.header}</div><main class="hero"><p class="kicker">${safe(p.kicker)}</p><h1 class="title">${safe(p.title)}</h1><p class="sub">${safe(p.subtitle)}</p><div class="highlights">${p.highlights.map((item) => `<div>${safe(item)}</div>`).join('')}</div><section class="hero-card"><h2 class="panel-title">${safe(p.launchDateDisplay)}</h2><p class="panel-copy">${safe(p.panelText)}</p><div class="countdown" id="countdown">${['Days','Hours','Minutes','Seconds'].map((label) => `<article><strong>00</strong><span>${label}</span></article>`).join('')}</div><form class="notify" id="notifyForm"><input id="emailInput" type="email" placeholder="Enter your email address" required><button id="notifyBtn" type="submit">Notify Me</button><p class="status" id="status" aria-live="polite"></p></form></section></main><div class="slot">${state.layout.footer}</div><div class="slot">${state.layout.bottomNav}</div></div>`;
}

function bind() { document.getElementById('notifyForm')?.addEventListener('submit', submitNewsletter); }

async function submitNewsletter(event) {
  event.preventDefault();
  const email = document.getElementById('emailInput').value.trim();
  const button = document.getElementById('notifyBtn');
  const status = document.getElementById('status');
  button.disabled = true; button.textContent = 'Sending...'; status.textContent = ''; status.classList.remove('error');
  try {
    const body = new URLSearchParams({ email, source_page: 'comingsoon-mobile', csrfmiddlewaretoken: cookie('csrftoken') });
    const response = await fetch(new URL('/newsletter/subscribe/', state.apiBase), { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': cookie('csrftoken') }, body: body.toString() });
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.message || 'Unable to subscribe right now.');
    document.getElementById('emailInput').value = '';
    status.textContent = data.message || 'Subscribed successfully.';
  } catch (error) {
    status.textContent = error.message || 'Unable to subscribe right now.';
    status.classList.add('error');
  } finally {
    button.disabled = false; button.textContent = 'Notify Me';
  }
}

function startCountdown() {
  const nodes = Array.from(document.querySelectorAll('#countdown strong'));
  if (!nodes.length || !state.page.launchDateIso) return;
  const launchAt = new Date(state.page.launchDateIso).getTime();
  const tick = () => {
    const diff = Math.max(launchAt - Date.now(), 0);
    [Math.floor(diff / 86400000), Math.floor((diff % 86400000) / 3600000), Math.floor((diff % 3600000) / 60000), Math.floor((diff % 60000) / 1000)].forEach((value, index) => nodes[index] && (nodes[index].textContent = String(value).padStart(2, '0')));
  };
  tick(); clearInterval(window.__vmCsMobileTimer); window.__vmCsMobileTimer = setInterval(tick, 1000);
}

function parseComingSoon(doc) {
  return {
    kicker: doc.querySelector('.vm-cs-kicker')?.textContent?.trim() || 'Private Preview',
    title: doc.querySelector('.vm-cs-title')?.textContent?.trim() || 'Coming Soon',
    subtitle: doc.querySelector('.vm-cs-sub')?.textContent?.trim() || 'Be the first to witness the launch.',
    launchDateDisplay: doc.getElementById('vmLaunchDate')?.textContent?.trim() || 'Soon',
    launchDateIso: doc.querySelector('[data-launch-date]')?.getAttribute('data-launch-date') || '',
    panelText: doc.querySelector('.vm-cs-card p:not(.vm-cs-date):not(.vm-cs-msg)')?.textContent?.trim() || 'Subscribe for early access and launch alerts.',
    highlights: Array.from(doc.querySelectorAll('.vm-cs-grid > div')).map((node) => node.textContent.replace(/\s+/g, ' ').trim()).filter(Boolean).slice(0, 4),
  };
}

async function fetchDocument(path) {
  let last = new Error('Request failed.');
  for (const base of bases()) {
    try {
      const response = await fetch(new URL(path, base), { credentials: 'include' });
      const text = await response.text();
      if (!response.ok && response.status >= 500) throw new Error(`Server error ${response.status}`);
      state.apiBase = base;
      return new DOMParser().parseFromString(text, 'text/html');
    } catch (error) { last = error; }
  }
  throw new Error(`${last.message} Use ?apiBase=http://127.0.0.1:8000 if needed.`);
}

function bases() {
  const url = new URL(location.href);
  const explicit = url.searchParams.get('apiBase') || localStorage.getItem('vmApiBase') || '';
  const current = `${url.protocol}//${url.host}`;
  const fallback = ['localhost', '127.0.0.1'].includes(url.hostname) ? `${url.protocol}//${url.hostname}:8000` : '';
  return [...new Set([explicit, current, fallback].filter(Boolean))];
}

function pick(doc, selectors) { for (const selector of selectors) { const node = doc.querySelector(selector); if (node) return node.outerHTML; } return ''; }
function cookie(name) { return document.cookie.split('; ').find((part) => part.startsWith(`${name}=`))?.split('=')[1] || ''; }
function safe(value) { return String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }
