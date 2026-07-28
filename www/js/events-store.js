// 자동 추출(JSON) + 검수 상태(hub_api.py) + 개인 일정(hub_api.py) 3원 병합
const LAST_VISIT_KEY = 'zdnetevent.lastVisitAt';

function applyOverrides(event, overrides) {
  if (!overrides) return event;
  return { ...event, ...overrides };
}

function mergeEvents(autoEvents, reviewStatusMap, manualEvents) {
  const merged = [];

  for (const e of autoEvents) {
    const review = reviewStatusMap ? reviewStatusMap[e.id] : null;
    const status = review ? review.status : 'pending';
    if (status === 'rejected') continue;
    const withOverrides = applyOverrides(e, review ? review.overrides : null);
    merged.push({ ...withOverrides, source: 'zdbriefing', status });
  }

  if (manualEvents) {
    for (const e of manualEvents) {
      merged.push({
        id: `manual-${e.id}`,
        rawId: e.id,
        title: e.title,
        organizer: e.organizer,
        start_at: e.start_at,
        end_at: e.end_at,
        time: e.time,
        location: e.location,
        description: e.description,
        tags: [],
        source: 'manual',
        status: null,
        created_at: e.created_at,
      });
    }
  }

  merged.sort((a, b) => (a.start_at || '').localeCompare(b.start_at || ''));
  return merged;
}

function getLastVisitAt() {
  return localStorage.getItem(LAST_VISIT_KEY) || '1970-01-01T00:00:00.000Z';
}

function markAllRead() {
  localStorage.setItem(LAST_VISIT_KEY, new Date().toISOString());
}

function computeNewEvents(mergedEvents) {
  const lastVisit = getLastVisitAt();
  return mergedEvents.filter((e) => e.created_at && e.created_at > lastVisit);
}

function collectAllTags(mergedEvents) {
  const set = new Set();
  for (const e of mergedEvents) {
    for (const t of e.tags || []) set.add(t);
  }
  return Array.from(set).sort();
}

function filterByTags(mergedEvents, activeTags) {
  if (!activeTags || activeTags.length === 0) return mergedEvents;
  return mergedEvents.filter((e) => (e.tags || []).some((t) => activeTags.includes(t)));
}
