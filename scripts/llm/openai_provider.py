"""Raw HTTP call to the OpenAI Chat Completions API — no `openai` pip package."""
import json
import urllib.error
import urllib.request

from llm.base import ProviderError

API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"


def generate(prompt, api_key, model=None):
    body = json.dumps(
        {
            "model": model or DEFAULT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        }
    ).encode("utf-8")

    req = urllib.request.Request(API_URL, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        if e.code == 401:
            raise ProviderError("OpenAI API 키가 올바르지 않아요. 키를 다시 확인해 주세요.") from e
        if e.code == 429:
            raise ProviderError("OpenAI 요청 한도(429)에 걸렸어요. 잠시 후 다시 시도해 주세요.") from e
        raise ProviderError(f"OpenAI 호출 실패 ({e.code}): {detail[:200]}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"OpenAI에 연결하지 못했어요: {e.reason}") from e
    except TimeoutError as e:
        raise ProviderError("OpenAI 응답이 너무 오래 걸려요 (시간 초과).") from e

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ProviderError(f"OpenAI 응답 형식이 예상과 달라요: {data!r}") from e


def validate_key(api_key):
    """Cheap check that the key at least authenticates. Returns (ok, message)."""
    try:
        generate("답장하지 말고 그냥 'ok'라고만 출력해줘.", api_key)
        return True, "OK"
    except ProviderError as e:
        return False, str(e)
