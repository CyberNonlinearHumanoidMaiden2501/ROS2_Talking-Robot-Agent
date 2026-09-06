"""brain_node — the conductor: turn-taking state machine, persona, barge-in.

Single-threaded executor and fully event-driven (no blocking waits — rclpy
forbids spin_until_future_complete from inside a spinning executor):

    LISTENING  -> (turn_end_ms of quiet) -> PROCESSING (async LLM + synth chain)
    PROCESSING -> (reply synthesized + Play goal sent) -> SPEAKING
    SPEAKING   -> (goal completed) -> LISTENING
               -> (VAD speech window during playback = barge-in)
                  cancel goal, record the reply as-spoken, LISTENING

Utterances arriving while PROCESSING/SPEAKING accumulate and form the next
turn (DDS queues them; ~1 msg/s is safe for depth 10).
"""

import json
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import String

from vr_brain.conversation import (ConversationStore, as_spoken_text,
                                   is_cjk, split_sentences)
from vr_brain.persona import build_system_prompt, load_persona
from vr_interfaces.action import Play
from vr_interfaces.msg import AudioChunk, SpeechSegment, Utterance
from vr_interfaces.srv import ChatFast, Synthesize

LISTENING = "LISTENING"
PROCESSING = "PROCESSING"
SPEAKING = "SPEAKING"


class BrainNode(Node):
    def __init__(self):
        super().__init__("brain_node")
        self.declare_parameter("persona_path", "")
        self.declare_parameter("turn_end_ms", 1500)
        self.declare_parameter("history_limit", 20)
        self.declare_parameter("voice_en", "af_heart")
        self.declare_parameter("voice_zh", "zf_001")
        self.declare_parameter("poll_ms", 100)

        self._persona = load_persona(self.get_parameter("persona_path").value)
        self._store = ConversationStore(limit=int(self.get_parameter("history_limit").value))
        self._turn_end_s = float(self.get_parameter("turn_end_ms").value) / 1000.0

        self._state = LISTENING
        self._turn_parts: list[str] = []
        self._last_utterance_lang = ""
        self._last_user_audio_time = time.time()

        # async reply pipeline state
        self._pending_sentences: list[str] = []
        self._segments: list[SpeechSegment] = []
        self._reply_segment_texts: list[str] = []
        self._reply_segment_counts: list[int] = []
        self._play_goal_handle = None
        self._play_result_future = None
        self._cancel_sent = False
        self._barge_in = False

        self._log_pub = self.create_publisher(String, "brain/log", 10)
        self.create_subscription(Utterance, "asr/utterance", self._on_utterance, 10)
        self.create_subscription(AudioChunk, "asr/utterance_audio", self._on_utterance_audio, 10)
        self._chat_cli = self.create_client(ChatFast, "llm/chat_fast")
        self._synth_cli = self.create_client(Synthesize, "tts/synthesize")
        self._play_cli = ActionClient(self, Play, "audio/play")
        self.create_timer(self.get_parameter("poll_ms").value / 1000.0, self._tick)

        self._log(f"brain_node ready (persona: {self._persona.get('name', '?')})")

    # ---- observability -----------------------------------------------------

    def _log(self, text: str):
        self._log_pub.publish(String(data=text))
        self.get_logger().info(text)

    # ---- subscriptions -----------------------------------------------------

    def _on_utterance(self, msg: Utterance):
        self._turn_parts.append(msg.text)
        if msg.language:
            self._last_utterance_lang = msg.language
        self._last_user_audio_time = time.time()
        self._log(f"utterance: {msg.text}")

    def _on_utterance_audio(self, msg: AudioChunk):
        self._last_user_audio_time = time.time()
        if self._state == SPEAKING:
            self._barge_in = True

    # ---- state machine -----------------------------------------------------

    def _tick(self):
        if self._state == SPEAKING:
            if self._barge_in and not self._cancel_sent:
                self._log("barge-in: canceling playback")
                self._play_goal_handle.cancel_goal_async()
                self._cancel_sent = True
            if self._play_result_future is not None and self._play_result_future.done():
                self._finish_speaking()
        elif self._state == LISTENING:
            if self._turn_parts and time.time() - self._last_user_audio_time >= self._turn_end_s:
                self._start_processing()

    def _start_processing(self):
        self._state = PROCESSING
        turn_text = " ".join(self._turn_parts)
        language = self._last_utterance_lang
        self._turn_parts = []
        self._last_utterance_lang = ""
        self._log(f"turn: {turn_text}")

        self._store.add("user", turn_text)
        system = build_system_prompt(self._persona, language)
        messages = [{"role": "system", "content": system}] + self._store.messages_for_llm()

        req = ChatFast.Request()
        req.payload_json = json.dumps({"messages": messages})
        if not self._chat_cli.wait_for_service(timeout_sec=5.0):
            self._log("ERROR: llm/chat_fast not available")
            self._speak_apology("Sorry, my brain is not reachable right now.")
            return
        future = self._chat_cli.call_async(req)
        future.add_done_callback(self._on_chat_result)

    def _on_chat_result(self, future):
        try:
            resp = future.result()
        except Exception as exc:
            self._log(f"ERROR: llm call failed: {exc}")
            self._speak_apology("Sorry, something went wrong on my side.")
            return
        if not resp.success or not resp.reply_text:
            self._log(f"ERROR: llm error: {resp.error}")
            self._speak_apology("Sorry, something went wrong on my side.")
            return

        reply = resp.reply_text.strip()
        self._log(f"reply: {reply}")
        sentences = split_sentences(reply)
        if not sentences:
            self._state = LISTENING
            return
        self._pending_sentences = sentences
        self._segments = []
        self._reply_segment_texts = []
        self._reply_segment_counts = []
        self._synth_next_sentence()

    def _synth_next_sentence(self):
        if not self._pending_sentences:
            self._send_play_goal()
            return
        sentence = self._pending_sentences[0]   # popped when its result arrives
        if not self._synth_cli.wait_for_service(timeout_sec=5.0):
            self._log("ERROR: tts/synthesize not available")
            self._speak_apology("Sorry, my voice is not reachable right now.")
            return
        sreq = Synthesize.Request()
        sreq.text = sentence
        sreq.voice = self._voice_for(sentence)
        future = self._synth_cli.call_async(sreq)
        future.add_done_callback(self._on_synth_result)

    def _on_synth_result(self, future):
        sentence = self._pending_sentences.pop(0)   # the sentence this result belongs to
        try:
            resp = future.result()
        except Exception as exc:
            self._log(f"ERROR: synthesis failed: {exc}")
            self._speak_apology("Sorry, my voice failed just now.")
            return
        if not resp.success:
            self._log(f"ERROR: synthesis failed: {resp.error}")
            self._speak_apology("Sorry, my voice failed just now.")
            return
        self._segments.append(SpeechSegment(samples=resp.samples))
        self._reply_segment_texts.append(sentence)
        self._reply_segment_counts.append(len(resp.samples))
        self._reply_sample_rate = resp.sample_rate
        self._synth_next_sentence()

    def _send_play_goal(self):
        goal = Play.Goal()
        goal.segments = self._segments
        goal.sample_rate = self._reply_sample_rate
        goal_future = self._play_cli.send_goal_async(goal)
        goal_future.add_done_callback(self._on_goal_sent)

    def _on_goal_sent(self, future):
        try:
            self._play_goal_handle = future.result()
        except Exception as exc:
            self._log(f"ERROR: play goal send failed: {exc}")
            self._state = LISTENING
            return
        if not self._play_goal_handle.accepted:
            self._log("ERROR: play goal rejected")
            self._state = LISTENING
            return
        self._cancel_sent = False
        self._barge_in = False
        self._play_result_future = self._play_goal_handle.get_result_async()
        self._state = SPEAKING
        self._log(f"speaking: {len(self._segments)} segments")

    def _finish_speaking(self):
        result = self._play_result_future.result().result
        if result.completed:
            self._store.add("assistant", " ".join(self._reply_segment_texts))
            self._log("speech completed")
        else:
            spoken, _ = as_spoken_text(
                self._reply_segment_texts, self._reply_segment_counts,
                result.completed, result.last_segment_index, result.samples_played_in_last)
            self._store.add("assistant", f"{spoken} (interrupted)")
            self._log(f"speech interrupted; recorded as-spoken: {spoken!r}")
        self._segments = []
        self._reply_segment_texts = []
        self._reply_segment_counts = []
        self._play_goal_handle = None
        self._play_result_future = None
        self._state = LISTENING

    def _speak_apology(self, text: str):
        """Speak a canned line (errors) through the normal synth + play path."""
        self._pending_sentences = [text]
        self._segments = []
        self._reply_segment_texts = []
        self._reply_segment_counts = []
        self._synth_next_sentence()

    def _voice_for(self, text: str) -> str:
        return self.get_parameter("voice_zh").value if is_cjk(text) \
            else self.get_parameter("voice_en").value


def main(args=None):
    rclpy.init(args=args)
    node = BrainNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
