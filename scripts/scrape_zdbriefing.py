"""오케스트레이터: 최신 [ZD브리핑] 발견 -> 추출 -> data/events.json에 idempotent 반영.

GitHub Actions 주간 크론이 이 스크립트를 실행한다. 새 기사가 없거나(8일 이내
기사가 없음) 이미 처리한 기사라면 변경 없이 종료 코드 0으로 끝난다.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from extract_events import extract_events
from find_latest_article import find_latest_article
from notify_fcm import send as _notify_fcm

REPO_ROOT = Path(__file__).parent.parent
EVENTS_JSON = REPO_ROOT / "data" / "events.json"


def _parse_dotenv(path: Path) -> dict:
    result = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return result


def _notify_discord(message: str) -> None:
    """DISCORD_WEBHOOK_URL이 설정돼 있으면 저비용 운영 로그를 남긴다. 선택 사항."""
    url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not url:
        env = _parse_dotenv(REPO_ROOT / ".env")
        url = env.get("DISCORD_WEBHOOK_URL", "")
    if not url:
        return
    try:
        payload = json.dumps({"content": message}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass  # 알림 실패는 파이프라인을 막지 않음


def _load_existing() -> dict:
    if not EVENTS_JSON.exists():
        return {"source_article": None, "generated_at": None, "events": []}
    with open(EVENTS_JSON, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    article = find_latest_article()

    existing = _load_existing()
    existing_url = (existing.get("source_article") or {}).get("url")
    if existing_url == article["url"]:
        print(f"변경 없음 (이미 처리됨): {article['url']}")
        return

    raw_events = extract_events(article)

    date_str = article["published_at"].strftime("%Y%m%d")
    now_iso = datetime.now(timezone.utc).isoformat()

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
            "source_url": article["url"],
            "created_at": now_iso,
        })

    output = {
        "source_article": {
            "url": article["url"],
            "title": article["title"],
            "published_at": article["published_at"].isoformat(),
        },
        "generated_at": now_iso,
        "events": events,
    }

    EVENTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(EVENTS_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    summary = f"{len(events)}건 추출됨: {article['title']} ({article['url']})"
    print(summary)
    _notify_discord(f"📅 ZD브리핑 캘린더 갱신\n{summary}")
    _notify_fcm("ZD브리핑 새 일정 등록", summary)


if __name__ == "__main__":
    main()
