// 앱 부트스트랩 — 상태 관리 + DOM 바인딩
const state = {
  year: 0,
  month: 0, // 1-12
  autoEvents: [],
  reviewStatus: null, // null = hub_api.py 연결 불가
  manualEvents: null, // null = hub_api.py 연결 불가
  merged: [],
  activeTags: [],
};

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str == null ? '' : String(str);
  return div.innerHTML;
}

// ── 데이터 로드 ───────────────────────────────────────────────────────

async function loadAll() {
  const [auto, review, manual] = await Promise.all([
    fetchAutoEvents(),
    fetchReviewStatus(),
    fetchManualEvents(),
  ]);
  state.autoEvents = auto.events;
  state.reviewStatus = review;
  state.manualEvents = manual;
  state.merged = mergeEvents(state.autoEvents, state.reviewStatus, state.manualEvents);
}

function hubReachable() {
  return state.manualEvents !== null;
}

// ── 렌더링 ────────────────────────────────────────────────────────────

function renderBanner() {
  document.getElementById('hubBanner').hidden = hubReachable();
}

function renderCalendar() {
  document.getElementById('monthLabel').textContent = `${state.year}년 ${state.month}월`;
  const filtered = filterByTags(state.merged, state.activeTags);
  document.getElementById('calendarRoot').innerHTML = renderCalendarGrid(state.year, state.month, filtered);
}

function renderTagFilter() {
  const tags = collectAllTags(state.merged);
  const container = document.getElementById('tagFilter');
  if (tags.length === 0) {
    container.innerHTML = '';
    return;
  }
  container.innerHTML = tags
    .map((t) => {
      const on = state.activeTags.includes(t) ? 'on' : '';
      return `<button type="button" class="chip ${on}" data-tag="${escapeHtml(t)}">${escapeHtml(t)}</button>`;
    })
    .join('');
}

function renderBellBadge() {
  const newEvents = computeNewEvents(state.merged);
  const badge = document.getElementById('bellBadge');
  if (newEvents.length > 0) {
    badge.hidden = false;
    badge.textContent = newEvents.length > 9 ? '9+' : String(newEvents.length);
  } else {
    badge.hidden = true;
  }
}

function renderAll() {
  renderBanner();
  renderTagFilter();
  renderCalendar();
  renderBellBadge();
}

function eventStatusBadge(e) {
  if (e.source === 'manual') return '<span class="tag-badge manual">직접입력</span>';
  if (e.status === 'pending') return '<span class="tag-badge pending">AI 추출 · 확인 필요</span>';
  return '<span class="tag-badge auto">자동</span>';
}

function eventActionsHtml(e) {
  if (e.source === 'manual') {
    return `<div class="row-actions">
      <button type="button" class="btn-link" data-action="edit-manual" data-id="${e.rawId}">수정</button>
      <button type="button" class="btn-link danger" data-action="delete-manual" data-id="${e.rawId}">삭제</button>
    </div>`;
  }
  if (!hubReachable()) return '';
  if (e.status === 'pending') {
    return `<div class="row-actions">
      <button type="button" class="btn-link" data-action="edit-auto" data-id="${e.id}">수정</button>
      <button type="button" class="btn-link" data-action="confirm-auto" data-id="${e.id}">확정</button>
      <button type="button" class="btn-link danger" data-action="reject-auto" data-id="${e.id}">거절</button>
    </div>`;
  }
  return `<div class="row-actions">
    <button type="button" class="btn-link" data-action="edit-auto" data-id="${e.id}">수정</button>
  </div>`;
}

function renderEventRow(e) {
  const timeLabel = e.time ? e.time : '종일';
  const tagsHtml = (e.tags || []).map((t) => `<span class="mini-tag">${escapeHtml(t)}</span>`).join('');
  return `<div class="event-row">
    <div class="event-row-head">
      <span class="event-title">${escapeHtml(e.title)}</span>
      ${eventStatusBadge(e)}
    </div>
    <div class="event-meta">${escapeHtml(timeLabel)} · ${escapeHtml(e.organizer || '주최자 미상')} · ${escapeHtml(e.location || '장소 미상')}</div>
    ${e.description ? `<div class="event-desc">${escapeHtml(e.description)}</div>` : ''}
    ${tagsHtml ? `<div class="mini-tags">${tagsHtml}</div>` : ''}
    ${eventActionsHtml(e)}
  </div>`;
}

// ── 시트/모달 공통 헬퍼 ──────────────────────────────────────────────

function showPanel(name) {
  document.getElementById(`${name}Backdrop`).hidden = false;
  document.getElementById(`${name}${name === 'day' || name === 'new' ? 'Sheet' : 'Modal'}`).hidden = false;
}

function hidePanel(name) {
  document.getElementById(`${name}Backdrop`).hidden = true;
  document.getElementById(`${name}${name === 'day' || name === 'new' ? 'Sheet' : 'Modal'}`).hidden = true;
}

// ── 일자 상세 시트 ────────────────────────────────────────────────────

let selectedDate = null;

function openDaySheet(date) {
  selectedDate = date;
  const filtered = filterByTags(state.merged, state.activeTags);
  const dayEvents = eventsForDay(filtered, date);
  document.getElementById('daySheetTitle').textContent = date;
  document.getElementById('dayEventList').innerHTML = dayEvents.length
    ? dayEvents.map(renderEventRow).join('')
    : '<div class="empty">일정이 없습니다.</div>';
  showPanel('day');
}

async function reloadAndRerender() {
  await loadAll();
  renderAll();
  if (selectedDate) openDaySheet(selectedDate);
}

// ── 추가/수정 모달 ────────────────────────────────────────────────────

let editContext = { mode: 'create' }; // 'create' | 'manual' | 'auto'

function openEditModal(ctx) {
  editContext = ctx;
  const form = document.getElementById('editForm');
  form.reset();
  document.getElementById('btnDeleteEvent').hidden = ctx.mode !== 'manual';

  const titleMap = { create: '일정 추가', manual: '내 일정 수정', auto: '자동 일정 수정' };
  document.getElementById('editModalTitle').textContent = titleMap[ctx.mode];

  const e = ctx.event || {};
  document.getElementById('fTitle').value = e.title || '';
  document.getElementById('fOrganizer').value = e.organizer || '';
  document.getElementById('fStartAt').value = e.start_at || selectedDate || todayStr();
  document.getElementById('fEndAt').value = e.end_at || '';
  const allDay = !e.time;
  document.getElementById('fAllDay').checked = allDay;
  document.getElementById('timeField').hidden = allDay;
  document.getElementById('fTime').value = e.time || '';
  document.getElementById('fLocation').value = e.location || '';
  document.getElementById('fDescription').value = e.description || '';

  showPanel('edit');
}

function readEditForm() {
  const allDay = document.getElementById('fAllDay').checked;
  return {
    title: document.getElementById('fTitle').value.trim(),
    organizer: document.getElementById('fOrganizer').value.trim() || null,
    start_at: document.getElementById('fStartAt').value,
    end_at: document.getElementById('fEndAt').value || null,
    time: allDay ? null : document.getElementById('fTime').value || null,
    location: document.getElementById('fLocation').value.trim() || null,
    description: document.getElementById('fDescription').value.trim() || null,
  };
}

// ── 이벤트 바인딩 ─────────────────────────────────────────────────────

function bindEvents() {
  document.getElementById('btnPrevMonth').addEventListener('click', () => {
    state.month -= 1;
    if (state.month < 1) {
      state.month = 12;
      state.year -= 1;
    }
    renderCalendar();
  });

  document.getElementById('btnNextMonth').addEventListener('click', () => {
    state.month += 1;
    if (state.month > 12) {
      state.month = 1;
      state.year += 1;
    }
    renderCalendar();
  });

  document.getElementById('calendarRoot').addEventListener('click', (ev) => {
    const btn = ev.target.closest('.day-cell');
    if (btn) openDaySheet(btn.dataset.date);
  });

  document.getElementById('tagFilter').addEventListener('click', (ev) => {
    const chip = ev.target.closest('.chip');
    if (!chip) return;
    const tag = chip.dataset.tag;
    const idx = state.activeTags.indexOf(tag);
    if (idx >= 0) state.activeTags.splice(idx, 1);
    else state.activeTags.push(tag);
    renderTagFilter();
    renderCalendar();
    if (selectedDate) openDaySheet(selectedDate);
  });

  document.getElementById('btnCloseDay').addEventListener('click', () => {
    hidePanel('day');
    selectedDate = null;
  });
  document.getElementById('dayBackdrop').addEventListener('click', () => {
    hidePanel('day');
    selectedDate = null;
  });

  document.getElementById('btnBell').addEventListener('click', () => {
    const newEvents = computeNewEvents(state.merged);
    document.getElementById('newEventList').innerHTML = newEvents.length
      ? newEvents.map(renderEventRow).join('')
      : '<div class="empty">새 일정이 없습니다.</div>';
    showPanel('new');
  });
  const closeNew = () => {
    hidePanel('new');
    markAllRead();
    renderBellBadge();
  };
  document.getElementById('btnCloseNew').addEventListener('click', closeNew);
  document.getElementById('newBackdrop').addEventListener('click', closeNew);

  document.getElementById('btnAdd').addEventListener('click', () => openEditModal({ mode: 'create' }));
  document.getElementById('btnCloseEdit').addEventListener('click', () => hidePanel('edit'));
  document.getElementById('editBackdrop').addEventListener('click', () => hidePanel('edit'));

  document.getElementById('fAllDay').addEventListener('change', (ev) => {
    document.getElementById('timeField').hidden = ev.target.checked;
  });

  document.getElementById('editForm').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const payload = readEditForm();
    try {
      if (editContext.mode === 'create') {
        await createManualEvent(payload);
      } else if (editContext.mode === 'manual') {
        await updateManualEvent(editContext.event.rawId, payload);
      } else if (editContext.mode === 'auto') {
        await setReviewStatus(editContext.event.id, 'confirmed', payload);
      }
      hidePanel('edit');
      await reloadAndRerender();
    } catch (e) {
      alert(`저장 실패: ${e.message}`);
    }
  });

  document.getElementById('btnDeleteEvent').addEventListener('click', async () => {
    if (editContext.mode !== 'manual') return;
    if (!confirm('이 일정을 삭제하시겠습니까?')) return;
    try {
      await deleteManualEvent(editContext.event.rawId);
      hidePanel('edit');
      await reloadAndRerender();
    } catch (e) {
      alert(`삭제 실패: ${e.message}`);
    }
  });

  document.getElementById('dayEventList').addEventListener('click', async (ev) => {
    const btn = ev.target.closest('[data-action]');
    if (!btn) return;
    const action = btn.dataset.action;
    const id = btn.dataset.id;
    try {
      if (action === 'delete-manual') {
        if (!confirm('이 일정을 삭제하시겠습니까?')) return;
        await deleteManualEvent(id);
        await reloadAndRerender();
      } else if (action === 'confirm-auto') {
        await setReviewStatus(id, 'confirmed');
        await reloadAndRerender();
      } else if (action === 'reject-auto') {
        if (!confirm('이 일정을 거절하시겠습니까? 캘린더에서 숨겨집니다.')) return;
        await setReviewStatus(id, 'rejected');
        await reloadAndRerender();
      } else if (action === 'edit-manual') {
        const raw = (state.manualEvents || []).find((m) => String(m.id) === String(id));
        openEditModal({ mode: 'manual', event: { ...raw, rawId: raw.id } });
      } else if (action === 'edit-auto') {
        const merged = state.merged.find((m) => m.id === id);
        openEditModal({ mode: 'auto', event: merged });
      }
    } catch (e) {
      alert(`처리 실패: ${e.message}`);
    }
  });

  document.getElementById('btnSettings').addEventListener('click', () => {
    const s = getSettings();
    document.getElementById('sBase').value = s.base || '';
    document.getElementById('sToken').value = s.token || '';
    showPanel('settings');
  });
  document.getElementById('btnCloseSettings').addEventListener('click', () => hidePanel('settings'));
  document.getElementById('settingsBackdrop').addEventListener('click', () => hidePanel('settings'));

  document.getElementById('settingsForm').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    saveSettings({
      base: document.getElementById('sBase').value.trim(),
      token: document.getElementById('sToken').value.trim(),
    });
    hidePanel('settings');
    await reloadAndRerender();
  });
}

// ── 초기화 ────────────────────────────────────────────────────────────

async function init() {
  const now = new Date();
  state.year = now.getFullYear();
  state.month = now.getMonth() + 1;
  bindEvents();
  await loadAll();
  renderAll();
}

document.addEventListener('DOMContentLoaded', init);
