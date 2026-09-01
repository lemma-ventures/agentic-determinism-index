"""Provider adapters.

Each adapter turns a probe case into an HTTP request and extracts
(text, fingerprint, model_version) from the response. Adding a provider means
adding one subclass and registering it in PROVIDERS — the probe loop never
special-cases providers.

API keys are read from the environment at call time and are never written to
transcripts or manifests.
"""
import json
import os
import ssl
import urllib.error
import urllib.request

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None


def _ssl_context():
    """Prefer certifi's CA bundle. The python.org macOS builds ship without
    a system trust store, which otherwise makes every HTTPS probe fail with
    CERTIFICATE_VERIFY_FAILED even when curl works fine."""
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


class Provider:
    def __init__(self, target):
        self.target = target
        self.model = target["model"]
        self.key_env = target.get("api_key_env", "")

    @property
    def api_key(self):
        return os.environ.get(self.key_env, "") if self.key_env else ""

    def request(self, case):
        raise NotImplementedError

    def parse(self, body):
        raise NotImplementedError

    def describe_request(self, case):
        """The exact request a probe sends, for the transcript: URL, JSON
        payload, and non-auth headers. Scores must be re-derivable from
        transcripts, which requires the request bytes, not just the response.
        Credentials never enter transcripts."""
        req = self.request(case)
        headers = {
            k: v
            for k, v in req.header_items()
            if k.lower()
            not in ("authorization", "x-goog-api-key", "x-api-key",
                    "content-type", "content-length")
        }
        payload = json.loads(req.data.decode("utf-8")) if req.data else None
        return {"url": req.full_url, "payload": payload, "headers": headers}

    def call(self, case, timeout=180):
        req = self.request(case)
        try:
            with urllib.request.urlopen(
                req, timeout=timeout, context=_ssl_context()
            ) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"HTTP {e.code}: {detail}") from None
        return self.parse(body)

    @staticmethod
    def _post(url, payload, headers):
        headers = {"Content-Type": "application/json", **headers}
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        return urllib.request.Request(url, data=data, headers=headers, method="POST")


class OpenAIChat(Provider):
    """OpenAI Chat Completions, and any endpoint speaking the same protocol
    (gateways, routers, self-hosted vLLM/SGLang) via `base_url`."""

    default_base = "https://api.openai.com/v1"

    def request(self, case):
        p = case.get("params", {})
        payload = {
            "model": self.model,
            "messages": case["messages"],
            "temperature": p.get("temperature", 0),
            "max_tokens": p.get("max_tokens", 512),
        }
        if p.get("seed") is not None:
            payload["seed"] = p["seed"]
        if p.get("json"):
            payload["response_format"] = {"type": "json_object"}
        base = self.target.get("base_url", self.default_base).rstrip("/")
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return self._post(f"{base}/chat/completions", payload, headers)

    def parse(self, body):
        return {
            "text": body["choices"][0]["message"].get("content") or "",
            "fingerprint": body.get("system_fingerprint"),
            "model_version": body.get("model"),
        }


class AnthropicMessages(Provider):
    """Anthropic Messages API. No seed parameter exists; cases run at the
    temperature they specify (0 for all v0.1 cases)."""

    def request(self, case):
        p = case.get("params", {})
        payload = {
            "model": self.model,
            "messages": case["messages"],
            "temperature": p.get("temperature", 0),
            "max_tokens": p.get("max_tokens", 512),
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        return self._post("https://api.anthropic.com/v1/messages", payload, headers)

    def parse(self, body):
        text = "".join(b.get("text", "") for b in body.get("content", [])
                       if b.get("type") == "text")
        return {"text": text, "fingerprint": None, "model_version": body.get("model")}


class NvidiaNIM(Provider):
    """NVIDIA NIM. OpenAI-compatible chat protocol, served from a fixed
    base URL.

    NVIDIA documents deterministic mode as a *container* environment
    variable (`NIM_FORCE_DETERMINISTIC=1`) on self-hosted NIM deployments
    with TRT-LLM buildable profiles
    (https://docs.nvidia.com/nim/large-language-models/latest/deterministic-mode.html).
    It is not a request parameter on integrate.api.nvidia.com.

    With `force_deterministic: true` the harness still sends
    `NIM_FORCE_DETERMINISTIC: 1` as a request header so a dry run can
    measure whether the hosted API silently honors it. Expect no effect
    on the hosted endpoint; the supported measurement of that mode is to
    self-host a NIM with the env var set and probe it via
    `openai_compatible`.
    """

    default_base = "https://integrate.api.nvidia.com/v1"

    def request(self, case):
        req = OpenAIChat.request(self, case)
        if self.target.get("force_deterministic"):
            # Recorded in transcripts via describe_request. Not documented
            # as honored by the hosted API; kept for the A/B measurement.
            req.add_header("NIM_FORCE_DETERMINISTIC", "1")
        return req

    def parse(self, body):
        return OpenAIChat.parse(self, body)


class OpenRouter(Provider):
    """OpenRouter. OpenAI-compatible, but it routes each request to one of
    several upstream providers behind a single model string — so burst
    behavior is expected to be poor and is an interesting test of whether a
    "model" name even pins a backend. Records the routed `provider` as the
    fingerprint when no system_fingerprint is returned.

    Optional target keys pin routing for multi-provider dry runs:
      "provider_prefs": {"order": ["groq"], "allow_fallbacks": false}
    See https://openrouter.ai/docs/guides/routing/provider-selection
    """

    default_base = "https://openrouter.ai/api/v1"

    def request(self, case):
        # Build the OpenAI-compatible payload, then optionally pin routing.
        # Rebuild via _post so Content-Length matches the final body.
        p = case.get("params", {})
        payload = {
            "model": self.model,
            "messages": case["messages"],
            "temperature": p.get("temperature", 0),
            "max_tokens": p.get("max_tokens", 512),
        }
        if p.get("seed") is not None:
            payload["seed"] = p["seed"]
        if p.get("json"):
            payload["response_format"] = {"type": "json_object"}
        prefs = self.target.get("provider_prefs")
        if prefs:
            payload["provider"] = prefs
        base = self.target.get("base_url", self.default_base).rstrip("/")
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return self._post(f"{base}/chat/completions", payload, headers)

    def parse(self, body):
        r = OpenAIChat.parse(self, body)
        if r["fingerprint"] is None:
            r["fingerprint"] = body.get("provider")
        return r


class HuggingFace(Provider):
    """Hugging Face. OpenAI-compatible via the HF Router
    (https://router.huggingface.co/v1) by default; point `base_url` at a
    dedicated Inference Endpoint to probe a single pinned deployment instead.
    Because you can pin an endpoint, this is the hosted provider most likely
    to approach self-hosted-style scores."""

    default_base = "https://router.huggingface.co/v1"

    def request(self, case):
        return OpenAIChat.request(self, case)

    def parse(self, body):
        return OpenAIChat.parse(self, body)


class GeminiGenerate(Provider):
    def request(self, case):
        p = case.get("params", {})
        gen = {
            "temperature": p.get("temperature", 0),
            "maxOutputTokens": p.get("max_tokens", 512),
        }
        if p.get("seed") is not None:
            gen["seed"] = p["seed"]
        if p.get("json"):
            gen["responseMimeType"] = "application/json"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": m["content"]}]}
                         for m in case["messages"] if m["role"] == "user"],
            "generationConfig": gen,
        }
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent")
        return self._post(url, payload, {"x-goog-api-key": self.api_key})

    def parse(self, body):
        parts = body["candidates"][0].get("content", {}).get("parts", [])
        return {
            "text": "".join(p.get("text", "") for p in parts),
            "fingerprint": None,
            "model_version": body.get("modelVersion"),
        }


PROVIDERS = {
    "openai": OpenAIChat,
    "openai_compatible": OpenAIChat,
    "anthropic": AnthropicMessages,
    "gemini": GeminiGenerate,
    "nvidia_nim": NvidiaNIM,
    "openrouter": OpenRouter,
    "huggingface": HuggingFace,
}


def make_provider(target):
    kind = target.get("provider")
    if kind not in PROVIDERS:
        raise ValueError(f"unknown provider {kind!r}; known: {sorted(PROVIDERS)}")
    return PROVIDERS[kind](target)
