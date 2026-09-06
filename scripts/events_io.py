"""data/events.json 읽기/쓰기 + 누적 병합 공용 유틸.

scrape_zdbriefing.py(주간 자동 실행)와 backfill_events.py(1회성 소급 수집) 양쪽이
공유한다. 예전엔 스크래핑할 때마다 이번 주 이벤트로 파일을 통째로 덮어써서 지난 주
자동 추출 일정이 매주 유실됐음 — 이제는 id 기준으로 upsert 병합하고 365일(RETENTION_DAYS)
초과분만 정리해, 프론트엔드의 이전/다음 달 캘린더 탐색으로 과거 일정을 계속 볼 수 있다.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
EVENTS_JSON = REPO_ROOT / "data" / "events.json"
RETENTION_DAYS = 365


def load_events() -> dict:
    if not EVENTS_JSON.exists():
        return {"source_article": None, "generated_at": None, "events": []}
    with open(EVENTS_JSON, encoding="utf-8") as f:
        return json.load(f)


def build_event_dicts(raw_events: list, date_str: str, source_url: str, now_iso: str) -> list:
    """extract_events()의 원시 결과를 이벤트당 안정적인 id를 가진 저장 스키마로 변환.

    id는 `zdb-{기사 발행일}-{같은 기사 내 순번}` 형식 — 같은 기사를 다시 처리해도
    같은 id가 나와 merge_and_save()에서 자연히 중복 제거된다.
    """
    events = []
    for i, e in enumerate(raw_events, start=1):
        events.append({
            "id": f"zdb-{date_str}-{i:02d}",
            "title": e["title"],
            "organizer": e["organizer"],
            "start_at": e["start_at"],
            "end_at": e["end_at"],
            "time": e["time"],
            "location": e["location"],
            "description": e["description"],
            "tags": e["tags"],
            "source": "zdbriefing",
            "source_url": source_url,
            "created_at": now_iso,
        })
    return events


def prune_old(events: list, retention_days: int = RETENTION_DAYS) -> list:
    """일정의 마지막 관련 날짜(end_at 있으면 그걸, 없으면 start_at)가 retention_days보다
    오래된 것만 제거 — 이미 지난 일정이어도 최근 것이면 계속 보여야 하므로 '지금 시점'이
    아니라 '얼마나 오래 전 일정이었는가'로 판단한다."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).date().isoformat()
    return [e for e in events if (e.get("end_at") or e.get("start_at") or "9999-99-99") >= cutoff]


def merge_and_save(existing: dict, new_events: list, source_article: dict) -> dict:
    """new_events를 기존 events에 id 기준 upsert 병합 후 저장(RETENTION_DAYS 초과분은 정리)."""
    by_id = {e["id"]: e for e in existing.get("events", [])}
    for e in new_events:
        by_id[e["id"]] = e
    merged = prune_old(list(by_id.values()))
    merged.sort(key=lambda e: (e.get("start_at") or "", e.get("id") or ""))

    output = {
        "source_article": source_article,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "events": merged,
    }
    EVENTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(EVENTS_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    return output
