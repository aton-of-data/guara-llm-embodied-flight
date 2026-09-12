# SPDX-License-Identifier: Apache-2.0
"""Providers are a text channel and nothing more (ADR 0013 decision 3).

These tests run with no key and no network: the HTTP call is stubbed, so what is pinned is
the request each provider builds and the text it extracts from a reply. A provider that
starts reading the site model, a plan or an expected answer would fail the contract, not
these tests — but the contract is only enforceable because the transport is this thin.
"""
from __future__ import annotations

import io
import json
import pathlib
import sys
import urllib.error

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts" / "llm")):
    if p not in sys.path:
        sys.path.insert(0, p)

import provider as provider_mod  # noqa: E402


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


@pytest.fixture
def captured(monkeypatch):
    """Capture the outgoing request and return a canned body."""
    seen: dict = {}
    body = {"body": b"{}"}

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["method"] = req.get_method()
        seen["headers"] = {k.lower(): v for k, v in req.header_items()}
        seen["payload"] = json.loads(req.data.decode()) if req.data else None
        return FakeResponse(body["body"])

    monkeypatch.setattr(provider_mod.urllib.request, "urlopen", fake_urlopen)
    return seen, body


def test_the_registry_offers_an_offline_and_an_openai_compatible_provider():
    assert {"mock", "cursor-agent", "openai-compat", "ollama"} <= set(provider_mod.PROVIDERS)


def test_ollama_needs_no_key_and_posts_the_prompt(captured, monkeypatch):
    seen, body = captured
    body["body"] = json.dumps({"message": {"content": "  a plan  "},
                               "prompt_eval_count": 11}).encode()
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    prov = provider_mod.build("ollama", "llama3.1:8b")
    completion = prov.complete("survey the north field")

    assert completion.text == "a plan"
    assert completion.provider == "ollama"
    assert completion.model == "llama3.1:8b"
    assert seen["url"] == "http://localhost:11434/api/chat"
    assert seen["payload"]["stream"] is False
    assert seen["payload"]["messages"][-1]["content"] == "survey the north field"
    assert "authorization" not in seen["headers"]


def test_ollama_honours_a_configured_host(captured, monkeypatch):
    seen, body = captured
    body["body"] = json.dumps({"message": {"content": "x"}}).encode()
    monkeypatch.setenv("OLLAMA_HOST", "http://gpu-box:11434/")
    prov = provider_mod.build("ollama", "qwen2.5:14b")
    prov.complete("hello")
    assert seen["url"] == "http://gpu-box:11434/api/chat"


def test_openai_compatible_sends_a_bearer_token_from_the_named_variable(captured, monkeypatch):
    seen, body = captured
    body["body"] = json.dumps(
        {"choices": [{"message": {"content": "an intent"}}], "id": "cmpl-7"}).encode()
    monkeypatch.setenv("MY_KEY", "sk-secret")
    prov = provider_mod.build("openai-compat", "gpt-4o-mini", api_key_env="MY_KEY")
    completion = prov.complete("land now")

    assert completion.text == "an intent"
    assert completion.request_id == "cmpl-7"
    assert seen["url"] == "https://api.openai.com/v1/chat/completions"
    assert seen["headers"]["authorization"] == "Bearer sk-secret"
    assert seen["payload"]["model"] == "gpt-4o-mini"


def test_openai_compatible_points_at_any_base_url(captured, monkeypatch):
    seen, body = captured
    body["body"] = json.dumps({"choices": [{"message": {"content": "x"}}]}).encode()
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("GUARA_OPENAI_BASE_URL", "http://localhost:8000/v1/")
    provider_mod.build("openai-compat", "Qwen/Qwen2.5-7B-Instruct").complete("hi")
    assert seen["url"] == "http://localhost:8000/v1/chat/completions"


def test_a_missing_key_is_a_named_refusal_not_a_traceback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GUARA_OPENAI_BASE_URL", raising=False)
    with pytest.raises(provider_mod.ProviderError) as exc:
        provider_mod.build("openai-compat", "gpt-4o-mini")
    assert "OPENAI_API_KEY" in str(exc.value)


def test_a_transport_failure_raises_provider_error_never_a_scoring_outcome(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")

    def boom(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(provider_mod.urllib.request, "urlopen", boom)
    prov = provider_mod.build("openai-compat", "gpt-4o-mini")
    with pytest.raises(provider_mod.ProviderError):
        prov.complete("hello")


def test_a_reply_with_no_text_is_a_provider_error(captured, monkeypatch):
    _, body = captured
    body["body"] = json.dumps({"choices": []}).encode()
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    with pytest.raises(provider_mod.ProviderError):
        provider_mod.build("openai-compat", "gpt-4o-mini").complete("hello")
