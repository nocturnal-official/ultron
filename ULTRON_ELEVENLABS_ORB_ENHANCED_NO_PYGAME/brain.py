"""The AI brain: runs a tool-using conversation on Claude (Anthropic) or ChatGPT (OpenAI)."""
import json
import platform
from datetime import datetime

from config import CFG
from tools import anthropic_tools, execute_tool, load_contacts, openai_tools

MAX_TOOL_ROUNDS = 15
MAX_HISTORY = 40


def system_prompt() -> str:
    os_name = {"Darwin": "macOS"}.get(platform.system(), platform.system())
    contacts = ", ".join(sorted(load_contacts().keys())) or "none saved yet"
    user = f"The user's name is {CFG.user_name}. " if CFG.user_name else ""
    try:
        from actions.memory import memory_for_prompt
        mem = memory_for_prompt()
    except Exception:
        mem = ""
    mem_block = ("\n\n" + mem) if mem else ""
    return f"""You are ULTRON, a personal AI agent running on the user's {os_name} computer.{mem_block}
{user}Current date/time: {datetime.now():%A %d %B %Y, %I:%M %p}.

Personality: calm, confident, a little theatrical and dry-witted, like a supremely capable machine
intelligence. Keep it short: one or two lines of flair at most, then get the job done.
You are loyal to the user and always helpful and honest.

How you work:
- Use your tools to actually do things: search the web, read pages, open apps and websites,
  send WhatsApp/Discord messages and emails, read the inbox, and control the USB-connected Android phone.
- For facts that may have changed (news, prices, people, scores), search before answering, and
  mention where the information came from.
- When asked to write an email, write a complete, polished email. If the user only asked you to
  draft it, show the draft and don't send it. Send only when they asked to send.
- Saved contacts: {contacts}. If a person isn't saved and you need their number/address/ID, ask.
- Never claim you did something unless the tool result says ok=true. If a tool fails, say what
  went wrong and how to fix it in one or two sentences.
- If the user declines an action, accept it and don't try again.
- Replies are shown in a terminal and may be spoken aloud: plain text, no markdown tables."""


class Brain:
    def __init__(self, provider: str = None, confirm=None, on_tool=None):
        self.provider = provider or CFG.provider
        self.confirm = confirm
        self.on_tool = on_tool or (lambda name, args: None)
        self.messages = []
        if self.provider == "anthropic":
            if not CFG.anthropic_api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is missing from .env")
            import anthropic
            self.client = anthropic.Anthropic(api_key=CFG.anthropic_api_key)
            self.model = CFG.anthropic_model
        elif self.provider == "openai":
            if not CFG.openai_api_key:
                raise RuntimeError("OPENAI_API_KEY is missing from .env")
            import openai
            self.client = openai.OpenAI(api_key=CFG.openai_api_key)
            self.model = CFG.openai_model
        elif self.provider == "ollama":
            # Local model via an OpenAI-compatible endpoint (Ollama or LM Studio).
            import openai
            self.client = openai.OpenAI(api_key="ollama", base_url=f"{CFG.ollama_url}/v1")
            self.model = CFG.ollama_model
        else:
            raise RuntimeError("No AI provider configured. Put ANTHROPIC_API_KEY or OPENAI_API_KEY "
                               "in .env, or set AI_PROVIDER=ollama for a local model.")

    @property
    def label(self) -> str:
        kind = {"anthropic": "Claude", "openai": "ChatGPT", "ollama": "Local"}[self.provider]
        return f"{kind} ({self.model})"

    def reset(self):
        self.messages = []

    def _run_tool(self, name, args):
        self.on_tool(name, args)
        return execute_tool(name, args, self.confirm)

    def _trim(self):
        """Keep history short without separating a tool call from its result."""
        if len(self.messages) <= MAX_HISTORY:
            return
        msgs = self.messages[-MAX_HISTORY:]
        while msgs and not (msgs[0]["role"] == "user" and isinstance(msgs[0]["content"], str)):
            msgs.pop(0)
        self.messages = msgs

    def ask(self, text: str) -> str:
        self._trim()
        self.messages.append({"role": "user", "content": text})
        try:
            if self.provider == "anthropic":
                return self._ask_anthropic()
            return self._ask_openai()
        except Exception as e:
            # Roll back to a clean state so the next turn isn't broken by a half-finished exchange
            while self.messages and not (self.messages[-1]["role"] == "user"
                                         and isinstance(self.messages[-1]["content"], str)):
                self.messages.pop()
            if self.messages:
                self.messages.pop()
            return f"[Brain error] {type(e).__name__}: {e}"

    # ---------------------------------------------------------------- Claude
    def _ask_anthropic(self) -> str:
        tools = anthropic_tools()
        for _ in range(MAX_TOOL_ROUNDS):
            resp = self.client.messages.create(
                model=self.model, max_tokens=4096, system=system_prompt(),
                tools=tools, messages=self.messages)
            self.messages.append({"role": "assistant", "content": resp.content})
            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            if not tool_uses:
                return "".join(b.text for b in resp.content if b.type == "text").strip()
            results = [{"type": "tool_result", "tool_use_id": b.id,
                        "content": self._run_tool(b.name, dict(b.input or {}))} for b in tool_uses]
            self.messages.append({"role": "user", "content": results})
        return "I've hit my step limit for this request. Tell me to continue if you want me to keep going."

    # ---------------------------------------------------------------- ChatGPT
    def _ask_openai(self) -> str:
        tools = openai_tools()
        for _ in range(MAX_TOOL_ROUNDS):
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_prompt()}] + self.messages,
                tools=tools)
            msg = resp.choices[0].message
            calls = msg.tool_calls or []
            entry = {"role": "assistant", "content": msg.content or ""}
            if calls:
                entry["tool_calls"] = [{"id": c.id, "type": "function",
                                        "function": {"name": c.function.name,
                                                     "arguments": c.function.arguments or "{}"}}
                                       for c in calls]
            self.messages.append(entry)
            if not calls:
                return (msg.content or "").strip()
            for c in calls:
                try:
                    args = json.loads(c.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                self.messages.append({"role": "tool", "tool_call_id": c.id,
                                      "content": self._run_tool(c.function.name, args)})
        return "I've hit my step limit for this request. Tell me to continue if you want me to keep going."
