"""Parser for extracting financial metrics from SEC Form D XML filings."""

import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List
import pandas as pd

from fetcher import fetch_recent_form_d_entries, get_sec_session


def get_xml_url(index_url: str) -> str:
    """Convert an EDGAR -index.htm URL into its raw primary_doc.xml URL."""
    base_folder = index_url.rsplit("/", 1)[0]
    return f"{base_folder}/primary_doc.xml"


def parse_form_d_xml(xml_url: str) -> Dict[str, Any]:
    """Download and extract core alternative investment metrics from primary_doc.xml."""
    session = get_sec_session()
    response = session.get(xml_url, timeout=10)
    response.raise_for_status()

    root = ET.fromstring(response.content)

    # Extract key fields from the XML tree
    entity_name = root.findtext(".//primaryIssuer/entityName", default="Unknown")
    entity_type = root.findtext(".//primaryIssuer/entityType", default="Unknown")
    industry = root.findtext(".//offeringData/industryGroup/industryGroupType", default="Unspecified")
    fund_type = root.findtext(
        ".//offeringData/industryGroup/investmentFundInfo/investmentFundType",
        default="N/A (Operating/Other)",
    )

    # Offering & fundraising numbers
    total_offering = root.findtext(
        ".//offeringData/offeringSalesAmounts/totalOfferingAmount", default="Indefinite"
    )
    total_sold = root.findtext(
        ".//offeringData/offeringSalesAmounts/totalAmountSold", default="0"
    )
    min_investment = root.findtext(
        ".//offeringData/minimumInvestmentAccepted", default="0"
    )
    num_investors = root.findtext(
        ".//offeringData/investors/totalNumberAlreadyInvested", default="0"
    )

    # Extract key executives / general partners
    managers: List[str] = []
    for person in root.findall(".//relatedPersonsList/relatedPersonInfo"):
        first = person.findtext(".//relatedPersonName/firstName", default="")
        last = person.findtext(".//relatedPersonName/lastName", default="")
        full_name = f"{first} {last}".strip()
        if full_name:
            managers.append(full_name)

    return {
        "Entity Name": entity_name,
        "Structure": entity_type,
        "Industry": industry,
        "Fund Type": fund_type,
        "Target Offering ($)": total_offering,
        "Amount Raised ($)": total_sold,
        "Min Ticket ($)": min_investment,
        "Investors Count": num_investors,
        "Key People": ", ".join(managers[:3]) if managers else "None listed",
        "XML Source": xml_url,
    }

def format_currency(value: str) -> str:
    """Format numeric strings with commas (e.g., '231105832' -> '$231,105,832')."""
    if value.isdigit():
        return f"${int(value):,}"
    return value

if __name__ == "__main__":
    print("Fetching latest Form D filings and extracting hidden deal terms...\n")
    recent_filings = fetch_recent_form_d_entries(limit=5)
    parsed_deals: List[Dict[str, Any]] = []

    for filing in recent_filings:
        xml_url = get_xml_url(filing["url"])
        try:
            deal_data = parse_form_d_xml(xml_url)
            parsed_deals.append(deal_data)
            # Polite 0.2s pause to respect SEC rate limits (max 10 requests/sec)
            time.sleep(0.2)
        except Exception as exc:
            print(f"Skipped {filing['title']} due to error: {exc}")

    # Convert to a Pandas DataFrame for clean inspection
    df = pd.DataFrame(parsed_deals)

    # Print each deal's extracted transparency profile
    for idx, deal in enumerate(parsed_deals, start=1):
        print(f"=== [{idx}] {deal['Entity Name']} ({deal['Structure']}) ===")
        print(f"  Industry / Fund : {deal['Industry']} | {deal['Fund Type']}")
        print(f"  Target Offering : {format_currency(deal['Target Offering ($)'])}")
        print(f"  Capital Raised  : {format_currency(deal['Amount Raised ($)'])} (from {deal['Investors Count']} investors)")
        print(f"  Minimum Ticket  : {format_currency(deal['Min Ticket ($)'])}")
        print(f"  Key Principals  : {deal['Key People']}\n")