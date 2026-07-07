"""xAI / OpenRouter Grok API client."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import httpx
from openai import OpenAI

from app.prompts import allocation_prompt, firm_prompt, macro_prompt

PROVIDERS = {
    "xai": {
        "base_url": "https://api.x.ai/v1",
        "default_model": "grok-4.3",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "x-ai/grok-4.3",
    },
}


@dataclass
class GrokResult:
    text: str
    cost_usd: float = 0.0
    usage: dict[str, Any] = field(default_factory=dict)


def _cost_from_usage(usage: Any) -> float:
    if usage is None:
        return 0.0
    ticks = getattr(usage, "cost_in_usd_ticks", None)
    if ticks is None and isinstance(usage, dict):
        ticks = usage.get("cost_in_usd_ticks")
    if ticks:
        return float(ticks) / 10_000_000_000
    # OpenRouter may expose cost directly on usage in some responses
    if isinstance(usage, dict):
        cost = usage.get("cost")
        if cost is not None:
            return float(cost)
    cost_attr = getattr(usage, "cost", None)
    if cost_attr is not None:
        return float(cost_attr)
    return 0.0


def _extract_text(response: Any) -> str:
    if hasattr(response, "output_text") and response.output_text:
        return str(response.output_text)
    parts: list[str] = []
    output = getattr(response, "output", None) or []
    for item in output:
        content = getattr(item, "content", None) or []
        for block in content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
    if parts:
        return "\n".join(parts)
    choices = getattr(response, "choices", None)
    if choices:
        msg = choices[0].message
        return msg.content or ""
    return str(response)


def parse_score(text: str) -> int | None:
    patterns = [
        r"Score:\s*(\d{1,3})",
        r"score:\s*(\d{1,3})",
        r"Investment Score:\s*(\d{1,3})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = int(match.group(1))
            return max(1, min(100, value))
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    for line in reversed(lines[-5:]):
        if re.fullmatch(r"\d{1,3}", line):
            return max(1, min(100, int(line)))
    return None


def resolve_model(provider: str, model: str) -> str:
    cfg = PROVIDERS.get(provider, PROVIDERS["xai"])
    if not model:
        return cfg["default_model"]
    if provider == "openrouter" and "/" not in model:
        return f"x-ai/{model}"
    return model


class GrokClient:
    def __init__(
        self,
        api_key: str,
        model: str = "grok-4.3",
        provider: str = "xai",
    ) -> None:
        self.provider = provider if provider in PROVIDERS else "xai"
        cfg = PROVIDERS[self.provider]
        self.api_key = api_key
        self.model = resolve_model(self.provider, model or cfg["default_model"])
        self.base_url = cfg["base_url"]
        default_headers: dict[str, str] = {}
        if self.provider == "openrouter":
            default_headers = {
                "HTTP-Referer": "http://localhost:8765",
                "X-Title": "Gecko PM",
            }
        self._extra_headers = default_headers
        self.client = OpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=httpx.Timeout(3600.0, connect=60.0),
            default_headers=default_headers or None,
        )
        self.total_cost_usd = 0.0

    def _openrouter_responses_post(self, body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self._extra_headers,
        }
        with httpx.Client(timeout=httpx.Timeout(3600.0, connect=60.0)) as client:
            resp = client.post(f"{self.base_url}/responses", headers=headers, json=body)
            if resp.status_code >= 400:
                detail = resp.text[:500]
                raise RuntimeError(f"OpenRouter API {resp.status_code}: {detail}")
            return resp.json()

    def _extract_text_from_dict(self, data: dict[str, Any]) -> str:
        if data.get("output_text"):
            return str(data["output_text"])
        parts: list[str] = []
        for item in data.get("output", []):
            for block in item.get("content", []):
                if block.get("type") in ("output_text", "text") and block.get("text"):
                    parts.append(block["text"])
        if parts:
            return "\n".join(parts)
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "") or ""
        return str(data)

    def _record_dict(self, data: dict[str, Any]) -> GrokResult:
        usage = data.get("usage", {})
        cost = _cost_from_usage(usage)
        self.total_cost_usd += cost
        return GrokResult(
            text=self._extract_text_from_dict(data),
            cost_usd=cost,
            usage=usage if isinstance(usage, dict) else {},
        )

    def _record(self, response: Any) -> GrokResult:
        usage = getattr(response, "usage", None)
        cost = _cost_from_usage(usage)
        self.total_cost_usd += cost
        usage_dict: dict[str, Any] = {}
        if usage is not None:
            if hasattr(usage, "model_dump"):
                usage_dict = usage.model_dump()
            elif isinstance(usage, dict):
                usage_dict = usage
        return GrokResult(text=_extract_text(response), cost_usd=cost, usage=usage_dict)

    def _create_response(self, prompt: str, *, web_search: bool = False) -> Any:
        if self.provider == "openrouter":
            body: dict[str, Any] = {
                "model": self.model,
                "input": [{"role": "user", "content": prompt}],
                "max_output_tokens": 16000,
            }
            if web_search:
                body["plugins"] = [{"id": "web", "max_results": 10}]
            return self._openrouter_responses_post(body)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "input": [{"role": "user", "content": prompt}],
        }
        if web_search:
            kwargs["tools"] = [{"type": "web_search"}, {"type": "x_search"}]
        return self.client.responses.create(**kwargs)

    def _to_result(self, response: Any) -> GrokResult:
        if isinstance(response, dict):
            return self._record_dict(response)
        return self._record(response)

    def score_firm(
        self,
        ticker: str,
        company_name: str,
        industry: str,
        macro_news: str,
        financials: str,
        news: str,
    ) -> GrokResult:
        prompt = firm_prompt(company_name, industry, macro_news, financials, news)
        response = self._create_response(prompt)
        result = self._to_result(response)
        score = parse_score(result.text)
        result.usage["parsed_score"] = score
        result.usage["ticker"] = ticker
        return result

    def generate_macro_report(self, context: str) -> GrokResult:
        prompt = macro_prompt(context)
        try:
            response = self._create_response(prompt, web_search=True)
            return self._to_result(response)
        except Exception:
            # If live search fails, still generate from injected news context
            response = self._create_response(prompt, web_search=False)
            return self._to_result(response)

    def generate_allocation(self, top_reports: str) -> GrokResult:
        prompt = allocation_prompt(top_reports)
        response = self._create_response(prompt)
        return self._to_result(response)
