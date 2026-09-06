# ZD브리핑 캘린더 앱 (zdnet-event-app)

지디넷코리아의 매주 일요일 "[ZD브리핑]" 기사(그 주 IT 업계 일정 큐레이션)를 Claude API로 구조화
추출해 개인 캘린더로 만든 앱. 개인 CRUD, 자동 추출 일정 검수(pending/confirmed/rejected),
태그 필터링. `namhyeokwoo/zdnet-event-app` — **의도적으로 public** (data/events.json을
raw.githubusercontent.com에서 인증 없이 fetch하기 위함, 민감정보 없음).

## 배포 구조

- **프론트엔드(웹)**: https://namhyeokwoo.github.io/zdnet-event-app/ — GitHub Pages,
  `.github/workflows/pages.yml`이 `www/` 자동 배포. PC 전원 무관
- **프론트엔드(모바일)**: 같은 `www/` 코드를 Capacitor로 감싼 앱(appId `com.ska90.zdnetevent`).
  서버 URL/토큰은 설정 모달에서 localStorage 관리 — 서버 주소 바뀌어도 재빌드 불필요
- **읽기 경로(자동 추출)**: `.github/workflows/scrape.yml`(매주 일 20:30 KST + 월 08:00 폴백)
  → `scripts/scrape_zdbriefing.py` → `data/events.json` 커밋 → `www/js/api.js`가
  raw.githubusercontent.com에서 직접 fetch. 검색은 `search.zdnet.co.kr/?kwd=[ZD브리핑]` 우선,
  RSS(`feeds.feedburner.com/zdkorea`) 폴백
- **쓰기 경로(CRUD/검수/태그)**: `api/`(Flask, `rootDir: api`) → **Render**(무료,
  `zdnet-event-api`, https://zdnet-event-api.onrender.com) + **Neon**(무료 Postgres, pooled
  연결 문자열 권장). `render.yaml`은 반드시 저장소 **루트**에 있어야 Blueprint가 인식함

## 계정/시크릿 (위치만 기록)

- GitHub repo secret `ANTHROPIC_API_KEY` (이 repo, Actions용)
- Render 환경변수 `HUB_API_TOKEN`/`DATABASE_URL`/`ALLOWED_ORIGINS` (Render 대시보드에서 직접,
  Claude에게 값 공유 안 됨)
- Neon 프로젝트 (console.neon.tech, 사용자가 직접 생성)

## 무료 서비스 선택 근거 (재조사 불필요)

Render(콜드스타트 15분 비활성 후 30~60초, 자동 재기동) + Neon(영구 무료, 자동 suspend/resume).
기각: PythonAnywhere(3개월마다 수동 갱신), Supabase(1주 비활성 시 수동 재개), Render 자체
Postgres(30~90일 후 삭제), Fly.io/Cloud Run(카드 필수), Railway(영구 무료 아님).

## hub-app 통합

hub-app 대시보드에 `embedUrl` 타일로 통합됨(iframe으로 열림, job 실행 흐름과 무관). 상세는
[[../hub-app/CLAUDE.md|hub-app]] 참고. FCM "신규 일정" 알림도 `scripts/notify_fcm.py`로 추가됨.

## 겪은 버그 (재발 방지)

1. **scrape.yml push 버그**: "커밋 성공 후 → push 여부를 다시 `git diff --cached --quiet`로
   검사"하면 커밋 직후 staging이 clean해져 두 번째 diff가 항상 "변경 없음"으로 평가 → **push가
   영원히 안 실행됨**(워크플로는 초록 체크로 성공 표시라 눈치채기 어려움). `if ! git diff
   --cached --quiet; then commit; push; fi` 단일 블록으로 수정함
2. **Flask `methods=[..., "OPTIONS"]` 명시 시 CORS preflight가 실제 뷰 로직을 실행**해버려
   (예: 존재하지 않는 id PUT preflight가 404 반환) 브라우저가 실제 요청을 차단. OPTIONS를
   methods에서 빼고 Flask 기본 처리에 맡기는 걸로 수정. **`hub_api.py`(claude-hub repo)의 남은
   라우트들이 아직 같은 패턴을 씀 — 나중에 브라우저 CORS 대상이 되면 재발할 것**
3. Render `DATABASE_URL`에 예시 placeholder(`ep-xxxx.region.aws.neon.tech`)를 문자 그대로
   넣어서 배포 실패한 적 있음 — 연결 문자열 예시를 줄 때는 "이건 예시"를 명확히 강조할 것
4. 별도 claude.ai 세션이 이 프로젝트를 Next.js+Prisma로 착각해 Vercel+Neon용 제안을 한 적 있음
   — 실제로는 Capacitor 정적 HTML/JS + Flask. 다른 세션발 제안은 실제 코드와 대조 후 반영할 것

## 범위 밖 (재검토 불필요)

OS 푸시(FCM으로 대체 완료), 행사 종료 후 AI 요약, 관심사 프리셋(TagGroup), 광고 배너.

**How to apply:** URL(Render/Neon)이 여전히 유효한지 `curl`로 먼저 확인 후 작업할 것(무료
서비스는 장기 미사용 시 정책이 바뀔 수 있음). [[project_workspace_repos]], [[project_hub_app]] 참고.
