import requests
from typing import List, Dict


def fetch_attractions(destination: str, limit: int = 6) -> List[Dict[str, str]]:
    """
    Fetch a small set of relevant attractions using the Wikipedia search API.

    This is a lightweight, public data source to seed the LLM with context.
    We intentionally keep this simple and avoid heavy scraping or parsing.
    """
    if not destination:
        return []
    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": f"{destination} notable attractions OR landmarks",
            "format": "json",
            "srlimit": str(limit),
        }
        headers = {"User-Agent": "WanderGenie/1.0 (LLM Portfolio)"}
        resp = requests.get("https://en.wikipedia.org/w/api.php", params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("query", {}).get("search", [])
        attractions: List[Dict[str, str]] = []
        for item in results:
            title = item.get("title", "")
            snippet = item.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", "")
            if title:
                attractions.append({"name": title, "desc": snippet})
        return attractions
    except Exception:
        return []