"""GitHub Actions entry point: reads request.json, produces plan/index.html + plan/itinerary.json.

Runs unattended (no interactive input) — this is what replaces the CLI tool's
cli.py orchestration for the web-triggered flow. request.json is written by
the frontend (assets/app.js) via the GitHub Contents API.

Secrets (from the workflow's `env:` block, sourced from repo Settings > Secrets):
  NCP_KEY_ID, NCP_KEY_SECRET   (required)
  OPENAI_API_KEY or ANTHROPIC_API_KEY   (required unless request mode is "itinerary")
  LLM_PROVIDER  ("openai" | "anthropic", optional — inferred from which key is set if omitted)
  ACCENT_COLOR  (optional)
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import geocode_pipeline
import schema
import theme
import render
from llm import anthropic_provider, base, openai_provider
from llm.base import ProviderError

ROOT = Path(__file__).resolve().parent.parent
REQUEST_PATH = ROOT / "request.json"
OUTPUT_DIR = ROOT / "plan"
MAX_LLM_RETRIES = 3


def _pick_provider():
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if provider in ("openai", "anthropic"):
        return provider
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def _call_llm(answers):
    provider = _pick_provider()
    if not provider:
        raise ProviderError(
            "OPENAI_API_KEY 또는 ANTHROPIC_API_KEY 시크릿이 설정되어 있지 않아요. "
            "레포지토리 Settings > Secrets에 등록하거나, '이미 만든 JSON 붙여넣기' 모드를 사용해 주세요."
        )

    prior_errors = None
    for _ in range(MAX_LLM_RETRIES):
        prompt = base.build_prompt(answers, prior_errors=prior_errors)
        if provider == "openai":
            raw = openai_provider.generate(prompt, os.environ["OPENAI_API_KEY"])
        else:
            raw = anthropic_provider.generate(prompt, os.environ["ANTHROPIC_API_KEY"])

        try:
            data = schema.parse_llm_json(raw)
        except schema.ItineraryError as e:
            prior_errors = [str(e)]
            continue

        data = schema.normalize_itinerary(data)
        problems = schema.validate_itinerary(data)
        if not problems:
            return data
        prior_errors = problems

    raise ProviderError(f"{MAX_LLM_RETRIES}번 시도했는데도 올바른 형식의 여행 계획을 받지 못했어요.")


def main():
    if not REQUEST_PATH.exists():
        print(f"{REQUEST_PATH} 가 없어요.")
        sys.exit(1)

    request_data = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    mode = request_data.get("mode", "facts")

    if mode == "itinerary":
        itinerary = schema.normalize_itinerary(request_data["itinerary"])
    else:
        try:
            itinerary = _call_llm(request_data["answers"])
        except ProviderError as e:
            print(f"LLM 호출 실패: {e}")
            sys.exit(1)

    problems = schema.validate_itinerary(itinerary)
    if problems:
        print("생성된 여행 계획에 문제가 있어요:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)

    ncp_key_id = os.environ.get("NCP_KEY_ID")
    ncp_key_secret = os.environ.get("NCP_KEY_SECRET")
    if not ncp_key_id or not ncp_key_secret:
        print("NCP_KEY_ID / NCP_KEY_SECRET 시크릿이 설정되어 있지 않아요.")
        sys.exit(1)

    map_data, day_routes, unresolved = geocode_pipeline.build_map_data(itinerary, ncp_key_id, ncp_key_secret)
    itinerary["_unresolved_names"] = [name for _, name in unresolved]

    accent_color = os.environ.get("ACCENT_COLOR") or theme.DEFAULT_ACCENT
    html_out = render.render_page(itinerary, map_data, day_routes, ncp_key_id, accent_color)

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "index.html").write_text(html_out, encoding="utf-8")

    saved_itinerary = {k: v for k, v in itinerary.items() if k != "_unresolved_names"}
    (OUTPUT_DIR / "itinerary.json").write_text(
        json.dumps(saved_itinerary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    status = {
        "request_id": request_data.get("request_id"),
        "ok": True,
        "unresolved": [{"day": d, "name": n} for d, n in unresolved],
    }
    (OUTPUT_DIR / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"완료: {OUTPUT_DIR / 'index.html'}")
    if unresolved:
        print("주소를 찾지 못한 장소:")
        for day_number, name in unresolved:
            print(f"  - {day_number}일차: {name}")


if __name__ == "__main__":
    main()
