"""Kokoro TTS engine — bilingual (en/zh) wrapper around the kokoro package."""

from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger("vr_tts.kokoro_engine")

EN_REPO = "hexgrad/Kokoro-82M"             # v1.0 checkpoint, en (+ other langs)
ZH_REPO = "hexgrad/Kokoro-82M-v1.1-zh"     # v1.1 zh checkpoint, better Mandarin
SAMPLE_RATE = 24000                        # Kokoro's fixed output rate


def voice_lang(voice: str) -> str:
    """Mandarin voice ids (zf_*/zm_*) route to the zh pipeline; everything
    else goes to the en pipeline."""
    return "z" if voice.startswith(("zf_", "zm_")) else "a"


class KokoroEngine:
    def __init__(self, device: str | None = None):
        # device: None = let kokoro pick (cuda if available), else "cuda"/"cpu"
        self._device = device
        self._pipelines: dict[str, object] = {}

    def _pipeline(self, lang: str):
        if lang not in self._pipelines:
            from kokoro import KPipeline

            repo = ZH_REPO if lang == "z" else EN_REPO
            self._pipelines[lang] = KPipeline(lang_code=lang, repo_id=repo, device=self._device)
            log.info("kokoro pipeline ready: lang=%s repo=%s", lang, repo)
        return self._pipelines[lang]

    def synth(self, text: str, voice: str, speed: float = 1.0) -> tuple[np.ndarray, int]:
        """Synthesize text with the given voice; returns (int16 samples, rate)."""
        lang = voice_lang(voice)
        pipe = self._pipeline(lang)
        chunks = []
        for graphemes, phonemes, audio in pipe(text, voice=voice, speed=speed):
            if audio is not None:
                chunks.append(np.asarray(audio, dtype=np.float32))
        if not chunks:
            raise RuntimeError(f"kokoro produced no audio for voice {voice!r}")
        audio = np.clip(np.concatenate(chunks), -1.0, 1.0)
        return (audio * 32767.0).astype(np.int16), SAMPLE_RATE
