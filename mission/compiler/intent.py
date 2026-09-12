# SPDX-License-Identifier: Apache-2.0
"""Mission Intent parsing and validation (AC-23).

The caller of `parse_model_output` is an untrusted language model, so the contract is:
whatever the bytes are, this module raises `IntentError` or returns a validated `Intent`.
It never raises anything else, never partially accepts, and never repairs an intent's
meaning — recovering a JSON object out of a chatty answer is the only leniency allowed, and
it is lexical, not semantic.
"""
from __future__ import annotations

import functools
import hashlib
import json
import pathlib
from dataclasses import dataclass

import jsonschema

SCHEMA_FILE = pathlib.Path(__file__).resolve().parents[1] / "schema/mission_intent.schema.json"

#: Intents that must never depend on a model being reachable, correct or fast
#: (LLM-EMBODIMENT.md §5.2, ADR 0013 decision 6).
STOP_CLASS = ("abort", "land_now", "return_home")

#: Intents that produce no plan at all.
NOT_COMPILABLE = STOP_CLASS + ("status",)

MAX_MODEL_OUTPUT_BYTES = 64 * 1024


class IntentError(Exception):
    """Rejection of a candidate intent, with a machine-readable code and a reason."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f"{code}: {reason}")
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class Intent:
    intent: str
    utterance_hash: str
    field_id: str | None = None
    poi_id: str | None = None
    sensor: str | None = None
    gsd_cm: float | None = None
    overlap_front: float | None = None
    overlap_side: float | None = None
    altitude_agl_m: float | None = None
    deliver: tuple[str, ...] = ()
    canonical: str = ""

    @property
    def is_stop_class(self) -> bool:
        return self.intent in STOP_CLASS

    @property
    def is_compilable(self) -> bool:
        return self.intent not in NOT_COMPILABLE

    def hash(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical.encode()).hexdigest()


@functools.lru_cache(maxsize=1)
def schema() -> dict:
    return json.loads(SCHEMA_FILE.read_text())


def parse(raw: dict) -> Intent:
    """Validate a candidate intent object against the published schema."""
    if not isinstance(raw, dict):
        raise IntentError("schema", f"intent must be a JSON object, got {type(raw).__name__}")
    try:
        jsonschema.validate(raw, schema(), cls=jsonschema.Draft202012Validator)
    except jsonschema.ValidationError as e:
        path = "/".join(str(p) for p in e.absolute_path) or "intent"
        raise IntentError("schema", f"{path}: {e.message}") from None
    except jsonschema.SchemaError as e:  # pragma: no cover - guards a corrupted schema file
        raise IntentError("schema", f"schema file is invalid: {e.message}") from None

    overlap = raw.get("overlap") or {}
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    return Intent(
        intent=raw["intent"],
        utterance_hash=raw["utterance_hash"],
        field_id=raw.get("field_id"),
        poi_id=raw.get("poi_id"),
        sensor=raw.get("sensor"),
        gsd_cm=raw.get("gsd_cm"),
        overlap_front=overlap.get("front"),
        overlap_side=overlap.get("side"),
        altitude_agl_m=raw.get("altitude_agl_m"),
        deliver=tuple(raw.get("deliver", ())),
        canonical=canonical,
    )


def _extract_json_object(text: str) -> str:
    """Return the first balanced top-level {...} block, ignoring braces inside strings."""
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    raise IntentError("not_json", "no balanced JSON object in model output")


def parse_model_output(raw: str, utterance_hash: str | None = None) -> Intent:
    """Parse whatever a model returned. Lexical recovery only; no semantic repair.

    `utterance_hash` is provenance, not content: it is produced by whatever recorded the
    command, so when the caller supplies one it is injected if the model omitted it and it
    *overrides* any value the model invented. Nothing else in the document is ever written by
    this function.
    """
    if not isinstance(raw, str):
        raise IntentError("not_json", f"model output must be text, got {type(raw).__name__}")
    if len(raw.encode("utf-8", errors="replace")) > MAX_MODEL_OUTPUT_BYTES:
        raise IntentError("not_json", "model output exceeds the accepted size")
    text = raw.strip()
    if not text:
        raise IntentError("not_json", "model returned nothing")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        obj = None
    if not isinstance(obj, dict):
        try:
            obj = json.loads(_extract_json_object(text))
        except json.JSONDecodeError as e:
            raise IntentError("not_json", f"malformed JSON object: {e.msg}") from None
        if not isinstance(obj, dict):
            raise IntentError("not_json", "recovered value is not a JSON object")
    if utterance_hash is not None and isinstance(obj, dict):
        obj = dict(obj)
        obj["utterance_hash"] = utterance_hash
    return parse(obj)


def utterance_hash(utterance: str) -> str:
    return "sha256:" + hashlib.sha256(utterance.encode()).hexdigest()
