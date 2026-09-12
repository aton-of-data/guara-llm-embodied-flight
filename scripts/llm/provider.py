#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Providers for the LLM evaluation harness (ADR 0013 decision 3).

One operation: prompt in, text out. A provider never sees the site model, never sees a plan
and never learns what the expected answer was; it is a text channel, so that adding one
cannot change a result. `mock` is a first-class provider with no key and no network, which is
what makes the harness itself testable (AC-30).

The credential is read from an environment variable whose *name* is recorded in the run
evidence; the value never enters a log, a prompt or a result file (ADR 0013 decision 7).
"""
from __future__ import annotations

import abc
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (ROOT, ROOT / "scripts" / "llm"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import envfile as envfile_mod  # noqa: E402


class ProviderError(RuntimeError):
    """The provider could not produce a completion. Never a scoring outcome."""


def is_capacity_error(exc: BaseException) -> bool:
    """True when Cursor refused a create because too many Cloud Agents are live."""
    msg = str(exc).lower()
    return "http 400" in msg and (
        "simultaneous" in msg or "limit for your current plan" in msg
        or "upgrade to ultra" in msg)


@dataclass
class Completion:
    text: str
    duration_ms: int
    provider: str
    model: str
    request_id: str = ""
    meta: dict = field(default_factory=dict)


class Provider(abc.ABC):
    name: str = "abstract"

    def __init__(self, model: str) -> None:
        self.model = model

    @abc.abstractmethod
    def complete(self, prompt: str) -> Completion:
        """Return the model's answer to `prompt`, or raise ProviderError."""


# ---------------------------------------------------------------------------------------
# mock
# ---------------------------------------------------------------------------------------

_SENSOR_WORDS = {
    "rgb": ("rgb", "photo", "foto", "ortomosaic", "orthomosaic"),
    "multispectral": ("multispectral", "multiespectral", "ndvi", "ndre"),
    "thermal": ("thermal", "térmic", "termic"),
}
_PRODUCT_WORDS = {
    "ndvi": ("ndvi",),
    "ndre": ("ndre",),
    "thermal_map": ("thermal map", "mapa térmico", "mapa termico"),
    "plant_count": ("count the plants", "conta as plantas", "plant count"),
    "photos": ("photos", "fotos"),
    "orthomosaic": ("orthomosaic", "ortomosaico", "ortomosaic"),
}
_FIELD_WORDS = {
    "north-3": ("north 3", "north three", "north-3", "north field", "campo norte",
                "north três"),
    "river-edge": ("river edge", "river-edge", "beira do rio", "riverbank"),
    "outside-fence": ("outside fence", "outside-fence", "fora da cerca", "milharal"),
}
_POI_WORDS = {
    "pivot-2": ("pivot 2", "pivot-2", "pivô 2", "pivo 2"),
    "tower-1": ("water tower", "tower", "caixa d'água", "caixa d'agua", "torre"),
}
_INSPECT_WORDS = ("check ", "inspect", "look at", "olhada", "checar", "inspeciona", "checa ")
_NUMBER_WORDS = {
    "one and a half": 1.5, "um centímetro e meio": 1.5, "half a": 0.5,
    "one": 1.0, "two": 2.0, "three": 3.0, "four": 4.0, "five": 5.0, "six": 6.0,
    "seven": 7.0, "eight": 8.0, "nine": 9.0, "ten": 10.0, "twelve": 12.0,
    "fifteen": 15.0, "twenty": 20.0,
    "um milímetro": 0.1, "one millimetre": 0.1, "one millimeter": 0.1,
    "dois": 2.0, "três": 3.0, "tres": 3.0, "quatro": 4.0, "cinco": 5.0, "seis": 6.0,
    "sete": 7.0, "oito": 8.0, "nove": 9.0, "dez": 10.0, "doze": 12.0, "quinze": 15.0,
    "trezentos": 300.0,
}


class MockProvider(Provider):
    """A rule-based stub, not a model.

    It exists to exercise the pipeline deterministically. It extracts the site objects it
    recognises by substring and emits an intent; when it recognises nothing it emits an error
    document, which the validator rejects. Its accuracy is not a result about anything, and
    the report labels it as a stub rather than as a model.
    """

    name = "mock"

    def __init__(self, model: str = "rule-based-stub/1") -> None:
        super().__init__(model)

    @staticmethod
    def _first(words: dict, text: str) -> str | None:
        for key, needles in words.items():
            if any(n in text for n in needles):
                return key
        return None

    @staticmethod
    def _gsd(text: str) -> float | None:
        digits = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:cm|cent[íi]met)", text)
        if digits:
            return float(digits.group(1).replace(",", "."))
        # Prefer the number word immediately before the unit: "north three, ... five
        # centimetres" must read five, not three.
        near = re.search(r"([a-zà-ú]+(?:\s+[a-zà-ú]+){0,3})\s+(?:cm|cent[íi]met\w*)", text)
        if near:
            phrase = near.group(1)
            for word, value in _NUMBER_WORDS.items():
                if phrase.endswith(word) or f" {word} " in f" {phrase} ":
                    return value
        for word, value in _NUMBER_WORDS.items():
            if word in text:
                return value
        return None

    def complete(self, prompt: str) -> Completion:
        started = time.monotonic()
        marker = "UTTERANCE:"
        utterance = prompt.split(marker, 1)[1].strip() if marker in prompt else prompt
        text = utterance.lower()

        field_id = self._first(_FIELD_WORDS, text)
        poi_id = self._first(_POI_WORDS, text)
        sensor = self._first(_SENSOR_WORDS, text)
        gsd = self._gsd(text)
        products = [p for p, needles in _PRODUCT_WORDS.items() if any(n in text for n in needles)]

        inspect = any(w in text for w in _INSPECT_WORDS) and poi_id is not None
        if inspect:
            body = {"intent": "inspect_point", "poi_id": poi_id}
        elif field_id is not None:
            body = {"intent": "survey", "field_id": field_id}
        else:
            answer = json.dumps({"error": "no known field or point of interest in the command"})
            return Completion(answer, int((time.monotonic() - started) * 1000), self.name,
                              self.model, request_id="mock")

        body["sensor"] = sensor or "rgb"
        body["gsd_cm"] = gsd if gsd is not None else 3.0
        body["overlap"] = {"front": 0.75, "side": 0.65}
        body["altitude_agl_m"] = None
        default_product = {"thermal": "thermal_map", "multispectral": "ndvi",
                           "rgb": "orthomosaic"}[body["sensor"]]
        body["deliver"] = products or [default_product]
        return Completion(json.dumps(body), int((time.monotonic() - started) * 1000),
                          self.name, self.model, request_id="mock")


# ---------------------------------------------------------------------------------------
# Cursor cloud agents
# ---------------------------------------------------------------------------------------

class CursorAgentProvider(Provider):
    """Cursor Cloud Agents API, used as a text channel (ADR 0013 instrument role).

    A no-repo agent is created by omitting both `repos` and `env`, so the agent has no
    repository, no branch and nothing to push: it answers and terminates. The run's
    `result` field is the final assistant reply, which is the only thing the harness
    reads. This is not a chat-completions API; it is the documented surface for Cursor
    models reached with `CURSOR_API_KEY`.

    Endpoints (https://cursor.com/docs/cloud-agent/api/endpoints):
      POST /v1/agents                       create an agent and enqueue its first run
      GET  /v1/agents/{id}/runs/{runId}     read run status and `result`
      GET  /v1/models                       list model ids for this key
    """

    name = "cursor-agent"
    base_url = "https://api.cursor.com"

    def __init__(self, model: str, api_key_env: str = "CURSOR_API_KEY",
                 timeout_s: float = 420.0, poll_s: float = 5.0) -> None:
        super().__init__(model)
        self.api_key_env = api_key_env
        self.timeout_s = timeout_s
        self.poll_s = poll_s
        envfile_mod.load_env_file()
        self._key = os.environ.get(api_key_env, "").strip()
        if not self._key:
            raise ProviderError(
                f"{api_key_env} is not set. Put it in .env (git-ignored); "
                f"the harness records only the variable name, never the value.")

    def _request(self, method: str, path: str, payload: dict | None = None,
                 timeout_s: float | None = None) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            f"{self.base_url}{path}", data=data, method=method,
            headers={"Authorization": f"Bearer {self._key}",
                     "Content-Type": "application/json",
                     "User-Agent": "guara-llm-eval/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=timeout_s or self.timeout_s) as resp:
                body = resp.read().decode()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:400]
            raise ProviderError(f"{method} {path} -> HTTP {e.code}: {detail}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            raise ProviderError(f"{method} {path} -> {e}") from None
        return json.loads(body) if body else {}

    def _delete_agent(self, agent_id: str) -> None:
        """Free a Cloud Agent slot. DELETE is documented as permanent; archive is the fallback."""
        if not agent_id:
            return
        try:
            self._request("DELETE", f"/v1/agents/{agent_id}", timeout_s=30.0)
            return
        except ProviderError:
            pass
        try:
            self._request("POST", f"/v1/agents/{agent_id}/archive", timeout_s=30.0)
        except ProviderError:
            pass

    @staticmethod
    def _run_payload(payload: dict) -> dict:
        run = payload.get("run") if isinstance(payload.get("run"), dict) else payload
        return run if isinstance(run, dict) else {}

    def reclaim(self) -> int:
        """Delete leftover `guara-llm-eval` agents so a new run is not blocked by the plan cap."""
        deleted = 0
        cursor = None
        for _ in range(20):
            path = "/v1/agents?limit=100&includeArchived=false"
            if cursor:
                path += f"&cursor={cursor}"
            payload = self._request("GET", path, timeout_s=30.0)
            items = payload.get("items") or []
            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get("name") != "guara-llm-eval":
                    continue
                ident = item.get("id")
                if ident:
                    self._delete_agent(str(ident))
                    deleted += 1
            cursor = payload.get("nextCursor")
            if not cursor:
                break
        return deleted

    def complete(self, prompt: str) -> Completion:
        started = time.monotonic()
        created = None
        last_err: ProviderError | None = None
        for attempt in range(8):
            try:
                created = self._request("POST", "/v1/agents", {
                    "prompt": {"text": prompt},
                    "model": {"id": self.model},
                    "name": "guara-llm-eval",
                })
                break
            except ProviderError as e:
                last_err = e
                if not is_capacity_error(e):
                    raise
                time.sleep(min(60.0, 8.0 * (attempt + 1)))
        else:
            raise last_err or ProviderError("Cloud Agent create retries exhausted")

        agent_id = created.get("agent", {}).get("id", "")
        run = self._run_payload(created)
        run_id = run.get("id", "")
        if not agent_id or not run_id:
            raise ProviderError(f"unexpected create response: {json.dumps(created)[:300]}")

        try:
            deadline = time.monotonic() + self.timeout_s
            text = None
            while time.monotonic() <= deadline:
                status = str(run.get("status", "")).upper()
                candidate = run.get("result")
                if isinstance(candidate, str) and candidate.strip():
                    text = candidate
                elif isinstance(candidate, dict):
                    for key in ("text", "result", "message", "content"):
                        val = candidate.get(key)
                        if isinstance(val, str) and val.strip():
                            text = val
                            break
                if status in {"ERROR", "CANCELLED", "EXPIRED"}:
                    raise ProviderError(f"run {run_id} ended as {run.get('status')}")
                if status == "FINISHED" and text is not None:
                    break
                time.sleep(self.poll_s)
                run = self._run_payload(
                    self._request("GET", f"/v1/agents/{agent_id}/runs/{run_id}"))
            else:
                raise ProviderError(
                    f"run {run_id} did not yield a text result within {self.timeout_s}s "
                    f"(status={run.get('status')!r}, keys={sorted(run.keys())})")
            return Completion(
                text=text,
                duration_ms=int((time.monotonic() - started) * 1000),
                provider=self.name,
                model=self.model,
                request_id=f"{agent_id}/{run_id}",
                meta={"api_duration_ms": run.get("durationMs"), "status": run.get("status")},
            )
        finally:
            self._delete_agent(agent_id)

    def available_models(self) -> list[str]:
        payload = self._request("GET", "/v1/models", timeout_s=30.0)
        models = payload.get("items", payload.get("models", []))
        ids: list[str] = []
        seen: set[str] = set()
        for item in models:
            ident = item if isinstance(item, str) else (item.get("id") if isinstance(item, dict) else None)
            if ident and ident not in seen:
                seen.add(ident)
                ids.append(str(ident))
        return ids


PROVIDERS = {"mock": MockProvider, "cursor-agent": CursorAgentProvider}


def build(name: str, model: str | None = None, **kwargs) -> Provider:
    if name not in PROVIDERS:
        raise ProviderError(f"unknown provider '{name}'; known: {sorted(PROVIDERS)}")
    cls = PROVIDERS[name]
    if name == "mock":
        return cls(model or "rule-based-stub/1")
    if not model:
        raise ProviderError(f"provider '{name}' needs an explicit --model")
    return cls(model, **kwargs)
