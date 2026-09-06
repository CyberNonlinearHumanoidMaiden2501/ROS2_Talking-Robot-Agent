"""Persona card -> system prompt for the fast LLM."""

from __future__ import annotations

import yaml


def load_persona(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def build_system_prompt(persona: dict, reply_language: str = "") -> str:
    lines = [
        f"You are {persona.get('name', 'Nova')}, an AI companion. Stay in character at all times.",
        f"Personality: {'; '.join(persona.get('personality', []))}",
        f"Speech style: {'; '.join(persona.get('speech_style', []))}",
    ]
    if persona.get("catchphrases"):
        lines.append(f"Catchphrases you may use: {'; '.join(persona['catchphrases'])}")
    if persona.get("backstory"):
        lines.append(f"Backstory: {persona['backstory']}")
    lines.append(
        "You are speaking out loud through a voice synthesizer: keep replies short, "
        "conversational and spoken-style. No markdown, no emoji, no lists."
    )
    if persona.get("reply_language", "follow-user") == "follow-user":
        if reply_language:
            lines.append(f"Reply in {reply_language}.")
        else:
            lines.append("Reply in the same language the user is speaking.")
    return "\n".join(lines)
