"""오케스트레이터: 최신 [ZD브리핑] 발견 -> 추출 -> data/events.json에 idempotent 누적 반영.

GitHub Actions 주간 크론이 이 스크립트를 실행한다. 새 기사가 없거나(8일 이내
기사가 없음) 이미 처리한 기사라면 변경 없이 종료 코드 0으로 끝난다. 새 기사가 있으면
기존 누적 이벤트에 이번 주 이벤트를 병합해 저장한다(events_io.merge_and_save) —
예전처럼 파일을 통째로 덮어쓰지 않는다.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from events_io import build_event_dicts, load_events, merge_and_save
from extract_events import extract_events
from find_latest_article import find_latest_article
from notify_fcm import send as _notify_fcm

REPO_ROOT = Path(__file__).parent.parent


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


def main() -> None:
    article = find_latest_article()

    existing = load_events()
    existing_url = (existing.get("source_article") or {}).get("url")
    if existing_url == article["url"]:
        print(f"변경 없음 (이미 처리됨): {article['url']}")
        return

    raw_events = extract_events(article)

    date_str = article["published_at"].strftime("%Y%m%d")
    now_iso = datetime.now(timezone.utc).isoformat()
    new_events = build_event_dicts(raw_events, date_str, article["url"], now_iso)

    source_article = {
        "url": article["url"],
        "title": article["title"],
        "published_at": article["published_at"].isoformat(),
    }
    output = merge_and_save(existing, new_events, source_article)

    summary = (
        f"{len(new_events)}건 추출됨 (누적 {len(output['events'])}건): "
        f"{article['title']} ({article['url']})"
    )
    print(summary)
    _notify_discord(f"📅 ZD브리핑 캘린더 갱신\n{summary}")
    _notify_fcm("ZD브리핑 새 일정 등록", summary)


if __name__ == "__main__":
    main()
