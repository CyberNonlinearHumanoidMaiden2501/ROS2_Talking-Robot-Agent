# vocal-robot

A bilingual (English/Chinese) voice agent built on ROS2 Jazzy that cosplays an
anime character. Local speech recognition and speech synthesis, cloud LLMs for
conversation (fast) and reasoning/tools (slow), with a ROS2 tool bus designed
to grow into physical-world actuators.

## Architecture

```
mic ──► audio_node ──► asr_node ──► brain_node ──► fast_llm_node   (deepseek-v4-flash)
                                      │   ▲            │
speaker ◄── audio_node ◄── tts_node ◄─┘   └── escalate ▼
                                          reasoning_llm_node (deepseek-v4-pro)
                                                  │
                                          ExecuteTool service (tools.yaml)
```

- **capture_node** (`vr_audio`): mic sensor — publishes `/audio/raw` (16 kHz
  mono blocks); ducks (mutes) while the robot speaks via `/audio/playing`.
- **playback_node** (`vr_audio`): speaker actuator — serves the `Play` action
  with exact truncation reporting (timer-driven playback, 50 ms ticks,
  single-threaded executor).
- **vad_node** (`vr_asr`): Silero VAD (always-on trigger) + utterance
  segmentation — publishes `/asr/speech_state` and `/asr/utterance_audio`.
- **asr_node** (`vr_asr`): faster-whisper (multilingual en/zh, GPU int8)
  transcribes segments from vad_node; publishes `/asr/utterance`.
- **tts_node** (`vr_tts`): single Synthesize interface; Kokoro by default,
  GPT-SoVITS/Orpheus as swappable engines (M4).
- **fast_llm_node / reasoning_llm_node** (`vr_llm`): stateless DeepSeek adapters.
- **brain_node** (`vr_brain`): the conductor — state machine, conversation store,
  persona, tool registry, barge-in, escalation.

## Milestones

Every milestone ends with a git commit.

| # | Milestone | Status |
|---|-----------|--------|
| M0 | Toolchain, repo, interfaces, stub nodes | done |
| M1 | Voice I/O: VAD + Whisper ASR + Kokoro TTS | implemented; owner tests pending |
| M2 | Conversation core: brain + fast LLM + persona + barge-in | pending |
| M3 | Reasoning escalation + digital tools | pending |
| M4 | Cosplay voice (GPT-SoVITS cloning) | pending |
| M5 | Physical-world tool registry contract | pending |

## Testing convention

Physical-interaction tests — anything using the microphone, speakers, audio
routing, or future hardware — are run by the project owner. The owner-run
test steps are documented in markdown in [TEST_REPORT.md](TEST_REPORT.md)
(no test scripts).

All other verification is automated and software-only: builds, unit tests,
interface checks, and file-based audio pipelines (e.g. TTS -> WAV -> ASR
round-trips on recorded or synthetic audio). Those never touch hardware.

## Setup

1. `bash scripts/install_sudo.sh`  (one-time, needs sudo)
2. `bash scripts/setup_env.sh`     (venv + Python deps)
3. `bash scripts/download_models.sh` (whisper medium + Kokoro weights)
4. `bash scripts/build.sh`         (colcon build)
5. `bash scripts/run_vocal_robot.sh`
