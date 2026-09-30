"""Web search, weather and YouTube."""
import re
import subprocess
import sys
import webbrowser
from urllib.parse import quote_plus

import requests

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def _ddg(query, max_results=6, news=False):
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
    except ImportError:
        return []
    with DDGS() as d:
        gen = d.news(query, max_results=max_results) if news else d.text(query, max_results=max_results)
        return list(gen)


def web_search(query: str = "", mode: str = "search", items=None, aspect: str = "general") -> str:
    """mode: search | news | research | price | compare"""
    from ai_helper import complete_text, provider_available
    mode = (mode or "search").lower().strip()
    items = items or []
    if not query and not items:
        return "Give me something to search for."

    if mode == "compare" or items:
        results = {}
        for it in items or [query]:
            results[it] = _ddg(f"{it} {aspect}", 4)
        ctx = "\n".join(f"## {k}\n" + "\n".join(f"- {r.get('title','')}: {r.get('body','')}"
                        for r in v) for k, v in results.items())
        if provider_available():
            try:
                return complete_text(f"Compare {', '.join(results)} on {aspect}. "
                                     f"Use these search snippets:\n{ctx}\n\nGive a concise comparison with sources.")
            except Exception:
                pass
        return ctx or "No results."

    news = mode == "news"
    results = _ddg(query, 8 if news else 6, news=news)
    if not results:
        return f"No results for: {query}"
    snippets = "\n".join(
        f"{i}. {r.get('title','')} — {r.get('body','')} [{r.get('url') or r.get('href','')}]"
        for i, r in enumerate(results, 1))
    if provider_available():
        instruction = {
            "news": "Summarize the latest news below in 3-4 sentences, then list the sources.",
            "research": "Give a thorough, well-structured answer using the material below. Cite sources.",
            "price": "State the current price(s) found below and where from.",
        }.get(mode, "Answer the query using the material below, then list the sources used.")
        try:
            return complete_text(f"Query: {query}\n\nSearch results:\n{snippets}\n\n{instruction}")
        except Exception:
            pass
    return f"Results for {query}:\n{snippets}"


def weather(city: str = "", when: str = "today") -> str:
    from config import CFG
    city = (city or CFG.default_city).strip()
    if not city:
        return "Which city? (You can set DEFAULT_CITY in .env.)"
    try:
        r = requests.get(f"https://wttr.in/{quote_plus(city)}?format=j1", headers=_UA, timeout=15)
        r.raise_for_status()
        data = r.json()
        cur = data["current_condition"][0]
        today = data["weather"][0]
        desc = cur["weatherDesc"][0]["value"]
        return (f"{city}: {desc}, {cur['temp_C']}°C (feels {cur['FeelsLikeC']}°C), "
                f"humidity {cur['humidity']}%, wind {cur['windspeedKmph']} km/h. "
                f"Today {today['mintempC']}–{today['maxtempC']}°C.")
    except Exception as e:
        webbrowser.open(f"https://www.google.com/search?q={quote_plus('weather ' + city + ' ' + when)}")
        return f"Couldn't fetch live weather ({e}); opened a weather search for {city} instead."


def _open_url(url):
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", url])
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            webbrowser.open(url)
    except Exception:
        webbrowser.open(url)


def flights(origin: str, destination: str, date: str = "", return_date: str = "") -> str:
    """Open Google Flights pre-filled for the route (browsing/booking stays with the user)."""
    if not origin or not destination:
        return "I need both an origin and a destination."
    q = f"Flights from {origin} to {destination}"
    if date:
        q += f" on {date}"
    if return_date:
        q += f" returning {return_date}"
    _open_url(f"https://www.google.com/travel/flights?q={quote_plus(q)}")
    return f"Opened Google Flights for {origin} to {destination}{(' on ' + date) if date else ''}."


def youtube(action: str = "play", query: str = "", url: str = "") -> str:
    action = (action or "play").lower().strip()
    if action == "play":
        if not query:
            return "What should I play?"
        try:
            r = requests.get(f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp=EgIQAQ%3D%3D",
                             headers=_UA, timeout=10)
            ids = re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', r.text)
            if ids:
                _open_url(f"https://www.youtube.com/watch?v={ids[0]}")
                return f"Playing: {query}"
        except Exception:
            pass
        _open_url(f"https://www.youtube.com/results?search_query={quote_plus(query)}")
        return f"Opened YouTube search for: {query}"
    if action == "summarize":
        vid = re.search(r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})", url or "")
        if not vid:
            return "Give me a YouTube URL to summarize."
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            from ai_helper import complete_text
            parts = YouTubeTranscriptApi.get_transcript(vid.group(1), languages=["en", "hi"])
            text = " ".join(p["text"] for p in parts)[:40000]
            return complete_text(f"Summarize this YouTube transcript in a short overview plus 3-5 key points:\n\n{text}")
        except Exception as e:
            return f"Couldn't summarize (needs youtube-transcript-api and a transcript): {e}"
    return f"Unknown YouTube action '{action}'. Use play or summarize."
