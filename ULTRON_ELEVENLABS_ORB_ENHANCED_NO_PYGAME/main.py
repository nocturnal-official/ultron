"""ULTRON - personal AI agent.

  python main.py             terminal / typed mode
  python main.py --voice    terminal + microphone + speech output
  python gui.py              futuristic graphical HUD
"""
import argparse
import os
import sys

from config import CFG

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.system("")

RED, DIM, BOLD, CYAN, YELLOW, RESET = "\033[91m", "\033[2m", "\033[1m", "\033[96m", "\033[93m", "\033[0m"

BANNER = rf"""{RED}{BOLD}
  _   _ _   _____ ____   ___  _   _
 | | | | | |_   _|  _ \ / _ \| \ | |
 | | | | |   | | | |_) | | | |  \| |
 | |_| | |___| | |  _ <| |_| | |\  |
  \___/|_____|_| |_| \_\\___/|_| \_|
{RESET}{DIM}  personal AI agent{RESET}
"""

HELP = f"""{CYAN}Commands:{RESET}
  /claude /chatgpt /local   switch AI brain
  /reset                    forget this conversation
  /confirm on|off           ask before messages, emails, deletes, control, unlocking
  /voice                    toggle voice
  /help                     this list
  /exit                     quit
"""

LABELS = {
    "send_whatsapp_message": "Send WhatsApp message",
    "send_discord_message": "Send Discord message",
    "send_email": "Send email",
    "phone_unlock": "Unlock the phone",
    "close_app": "Close app",
    "computer_control": "Control mouse/keyboard",
    "set_reminder": "Set a reminder",
    "send_message_ui": "Send message (via app)",
    "computer_setting": "Change a system setting",
    "file_op": "Delete a file",
}


def confirm(name: str, args: dict) -> bool:
    print(f"\n{YELLOW}{BOLD}>> {LABELS.get(name, name)}{RESET}")
    for k, v in args.items():
        text = str(v)
        if "\n" in text:
            text = "\n      " + text.replace("\n", "\n      ")
        print(f"{YELLOW}   {k}:{RESET} {text}")
    try:
        answer = input(f"{YELLOW}   Go ahead? [y/N]: {RESET}").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


def show_tool(name: str, args: dict):
    short = ", ".join(f"{k}={str(v)[:40]!r}" for k, v in args.items() if k not in ("body", "message"))
    print(f"{DIM}   [{name}] {short}{RESET}")


def main():
    parser = argparse.ArgumentParser(description="ULTRON personal AI agent")
    parser.add_argument("--voice", action="store_true", help="talk to Ultron with your microphone")
    parser.add_argument("--provider", choices=["claude", "chatgpt", "local"], help="override AI_PROVIDER")
    opts = parser.parse_args()

    from brain import Brain
    from voice import Voice

    print(BANNER)
    provider = {"claude": "anthropic", "chatgpt": "openai", "local": "ollama"}.get(opts.provider, CFG.provider)
    try:
        brain = Brain(provider, confirm=confirm, on_tool=show_tool)
    except Exception as e:
        print(f"{RED}{e}{RESET}\nCopy .env.example to .env and add your API key.")
        sys.exit(1)

    voice = None
    if opts.voice:
        try:
            voice = Voice()
        except Exception as e:
            print(f"{RED}Voice unavailable ({e}).{RESET}")

    print(f"{DIM}Brain: {brain.label}   Confirm actions: {'on' if CFG.confirm_actions else 'off'}"
          f"   Voice: {'on' if voice else 'off'}   (/help for commands){RESET}\n")
    greeting = "Online. What do you need?"
    print(f"{RED}{BOLD}ULTRON:{RESET} {greeting}\n")
    if voice:
        voice.speak(greeting)

    while True:
        try:
            if voice:
                text = voice.listen()
                if not text:
                    continue
                print(f"{CYAN}{BOLD}YOU:{RESET} {text}")
            else:
                text = input(f"{CYAN}{BOLD}YOU:{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{RED}ULTRON:{RESET} Going dark.")
            break

        if not text:
            continue
        cmd = text.lower()
        if cmd in ("/exit", "/quit", "exit", "quit"):
            print(f"{RED}ULTRON:{RESET} Going dark.")
            break
        if cmd == "/help":
            print(HELP)
            continue
        if cmd == "/reset":
            brain.reset()
            print(f"{DIM}Conversation cleared.{RESET}\n")
            continue
        if cmd in ("/claude", "/chatgpt", "/local"):
            prov = {"/claude": "anthropic", "/chatgpt": "openai", "/local": "ollama"}[cmd]
            try:
                brain = Brain(prov, confirm=confirm, on_tool=show_tool)
                print(f"{DIM}Switched to {brain.label}.{RESET}\n")
            except Exception as e:
                print(f"{RED}{e}{RESET}\n")
            continue
        if cmd.startswith("/confirm"):
            CFG.confirm_actions = not cmd.endswith("off")
            print(f"{DIM}Confirm actions: {'on' if CFG.confirm_actions else 'off'}{RESET}\n")
            continue
        if cmd == "/voice":
            if voice:
                voice.close()
                voice = None
            else:
                try:
                    voice = Voice()
                except Exception as e:
                    print(f"{RED}Voice unavailable: {e}{RESET}")
            print(f"{DIM}Voice: {'on' if voice else 'off'}{RESET}\n")
            continue

        reply = brain.ask(text)
        print(f"\n{RED}{BOLD}ULTRON:{RESET} {reply}\n")
        if voice and reply:
            voice.speak(reply)


if __name__ == "__main__":
    main()
