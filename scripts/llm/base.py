"""Shared prompt construction for every LLM provider (API-based or manual paste).

Using one function for all providers keeps behavior identical regardless of
which LLM ends up generating the itinerary.
"""
from schema import PROMPT_SPEC_TEXT


class ProviderError(Exception):
    pass


def build_prompt(answers, prior_errors=None):
    lines = [
        "당신은 한국 여행 전문 플래너입니다. 아래 조건에 맞는 여행 일정을 짜주세요.",
        "",
        f"- 여행지: {answers.get('destination', '(미지정)')}",
        f"- 기간: {answers.get('start_date')} ~ {answers.get('end_date')}",
        f"- 동행: {answers.get('travelers', '(미지정)')}",
        f"- 예산: {answers.get('budget', '(미지정)')}",
        f"- 관심사/스타일: {answers.get('interests', '(미지정)')}",
    ]
    if answers.get("base_location"):
        lines.append(f"- 숙소/베이스캠프: {answers['base_location']}")
    if answers.get("rental_car_day"):
        lines.append(f"- 렌트카를 쓰는 날: {answers['rental_car_day']}일차")
    if answers.get("must_see"):
        lines.append(f"- 꼭 가고 싶은 곳/하고 싶은 것: {answers['must_see']}")
    if answers.get("notes"):
        lines.append(f"- 추가 참고사항: {answers['notes']}")

    lines.append("")
    lines.append(PROMPT_SPEC_TEXT)

    if prior_errors:
        lines.append("")
        lines.append(
            "방금 준 답변에 아래 문제가 있었습니다. 문제를 모두 고쳐서 "
            "처음부터 완전한 JSON을 다시 출력해 주세요:"
        )
        for err in prior_errors:
            lines.append(f"- {err}")

    return "\n".join(lines)
