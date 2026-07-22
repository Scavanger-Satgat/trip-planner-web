"""Raw HTTP call to the Anthropic Messages API — no `anthropic` pip package."""
import json
import urllib.error
import urllib.request

from llm.base import ProviderError

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5"


def generate(prompt, api_key, model=None):
    body = json.dumps(
        {
            "model": model or DEFAULT_MODEL,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")

    req = urllib.request.Request(API_URL, data=body, method="POST")
    req.add_header("x-api-key", api_key)
    req.add_header("anthropic-version", API_VERSION)
    req.add_header("content-type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        if e.code == 401:
            raise ProviderError("Anthropic API 키가 올바르지 않아요. 키를 다시 확인해 주세요.") from e
        if e.code == 429:
            raise ProviderError("Anthropic 요청 한도(429)에 걸렸어요. 잠시 후 다시 시도해 주세요.") from e
        raise ProviderError(f"Anthropic 호출 실패 ({e.code}): {detail[:200]}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"Anthropic에 연결하지 못했어요: {e.reason}") from e
    except TimeoutError as e:
        raise ProviderError("Anthropic 응답이 너무 오래 걸려요 (시간 초과).") from e

    try:
        return data["content"][0]["text"]
    except (KeyError, IndexError, TypeError) as e:
        raise ProviderError(f"Anthropic 응답 형식이 예상과 달라요: {data!r}") from e


def validate_key(api_key):
    """Cheap check that the key at least authenticates. Returns (ok, message)."""
    try:
        generate("답장하지 말고 그냥 'ok'라고만 출력해줘.", api_key)
        return True, "OK"
    except ProviderError as e:
        return False, str(e)
