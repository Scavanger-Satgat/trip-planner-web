"""Itinerary JSON schema: the spec text handed to LLMs/humans, plus parsing and validation.

No third-party dependency (no jsonschema) — plain Python checks only.
"""
import json
import re

VALID_CATEGORIES = ("food", "cafe", "activity", "special")

PROMPT_SPEC_TEXT = """\
아래 JSON 스키마와 정확히 같은 구조로만 답변해 주세요. 다른 설명 없이 JSON만 출력하세요.

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
- JSON 앞뒤에 다른 설명 문장을 붙이지 마세요. JSON 코드블록(```json ... ```)만 출력해도 괜찮습니다.
"""


class ItineraryError(Exception):
    pass


def parse_llm_json(raw_text):
    """Extract and parse a JSON object out of raw LLM/human-pasted text.

    Tries, in order: direct json.loads, stripped ```json fences, and the
    substring between the first '{' and the last '}'.
    """
    text = raw_text.strip()

    for candidate in _candidates(text):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise ItineraryError(
        "JSON으로 읽을 수 없어요. 코드블록(```json ... ```) 안에 있는 내용만, "
        "다른 설명 문장 없이 붙여넣어 주세요."
    )


def _candidates(text):
    yield text

    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence_match:
        yield fence_match.group(1).strip()

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        yield text[first_brace : last_brace + 1]


def normalize_itinerary(data):
    """Cheap type coercion before validation (stringified numbers, stray whitespace)."""
    if not isinstance(data, dict):
        return data

    for day in data.get("days", []) or []:
        if isinstance(day, dict) and "day_number" in day:
            try:
                day["day_number"] = int(day["day_number"])
            except (TypeError, ValueError):
                pass

    rcd = data.get("rental_car_day")
    if rcd is not None and rcd != "":
        try:
            data["rental_car_day"] = int(rcd)
        except (TypeError, ValueError):
            pass
    elif rcd == "":
        data["rental_car_day"] = None

    for day in data.get("days", []) or []:
        if not isinstance(day, dict):
            continue
        for list_key in ("stops", "transit_notes", "cards", "callouts"):
            if day.get(list_key) is None:
                day[list_key] = []

    if data.get("pool") is None:
        data["pool"] = []
    if data.get("footer_notes") is None:
        data["footer_notes"] = []
    if data.get("meta_chips") is None:
        data["meta_chips"] = []

    return data


def _validate_place(place, path, problems):
    if not isinstance(place, dict):
        problems.append(f"{path}: 객체(dict)여야 합니다.")
        return
    if not place.get("name"):
        problems.append(f"{path}: name이 비어 있습니다.")
    category = place.get("category")
    if category not in VALID_CATEGORIES:
        problems.append(
            f"{path}: category 값이 '{category}'인데, "
            f"{'/'.join(VALID_CATEGORIES)} 중 하나여야 합니다."
        )


def validate_itinerary(data):
    """Return a list of human-readable problems. Empty list means valid.

    Does not raise, and does not stop at the first problem — accumulates all
    of them so a single correction round can fix everything.
    """
    problems = []

    if not isinstance(data, dict):
        return ["최상위 값이 JSON 객체(dict)가 아닙니다."]

    for key in ("trip_title", "start_date", "end_date"):
        if not data.get(key):
            problems.append(f"'{key}' 필드가 비어 있습니다.")

    days = data.get("days")
    if not isinstance(days, list) or not days:
        problems.append("'days' 배열이 비어 있거나 없습니다.")
        days = []

    seen_day_numbers = set()
    for i, day in enumerate(days):
        prefix = f"days[{i}]"
        if not isinstance(day, dict):
            problems.append(f"{prefix}: 객체(dict)여야 합니다.")
            continue

        day_number = day.get("day_number")
        if not isinstance(day_number, int):
            problems.append(f"{prefix}.day_number: 정수여야 합니다 (현재: {day_number!r}).")
        elif day_number in seen_day_numbers:
            problems.append(f"{prefix}.day_number: {day_number}가 중복됩니다.")
        else:
            seen_day_numbers.add(day_number)

        for key in ("date_label", "theme_label", "title"):
            if not day.get(key):
                problems.append(f"{prefix}.{key}: 비어 있습니다.")

        stops = day.get("stops", [])
        if not isinstance(stops, list):
            problems.append(f"{prefix}.stops: 배열이어야 합니다.")
            stops = []
        for j, stop in enumerate(stops):
            _validate_place(stop, f"{prefix}.stops[{j}]", problems)

        transit_notes = day.get("transit_notes", [])
        if isinstance(transit_notes, list) and isinstance(stops, list) and stops:
            expected = max(len(stops) - 1, 0)
            if len(transit_notes) != expected:
                problems.append(
                    f"{prefix}.transit_notes: {len(transit_notes)}개인데, "
                    f"stops가 {len(stops)}개면 {expected}개가 있어야 자연스러워요 "
                    "(치명적 오류는 아니니 참고만 하세요)."
                )

        cards = day.get("cards", [])
        if not isinstance(cards, list):
            problems.append(f"{prefix}.cards: 배열이어야 합니다.")
            cards = []
        for j, card in enumerate(cards):
            _validate_place(card, f"{prefix}.cards[{j}]", problems)

        for j, callout in enumerate(day.get("callouts", []) or []):
            if not isinstance(callout, dict) or "text" not in callout:
                problems.append(f"{prefix}.callouts[{j}]: {{type, text}} 형태여야 합니다.")

    rental_car_day = data.get("rental_car_day")
    if rental_car_day is not None and rental_car_day not in seen_day_numbers:
        problems.append(
            f"'rental_car_day' 값({rental_car_day!r})이 실제 days 안의 day_number 중에 없습니다."
        )

    for j, place in enumerate(data.get("pool", []) or []):
        _validate_place(place, f"pool[{j}]", problems)

    for j, note in enumerate(data.get("footer_notes", []) or []):
        if not isinstance(note, dict) or "text" not in note:
            problems.append(f"footer_notes[{j}]: {{label, text}} 형태여야 합니다.")

    return problems
