"""Write, edit, explain, optimize and run code with the configured brain."""
import re
import subprocess
import sys
from pathlib import Path

_DESKTOP = Path.home() / "Desktop"
_EXT = {"python": ".py", "javascript": ".js", "typescript": ".ts", "html": ".html",
        "css": ".css", "java": ".java", "cpp": ".cpp", "c": ".c", "bash": ".sh",
        "go": ".go", "rust": ".rs", "sql": ".sql"}
_RUN = {".py": [sys.executable], ".js": ["node"], ".sh": ["bash"], ".rb": ["ruby"], ".php": ["php"]}


def _clean(text: str) -> str:
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text.strip())
    return re.sub(r"\n?```$", "", text).strip()


def _save(path: Path, code: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")


def code_helper(action: str = "write", description: str = "", language: str = "python",
                output_path: str = "", file_path: str = "", args: str = "", timeout: int = 30) -> str:
    from ai_helper import complete_text
    a = (action or "write").lower().strip()
    lang = (language or "python").lower()
    try:
        if a == "write":
            if not description:
                return "Describe what the code should do."
            code = _clean(complete_text(
                f"Write clean, complete, working {lang} code for: {description}. "
                f"Output only the code, no markdown, no explanation."))
            out = Path(output_path).expanduser() if output_path else _DESKTOP / f"ultron_code{_EXT.get(lang, '.txt')}"
            if not out.is_absolute():
                out = _DESKTOP / out
            _save(out, code)
            preview = "\n".join(code.splitlines()[:12])
            return f"Wrote {out}\n\nPreview:\n{preview}"
        if a in ("edit", "explain", "optimize", "review", "document"):
            if not file_path or not Path(file_path).expanduser().is_file():
                return "Give an existing file_path."
            fp = Path(file_path).expanduser()
            content = fp.read_text(encoding="utf-8", errors="ignore")[:30000]
            if a == "explain" or a == "review":
                verb = "Explain what this code does" if a == "explain" else "Review this code for bugs and improvements"
                return complete_text(f"{verb}:\n\n```\n{content}\n```")
            verb = {"edit": f"Apply this change: {description}", "optimize": "Optimize this code",
                    "document": "Add clear comments/docstrings"}[a]
            new = _clean(complete_text(f"{verb}. Return only the complete updated code.\n\n```\n{content}\n```"))
            _save(fp, new)
            return f"Updated {fp.name}."
        if a == "run":
            fp = Path(file_path).expanduser()
            if not fp.is_file():
                return "Give an existing file_path to run."
            interp = _RUN.get(fp.suffix.lower())
            if not interp:
                return f"Don't know how to run {fp.suffix}."
            r = subprocess.run(interp + [str(fp)] + (args.split() if args else []),
                               capture_output=True, text=True, timeout=timeout, cwd=str(fp.parent))
            out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
            return f"Output:\n{out[:3000]}" if out.strip() else "Ran with no output."
        return f"Unknown code action '{action}'. Use write, edit, explain, optimize, run."
    except subprocess.TimeoutExpired:
        return f"Execution timed out after {timeout}s."
    except Exception as e:
        return f"code_helper failed: {e}"
