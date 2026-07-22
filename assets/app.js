"use strict";

// Mirrors trip_planner_lib/schema.py's PROMPT_SPEC_TEXT and llm/base.py's build_prompt.
// Kept as plain text/string building (no build step) so this stays a static page.
const PROMPT_SPEC_TEXT = `아래 JSON 스키마와 정확히 같은 구조로만 답변해 주세요. 다른 설명 없이 JSON만 출력하세요.

{
  "trip_title": "문자열 - 여행 제목 (예: '부산 여행')",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "meta_chips": ["문자열 배열 - 여행 요약 태그, 예: '3박 4일', '성인 2인'"],
  "rental_car_day": null,
  "days": [
    {
      "day_number": 1,
      "date_label": "문자열 - 예: '8/1 (토)'",
      "theme_label": "문자열 - 그날 테마 한 줄, 예: '도착 & 해운대'",
      "title": "문자열 - 그날 제목",
      "subtitle": "문자열 - 부제목",
      "stats": ["문자열 배열 - 예: '이동 40분', '총 3곳'"],
      "stops": [
        {
          "name": "장소 이름",
          "address_hint": "이 장소의 정식 도로명/지번 주소 - 최대한 정확하게. 상호명만으로는 지도에 표시할 수 없습니다.",
          "category": "food 중 하나 | cafe | activity | special",
          "location_note": "짧은 위치 설명, 예: '해운대구 우동'",
          "stop_note": "선택 - 이 장소에서의 메모"
        }
      ],
      "transit_notes": ["문자열 배열 - stops 사이 이동 방법, stops보다 1개 적음"],
      "cards": [
        {
          "name": "장소 이름",
          "address_hint": "정식 주소",
          "category": "food | cafe | activity | special",
          "location_note": "짧은 위치 설명",
          "description": "설명",
          "price": "선택 - 가격대",
          "caution": "선택 - 주의사항"
        }
      ],
      "callouts": [{"type": "warn 또는 good", "text": "문자열"}],
      "alt_line": "선택 - 대안 한 줄"
    }
  ],
  "pool": [
    "cards와 동일한 모양의 객체 배열 - 이번 일정에는 안 넣었지만 대안으로 제시할 후보 장소들"
  ],
  "footer_notes": [{"label": "문자열", "text": "문자열"}]
}

규칙:
- category는 반드시 food, cafe, activity, special 중 하나여야 합니다.
- address_hint는 지오코딩(주소→좌표 변환)에 쓰이므로, 상호명이 아니라 "정식 도로명 주소 또는 지번 주소"를 최대한 정확히 적어주세요. 확실하지 않으면 최소한 "시/도 + 구/군 + 동" 수준까지는 적어주세요.
- rental_car_day는 실제 days 안에 있는 day_number 값이거나, 렌트카를 쓰는 날이 없으면 null이어야 합니다.
- day_number는 1부터 시작하는 정수이며 중복되면 안 됩니다.
- stops, cards, pool, callouts, footer_notes, meta_chips는 없으면 빈 배열 []로 주세요 (필드 자체를 생략하지 마세요).
- JSON 앞뒤에 다른 설명 문장을 붙이지 마세요. JSON 코드블록(\`\`\`json ... \`\`\`)만 출력해도 괜찮습니다.`;

function buildPrompt(answers) {
  const lines = [
    "당신은 한국 여행 전문 플래너입니다. 아래 조건에 맞는 여행 일정을 짜주세요.",
    "",
    `- 여행지: ${answers.destination || "(미지정)"}`,
    `- 기간: ${answers.start_date} ~ ${answers.end_date}`,
    `- 동행: ${answers.travelers || "(미지정)"}`,
    `- 예산: ${answers.budget || "(미지정)"}`,
    `- 관심사/스타일: ${answers.interests || "(미지정)"}`,
  ];
  if (answers.base_location) lines.push(`- 숙소/베이스캠프: ${answers.base_location}`);
  if (answers.rental_car_day) lines.push(`- 렌트카를 쓰는 날: ${answers.rental_car_day}일차`);
  if (answers.must_see) lines.push(`- 꼭 가고 싶은 곳/하고 싶은 것: ${answers.must_see}`);
  if (answers.notes) lines.push(`- 추가 참고사항: ${answers.notes}`);
  lines.push("", PROMPT_SPEC_TEXT);
  return lines.join("\n");
}

// --- GitHub token handling -------------------------------------------------
// Isolated here on purpose: this is a PAT pasted by the user, used only for
// direct browser->GitHub API calls (never sent anywhere else). Swapping this
// for a GitHub App / OAuth device flow later only needs this section touched.
const TOKEN_STORAGE_KEY = "trip-planner-gh-token";

function loadStoredToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY) || "";
}

function persistTokenIfRequested(token, remember) {
  if (remember) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

// --- Repo detection ----------------------------------------------------------
function detectOwnerRepo() {
  const host = location.hostname; // "<owner>.github.io"
  const owner = host.split(".")[0];
  const firstSegment = location.pathname.split("/").filter(Boolean)[0];
  const repo = firstSegment || `${owner}.github.io`;
  return { owner, repo };
}

// --- base64 helpers (UTF-8 safe) --------------------------------------------
function utf8ToBase64(str) {
  const bytes = new TextEncoder().encode(str);
  let binary = "";
  bytes.forEach((b) => (binary += String.fromCharCode(b)));
  return btoa(binary);
}

// --- GitHub API calls --------------------------------------------------------
async function ghFetch(token, path, opts = {}) {
  const res = await fetch(`https://api.github.com${path}`, {
    ...opts,
    cache: "no-store",
    headers: {
      Authorization: `token ${token}`,
      Accept: "application/vnd.github+json",
      ...(opts.headers || {}),
    },
  });
  return res;
}

async function submitRequest(token, owner, repo, payload) {
  const path = `/repos/${owner}/${repo}/contents/request.json`;
  let sha;
  const existing = await ghFetch(token, path);
  if (existing.status === 200) {
    const data = await existing.json();
    sha = data.sha;
  } else if (existing.status !== 404) {
    const detail = await existing.text();
    throw new Error(`request.json 조회 실패 (${existing.status}): ${detail}`);
  }

  const body = {
    message: "Submit trip request",
    content: utf8ToBase64(JSON.stringify(payload, null, 2)),
  };
  if (sha) body.sha = sha;

  const put = await ghFetch(token, path, { method: "PUT", body: JSON.stringify(body) });
  if (!put.ok) {
    const detail = await put.text();
    throw new Error(`제출 실패 (${put.status}): ${detail}`);
  }
  return put.json();
}

async function findRunForCommit(token, owner, repo, commitSha, maxAttempts = 20) {
  // Ask GitHub to filter server-side by head_sha (more reliable than paging
  // through the general run list, which can be crowded by unrelated Pages
  // deployment runs). cache:"no-store" on ghFetch keeps this from seeing a
  // stale cached response while polling for a run that just started.
  for (let i = 0; i < maxAttempts; i++) {
    const res = await ghFetch(
      token,
      `/repos/${owner}/${repo}/actions/runs?head_sha=${commitSha}&event=push&per_page=5`
    );
    if (res.ok) {
      const data = await res.json();
      const match = (data.workflow_runs || [])[0];
      if (match) return match;
    }
    await new Promise((r) => setTimeout(r, 3000));
  }
  return null;
}

async function pollRun(token, owner, repo, runId, onUpdate, maxAttempts = 60) {
  for (let i = 0; i < maxAttempts; i++) {
    const res = await ghFetch(token, `/repos/${owner}/${repo}/actions/runs/${runId}`);
    if (res.ok) {
      const run = await res.json();
      onUpdate(run);
      if (run.status === "completed") return run;
    }
    await new Promise((r) => setTimeout(r, 5000));
  }
  return null;
}

// --- UI wiring ----------------------------------------------------------------
const form = document.getElementById("trip-form");
const tokenInput = document.getElementById("gh-token");
const rememberCheckbox = document.getElementById("remember-token");
const modeFactsBtn = document.getElementById("mode-facts");
const modeItineraryBtn = document.getElementById("mode-itinerary");
const factsFields = document.getElementById("facts-fields");
const itineraryFields = document.getElementById("itinerary-fields");
const modeHint = document.getElementById("mode-hint");
const showPromptBtn = document.getElementById("show-prompt-btn");
const promptBox = document.getElementById("prompt-box");
const promptText = document.getElementById("prompt-text");
const copyPromptBtn = document.getElementById("copy-prompt-btn");
const statusBox = document.getElementById("status-box");
const submitBtn = document.getElementById("submit-btn");

let mode = "facts";

const storedToken = loadStoredToken();
if (storedToken) {
  tokenInput.value = storedToken;
  rememberCheckbox.checked = true;
}

function setMode(next) {
  mode = next;
  modeFactsBtn.setAttribute("aria-pressed", String(mode === "facts"));
  modeItineraryBtn.setAttribute("aria-pressed", String(mode === "itinerary"));
  factsFields.style.display = mode === "facts" ? "block" : "none";
  itineraryFields.style.display = mode === "itinerary" ? "block" : "none";
  modeHint.textContent =
    mode === "facts"
      ? "저장소에 OPENAI_API_KEY 또는 ANTHROPIC_API_KEY 시크릿이 등록되어 있어야 해요."
      : "LLM 시크릿 없이도 사용할 수 있어요 — 원하는 챗봇에 프롬프트를 붙여넣고, 답변을 아래에 붙여넣으세요.";
}
modeFactsBtn.addEventListener("click", () => setMode("facts"));
modeItineraryBtn.addEventListener("click", () => setMode("itinerary"));
setMode("facts");

function currentFactsAnswers() {
  const answers = {
    destination: document.getElementById("f-destination").value.trim(),
    start_date: document.getElementById("f-start").value,
    end_date: document.getElementById("f-end").value,
    travelers: document.getElementById("f-travelers").value.trim(),
    budget: document.getElementById("f-budget").value.trim(),
    interests: document.getElementById("f-interests").value.trim(),
  };
  const base = document.getElementById("f-base").value.trim();
  const rental = document.getElementById("f-rental").value.trim();
  const mustSee = document.getElementById("f-mustsee").value.trim();
  const notes = document.getElementById("f-notes").value.trim();
  if (base) answers.base_location = base;
  if (rental) answers.rental_car_day = rental;
  if (mustSee) answers.must_see = mustSee;
  if (notes) answers.notes = notes;
  return answers;
}

showPromptBtn.addEventListener("click", () => {
  promptText.textContent = buildPrompt(currentFactsAnswersForPrompt());
  promptBox.style.display = "block";
});

function currentFactsAnswersForPrompt() {
  // Itinerary mode still needs the trip facts to build the copy-paste prompt,
  // so we read the same fields even though they're visually hidden in this mode.
  return currentFactsAnswers();
}

copyPromptBtn.addEventListener("click", async () => {
  await navigator.clipboard.writeText(promptText.textContent);
  copyPromptBtn.textContent = "복사됨!";
  setTimeout(() => (copyPromptBtn.textContent = "복사하기"), 1500);
});

function showStatus(kind, html) {
  statusBox.className = kind;
  statusBox.style.display = "block";
  statusBox.innerHTML = html;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const token = tokenInput.value.trim();
  if (!token) {
    showStatus("bad", "깃허브 개인 토큰을 입력해 주세요.");
    return;
  }
  persistTokenIfRequested(token, rememberCheckbox.checked);

  let payload;
  if (mode === "facts") {
    const answers = currentFactsAnswers();
    if (!answers.destination || !answers.start_date || !answers.end_date) {
      showStatus("bad", "여행지·시작일·종료일은 꼭 입력해 주세요.");
      return;
    }
    payload = { request_id: `${Date.now()}-${Math.random().toString(36).slice(2)}`, mode: "facts", answers };
  } else {
    const raw = document.getElementById("f-itinerary-json").value.trim();
    let itinerary;
    try {
      itinerary = JSON.parse(raw);
    } catch (err) {
      showStatus("bad", `JSON을 읽을 수 없어요: ${err.message}`);
      return;
    }
    payload = { request_id: `${Date.now()}-${Math.random().toString(36).slice(2)}`, mode: "itinerary", itinerary };
  }

  submitBtn.disabled = true;
  const { owner, repo } = detectOwnerRepo();

  try {
    showStatus("warn", "제출하고 있어요...");
    const putResult = await submitRequest(token, owner, repo, payload);
    const commitSha = putResult.commit && putResult.commit.sha;

    showStatus("warn", "깃허브 액션이 시작되기를 기다리고 있어요...");
    const run = await findRunForCommit(token, owner, repo, commitSha);
    if (!run) {
      showStatus(
        "warn",
        `제출은 됐는데 실행 상태를 못 찾았어요. <a href="https://github.com/${owner}/${repo}/actions" target="_blank" rel="noopener">액션 페이지</a>에서 직접 확인해 주세요.`
      );
      return;
    }

    await pollRun(token, owner, repo, run.id, (r) => {
      showStatus("warn", `진행 중이에요... (${r.status})`);
    });

    const finalRes = await ghFetch(token, `/repos/${owner}/${repo}/actions/runs/${run.id}`);
    const finalRun = await finalRes.json();

    if (finalRun.conclusion === "success") {
      showStatus(
        "good",
        `완료됐어요! <a href="./plan/" target="_blank" rel="noopener">여기서 확인하기</a>`
      );
    } else {
      showStatus(
        "bad",
        `실패했어요 (${finalRun.conclusion}). <a href="${finalRun.html_url}" target="_blank" rel="noopener">실행 로그 보기</a>`
      );
    }
  } catch (err) {
    showStatus("bad", `오류: ${err.message}`);
  } finally {
    submitBtn.disabled = false;
  }
});
