# vocal-robot — Implementation Plan

Approved 2026-08-31. Status: **M0 complete** (commit `20f882d`).

## Architecture

Five logical nodes; models are stateless adapters, the brain owns all state:

- **capture_node + playback_node** (`vr_audio`) — mic sensor (publishes `/audio/raw` 16 kHz mono via timer-driven pull reads, ducks on `/audio/playing`) and speaker actuator (Play action with exact played-sample truncation reporting; timer-driven playback at 50 ms ticks). Both single-threaded executors, no threads or queues.
- **vad_node + asr_node** (`vr_asr`) — Silero VAD with utterance segmentation (always-on trigger; publishes `/asr/speech_state` and trimmed `/asr/utterance_audio` segments) feeding faster-whisper transcription (medium, GPU int8, synchronous callback; publishes `/asr/utterance`). No threads or queues in either node.
- **tts_node** (`vr_tts`) — engine behind a single `Synthesize` service (text → WAV). Default engine **Kokoro 0.9.4** (fast, bilingual en/zh voices). Engine is a swappable backend; Orpheus and GPT-SoVITS plug in later as milestones.
- **fast_llm_node + reasoning_llm_node** (`vr_llm`) — thin OpenAI-compatible adapters to DeepSeek (`deepseek-v4-flash` for chat, `deepseek-v4-pro` for reasoning). No state, no tool execution.
- **brain_node** (`vr_brain`) — the conductor: state machine, canonical conversation store, persona loader, tool registry + `ExecuteTool` service (models propose, brain validates/executes), escalation dispatch, barge-in, staleness handling.

## Behavior spec

- **Trigger:** always-on VAD; utterance ends after ~600 ms silence (min 250 ms speech to filter noise).
- **Fast path:** user turn → fast LLM (persona system prompt + history) → reply rendered to Kokoro sentences → spoken, pipelined (TTS of sentence N+1 while N plays).
- **Escalation:** fast model emits an `escalate(question)` tool call → brain speaks a short filler ("Hmm, let me think…") → dispatches `ReasoningTask` action on the reasoning node → final findings rendered into natural speech by the fast model (one voice, reasoning traces never spoken or stored in chat context).
- **During reasoning:** fast model is read-only (no tools, no new escalations — enforced by brain, not prompts) and answers user questions anchored to throttled `[PROGRESS]` markers parsed from the reasoning stream. In-flight task is a speculative computation: invalidating user input → cancel action (ROS2 cancel) and re-dispatch; late-stage results → fold into final rendering. Stale results are version-checked against the conversation.
- **Barge-in:** speech detected while speaking → cancel playback (Play action returns played-sample count → brain records the response *as spoken, marked interrupted*) → user's interruption transcribed and appended → regenerate.
- **Bilingual:** reply in the language the user speaks (persona rule); ASR auto-detects en/zh per utterance.
- **Cosplay:** persona.yaml = character card (name, traits, speech quirks, catchphrases, backstory); injected as system prompt into every call; fast model does all speaking so personality is consistent. **Voice cloning (M4):** GPT-SoVITS (primary; MIT, strong for anime-style en/zh/ja voices) or XTTS-v2 (fallback; CPML non-commercial license) behind the same Synthesize interface, driven by a 10–60 s clean voice sample. Personal use only — don't distribute or publish a cloned real actor's voice.

## Workspace layout

```
/home/phalanx/vocal-robot/
├── .gitignore         (venv, model weights, build/install/log, API key, samples)
├── scripts/           setup_env.sh (venv), install_sudo.sh (apt, run by you), download_models.sh, run_vocal_robot.sh
└── src/               vr_interfaces  vr_audio  vr_asr  vr_tts  vr_llm  vr_brain  vr_bringup
    └── vr_bringup/    config/ (per-node ROS parameter yamls + pipewire echo-cancel drop-in),
                       data/ (persona.yaml, tools.yaml — content files loaded by path),
                       launch/vocal_robot.launch.py
```

## Git

- Repo initialized at the project root, with repository-local identity explicitly set: `user.name = "Qingyu Geng"`, `user.email = "yutsin2501@gmail.com"` (`git config` scoped to this repo, not just global).
- **Every milestone ends with a commit** of that milestone's verified working state — M0 through M5 each get a descriptive commit (e.g., "M1: voice I/O — VAD+whisper ASR, Kokoro TTS, echo-cancel"). Fixes during a milestone are squashed into that milestone's commit so history reads milestone-by-milestone.
- `.gitignore` covers the venv, downloaded model weights, ROS2 `build/install/log`, the DeepSeek key, and voice samples (samples stored outside the repo or under a git-ignored path).

## Interfaces (vr_interfaces)

- `msg/AudioChunk`, `msg/SpeechSegment`, `msg/SpeechState`, `msg/Utterance`
- `srv/Synthesize` (text, voice, speed → wav bytes)
- `srv/ChatFast` (assembled payload → reply text + optional tool call)
- `srv/ExecuteTool` (tool_name, params → result JSON; brain-enforced approval policy per tool: auto/ask/deny)
- `action/Play` (goal: WAV segments; feedback: segment + sample offset; result: completed vs truncated-at-sample — powers barge-in truncation)
- `action/ReasoningTask` (goal: query + context snapshot + tool schema; feedback: progress_summary; result: findings JSON + context version)
- Topics: `/audio/raw`, `/asr/speech_state`, `/asr/utterance`, `/brain/log` (debug transcript)

## Milestones (each ends with a git commit)

**M0 — Toolchain & skeleton.** ✅ done — commit `20f882d`.
Install colcon/rosdep/ffmpeg/portaudio19-dev via `install_sudo.sh` (needs sudo). Venv via uv with `--system-site-packages` so it sees system ROS2 deps (lark) after sourcing `/opt/ros/jazzy/setup.bash` (PEP 668 forbids system pip). Git init + repo-local identity + `.gitignore` + initial commit; workspace skeleton; interfaces build. *Verified: colcon build passes, launch file starts all nodes as stubs.*

**M1 — Voice I/O.** ✅ implemented; owner physical tests pending (see TEST_REPORT.md).
Audio capture/playback (sounddevice via PipeWire "default" routing, mock mode for dev); Silero VAD + faster-whisper medium (CUDA int8) transcribing en/zh; Kokoro TTS (en repo + v1.1-zh repo, af_heart/zf_001); Play action with exact truncation reporting; duck mode. Dev-verified: VAD segmentation, TTS→ASR round-trip (en 1.00 / zh 0.81 similarity), playback truncation math, mock-mode full-stack launch. Remaining: owner confirms mic transcripts and speaker audio.

**M2 — Conversation core.** Brain state machine + fast LLM + persona.yaml + conversation store; always-on trigger; barge-in with as-spoken truncation recording; bilingual replies. *Verify: natural full-loop conversation with the persona; interrupt mid-sentence and confirm the context reflects what was actually heard.*

**M3 — Reasoning escalation.** Reasoning node + ReasoningTask action + progress markers + ExecuteTool; v1 digital tools: get_time, calculator, web search (DuckDuckGo, keyless); filler speech; read-only mode; cancel/restart and stale-result policy. *Verify: ask something needing thought/tools → filler → integrated final answer; interrupt mid-reasoning cleanly.*

**M4 — Cosplay voice.** Voice-cloning pipeline (GPT-SoVITS preferred) + swap `tts.engine` in config. Needs from you: the character's name/traits (for persona.yaml) and a clean voice sample. Orpheus evaluated as an expressive-TTS branch.

**M5 — Physical world prep.** Formalize the tool registry contract (JSON schema per tool; each future actuator = a ROS2 service/action that plugs into ExecuteTool); document the pattern; optional Gazebo/Isaac mock tool.

## DeepSeek integration notes

- OpenAI-compatible API; model IDs, base URL, max tokens in `llm.yaml` (defaults: `deepseek-v4-flash`, `deepseek-v4-pro`; verified against the /models endpoint — account also has `deepseek-v4-flash-vision-exp` for future camera tools).
- API key read at runtime from `/home/phalanx/deepseek-api-key` (env var override supported); gitignored, never committed.
- Reasoning progress: prompt asks the model to emit `[PROGRESS] …` lines; the node parses them from the stream and throttles to ≥2 s; falls back to a generic "still working" if none arrive.

## Risks & mitigations

- **Mic (IEC958-only) may not work** → smoke test is M1's first step; fallbacks: profile switch via wpctl, or alternate USB mic.
- **Echo breaks barge-in** → PipeWire echo-cancel enabled in M1; fallback duck mode, barge-in deferred until AEC is solid.
- **DeepSeek latency** → pipelined TTS per sentence + filler during reasoning; bounded max_tokens for the reasoning model.
- **Kokoro zh voice quality** → acceptable for v1; M4 cloning replaces the voice entirely.
- **No passwordless sudo** → all privileged steps shipped as scripts you run once.

## Open items from user (not blocking M0–M1)

1. Character name + traits for persona.yaml (I'll draft a faithful card from the name if you don't have one).
2. Voice sample for M4 (10–60 s, clean, single speaker).
3. ✅ Resolved — a new PDP Audio Device USB mic appeared and is verified capturing (2026-08-31); it is the system default source and `config/audio.yaml` now points at it.
