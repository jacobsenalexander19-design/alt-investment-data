"""Generate a standalone interactive HTML dashboard for Form D Alternative Investments."""

from pathlib import Path
import pandas as pd
import plotly.express as px

from parser import CSV_OUTPUT_PATH, build_dataset

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HTML_OUTPUT_PATH = DATA_DIR / "dashboard.html"


def generate_html_dashboard():
    """Load Form D CSV data and export an interactive Plotly HTML dashboard."""
    if not CSV_OUTPUT_PATH.exists():
        print("Dataset not found. Fetching fresh Form D filings...")
        df = build_dataset(limit=30)
    else:
        df = pd.read_csv(CSV_OUTPUT_PATH)

    if df.empty:
        print("No data available to plot.")
        return

    print(f"Generating interactive dashboard from {len(df)} filings...")

    # 1. Scatter Plot: Whale vs. Syndicate Radar
    plot_df = df[(df["Amount Raised ($)"] > 0) & (df["Investors Count"] > 0)].copy()

    fig_scatter = px.scatter(
        plot_df,
        x="Investors Count",
        y="Amount Raised ($)",
        color="Fund Type",
        size="Avg Check ($)",
        hover_name="Entity Name",
        hover_data={
            "Location": True,
            "Avg Check ($)": ":$,.0f",
            "Min Ticket ($)": ":$,.0f",
            "Total Fees ($)": ":$,.0f",
            "Key People": True,
        },
        log_y=True,
        title="<b>Alternative Investments: Whale vs. Syndicate Radar</b>",
        height=500,
    )
    fig_scatter.update_layout(
        xaxis_title="Number of Accredited Investors",
        yaxis_title="Capital Raised ($, Log Scale)",
    )

    # 2. Bar Chart: Capital Flows by Industry
    sector_df = (
        df.groupby(["Industry", "Fund Type"], as_index=False)["Amount Raised ($)"]
        .sum()
        .query("`Amount Raised ($)` > 0")
        .sort_values(by="Amount Raised ($)", ascending=True)
    )

    fig_bar = px.bar(
        sector_df,
        x="Amount Raised ($)",
        y="Industry",
        color="Fund Type",
        orientation="h",
        title="<b>Capital Concentration by Industry & Fund Type</b>",
        height=500,
    )
    fig_bar.update_layout(
        xaxis_title="Total Capital Raised ($)",
        yaxis_title="Industry Group",
    )

    # Combine both figures into a single HTML file with custom styling
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Alt-Investment Transparency Radar</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                margin: 0;
                padding: 30px;
                background-color: #0e1117;
                color: #fafafa;
            }}
            h1 {{ margin-top: 0; color: #ffffff; }}
            .subtitle {{ color: #a3a3a3; margin-bottom: 30px; font-size: 1.1em; }}
            .card {{
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 30px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 15px;
                font-size: 0.9em;
            }}
            th, td {{
                padding: 10px 12px;
                text-align: left;
                border-bottom: 1px solid #30363d;
            }}
            th {{ background-color: #21262d; color: #c9d1d9; }}
            tr:hover {{ background-color: #21262d; }}
        </style>
    </head>
    <body>
        <h1>📊 Alternative Investment Transparency Radar</h1>
        <div class="subtitle">Live analysis of private funds and exempt offerings via SEC Form D filings.</div>
        
        <div class="card">
            {fig_scatter.to_html(full_html=False, include_plotlyjs='cdn')}
        </div>

        <div class="card">
            {fig_bar.to_html(full_html=False, include_plotlyjs='cdn')}
        </div>

        <div class="card">
            <h3 style="margin-top:0;">🕵️ Extracted Deal Transparency Table ({len(df)} Filings)</h3>
            <div style="overflow-x:auto;">
                {df[['Entity Name', 'Fund Type', 'Location', 'Amount Raised ($)', 'Investors Count', 'Avg Check ($)', 'Total Fees ($)', 'Key People']].to_html(index=False, classes='dataframe')}
            </div>
        </div>
    </body>
    </html>
    """

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HTML_OUTPUT_PATH.write_text(html_content, encoding="utf-8")
    print(f"\nSuccessfully generated interactive HTML dashboard at: {HTML_OUTPUT_PATH}")


if __name__ == "__main__":
    generate_html_dashboard()