"""fast_llm_node — stateless DeepSeek adapter for the fast conversation model.

Serves ChatFast on llm/chat_fast: the brain assembles the full payload
(system prompt + history + new user turn), this node only calls the API and
returns the reply text. No tools in M2 (tool_call_json is always "{}").
"""

import json
import os
import time

import rclpy
from rclpy.node import Node

from vr_interfaces.srv import ChatFast


class FastLlmNode(Node):
    def __init__(self):
        super().__init__("fast_llm_node")
        self.declare_parameter("base_url", "https://api.deepseek.com")
        self.declare_parameter("api_key_file", "~/deepseek-api-key")
        self.declare_parameter("model", "deepseek-v4-flash")
        self.declare_parameter("max_tokens", 1024)
        self.declare_parameter("temperature", 0.8)
        self.declare_parameter("timeout_s", 60)

        from openai import OpenAI

        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            key_path = os.path.expanduser(self.get_parameter("api_key_file").value)
            try:
                with open(key_path) as f:
                    api_key = f.read().strip()
            except OSError as exc:
                raise RuntimeError(
                    f"no API key: set DEEPSEEK_API_KEY or provide {key_path} ({exc})")
        # The SDK defaults to HTTP/2, which needs the optional 'h2' package and
        # fails as a connection error without it; pin an explicit HTTP/1.1 client.
        import httpx

        http_client = httpx.Client(
            http2=False,
            timeout=httpx.Timeout(float(self.get_parameter("timeout_s").value)),
        )
        self._client = OpenAI(base_url=self.get_parameter("base_url").value,
                              api_key=api_key, http_client=http_client)
        self._model = self.get_parameter("model").value

        self._srv = self.create_service(ChatFast, "llm/chat_fast", self._on_chat)
        self.get_logger().info(f"fast_llm_node ready (model: {self._model})")

    def _on_chat(self, req, resp):
        try:
            payload = json.loads(req.payload_json)
        except json.JSONDecodeError as exc:
            resp.success = False
            resp.error = f"bad payload_json: {exc}"
            return resp

        messages = payload.get("messages", [])
        t0 = time.time()
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=int(payload.get("max_tokens", self.get_parameter("max_tokens").value)),
                temperature=float(payload.get("temperature", self.get_parameter("temperature").value)),
            )
        except Exception as exc:
            self.get_logger().error(f"chat failed: {exc}")
            resp.success = False
            resp.error = str(exc)
            return resp

        content = completion.choices[0].message.content or ""
        self.get_logger().info(f"chat ok: {len(messages)} msgs -> {len(content)} chars "
                               f"in {time.time() - t0:.1f}s")
        resp.reply_text = content
        resp.tool_call_json = "{}"
        resp.success = True
        return resp


def main(args=None):
    rclpy.init(args=args)
    node = FastLlmNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
