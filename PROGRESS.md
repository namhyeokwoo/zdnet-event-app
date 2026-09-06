# ZD브리핑 캘린더 앱 — 진행 상황

## 최근 작업 (최근 커밋 기준)
- **주간 스크래핑 덮어쓰기 버그 수정(2026-09-06)**: `scrape_zdbriefing.py`가 매주 실행마다
  `data/events.json`을 이번 주 이벤트로 통째로 덮어써서, 과거 자동 추출 일정이 매주 유실되고
  있었음(수동 CRUD로 추가한 항목만 아니라 자동 추출분도 사라짐). `scripts/events_io.py`
  신설(`load_events`/`build_event_dicts`/`prune_old`/`merge_and_save`) — id 기준 upsert
  병합 + 365일(RETENTION_DAYS) 초과분만 정리하는 방식으로 교체. `scripts/backfill_events.py`
  신설(1회성 소급 수집, search.zdnet.co.kr 최대 10페이지 훑어 최근 1년치 [ZD브리핑] 기사를
  한 번에 처리) 실행해 `data/events.json`을 실제로 백필 완료. `.github/workflows/scrape.yml`에
  `timeout-minutes: 20` 추가(8월 GitHub Actions 사용량 폭주 사고 재발방지 조치, 다른
  저장소들과 동일 패턴). CLAUDE.md/PROGRESS.md와 함께 그동안 git 이력이 없던 미추적 상태였음.
  `/code-review` 지적 2건 반영: `backfill_events.py`의 `_already_processed()`가 날짜 접두사만
  보고 판정해 같은 날짜에 기사가 2건이면 두 번째를 통째로 놓치던 문제를 실제 `source_url`
  비교로 교체, `REQUEST_DELAY_SEC`가 스킵/실패 경로에선 적용 안 돼 재실행 시 빠른 연속
  요청으로 zdnet.co.kr 레이트리밋 걸릴 위험이 있던 걸 `finally` 블록으로 모든 후보마다
  적용되도록 수정. 나머지 2건(재추출 시 사라진 이벤트가 고아로 남을 수 있는 엣지케이스,
  `find_latest_article.py`와의 검색 로직 중복)은 발생 확률 낮고 백필은 저빈도 수동 스크립트라
  이번엔 보류 — 다음 항목 참고
- 캘린더/키워드 순서 변경 + 월간 전체 일정 표 추가
- ZD브리핑 신규 일정 FCM 푸시 알림 추가
- scrape.yml git push 로직 버그 수정 (커밋 후 push가 영원히 안 되던 문제)
- OPTIONS preflight가 실제 뷰 로직을 실행하던 CORS 버그 수정

## 현재 상태
전체 배포 스택(GitHub Pages 웹 + Render API + Neon DB) 정상 동작 확인됨. hub-app에 iframe
타일로 통합 완료.

## 다음 할 일 / 확인 대기 중
- FCM "신규 일정" 알림은 코드 배포됐지만 아직 실제 신규 기사가 없어 라이브 미검증 — 다음
  일요일 정기 scrape 실행 때 Discord+FCM 둘 다 오는지 자연 검증됨
- Render/Neon 무료 서비스 URL이 여전히 유효한지 장기 미사용 시 주기적으로 curl 확인 권장
- `events_io.merge_and_save()`는 id 기준 upsert만 하고 삭제는 안 함 — 같은 기사를 재추출했는데
  이벤트 수가 줄어들면 이전 실행의 남는 id가 고아로 영구 남을 수 있음(발생하려면 같은 URL을
  Claude가 비결정적으로 다르게 추출해야 해서 확률 낮음, 2026-09-06 `/code-review`가 지적)
- `backfill_events.py`의 검색 결과 페이지 파싱(`_list_candidates`)이 `find_latest_article.py`의
  단일 페이지 파싱 로직과 중복 구현 — 사이트 마크업 바뀌면 두 곳 다 고쳐야 함, 공용 헬퍼로
  추출 검토 여지 (2026-09-06 `/code-review` 지적)
