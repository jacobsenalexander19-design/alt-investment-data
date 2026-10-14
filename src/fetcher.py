"""SEC EDGAR Form D fetcher for alternative investment offerings."""

import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, List
from dotenv import load_dotenv
import requests

# Load environment variables from .env
load_dotenv()

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "DataExplorer research@example.com")
# Request 100 entries from the SEC feed so we can filter at least 30 pure Form D filings
FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=D&count=100&output=atom"


def get_sec_session() -> requests.Session:
    """Create a configured session with required SEC User-Agent headers."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": SEC_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "Host": "www.sec.gov",
        }
    )
    return session


def fetch_recent_form_d_entries(limit: int = 30) -> List[Dict[str, Any]]:
    """Fetch the latest Form D filings from the SEC EDGAR real-time feed."""
    session = get_sec_session()
    response = session.get(FEED_URL, timeout=10)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    namespaces = {"atom": "http://www.w3.org/2005/Atom"}

    filings: List[Dict[str, Any]] = []

    for entry in root.findall("atom:entry", namespaces):
        title = entry.findtext("atom:title", default="", namespaces=namespaces).strip()

        # Keep only genuine Form D and Form D/A (amendment) filings
        if not (title.startswith("D -") or title.startswith("D/A -")):
            continue

        link_elem = entry.find("atom:link", namespaces=namespaces)
        filing_url = link_elem.attrib.get("href", "") if link_elem is not None else ""
        summary = entry.findtext("atom:summary", default="", namespaces=namespaces)
        updated = entry.findtext("atom:updated", default="", namespaces=namespaces)

        filings.append(
            {
                "title": title,
                "url": filing_url.strip(),
                "summary": summary.strip(),
                "updated_at": updated.strip(),
            }
        )

        if len(filings) >= limit:
            break

    return filings


if __name__ == "__main__":
    entries = fetch_recent_form_d_entries(limit=10)
    print(f"Successfully fetched {len(entries)} pure Form D filings.")