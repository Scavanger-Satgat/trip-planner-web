# Trip Planner (웹 버전)

브라우저에서 폼만 채우면 깃허브 액션이 지도·경로가 담긴 여행 계획 페이지를 자동으로 만들어서 깃허브 페이지에 올려줘요. 서버를 직접 운영할 필요 없이, 깃허브 저장소 하나로 다 처리돼요.

## 처음 설정 (한 번만)

1. 이 저장소를 내 계정으로 가져오기 (Fork 또는 "Use this template")
2. **Settings → Pages** 에서 Source를 `main` 브랜치 / `/ (root)` 로 설정
3. **Settings → Secrets and variables → Actions** 에서 아래 시크릿 등록
   - `NCP_KEY_ID`, `NCP_KEY_SECRET` — 네이버 클라우드 플랫폼 Maps 애플리케이션의 Client ID/Secret (Dynamic Map, Geocoding, Directions 5 활성화한 것). Web 서비스 URL에는 `https://<내계정>.github.io` 등록 필요
   - `OPENAI_API_KEY` 또는 `ANTHROPIC_API_KEY` — AI가 자동으로 일정을 짜게 하려면 등록 (둘 다 없어도, 웹페이지에서 "이미 만든 JSON 붙여넣기" 모드로 계속 쓸 수 있어요)
   - (선택) `LLM_PROVIDER` — `openai` 또는 `anthropic`. 둘 다 등록했을 때 어느 걸 쓸지 지정
   - (선택) `ACCENT_COLOR` — 페이지 강조 색상 (hex)
4. **깃허브 개인 토큰(PAT) 발급** — https://github.com/settings/personal-access-tokens/new 에서 fine-grained 토큰 생성
   - Repository access: 이 저장소 하나만 선택
   - Permissions: **Contents: Read and write**, **Actions: Read and write**
   - 이 토큰을 웹페이지 폼에 입력해서 써요

## 사용법

`https://<내계정>.github.io/<저장소이름>/` 접속 → 토큰 입력 → 여행 정보 입력 → "여행 계획 만들기" 클릭. 깃허브 액션이 실행되는 동안 페이지에서 진행 상황이 표시되고, 끝나면 결과 링크가 나와요. 결과 페이지는 `/plan/` 경로에 생겨요.

## 어떻게 동작하나요

1. 브라우저가 입력한 내용을 `request.json`으로 저장소에 커밋 (깃허브 Contents API, PAT 사용)
2. `request.json` 변경을 감지해서 깃허브 액션(`​.github/workflows/build-trip.yml`)이 자동 실행
3. 액션 안에서 (필요하면) LLM 호출 → 네이버 지도 API로 좌표 변환 → `plan/index.html` 생성 → 자동 커밋
4. 깃허브 페이지가 갱신된 `plan/index.html`을 서빙

네이버 지도의 좌표 변환·경로 API는 브라우저에서 직접 호출할 수 없어서(CORS 미지원), 이 부분만 깃허브 액션 안에서 처리해요. 지도 자체를 화면에 띄우는 건 브라우저에서 바로 되고요.

## 보안 관련 (지금 방식과 나중에 강화할 수 있는 부분)

**지금 방식**: 사용자가 직접 발급한 깃허브 PAT를 웹페이지 폼에 입력 → 브라우저가 깃허브 API를 직접 호출. 토큰은 외부로 전송되지 않고, "이 브라우저에 기억하기"를 체크하지 않으면 저장되지도 않아요. 네이버/LLM 키는 브라우저에 전혀 노출되지 않고 깃허브 시크릿 안에서만 쓰여요.

**나중에 추가하면 좋은 것들** (`assets/app.js`의 "GitHub token handling" 섹션과 `README`의 이 항목만 고치면 돼요):
- PAT 직접 입력 대신 GitHub App + OAuth Device Flow로 교체 (토큰을 사용자가 직접 만들 필요 없이 "깃허브로 로그인" 버튼 하나로)
- 제출 전 토큰의 실제 권한 범위를 확인해서, 필요 이상으로 넓은 권한이면 경고
- `request.json` 제출에 rate limit / 중복 제출 방지
- 액션 실행 로그에 개인정보(주소 등)가 남지 않도록 마스킹
