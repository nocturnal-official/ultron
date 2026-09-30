"""Automate a real browser via Playwright: navigate, click, type, read, screenshot.

One persistent Chromium session runs in a background thread. First use launches it.
"""
import asyncio
import threading
from pathlib import Path

_session = None
_lock = threading.Lock()


class _Browser:
    def __init__(self):
        self._loop = None
        self._ready = threading.Event()
        self._pw = None
        self._ctx = None
        self._page = None
        threading.Thread(target=self._run, daemon=True, name="UltronBrowser").start()
        if not self._ready.wait(timeout=25):
            raise RuntimeError("Browser thread did not start.")

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._init())
        self._ready.set()
        self._loop.run_forever()

    async def _init(self):
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()

    def run(self, coro, timeout=60):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=timeout)

    async def _page_obj(self):
        if self._ctx is None:
            profile = str(Path.home() / ".ultron_browser")
            Path(profile).mkdir(parents=True, exist_ok=True)
            self._ctx = await self._pw.chromium.launch_persistent_context(
                profile, headless=False, no_viewport=True,
                args=["--start-maximized", "--disable-blink-features=AutomationControlled"])
            self._page = await self._ctx.new_page()
        if self._page is None or self._page.is_closed():
            self._page = await self._ctx.new_page()
        return self._page

    async def goto(self, url):
        if "://" not in url:
            url = "https://" + (url if "." in url else url + ".com")
        p = await self._page_obj()
        await p.goto(url, wait_until="domcontentloaded", timeout=30000)
        return f"Opened {p.url}"

    async def search(self, query, engine="google"):
        bases = {"google": "https://www.google.com/search?q=",
                 "bing": "https://www.bing.com/search?q=",
                 "duckduckgo": "https://duckduckgo.com/?q="}
        return await self.goto(bases.get(engine, bases["google"]) + query.replace(" ", "+"))

    async def click(self, description):
        p = await self._page_obj()
        for role in ("button", "link", "tab", "menuitem"):
            loc = p.get_by_role(role, name=description)
            if await loc.count():
                await loc.first.click(timeout=6000)
                return f"Clicked '{description}'."
        await p.get_by_text(description, exact=False).first.click(timeout=6000)
        return f"Clicked '{description}'."

    async def type_text(self, description, text):
        p = await self._page_obj()
        for loc in (p.get_by_placeholder(description, exact=False),
                    p.get_by_label(description, exact=False),
                    p.get_by_role("textbox", name=description),
                    p.get_by_role("searchbox")):
            if await loc.count():
                await loc.first.fill(text)
                return f"Typed into '{description}'."
        return f"Couldn't find a field for '{description}'."

    async def read(self):
        p = await self._page_obj()
        return (await p.inner_text("body"))[:6000]

    async def press(self, key):
        p = await self._page_obj()
        await p.keyboard.press(key)
        return f"Pressed {key}."

    async def screenshot(self):
        p = await self._page_obj()
        out = str(Path(__file__).resolve().parent.parent / "screenshots" / "browser.png")
        Path(out).parent.mkdir(exist_ok=True)
        await p.screenshot(path=out)
        return f"Saved {out}"

    async def close(self):
        if self._ctx:
            await self._ctx.close()
            self._ctx = self._page = None
        return "Browser closed."


def _get():
    global _session
    with _lock:
        if _session is None:
            _session = _Browser()
    return _session


def browser_control(action: str, url: str = "", query: str = "", engine: str = "google",
                    description: str = "", text: str = "", key: str = "Enter") -> str:
    a = (action or "").lower().strip()
    try:
        from playwright.async_api import async_playwright  # noqa: F401
    except ImportError:
        return "Playwright isn't installed. Run: pip install playwright && playwright install chromium"
    try:
        b = _get()
        if a == "go_to":
            return b.run(b.goto(url))
        if a == "search":
            return b.run(b.search(query, engine))
        if a == "click":
            return b.run(b.click(description or text))
        if a == "type":
            return b.run(b.type_text(description, text))
        if a in ("get_text", "read"):
            return b.run(b.read())
        if a == "press":
            return b.run(b.press(key))
        if a == "screenshot":
            return b.run(b.screenshot())
        if a == "close":
            return b.run(b.close())
        return f"Unknown browser action '{action}'. Try go_to, search, click, type, read, press, screenshot."
    except Exception as e:
        return f"Browser action '{action}' failed: {e}"
