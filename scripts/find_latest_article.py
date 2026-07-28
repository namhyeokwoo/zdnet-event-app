"""ZDNet Korea 최신 [ZD브리핑] 기사 탐색.

1차: https://search.zdnet.co.kr/?kwd=[ZD브리핑] 통합검색 (최신순 정렬, 확인됨).
2차 폴백: https://feeds.feedburner.com/zdkorea RSS 피드에서 제목 필터
  (it-news/scraper.py가 쓰는 것과 동일 피드지만, [ZD브리핑]이 안정적으로
  노출되지 않는 것을 확인했으므로 폴백으로만 사용).
"""
import re
import urllib.parse
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

KST = timezone(timedelta(hours=9))
SEARCH_URL = "https://search.zdnet.co.kr/?kwd=" + urllib.parse.quote("[ZD브리핑]")
RSS_URL = "https://feeds.feedburner.com/zdkorea"
FRESHNESS_WINDOW_DAYS = 8
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) zdnet-event-app/1.0"}

TITLE_PREFIX = "[ZD브리핑]"
PUBLISHED_RE = re.compile(r"입력\s*:\s*(\d{4})/(\d{2})/(\d{2})\s+(\d{2}):(\d{2})")


def _search_candidates() -> list[dict]:
    resp = requests.get(SEARCH_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    candidates = []
    for a in soup.select("a[href*='/view/?no=']"):
        text = a.get_text(strip=True)
        if text.startswith(TITLE_PREFIX):
            href = a["href"]
            if href.startswith("/"):
                href = "https://zdnet.co.kr" + href
            candidates.append({"url": href, "title": text})
    return candidates


def _rss_candidates() -> list[dict]:
    resp = requests.get(RSS_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    root = ElementTree.fromstring(resp.content)
    candidates = []
    for item in root.iter("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        if title_el is None or link_el is None:
            continue
        title = (title_el.text or "").strip()
        if title.startswith(TITLE_PREFIX):
            candidates.append({"url": (link_el.text or "").strip(), "title": title})
    return candidates


def fetch_article(url: str) -> dict:
    """기사 페이지를 가져와 본문 텍스트와 정확한 발행 시각을 추출."""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    body_el = soup.select_one("#articleBody")
    if body_el is None:
        raise RuntimeError(f"기사 본문(#articleBody)을 찾지 못했습니다: {url}")
    body_text = body_el.get_text("\n", strip=True)

    m = PUBLISHED_RE.search(html)
    if not m:
        raise RuntimeError(f"발행 시각('입력 :YYYY/MM/DD HH:MM')을 찾지 못했습니다: {url}")
    year, month, day, hour, minute = (int(g) for g in m.groups())
    published_at = datetime(year, month, day, hour, minute, tzinfo=KST)

    title_el = soup.select_one("title")
    title = title_el.get_text(strip=True) if title_el else ""
    # "<제목> - ZDNet korea" 형태이므로 접미사 제거
    title = re.sub(r"\s*-\s*ZDNet korea\s*$", "", title)

    return {"url": url, "title": title, "published_at": published_at, "body_text": body_text}


def find_latest_article() -> dict:
    """가장 최근의 [ZD브리핑] 기사를 찾아 발행일 포함 메타데이터를 반환.

    최근 8일 이내 기사가 없으면 RuntimeError — GitHub Actions가 이 예외로
    실패 상태가 되는 것이 곧 "새 기사 없음" 알림 역할을 한다.
    """
    candidates: list[dict] = []
    try:
        candidates = _search_candidates()
    except Exception:
        candidates = []

    if not candidates:
        try:
            candidates = _rss_candidates()
        except Exception:
            candidates = []

    if not candidates:
        raise RuntimeError("검색/RSS 양쪽에서 [ZD브리핑] 기사를 찾지 못했습니다.")

    # candidates는 최신순(검색 결과 문서 순서 = 최신 우선, 확인됨)
    newest = candidates[0]
    article = fetch_article(newest["url"])

    cutoff = datetime.now(KST) - timedelta(days=FRESHNESS_WINDOW_DAYS)
    if article["published_at"] < cutoff:
        raise RuntimeError(
            f"최근 {FRESHNESS_WINDOW_DAYS}일 이내 새 [ZD브리핑] 기사가 없습니다. "
            f"최신 기사: {article['title']} ({article['published_at'].isoformat()})"
        )

    return article


if __name__ == "__main__":
    result = find_latest_article()
    print(f"{result['published_at'].isoformat()}  {result['title']}")
    print(result["url"])
