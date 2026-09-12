# SPDX-License-Identifier: Apache-2.0
"""Space Mission Intent parsing (M16 / AC-50). Same contract as mission.compiler.intent.

The caller is an untrusted language model. This module raises SpaceIntentError or
returns a validated SpaceIntent. It never emits an F´ command, an Fpy directive or
an actuator name (ADR 0013 decision 2, risk RS-6).
"""
from __future__ import annotations

import functools
import hashlib
import json
import pathlib
from dataclasses import dataclass

import jsonschema

SCHEMA_FILE = pathlib.Path(__file__).resolve().parent / "schema/space_intent.schema.json"

STOP_CLASS = ("abort", "safe_mode")
NOT_COMPILABLE = STOP_CLASS + ("status",)
MAX_MODEL_OUTPUT_BYTES = 64 * 1024


class SpaceIntentError(Exception):
    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f"{code}: {reason}")
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class SpaceIntent:
    intent: str
    utterance_hash: str
    boresight_id: str | None = None
    target_id: str | None = None
    hold_s: float | None = None
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


def parse(raw: dict) -> SpaceIntent:
    if not isinstance(raw, dict):
        raise SpaceIntentError("schema", f"intent must be a JSON object, got {type(raw).__name__}")
    try:
        jsonschema.validate(raw, schema(), cls=jsonschema.Draft202012Validator)
    except jsonschema.ValidationError as e:
        path = "/".join(str(p) for p in e.absolute_path) or "intent"
        raise SpaceIntentError("schema", f"{path}: {e.message}") from None
    except jsonschema.SchemaError as e:  # pragma: no cover
        raise SpaceIntentError("schema", f"schema file is invalid: {e.message}") from None
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    return SpaceIntent(
        intent=raw["intent"],
        utterance_hash=raw["utterance_hash"],
        boresight_id=raw.get("boresight_id"),
        target_id=raw.get("target_id"),
        hold_s=raw.get("hold_s"),
        canonical=canonical,
    )


def _extract_json_object(text: str) -> str:
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
    raise SpaceIntentError("not_json", "no balanced JSON object in model output")


def parse_model_output(raw: str, utterance_hash: str | None = None) -> SpaceIntent:
    if not isinstance(raw, str):
        raise SpaceIntentError("not_json", f"model output must be text, got {type(raw).__name__}")
    if len(raw.encode("utf-8", errors="replace")) > MAX_MODEL_OUTPUT_BYTES:
        raise SpaceIntentError("not_json", "model output exceeds the accepted size")
    text = raw.strip()
    if not text:
        raise SpaceIntentError("not_json", "model returned nothing")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        obj = None
    if not isinstance(obj, dict):
        try:
            obj = json.loads(_extract_json_object(text))
        except json.JSONDecodeError as e:
            raise SpaceIntentError("not_json", f"malformed JSON object: {e.msg}") from None
        if not isinstance(obj, dict):
            raise SpaceIntentError("not_json", "recovered value is not a JSON object")
    if utterance_hash is not None:
        obj = dict(obj)
        obj["utterance_hash"] = utterance_hash
    return parse(obj)
