# SPDX-License-Identifier: Apache-2.0
"""Keyword grammar for the stop class, matched before any model is consulted.

`abort`, `land_now` and `return_home` map straight to platform modes and must never depend
on a model being reachable, correct or fast (LLM-EMBODIMENT.md §5.2, ADR 0013 decision 6).
This module is therefore the *first* thing the pipeline runs on a transcription, and if it
matches, no request is made.

Bias. The grammar is deliberately over-triggering: a false stop costs a flight, a missed stop
can cost an aircraft. One consequence is visible in the corpus — an adversarial utterance
that merely *mentions* aborting ("disable the abort keyword") is resolved as a stop and never
reaches the model. That is the intended direction of the error, and the evaluation reports
how many cases were resolved this way rather than hiding it.

Patterns are phrase-level, not word-level, precisely so that ordinary speech containing the
words does not fire: "we can land on fumes" is not a landing command.
"""
from __future__ import annotations

import re

#: (verb, compiled pattern) in match order. Patterns are matched case-insensitively against
#: the transcription with accents preserved.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # --- English -------------------------------------------------------------------
    ("abort", re.compile(r"\babort\b", re.I)),
    ("abort", re.compile(r"\bstop\s+(everything|now|the\s+mission|the\s+flight)\b", re.I)),
    ("abort", re.compile(r"^\s*stop\b", re.I)),
    ("abort", re.compile(r"\bcancel\s+the\s+(mission|flight)\b", re.I)),
    ("land_now", re.compile(r"\bland\s+(now|immediately|here|right\s+(now|here|there))\b", re.I)),
    ("land_now", re.compile(r"\bemergency\s+land(ing)?\b", re.I)),
    ("land_now", re.compile(r"\bput\s+it\s+down\s+(now|here)\b", re.I)),
    ("return_home", re.compile(r"\breturn\s+(to\s+launch|home|to\s+base)\b", re.I)),
    ("return_home", re.compile(r"\b(come|go)\s+(home|back\s+home)\b", re.I)),
    ("return_home", re.compile(r"\brtl\b", re.I)),
    # --- Portuguese (pt-BR) --------------------------------------------------------
    ("abort", re.compile(r"\babort(a|ar|e)\b", re.I)),
    ("abort", re.compile(r"\bcancela\s+(a\s+)?miss[ãa]o\b", re.I)),
    ("abort", re.compile(r"\bpara\s+tudo\b", re.I)),
    ("abort", re.compile(r"^\s*par(a|e)\b", re.I)),
    ("land_now", re.compile(r"\bpous(a|e)\s+(agora|j[áa]|aqui|imediatamente)\b", re.I)),
    ("land_now", re.compile(r"\bpousa[rg]?\s+de\s+emerg[êe]ncia\b", re.I)),
    ("return_home", re.compile(r"\bvolt(a|e)\s+(pra|para|pro|p\/)\s*(casa|base)\b", re.I)),
    ("return_home", re.compile(r"\bretorn(a|e|ar)\b", re.I)),
]

#: Precedence when several verbs match: the most authoritative wins.
_RANK = {"abort": 3, "land_now": 2, "return_home": 1}


def match(utterance: str) -> str | None:
    """Return the stop verb this utterance commands, or None.

    When more than one verb matches, the highest-ranked one is returned, so
    "land now, no, abort" aborts.
    """
    if not isinstance(utterance, str):
        return None
    hits = {verb for verb, pattern in _PATTERNS if pattern.search(utterance)}
    if not hits:
        return None
    return max(hits, key=lambda v: _RANK[v])
