// GitHub raw JSON(자동 추출 일정) + hub_api.py(개인 CRUD/검수) 연동
const AUTO_EVENTS_URL = 'https://raw.githubusercontent.com/namhyeokwoo/zdnet-event-app/main/data/events.json';
const SETTINGS_KEY = 'zdnetevent.settings';

function getSettings() {
  try {
    return JSON.parse(localStorage.getItem(SETTINGS_KEY)) || { base: '', token: '' };
  } catch (e) {
    return { base: '', token: '' };
  }
}

function saveSettings(settings) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}

async function fetchAutoEvents() {
  try {
    const res = await fetch(`${AUTO_EVENTS_URL}?t=${Date.now()}`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`auto events fetch failed: ${res.status}`);
    const data = await res.json();
    return { events: data.events || [], sourceArticle: data.source_article || null };
  } catch (e) {
    console.error('fetchAutoEvents', e);
    return { events: [], sourceArticle: null, error: true };
  }
}

function hubBase() {
  const { base } = getSettings();
  return (base || '').replace(/\/+$/, '');
}

async function hubFetch(path, opts = {}) {
  const base = hubBase();
  const { token } = getSettings();
  if (!base) throw new Error('hub-not-configured');
  const res = await fetch(`${base}${path}`, {
    ...opts,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) throw new Error(`hub api ${path} -> ${res.status}`);
  return res.json();
}

async function fetchManualEvents() {
  try {
    const r = await hubFetch('/events/manual');
    return r.data;
  } catch (e) {
    console.warn('fetchManualEvents unavailable', e.message);
    return null; // null = 개인 서버 연결 불가 (자동 이벤트는 계속 표시)
  }
}

async function fetchReviewStatus() {
  try {
    const r = await hubFetch('/events/review');
    return r.data;
  } catch (e) {
    console.warn('fetchReviewStatus unavailable', e.message);
    return null;
  }
}

async function createManualEvent(payload) {
  const r = await hubFetch('/events/manual', { method: 'POST', body: JSON.stringify(payload) });
  return r.data;
}

async function updateManualEvent(id, payload) {
  const r = await hubFetch(`/events/manual/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
  return r.data;
}

async function deleteManualEvent(id) {
  await hubFetch(`/events/manual/${id}`, { method: 'DELETE' });
}

async function setReviewStatus(eventId, status, overrides) {
  const r = await hubFetch(`/events/review/${eventId}`, {
    method: 'POST',
    body: JSON.stringify({ status, overrides: overrides || null }),
  });
  return r.data;
}

async function checkHubHealth() {
  try {
    await hubFetch('/health');
    return true;
  } catch (e) {
    return false;
  }
}
