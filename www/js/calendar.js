// 월간 캘린더 그리드 — 외부 라이브러리 없이 자체 구현
function pad2(n) {
  return String(n).padStart(2, '0');
}

function ymd(y, m, d) {
  return `${y}-${pad2(m)}-${pad2(d)}`;
}

function todayStr() {
  const t = new Date();
  return ymd(t.getFullYear(), t.getMonth() + 1, t.getDate());
}

function buildMonthGrid(year, month) {
  const firstDow = new Date(year, month - 1, 1).getDay();
  const numDays = new Date(year, month, 0).getDate();
  const prevNumDays = new Date(year, month - 1, 0).getDate();
  const cells = [];

  for (let i = 0; i < firstDow; i++) {
    const d = prevNumDays - firstDow + 1 + i;
    const y2 = month === 1 ? year - 1 : year;
    const m2 = month === 1 ? 12 : month - 1;
    cells.push({ date: ymd(y2, m2, d), day: d, inMonth: false });
  }
  for (let d = 1; d <= numDays; d++) {
    cells.push({ date: ymd(year, month, d), day: d, inMonth: true });
  }
  let nextDay = 1;
  while (cells.length % 7 !== 0) {
    const y2 = month === 12 ? year + 1 : year;
    const m2 = month === 12 ? 1 : month + 1;
    cells.push({ date: ymd(y2, m2, nextDay), day: nextDay, inMonth: false });
    nextDay++;
  }
  return cells;
}

function eventsForDay(events, date) {
  return events.filter((e) => {
    const start = e.start_at;
    const end = e.end_at || e.start_at;
    return date >= start && date <= end;
  });
}

function eventsForMonth(events, year, month) {
  const first = ymd(year, month, 1);
  const last = ymd(year, month, new Date(year, month, 0).getDate());
  return events
    .filter((e) => {
      const start = e.start_at;
      const end = e.end_at || e.start_at;
      return end >= first && start <= last;
    })
    .sort((a, b) => {
      if (a.start_at !== b.start_at) return a.start_at < b.start_at ? -1 : 1;
      return (a.time || '').localeCompare(b.time || '');
    });
}

function formatDateRange(e) {
  const s = e.start_at.slice(5).replace('-', '/');
  if (e.end_at && e.end_at !== e.start_at) {
    return `${s}~${e.end_at.slice(5).replace('-', '/')}`;
  }
  return s;
}

function renderMonthTable(year, month, events) {
  const list = eventsForMonth(events, year, month);
  if (list.length === 0) {
    return '<div class="empty">이번 달 일정이 없습니다.</div>';
  }
  const rows = list
    .map((e) => `<tr data-date="${e.start_at}">
      <td>${formatDateRange(e)}</td>
      <td>${escapeHtml(e.title)}</td>
      <td>${escapeHtml(e.organizer || '-')}</td>
      <td>${e.time ? escapeHtml(e.time) : '종일'}</td>
      <td>${escapeHtml(e.location || '-')}</td>
    </tr>`)
    .join('');
  return `<div class="table-wrap"><table class="month-table">
    <thead><tr><th>날짜</th><th>제목</th><th>주최기업</th><th>시간</th><th>장소</th></tr></thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}

const WEEKDAY_LABELS = ['일', '월', '화', '수', '목', '금', '토'];

function renderCalendarGrid(year, month, events) {
  const cells = buildMonthGrid(year, month);
  const today = todayStr();

  const header = WEEKDAY_LABELS.map((w, i) => {
    const cls = i === 0 ? 'wd sun' : i === 6 ? 'wd sat' : 'wd';
    return `<div class="${cls}">${w}</div>`;
  }).join('');

  const body = cells
    .map((cell) => {
      const dayEvents = eventsForDay(events, cell.date);
      const hasPending = dayEvents.some((e) => e.status === 'pending');
      const dotCount = Math.min(dayEvents.length, 4);
      const dots = dayEvents.length
        ? `<div class="day-dots">${'<span class="dot"></span>'.repeat(dotCount)}</div>`
        : '';
      const classes = [
        'day-cell',
        cell.inMonth ? '' : 'muted',
        cell.date === today ? 'today' : '',
        hasPending ? 'has-pending' : '',
      ]
        .filter(Boolean)
        .join(' ');
      return `<button type="button" class="${classes}" data-date="${cell.date}">
        <span class="day-num">${cell.day}</span>${dots}
      </button>`;
    })
    .join('');

  return `<div class="cal-header">${header}</div><div class="cal-grid">${body}</div>`;
}
