import re
import os
import requests

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CX      = os.environ.get("GOOGLE_CX", "")


def _clean(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def _overlap(sentence: str, snippet: str) -> float:
    sw = set(w for w in sentence.lower().split() if len(w) > 3)
    snw = set(snippet.lower().split())
    if not sw:
        return 0.0
    return len(sw & snw) / len(sw)


def check_wikipedia(sentences: list[str]) -> list[dict]:
    """Search key sentences against Russian + English Wikipedia."""
    candidates = [s for s in sentences if 7 <= len(s.split()) <= 35][:5]
    matches = []

    for sent in candidates:
        query = " ".join(sent.split()[:10])
        for lang in ("ru", "en"):
            try:
                r = requests.get(
                    f"https://{lang}.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "list":   "search",
                        "srsearch": query,
                        "format": "json",
                        "srlimit": 1,
                    },
                    timeout=4,
                )
                results = r.json().get("query", {}).get("search", [])
                if not results:
                    continue
                res     = results[0]
                snippet = _clean(res.get("snippet", ""))
                ov      = _overlap(sent, snippet)
                if ov >= 0.45:
                    title = res["title"]
                    url   = f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"
                    matches.append({
                        "sentence": sent[:90] + ("…" if len(sent) > 90 else ""),
                        "title":    title,
                        "url":      url,
                        "overlap":  round(ov * 100),
                        "source":   "Wikipedia",
                    })
                    break  # found in one lang, skip other
            except Exception:
                pass

    return matches


def check_google(sentences: list[str]) -> list[dict]:
    """Search sentences via Google Custom Search (requires env vars)."""
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        return []

    candidates = [s for s in sentences if 8 <= len(s.split()) <= 30][:3]
    matches = []

    for sent in candidates:
        query = " ".join(sent.split()[:12])
        try:
            r = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": GOOGLE_API_KEY,
                    "cx":  GOOGLE_CX,
                    "q":   f'"{query}"',
                    "num": 3,
                },
                timeout=5,
            )
            items = r.json().get("items", [])
            for item in items:
                snippet = _clean(item.get("snippet", ""))
                ov      = _overlap(sent, snippet)
                if ov >= 0.4:
                    matches.append({
                        "sentence": sent[:90] + ("…" if len(sent) > 90 else ""),
                        "title":    item.get("title", ""),
                        "url":      item.get("link", ""),
                        "overlap":  round(ov * 100),
                        "source":   "Google",
                    })
                    break
        except Exception:
            pass

    return matches
