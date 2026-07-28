"""[ZD브리핑] 기사 본문 -> 구조화된 이벤트 배열 (Claude API structured extraction)."""
import os

import anthropic

MODEL = "claude-sonnet-5"

EVENTS_SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "행사/일정 제목"},
                    "organizer": {
                        "type": ["string", "null"],
                        "description": "주최 기업/기관명. 불명확하면 null",
                    },
                    "start_at": {
                        "type": "string",
                        "description": "YYYY-MM-DD, 기사 발행일을 기준으로 해석한 절대 날짜",
                    },
                    "end_at": {
                        "type": ["string", "null"],
                        "description": "YYYY-MM-DD. '20~22일' 같은 범위 표현일 때만 채움, 아니면 null",
                    },
                    "time": {
                        "type": ["string", "null"],
                        "description": "HH:MM (24시간, 한국시간 기준). 시각 언급이 없으면 null",
                    },
                    "location": {"type": ["string", "null"], "description": "장소. 불명확하면 null"},
                    "description": {
                        "type": "string",
                        "description": "해당 일정만 다루는 1~2문장 한국어 요약 (기사 전체 요약 아님)",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "description": "주제 태그(예: AI, 반도체, 클라우드, 공공SW) + 관련 기업/기관명 태그를 함께 부여",
                    },
                },
                "required": [
                    "title", "organizer", "start_at", "end_at", "time",
                    "location", "description", "tags",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["events"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """당신은 한국 IT 업계 뉴스 기사에서 일정(이벤트)을 구조화된 데이터로 추출하는 전문가입니다.

입력은 지디넷코리아의 "[ZD브리핑]" 주간 코너 기사입니다. 이 기사는 정형화된 목록이 아니라
여러 일정이 산문 형태로 섞여 있는 뉴스 기사입니다. 다음 규칙을 반드시 지켜 모든 일정을 추출하세요.

## 날짜 해석 규칙
- 기사에 주어지는 "기사 발행일"을 기준점으로 상대 날짜를 절대 날짜(YYYY-MM-DD)로 변환합니다.
- "오는 23일", "23일", "N일" 같은 표현은 발행일 기준으로 가장 가까운 미래의 해당 일(day-of-month)로
  해석합니다. 그 날짜가 발행일보다 이전(day-of-month가 더 작음)이면 다음 달로 넘어간 것으로 판단합니다.
- "22일(현지시간)"처럼 현지시간이 언급되어도, "한국시간으로는 22일 오후 10시"처럼 한국시간이
  별도로 명시되어 있으면 그 한국시간 날짜/시각을 start_at/time으로 사용합니다. 한국시간 언급이
  없으면 현지시간 날짜를 그대로 사용합니다.
- "20~22일", "20∼22일", "19~29일" 같은 범위 표현은 start_at에 시작일, end_at에 종료일을 넣습니다.
  범위가 아니면 end_at은 반드시 null입니다.
- "▲22일 A ▲23일 B ▲24일 C" 같은 불릿 나열은 불릿 하나당 별도의 이벤트로 분리합니다. 각 불릿이
  가리키는 개별 날짜를 그 이벤트의 start_at으로 사용합니다.

## 추출 범위
- 기사에 언급된 모든 개별 일정을 빠짐없이 추출하세요. 같은 날짜를 공유하는 일정이라도 병합하거나
  생략하지 말고 각각 별도 이벤트로 만드세요.
- description은 기사 전체 요약이 아니라, 그 일정 하나에 해당하는 문단/구절만 1~2문장으로
  압축한 한국어 요약이어야 합니다.
- 시각이 명시되지 않은 일정은 time을 null로 둡니다(종일 일정으로 처리됨).
- tags는 최소 1개 이상, 주제(AI/반도체/클라우드/공공SW/게임/금융 등)와 관련 기업·기관명을
  함께 부여하세요. 예: "삼성 갤럭시 언팩" -> ["스마트폰", "삼성전자"]
"""


def extract_events(article: dict) -> list[dict]:
    """article: find_latest_article.fetch_article()의 반환값
    (url, title, published_at: datetime, body_text: str)
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY") or None)

    published_at = article["published_at"]
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"][published_at.weekday()]
    user_prompt = (
        f"기사 발행일: {published_at.strftime('%Y-%m-%d')} ({weekday_kr}요일)\n"
        f"기사 제목: {article['title']}\n\n"
        f"기사 본문:\n{article['body_text']}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": EVENTS_SCHEMA}},
        messages=[{"role": "user", "content": user_prompt}],
    )

    import json

    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    return data["events"]


if __name__ == "__main__":
    import sys

    sys.path.insert(0, os.path.dirname(__file__))
    from find_latest_article import fetch_article

    url = sys.argv[1] if len(sys.argv) > 1 else "https://zdnet.co.kr/view/?no=20260719122204"
    article = fetch_article(url)
    events = extract_events(article)
    print(f"{len(events)}건 추출됨\n")
    for e in events:
        print(f"- [{e['start_at']}{' ~ ' + e['end_at'] if e['end_at'] else ''}] "
              f"{e['time'] or '(시각 미상)'} {e['title']} ({e['organizer'] or '주최자 미상'}) "
              f"@ {e['location'] or '장소 미상'}  tags={e['tags']}")
        print(f"    {e['description']}")
