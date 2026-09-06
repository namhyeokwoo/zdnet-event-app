"""과거 [ZD브리핑] 기사를 최근 1년치까지 소급 수집해 data/events.json을 채우는 1회성 스크립트.

scrape_zdbriefing.py는 매주 최신 기사 1건만 처리하는 반면, 이 스크립트는
search.zdnet.co.kr 검색 결과를 여러 페이지 훑어 과거 기사를 한 번에 모아 처리한다.
GitHub Actions 크론에는 연결하지 않음 — 사람이 필요할 때 수동 실행.

이미 처리된 기사(동일 발행일 접두사의 이벤트가 events.json에 있는 경우)는 건너뛰므로
중간에 실패해도 재실행하면 이어서 처리된다(Claude API 재호출 비용 절약).

사용법: ANTHROPIC_API_KEY 환경변수 설정 후 `python scripts/backfill_events.py`
        `--limit N`으로 처리 건수를 제한해 먼저 소규모로 검증 가능.
"""
import argparse
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from events_io import build_event_dicts, load_events, merge_and_save
from extract_events import extract_events
from find_latest_article import HEADERS, TITLE_PREFIX, fetch_article

SEARCH_URL_TMPL = (
    "https://search.zdnet.co.kr/?kwd=" + urllib.parse.quote("[ZD브리핑]") + "&area=&pageno={}&term="
)
BACKFILL_DAYS = 365
MAX_PAGES = 10  # 실제 확인된 결과는 4페이지(약 76건, ~1.5년치)뿐이지만 여유를 둔 안전판
REQUEST_DELAY_SEC = 2  # zdnet.co.kr / Claude API 양쪽에 예의상 텀


def _list_candidates() -> list[dict]:
    """검색 결과를 페이지별로 훑어 [ZD브리핑] 기사 후보를 최신순으로 모은다.
    빈 페이지가 나오면 그 이상 페이지는 없다고 보고 중단."""
    seen_urls = set()
    candidates = []
    for page in range(1, MAX_PAGES + 1):
        resp = requests.get(SEARCH_URL_TMPL.format(page), headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        links = [
            a for a in soup.select("a[href*='/view/?no=']")
            if a.get_text(strip=True).startswith(TITLE_PREFIX)
        ]
        new_on_page = 0
        for a in links:
            href = a["href"]
            if href.startswith("/"):
                href = "https://zdnet.co.kr" + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            candidates.append({"url": href, "title": a.get_text(strip=True)})
            new_on_page += 1
        if new_on_page == 0:
            break
    return candidates


def _within_window(url: str, cutoff_yyyymmdd: str) -> bool:
    """기사 URL의 `no=YYYYMMDDHHMMSS`에서 날짜를 뽑아 대략적인 기간 필터링.
    패턴이 안 맞으면 일단 포함시키고, 실제 발행일은 fetch_article()에서 정확히 확인."""
    m = re.search(r"no=(\d{8})", url)
    if not m:
        return True
    return m.group(1) >= cutoff_yyyymmdd


def _already_processed(events_by_id: dict, source_url: str) -> bool:
    """날짜 접두사가 아니라 실제 기사 URL로 판정 — 같은 날짜에 기사가 2건 이상
    발행돼도(정정/재게시 등) 서로 다른 기사면 각각 처리된다."""
    return any(e.get("source_url") == source_url for e in events_by_id.values())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="처리할 최대 기사 수(검증용)")
    parser.add_argument("--days", type=int, default=BACKFILL_DAYS, help="소급 기간(기본 365일)")
    args = parser.parse_args()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y%m%d")
    print(f"검색 결과 수집 중... (소급 기준일 {cutoff} 이후)")
    candidates = _list_candidates()
    candidates = [c for c in candidates if _within_window(c["url"], cutoff)]
    candidates.sort(key=lambda c: c["url"])  # no= 접두사 오름차순 = 발행일 오름차순(과거->최근)
    if args.limit:
        candidates = candidates[: args.limit]
    print(f"백필 대상 후보 {len(candidates)}건")

    existing = load_events()
    events_by_id = {e["id"]: e for e in existing.get("events", [])}
    source_article = existing.get("source_article")

    processed = 0
    skipped = 0
    failed = []

    for idx, c in enumerate(candidates, start=1):
        try:
            try:
                article = fetch_article(c["url"])
            except Exception as e:
                failed.append((c["url"], f"fetch 실패: {e}"))
                continue

            if _already_processed(events_by_id, c["url"]):
                print(f"[{idx}/{len(candidates)}] 스킵(이미 처리됨): {article['title']}")
                skipped += 1
                continue

            date_str = article["published_at"].strftime("%Y%m%d")
            try:
                raw_events = extract_events(article)
            except Exception as e:
                failed.append((c["url"], f"추출 실패: {e}"))
                continue

            now_iso = datetime.now(timezone.utc).isoformat()
            new_events = build_event_dicts(raw_events, date_str, article["url"], now_iso)
            for e in new_events:
                events_by_id[e["id"]] = e

            if source_article is None or article["published_at"].isoformat() > source_article.get(
                "published_at", ""
            ):
                source_article = {
                    "url": article["url"],
                    "title": article["title"],
                    "published_at": article["published_at"].isoformat(),
                }

            # 매 기사 처리 후 즉시 저장 — 중간에 실패해도 이미 처리한 만큼은 보존되고,
            # 재실행 시 _already_processed()로 건너뛰어 API를 다시 호출하지 않는다.
            output = merge_and_save({"events": list(events_by_id.values())}, [], source_article)
            events_by_id = {e["id"]: e for e in output["events"]}

            processed += 1
            print(f"[{idx}/{len(candidates)}] {len(new_events)}건 추출 (누적 {len(events_by_id)}건): {article['title']}")
        finally:
            # 스킵/실패 경로도 이미 fetch_article()로 HTTP 요청을 1회 소모했으므로,
            # 재실행 시 무더기 스킵이 요청 속도 제한에 걸리지 않도록 매 후보마다 텀을 둔다.
            time.sleep(REQUEST_DELAY_SEC)

    print(f"\n완료: 처리 {processed}건, 스킵 {skipped}건, 실패 {len(failed)}건, 최종 누적 이벤트 {len(events_by_id)}건")
    for url, reason in failed:
        print(f"  실패: {url} — {reason}")


if __name__ == "__main__":
    main()
