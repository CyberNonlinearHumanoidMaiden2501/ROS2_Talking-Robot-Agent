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

- **audio_node** (`vr_audio`): owns mic/speaker hardware; reports exact playback
  progress so interruptions truncate correctly; echo-cancel/duck logic.
- **asr_node** (`vr_asr`): Silero VAD (always-on trigger) + faster-whisper
  (multilingual en/zh, GPU int8).
- **tts_node** (`vr_tts`): single Synthesize interface; Kokoro by default,
  GPT-SoVITS/Orpheus as swappable engines (M4).
- **fast_llm_node / reasoning_llm_node** (`vr_llm`): stateless DeepSeek adapters.
- **brain_node** (`vr_brain`): the conductor — state machine, conversation store,
  persona, tool registry, barge-in, escalation.

## Milestones

Every milestone ends with a git commit.

| # | Milestone | Status |
|---|-----------|--------|
| M0 | Toolchain, repo, interfaces, stub nodes | in progress |
| M1 | Voice I/O: VAD + Whisper ASR + Kokoro TTS | pending |
| M2 | Conversation core: brain + fast LLM + persona + barge-in | pending |
| M3 | Reasoning escalation + digital tools | pending |
| M4 | Cosplay voice (GPT-SoVITS cloning) | pending |
| M5 | Physical-world tool registry contract | pending |

## Setup

1. `bash scripts/install_sudo.sh`  (one-time, needs sudo)
2. `bash scripts/setup_env.sh`     (venv + Python deps)
3. `bash scripts/build.sh`         (colcon build)
4. `bash scripts/run_vocal_robot.sh`
