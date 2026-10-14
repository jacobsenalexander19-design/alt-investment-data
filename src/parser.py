"""Parser for extracting financial metrics and fees from SEC Form D XML filings."""

from pathlib import Path
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List
import pandas as pd

from fetcher import fetch_recent_form_d_entries, get_sec_session

# Resolve path to the data/ folder at the root of the project
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CSV_OUTPUT_PATH = DATA_DIR / "form_d_deals.csv"


def get_xml_url(index_url: str) -> str:
    """Convert an EDGAR -index.htm URL into its raw primary_doc.xml URL."""
    base_folder = index_url.rsplit("/", 1)[0]
    return f"{base_folder}/primary_doc.xml"


def to_int(value: str) -> int:
    """Safely convert numeric XML strings to integers (defaults to 0 if 'Indefinite' or blank)."""
    try:
        return int(float(value.strip()))
    except (ValueError, AttributeError):
        return 0


def parse_form_d_xml(xml_url: str, filing_date: str = "") -> Dict[str, Any]:
    """Download and extract core alternative investment metrics from primary_doc.xml."""
    session = get_sec_session()
    response = session.get(xml_url, timeout=10)
    response.raise_for_status()

    root = ET.fromstring(response.content)

    # 1. Core Entity & Location Info
    entity_name = root.findtext(".//primaryIssuer/entityName", default="Unknown")
    entity_type = root.findtext(".//primaryIssuer/entityType", default="Unknown")
    location = root.findtext(
        ".//primaryIssuer/issuerAddress/stateOrCountryDescription",
        default=root.findtext(".//primaryIssuer/issuerAddress/stateOrCountry", default="Unspecified"),
    )

    # 2. Industry & Fund Strategy
    industry = root.findtext(".//offeringData/industryGroup/industryGroupType", default="Unspecified")
    fund_type = root.findtext(
        ".//offeringData/industryGroup/investmentFundInfo/investmentFundType",
        default="Operating Company / Other",
    )

    # 3. Fundraising & Ticket Metrics
    raw_target = root.findtext(
        ".//offeringData/offeringSalesAmounts/totalOfferingAmount", default="Indefinite"
    )
    amount_raised = to_int(
        root.findtext(".//offeringData/offeringSalesAmounts/totalAmountSold", default="0")
    )
    min_investment = to_int(
        root.findtext(".//offeringData/minimumInvestmentAccepted", default="0")
    )
    num_investors = to_int(
        root.findtext(".//offeringData/investors/totalNumberAlreadyInvested", default="0")
    )

    # 4. Hidden Middleman Fees (Sales Commissions & Finder's Fees)
    sales_commissions = to_int(
        root.findtext(
            ".//offeringData/salesCommissionsFindersFees/salesCommissions/dollarAmount",
            default="0",
        )
    )
    finders_fees = to_int(
        root.findtext(
            ".//offeringData/salesCommissionsFindersFees/findersFees/dollarAmount",
            default="0",
        )
    )
    total_fees = sales_commissions + finders_fees

    # 5. Derived Transparency Metrics
    avg_check = round(amount_raised / num_investors) if num_investors > 0 else 0
    fee_pct = round((total_fees / amount_raised) * 100, 2) if amount_raised > 0 else 0.0

    # 6. Key Principals / Fund Managers
    managers: List[str] = []
    for person in root.findall(".//relatedPersonsList/relatedPersonInfo"):
        first = person.findtext(".//relatedPersonName/firstName", default="")
        last = person.findtext(".//relatedPersonName/lastName", default="")
        full_name = f"{first} {last}".strip()
        if full_name:
            managers.append(full_name)

    return {
        "Filing Date": filing_date[:10] if filing_date else "Unknown",
        "Entity Name": entity_name,
        "Structure": entity_type,
        "Location": location.title(),
        "Industry": industry,
        "Fund Type": fund_type,
        "Target Offering": raw_target,
        "Amount Raised ($)": amount_raised,
        "Investors Count": num_investors,
        "Avg Check ($)": avg_check,
        "Min Ticket ($)": min_investment,
        "Sales Commissions ($)": sales_commissions,
        "Finders Fees ($)": finders_fees,
        "Total Fees ($)": total_fees,
        "Fee Drag (%)": fee_pct,
        "Key People": ", ".join(managers[:3]) if managers else "None listed",
        "XML Source": xml_url,
    }


def build_dataset(limit: int = 30) -> pd.DataFrame:
    """Fetch, parse, and save a structured CSV dataset of recent Form D filings."""
    print(f"Fetching {limit} recent Form D filings from SEC EDGAR...")
    recent_filings = fetch_recent_form_d_entries(limit=limit)
    parsed_deals: List[Dict[str, Any]] = []

    for idx, filing in enumerate(recent_filings, start=1):
        xml_url = get_xml_url(filing["url"])
        try:
            deal_data = parse_form_d_xml(xml_url, filing_date=filing["updated_at"])
            parsed_deals.append(deal_data)
            print(
                f"  [{idx}/{len(recent_filings)}] Parsed: {deal_data['Entity Name'][:40]:<40} "
                f"| Raised: ${deal_data['Amount Raised ($)']:>12,} | Loc: {deal_data['Location']}"
            )
            # Polite 0.2s pause to respect SEC rate limits
            time.sleep(0.2)
        except Exception as exc:
            print(f"  [{idx}/{len(recent_filings)}] Skipped {filing['title'][:35]} ({exc})")

    df = pd.DataFrame(parsed_deals)

    # Ensure data/ folder exists and save CSV
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_OUTPUT_PATH, index=False)
    print(f"\nSaved {len(df)} deals to: {CSV_OUTPUT_PATH}")
    return df


if __name__ == "__main__":
    df_deals = build_dataset(limit=30)

    if not df_deals.empty:
        total_raised = df_deals["Amount Raised ($)"].sum()
        total_fees = df_deals["Total Fees ($)"].sum()
        fee_deals = (df_deals["Total Fees ($)"] > 0).sum()

        print("\n=== BATCH TRANSPARENCY SUMMARY ===")
        print(f"Total Capital Raised Across {len(df_deals)} Filings : ${total_raised:,}")
        print(f"Total Broker Commissions & Finder's Fees : ${total_fees:,} ({fee_deals} deals paid fees)")
        print("\nTop 5 Largest Raises in Batch:")
        top_5 = df_deals.sort_values(by="Amount Raised ($)", ascending=False).head(5)
        for _, row in top_5.iterrows():
            print(
                f" • {row['Entity Name']} ({row['Location']}) — "
                f"Raised: ${row['Amount Raised ($)']:,.0f} from {row['Investors Count']} investors "
                f"(Avg Check: ${row['Avg Check ($)']:,.0f} | Fees: ${row['Total Fees ($)']:,.0f})"
            )