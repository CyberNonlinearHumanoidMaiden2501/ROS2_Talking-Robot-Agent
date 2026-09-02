# M1 Test Report — Voice I/O (owner-run physical tests)

This report describes the physical tests for milestone M1. Please review the
system first, then run the tests in order. No scripts are needed — every step
is a command you can inspect and run yourself. Report results (pass/fail +
any log lines) back to the developer.

## What M1 built

| Component | Interface | Role |
|---|---|---|
| `audio_node` (`vr_audio`) | publishes `/audio/raw`; serves `audio/play` action | Owns mic/speaker. Captures 16 kHz mono in 32 ms blocks; plays PCM segments and reports exactly where playback stopped (used later for barge-in truncation). In **duck mode** (M1 default) capture is muted while the robot speaks. |
| `asr_node` (`vr_asr`) | publishes `/asr/speech_state`, `/asr/utterance` | Silero VAD (always-on trigger) + faster-whisper medium (bilingual en/zh, GPU int8). |
| `tts_node` (`vr_tts`) | serves `/tts/synthesize` | Kokoro TTS, en + zh pipelines (24 kHz output). |
| `say.py` | CLI | Synthesize + play one sentence via the ROS2 interfaces. |

```
   mic ─► audio_node ──/audio/raw──► asr_node ──/asr/utterance──► (brain, M2)
 speaker ◄─ audio_node ◄─Play─ say.py / brain ◄─/tts/synthesize─ tts_node
```

Node settings are ROS parameter files in `src/vr_bringup/config/`
(`audio_node.yaml`, `asr_node.yaml`, `tts_node.yaml`, `llm_nodes.yaml`),
loaded by the launch file; the persona and tool registry are data files in
`src/vr_bringup/data/`.

## Already verified by the developer (software-only, no hardware used)

- Build: `colcon build` green for all 7 packages.
- Playback truncation/feedback math: 4/4 unit checks pass.
- VAD segmentation on generated speech/silence files: pass.
- TTS→ASR round-trip (Kokoro → WAV → Whisper, en + zh): pass — Whisper
  re-recognizes both languages with high similarity.
- Full stack launches in **mock audio mode** (no mic/speaker opened).

What has *not* been exercised: real microphone capture and real speaker
playback. That is exactly what the tests below cover.

## Prerequisites

- `libportaudio2` installed ✅ (you did this).
- Models downloaded to the HF cache (whisper medium, Kokoro en/zh) — done via
  `scripts/download_models.sh` (uses `HF_ENDPOINT=https://hf-mirror.com`).
- One-time build already done; after any code change run `bash scripts/build.sh`.

## Launching the stack

```bash
cd ~/vocal-robot
bash scripts/run_vocal_robot.sh
```

You should see all six nodes start. `audio_node` logs the enumerated audio
devices and `asr_node` logs "whisper ready: medium on cuda/int8_float16".
Leave this terminal running; use a second terminal for the tests below.

## Test 1 — Microphone capture + ASR (bilingual)

Goal: your voice is captured from the PDP mic and transcribed in both languages.

In a second terminal:

```bash
cd ~/vocal-robot
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export PATH="$PWD/.venv/bin:$PATH"
ros2 topic echo /asr/utterance
```

1. Speak a clear English sentence (e.g. "Hello, this is a microphone test.")
   and then pause ~1 second.
2. Speak a clear Chinese sentence (e.g. "你好，这是麦克风测试。") and pause again.
3. Watch the terminal: each utterance appears with `language` (`en`/`zh`),
   `confidence`, and the transcribed `text`.

While speaking you can also watch `/asr/speech_state` flip to `is_speech: True`
(`ros2 topic echo /asr/speech_state`).

**Pass:** both utterances appear with correct text and language, confidence
roughly > 0.5. **Fail:** nothing appears, wrong language, or garbage text.

If nothing appears: check the `audio_node` log — it prints the device list on
startup. The input device is configured as `"default"` (the PDP mic should be
the system default source; verify in GNOME Settings → Sound → Input). If the
mic works in GNOME's own level meter but not here, report the `audio_node`
log output.

## Test 2 — Speaker playback (TTS)

Goal: the robot speaks audibly in both languages. In a second terminal:

```bash
cd ~/vocal-robot
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export PATH="$PWD/.venv/bin:$PATH"
python scripts/say.py "Hello, my name is Nova, and my voice is working."
python scripts/say.py "你好，我的名字叫诺瓦，我的语音功能正常。"
```

The second sentence auto-selects the Mandarin voice (CJK detection). Other
Kokoro voices can be tried with `--voice` (English: `af_bella`, `af_nova`;
Mandarin: `zf_001`..`zf_046`) and speed with `--speed 1.1`.

**Pass:** both sentences are audible, intelligible, at a comfortable volume,
each in the right language. **Fail:** silence, noise, or wrong language.

If you hear nothing: check GNOME Settings → Sound → Output (default sink is
the USB Audio device) and the volume. The `audio_node` opens the device named
`"default"`, which follows the system default sink.

## Test 3 (optional) — Echo-cancel setup (groundwork for M2 barge-in)

M1 ships in **duck mode**: capture is muted while the robot speaks, so the
robot cannot hear you over its own voice (no barge-in yet). Enabling
PipeWire's echo-cancel module prepares the audio path for M2. This restarts
your audio session — run it when convenient, not during Test 1/2.

```bash
mkdir -p ~/.config/pipewire/pipewire.conf.d
cp ~/vocal-robot/src/vr_bringup/config/pipewire/99-echo-cancel.conf ~/.config/pipewire/pipewire.conf.d/
systemctl --user restart pipewire pipewire-pulse
```

Then in GNOME Settings → Sound, set **Output** to "Echo-Cancel Sink" and
**Input** to "Echo-Cancel Source" (or: `wpctl status` and
`wpctl set-default <id>`). Verify normal audio still works (play a video,
check the mic meter).

**Rollback:**

```bash
rm ~/.config/pipewire/pipewire.conf.d/99-echo-cancel.conf
systemctl --user restart pipewire pipewire-pulse
```

**Pass:** audio still works with EC sink/source selected. (Actual echo
suppression is exercised in M2.) To use echo-cancel with the robot, change
`echo_mode: "duck"` to `echo_mode: "aec"` in
`src/vr_bringup/config/audio_node.yaml` — capture will then stay live while
the robot speaks.

## Reporting results

For each test: PASS/FAIL, plus any unexpected log lines from the
`audio_node`/`asr_node`/`tts_node` terminals. Include the transcription text
Whisper produced (Test 1) so we can tune VAD/ASR settings if needed.
