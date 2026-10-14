"""House hunter agent: a smolagent that answers questions about Zillow for-sale listings.

Listings are extracted from every *.html / *.htm file in agent/files/ (pages saved
from Zillow, either search-result pages or individual home detail pages).

Usage:
    export ANTHROPIC_API_KEY=...
    python agent/agent.py "Which 3-bedroom homes are listed under $500k?"
"""

import json
import os
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from smolagents import CodeAgent, LiteLLMModel, tool

FILES_DIR = Path(__file__).resolve().parent / "files"
MODEL_ID = os.environ.get("MODEL_ID", "anthropic/claude-sonnet-5-5")

def _walk(obj):
    """Yield every dict nested in obj, descending into JSON-encoded strings too
    (Zillow detail pages store property data as a JSON string in gdpClientCache)."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)
    elif isinstance(obj, str) and len(obj) > 50 and obj.lstrip()[:1] in "{[":
        try:
            yield from _walk(json.loads(obj))
        except ValueError:
            pass


def _first(d, *keys):
    for k in keys:
        if d.get(k) not in (None, ""):
            return d[k]
    return None


def _normalize(d):
    """Map a Zillow listing dict (search result or detail page) to a compact record."""
    info = d.get("hdpData", {}).get("homeInfo", {})
    addr = d.get("address")
    if isinstance(addr, dict):
        addr = ", ".join(
            str(addr[k]) for k in ("streetAddress", "city", "state", "zipcode") if addr.get(k)
        )
    record = {
        "zpid": str(_first(d, "zpid") or info.get("zpid") or ""),
        "address": addr or _first(d, "streetAddress") or info.get("streetAddress"),
        "price": _first(d, "unformattedPrice", "price") or info.get("price"),
        "beds": _first(d, "beds", "bedrooms") or info.get("bedrooms"),
        "baths": _first(d, "baths", "bathrooms") or info.get("bathrooms"),
        "sqft": _first(d, "area", "livingArea") or info.get("livingArea"),
        "lot_size": _first(d, "lotSize", "lotAreaValue") or info.get("lotAreaValue"),
        "home_type": _first(d, "homeType") or info.get("homeType"),
        "status": _first(d, "statusText", "homeStatus") or info.get("homeStatus"),
        "year_built": _first(d, "yearBuilt"),
        "days_on_zillow": _first(d, "daysOnZillow") or info.get("daysOnZillow"),
        "zestimate": _first(d, "zestimate") or info.get("zestimate"),
        "hoa_fee": _first(d, "monthlyHoaFee"),
        "broker": _first(d, "brokerName", "brokerageName"),
        "description": _first(d, "description"),
        "url": _first(d, "detailUrl", "hdpUrl", "url"),
    }
    if isinstance(record["url"], str) and record["url"].startswith("/"):
        record["url"] = "https://www.zillow.com" + record["url"]
    return {k: v for k, v in record.items() if v not in (None, "")}


def _from_json_scripts(soup):
    """Extract listings from __NEXT_DATA__ and other embedded JSON blobs."""
    listings = {}
    for script in soup.find_all("script", type=re.compile("json")):
        try:
            data = json.loads(script.string or "")
        except ValueError:
            continue
        for d in _walk(data):
            if "zpid" not in d or not ("address" in d or "streetAddress" in d):
                continue
            rec = _normalize(d)
            key = rec.get("zpid") or rec.get("address")
            # Keep the richest version when a home appears more than once.
            if key and len(rec) > len(listings.get(key, {})):
                listings[key] = rec
    return list(listings.values())


def _from_property_cards(soup):
    """Fallback: scrape the visible listing cards on a search-results page."""
    listings = []
    for card in soup.select('article[data-test="property-card"], article.property-card'):
        price = card.select_one('[data-test="property-card-price"]')
        addr = card.find("address")
        link = card.find("a", href=True)
        rec = {
            "address": addr.get_text(" ", strip=True) if addr else None,
            "price": price.get_text(strip=True) if price else None,
            "details": [li.get_text(" ", strip=True) for li in card.select("ul li")],
            "url": link["href"] if link else None,
        }
        listings.append({k: v for k, v in rec.items() if v})
    return listings


def extract_listings(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    return _from_json_scripts(soup) or _from_property_cards(soup)


@tool
def read_listings() -> str:
    """Reads every HTML file in the agent/files directory. The files are Zillow pages
    (search results or home detail pages) of homes currently for sale. Extracts the
    housing data from each page and returns a JSON string: a list of objects, each with
    "file" (the source filename) and "listings" (a list of homes with fields such as
    address, price, beds, baths, sqft, lot_size, home_type, status, year_built,
    days_on_zillow, zestimate, hoa_fee, broker, description, url). Fields that could not
    be found are omitted; price may be a number or a formatted string like "$450,000".
    If no structured data was found in a page, "text" holds the page's visible text instead.
    """
    results = []
    files = sorted(p for p in FILES_DIR.iterdir() if p.suffix.lower() in (".html", ".htm"))
    for path in files:
        try:
            html = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            results.append({"file": path.name, "error": str(e)})
            continue
        listings = extract_listings(html)
        if listings:
            results.append({"file": path.name, "listings": listings})
        else:
            text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
            results.append({"file": path.name, "text": text[:20000]})
    if not results:
        return json.dumps({"error": f"No HTML files found in {FILES_DIR}"})
    return json.dumps(results)


def main() -> None:
    question = " ".join(sys.argv[1:]) or "Summarize the homes currently listed for sale."
    agent = CodeAgent(
        tools=[read_listings],
        model=LiteLLMModel(model_id=MODEL_ID),
        additional_authorized_imports=["json", "re", "statistics"],
    )
    print(agent.run(question))


if __name__ == "__main__":
    main()
