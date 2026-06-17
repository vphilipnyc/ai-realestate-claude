---
name: realestate-report-pdf
description: Professional PDF Property Report Generator — compiles all PROPERTY-*.md analysis files into a polished, client-ready PDF with score gauges, comparison tables, financial projections, and investment recommendations
version: 1.0.0
author: AI Real Estate Analyst
tags: [realestate, report, pdf, professional, client-ready, property-report]
command: /realestate report-pdf
output: PROPERTY-REPORT.pdf
---

# Professional PDF Property Report Generator

You are the PDF Report Generator for the AI Real Estate Analyst system. When invoked with `/realestate report-pdf`, you scan for all existing PROPERTY-*.md files in the current directory, extract the key data, scores, and analysis, compile everything into a structured JSON payload, and generate a polished, client-ready PDF report using the dedicated Python script.  The PDF needs text-wrapping in cells so that text doesn't bleed over borders.  For clarity, no overlapping text should appear.

**DISCLAIMER: For educational/research purposes only. Not financial or investment advice. All estimates are AI-generated approximations.**

---

## PURPOSE

Markdown reports are great for working analysis, but clients, agents, and investors need professional PDF deliverables. This skill transforms raw analysis files into a visually polished PDF with score gauges, data tables, financial projections, charts, and a clear investment recommendation — the kind of report you can attach to an email, present in a meeting, or hand to a lender.

---

## TRIGGER

This skill activates when the user runs:
- `/realestate report-pdf` — generate a PDF from all available analysis files
- `/realestate report-pdf <address>` — generate a PDF for a specific property
- Also triggered by "generate PDF", "create PDF report", "make a client report", or "professional report"

---

## EXECUTION PIPELINE

### STEP 1: CHECK FOR PDF GENERATION SCRIPT

The PDF generator (`generate_realestate_pdf.py`) is **bundled inside this skill
folder**, so it travels with the skill whether installed via the CLI or uploaded
to Claude Desktop. Locate it (the bundled copy first, then the CLI-installed
path):

```bash
SCRIPT=$(ls ./generate_realestate_pdf.py \
            "$(dirname "$0" 2>/dev/null)/generate_realestate_pdf.py" \
            ~/.claude/skills/realestate-report-pdf/generate_realestate_pdf.py \
            2>/dev/null | head -1)
```

**If the script exists:** Use it directly (proceed to Step 2).
**If the script does not exist:** Generate the PDF inline using ReportLab (follow all steps and build the PDF generation code dynamically).

### STEP 2: LOCATE THE PROPERTY FOLDER & SCAN FOR ANALYSIS FILES

**Property-folder convention (one folder per property under `properties/`).**
All inputs and outputs for a property live together in
`properties/<SLUG>/` so multiple properties can be analyzed side by side. Build
`<SLUG>` from the MLS number (if known) plus a short address slug, e.g.
`properties/MLS6712345-3792-E-Virgo-Pl/` — or just the address slug when no MLS
is available, e.g. `properties/3792-E-Virgo-Pl-Chandler-AZ-85249/`. Create it if
it does not exist:

```bash
mkdir -p "properties/<SLUG>"
```

Analysis `.md` files are written here by `/realestate analyze`; if older files
are still in the current directory, move them into the folder first.

**Scan the property folder for all PROPERTY-*.md files** (fall back to the
current directory for backward compatibility):

```bash
DIR="properties/<SLUG>"
ls -t "$DIR"/PROPERTY-*.md 2>/dev/null || ls -t PROPERTY-*.md 2>/dev/null
```

**Primary data sources (check for all of these):**

| File Pattern                 | Data It Contains                                 | PDF Section                   |
|------------------------------|--------------------------------------------------|-------------------------------|
| `PROPERTY-ANALYSIS-*.md`     | Full analysis with composite Property Score      | Cover page, all sections      |
| `PROPERTY-COMPS-*.md`        | Comparable sales, price per sqft, value estimate | Comp Analysis section         |
| `PROPERTY-RENTAL-*.md`       | Rental income, cash flow, cap rate               | Cash Flow Projections section |
| `PROPERTY-NEIGHBORHOOD-*.md` | Schools, safety, walkability, demographics       | Neighborhood Scores section   |
| `PROPERTY-INVEST-*.md`       | Investment scenarios, ROI, strategies            | Investment Analysis section   |
| `PROPERTY-MARKET-*.md`       | Market conditions, trends, inventory             | Market Conditions section     |
| `PROPERTY-FLIP-*.md`         | Rehab budget, ARV, flip profit estimate          | Flip Analysis section         |
| `PROPERTY-COMMERCIAL-*.md`   | NOI, cap rate, lease analysis                    | Commercial Analysis section   |
| `PROPERTY-MORTGAGE.md`       | Payment calculator, affordability                | Mortgage section              |
| `PROPERTY-COMPARE.md`        | Side-by-side comparison                          | Comparison section            |
| `PROPERTY-LISTING-*.md`      | MLS listing description                          | Listing section               |
| `PROPERTY-SCREEN-*.md`       | Screener results                                 | Screening section             |

**Find the most recent version of each:**
```bash
ls -t PROPERTY-ANALYSIS-*.md 2>/dev/null | head -1
ls -t PROPERTY-COMPS-*.md 2>/dev/null | head -1
ls -t PROPERTY-RENTAL-*.md 2>/dev/null | head -1
ls -t PROPERTY-NEIGHBORHOOD-*.md 2>/dev/null | head -1
ls -t PROPERTY-INVEST-*.md 2>/dev/null | head -1
ls -t PROPERTY-MARKET-*.md 2>/dev/null | head -1
```

**If no previous data exists:**
1. Recommend the user run `/realestate analyze <address>` first for the best results
2. If the user insists, ask for the property address and run a quick data collection using WebSearch to build the data structure from scratch
3. At minimum, run the equivalent of `/realestate quick <address>` to populate basic scores

### STEP 3: EXTRACT DATA FROM ANALYSIS FILES

Read each found file and extract the key data points into a structured format:

**From PROPERTY-ANALYSIS-*.md (primary source):**
- Property address
- Property type (SFR, condo, multi-family, etc.)
- Listing price
- Beds / Baths / Square footage / Lot size / Year built
- Composite Property Score (0-100)
- Property Grade (A+ through F)
- Signal (Strong Buy through Avoid) for each of Primary Residence and Rental Investment
- Category scores: Value & Comps, Income Potential, Neighborhood, Investment, Market
- Key findings (bulleted list)
- Risk factors
- Recommendation summary

**From PROPERTY-COMPS-*.md:**
- Comparable sales list (address, price, sqft, beds/baths, distance, sale date)
- Estimated market value
- Price per square foot vs comps
- Over/under priced assessment

**From PROPERTY-RENTAL-*.md:**
- Estimated monthly rent
- Net monthly cash flow
- Cap rate
- Cash-on-cash return
- Gross rent multiplier
- Expense breakdown
- Vacancy assumption

**From PROPERTY-NEIGHBORHOOD-*.md:**
- School ratings (elementary, middle, high)
- Walk Score / Transit Score / Bike Score
- Safety rating
- Demographics summary
- Growth outlook

**From PROPERTY-INVEST-*.md:**
- Best investment strategy
- Projected ROI (1yr, 3yr, 5yr)
- Risk level
- Value-add opportunity description
- Exit strategy options

**From PROPERTY-MARKET-*.md:**
- Market type (buyer/seller/balanced)
- Median home price
- Days on market (average)
- Inventory months
- Price trend (YoY)
- Economic drivers
- Appreciation Projection (generated through ReportLab)

### STEP 4: BUILD THE JSON DATA STRUCTURE

Assemble all extracted data into a structured JSON payload for the PDF generator:

> **CRITICAL — use these exact key names.** The PDF script
> (`generate_realestate_pdf.py`) reads the keys below verbatim. Any other key
> name (e.g. `property_address`, `comparable_sales`, `school_ratings`,
> `listing_price`) is **silently ignored** and the section falls back to demo
> defaults — which is what makes a report look generic / unlinked from the
> `.md` analyses. All values are strings unless noted; every section is optional
> and is skipped (or uses a built-in default) when absent.

```json
{
  "address": "3792 E Virgo Pl, Chandler, AZ 85249",
  "price": "$960,000",
  "date": "Jun 16, 2026 5:07 PM EDT",
  "overall_score": 76,
  "primary_signal": "BUY",
  "rental_signal": "WATCH",
  "listing_url": "https://www.zillow.com/homedetails/...  (optional)",

  "context_highlights": [
    "Top schools: Basha High (Top 5% in AZ) and Arizona College Prep (10/10).",
    "A+ safety — violent crime 1.5/1K vs 3.7/1K national.",
    "Affluent area: median household income $153,633 (~2x national)."
  ],

  "property_details": {
    "beds": "4", "baths": "3", "sqft": "2,400",
    "year_built": "2018", "lot_size": "0.20 acres",
    "property_type": "Single Family Residence"
  },

  "categories": {
    "Value & Comps":        {"score": 78, "weight": "25%"},
    "Income Potential":     {"score": 72, "weight": "20%"},
    "Neighborhood Quality": {"score": 80, "weight": "20%"},
    "Investment Upside":    {"score": 74, "weight": "20%"},
    "Market Conditions":    {"score": 70, "weight": "15%"}
  },

  "comps": [
    {"address": "125 Oak Ave", "price": "$430,000", "sqft": "1,900",
     "price_sqft": "$226", "sold_date": "Mar 2026", "distance": "0.3 mi"}
  ],
  "comp_summary": {"avg_price": "$432,000", "avg_price_sqft": "$228/sq ft"},

  "cashflow": {
    "items": [
      {"item": "Gross Rental Income", "monthly": "$2,650", "annual": "$31,800"},
      {"item": "Net Cash Flow", "monthly": "$320", "annual": "$3,840"}
    ]
  },

  "investment_metrics": {
    "cap_rate": "7.2%",   "cap_rate_status": "Strong for metro",
    "cash_on_cash": "9.8%", "coc_status": "Above 8% target",
    "grm": "13.4x",       "grm_status": "Favorable",
    "dscr": "1.32",       "dscr_status": "Comfortable (>1.25)",
    "one_pct": "0.62%",   "one_pct_status": "Below 1% rule",
    "breakeven": "84%",   "breakeven_status": "Healthy vacancy cushion"
  },

  "mortgage": {
    "purchase_price": "$425,000", "down_payment": "$85,000 (20%)",
    "loan_amount": "$340,000", "rate": "6.75%", "term": "30-year fixed",
    "monthly_pi": "$2,205", "monthly_piti": "$2,684"
  },

  "neighborhood": {
    "scores": {"School Rating": 92, "Safety / Crime": 88, "Walkability": 18,
               "Transit Access": 5, "Dining & Shopping": 55, "Growth Trajectory": 82},
    "details": [
      {"factor": "Top School", "detail": "Basha HS — Top 5% in AZ",
       "notes": "Chandler Unified 8/10"}
    ],
    "demographics": {
      "population_growth": "+2.2% annually", "median_age": "42.7 years",
      "employment_rate": "96.4%", "major_employers": "Intel, Microchip, NXP"
    }
  },

  "schools": [
    {"name": "Santan Junior High", "type": "Public", "grades": "7–8",
     "rating": "8/10 (GreatSchools)", "distance": "~2.0 mi",
     "notes": "Strong STEM scores"}
  ],
  "amenities": {
    "healthcare": [
      {"name": "Chandler Regional Medical Center",
       "detail": "465-bed Level I trauma center", "distance": "~7 mi"}
    ],
    "parks_recreation": [
      {"name": "Tumbleweed Park", "detail": "205-acre flagship; 18 pickleball courts",
       "distance": "~3 mi", "drive_time": "~8 min"}
    ]
  },
  "colleges": [
    {"name": "Chandler-Gilbert Community College", "type": "Community College",
     "distance": "~6 mi", "drive_time": "~12 min", "notes": "2-yr transfer programs"}
  ],
  "gyms": [
    {"name": "EOS Fitness (Chandler)", "amenities": "Pool, sauna, classes",
     "rating": "~4.4 (Google)", "notes": "Long-standing AZ chain; 24/7"}
  ],

  "strategies": [
    {"strategy": "Buy & Hold (Rental)", "projected_return": "7-9% annually",
     "timeframe": "5-10 years", "risk": "Vacancy, maintenance, downturn"}
  ],
  "appreciation_projections": [
    {"year": "Year 1", "conservative": "$979,200", "moderate": "$993,600",
     "aggressive": "$1,008,000"}
  ],
  "scenarios": [
    {"scenario": "Bull Case", "probability": "20%", "return": "+30% to +50% (5yr)",
     "trigger": "Rate cuts, semiconductor expansion accelerates"}
  ],

  "recommendation": {
    "signal": "BUY",
    "summary": "Solid buy-and-hold in a high-growth, top-school suburb...",
    "suggested_offer": "$405,000 - $415,000",
    "action_items": ["Order inspection (roof/HVAC)", "Verify HOA STR rules"]
  },
  "risk_factors": [
    {"factor": "Market Risk", "probability": "Medium", "impact": "High",
     "notes": "Cyclical correction risk in Phoenix metro"}
  ]
}
```

#### Field notes & non-obvious behaviors

- **Signals** (`primary_signal`, `rental_signal`, `recommendation.signal`) accept
  `AVOID` / `CAUTION` / `WATCH` / `BUY` / `STRONG BUY` (free-form like
  "Hold/Watch" is normalized). The cover shows Primary vs Rental as shaded boxes.
- **`price` may be a range** (e.g. `~$960,000–$1,000,000`); the chart uses the
  first number as the Year-0 origin, so don't worry about a single clean value.
- **`schools`** is auto-filtered to **grade 7+** for the detail table; carry
  sentiment (proficiency %, reputation) in `notes`.
- **`listing_url`** is optional — when omitted the cover links to a Zillow
  address search built from `address`, so a clickable listing link is **always
  present even when Zillow blocked live scraping**. Never skip the report
  because a listing fetch failed.
- **`cashflow.items`** — the **last** item is highlighted as the net/total row.
- **Avoid duplication:** `context_highlights` and `neighborhood.details` stay
  summary-level; `schools` / `amenities` / `colleges` / `gyms` carry the
  specifics. Don't repeat the same sentence in both.

#### Keys the script does NOT currently render

To save extraction effort: these are commonly produced by the analysis `.md`
files but are **not** read by the current PDF script — omit them or expect them
to be ignored: `comps_full`, `fmv_estimate`, `price_psf_analysis`,
`rental_comps`, `appreciation_history`, `market_data`, `offer_scenarios`,
`negotiation_levers`, `school_district`, `natural_disaster_risk`, `walkability`
(use `neighborhood.scores` instead), `demographics_detail`, `crime_detail`,
`planned_developments`, `amenities.grocery`, `amenities.shopping`,
`strategies[].pros`. (Flag if you want any of these surfaced in a future pass.)

### STEP 5: GENERATE THE PDF

Write the JSON payload from Step 4 into the property folder, then run the script
**with the input JSON and output path** (running it with no arguments only
produces the built-in demo report — it does NOT use your data):

```bash
DIR="properties/<SLUG>"
# write the Step 4 payload to "$DIR/property-data.json" (e.g. via the Write tool)
# $SCRIPT was resolved in Step 1 (bundled generate_realestate_pdf.py)
python3 "$SCRIPT" "$DIR/property-data.json" "$DIR/PROPERTY-REPORT.pdf"
```

**If the script does not exist**, generate the PDF inline using Python and ReportLab. The inline script must produce a PDF with the following sections:

#### PDF SECTIONS AND LAYOUT

**Page 1: Cover Page**
- Report title: "Property Analysis Report"
- Property address (large, centered)
- Property Score gauge (semicircular, color-coded: green 70+, yellow 40-69, red 0-39)
- Grade and Signal displayed prominently for each type (Primary and Rental Investment)
- Listing link ("View this listing on Zillow") at the bottom — always present (built from the address if no `listing_url`), even when Zillow blocked live data
- Report date
- Disclaimer footer

**Before Comparable Sales: Location & Lifestyle Context**
- High-level `context_highlights` bullets (summary of schools, safety, healthcare, recreation, jobs) shown up front

**Page 2: Property Overview**
- Property details table (price, beds, baths, sqft, lot, year, type)
- Property photo placeholder or description
- Executive summary (2-4 sentences)
- Key findings list (bulleted, top 5)

**Page 3: Comparable Sales Analysis**
- Comp table: address, price, $/sqft, beds/baths, distance, sale date
- Estimated value vs listing price
- Price per sqft comparison bar chart
- Over/under priced assessment with percentage

**Page 4: Cash Flow Projections**
- Rental income estimate
- Monthly expense breakdown table (mortgage, taxes, insurance, vacancy, maintenance, management)
- Net monthly cash flow (highlighted, green if positive, red if negative)
- Key return metrics: Cap Rate, Cash-on-Cash, GRM
- 5-year cash flow projection table

**Page 5: Neighborhood Scorecard + Location & Lifestyle detail**
- School ratings (elementary, middle, high) with bar visualization
- Walk Score / Transit Score / Bike Score gauges
- Safety rating
- Demographics summary
- Growth outlook
- Detailed commentary tables (each renders only if data present): Secondary Schools (grade 7+ with sentiment notes), Hospitals & Healthcare, Colleges & Universities (distance + drive time), Gyms & Fitness (amenities + reviews), Parks/Recreation & Landmarks (distance/drive time)

**Page 6: Investment Analysis**
- Category scores bar chart (all 5 categories)
- Best strategy recommendation
- Projected ROI table (1yr, 3yr, 5yr)
- Risk level assessment
- Value-add opportunity description
- Exit strategy options

**Page 7: Market Conditions**
- Market type indicator (buyer/seller/balanced)
- Median price and trend
- Days on market and inventory
- Economic drivers
- Price trend chart or table
- Supply/demand assessment

**Page 8: Recommendation & Next Steps**
- Overall recommendation (highlighted)
- Signal with explanation
- Key action items
- Suggested next steps
- Full disclaimer

#### PDF STYLING

| Element      | Style                                                                   |
|--------------|-------------------------------------------------------------------------|
| Colors       | Defer to colors in Python script                                        |
| Fonts        | Helvetica-Bold for headers, Helvetica for body                          |
| Score gauges | Semicircular arc gauges with color gradient (red -> yellow -> green)    |
| Tables       | Alternating row colors                                                  |
| Charts       | Horizontal bar charts for category scores and comparisons               |
| Footer       | Page numbers (e.g., "Page 1 of 12"), disclaimer, creation date and time |
| Margins      | 50pt top, 40pt sides, 50pt bottom                                       |

### STEP 6: VERIFY AND DELIVER

After PDF generation:

```bash
ls -la "properties/<SLUG>/PROPERTY-REPORT.pdf"
```

Confirm the file was created and report:
- File name and location
- File size
- Number of pages
- Which data sources were included (list the PROPERTY-*.md files used)
- Any data gaps (sections that had no source file — these will show "Data not available" in the PDF)

---

## OUTPUT SPECIFICATIONS

| Spec              | Value                                                |
|-------------------|------------------------------------------------------|
| Output folder     | `properties/<SLUG>/` (MLS# + address slug, one per property) |
| File name         | `PROPERTY-REPORT.pdf` inside the property folder     |
| Page size         | Letter (8.5" x 11")                                  |
| Orientation       | Portrait                                             |
| Pages             | 6-20 depending on available data                     |
| File size         | Typically 200KB - 1MB                                |
| Python dependency | ReportLab (`pip install reportlab` if not installed) |

---

## RULES

1. **Professional quality** — The PDF must look like it came from a real estate analytics firm, not a quick printout
2. **Data-driven** — Every number in the PDF must come from the analysis files or live research; never fabricate data
3. **Conservative estimates** — Use the same conservative projections from the analysis files
4. **Complete disclaimer** — Full disclaimer must appear on the cover page and the last page
5. **Graceful degradation** — If some analysis files are missing, generate the PDF with available data and mark missing sections as "Not analyzed — run /realestate [command] to add this data"
6. **Install dependencies** — If ReportLab is not installed, install it automatically: `pip install reportlab`
7. **Overwrite safely** — If `properties/<SLUG>/PROPERTY-REPORT.pdf` already exists, overwrite it (the latest data wins). Never write the PDF into the `scripts/` folder or the repo root — it belongs in the property folder.
8. **Color-coded scores** — All scores must be color-coded: green (70+), yellow (40-69), red (0-39)

## ERROR HANDLING

- If ReportLab is not installed, run `pip install reportlab` and retry
- If no PROPERTY-*.md files exist, prompt the user to run `/realestate analyze <address>` first
- If the Python script fails, capture the error message and display it to the user with troubleshooting steps
- If only partial data is available, generate a partial report and clearly mark which sections are incomplete
- If the PDF file cannot be written (permission error), suggest an alternative output directory

## DEPENDENCY INSTALLATION

If ReportLab is not available, install it:

```bash
pip install reportlab 2>/dev/null || pip3 install reportlab 2>/dev/null
```

If installation fails, provide manual instructions:
```
To install the PDF generation dependency:
  pip install reportlab
  
If using a virtual environment:
  python3 -m venv venv && source venv/bin/activate && pip install reportlab
```

---

## WHEN TO RECOMMEND PDF vs MARKDOWN

| Situation                               | Recommend |
|-----------------------------------------|-----------|
| Client presentation or email attachment | PDF       |
| Lender or partner due diligence package | PDF       |
| Quick internal reference                | Markdown  |
| Iterative editing and analysis          | Markdown  |
| Board or investor meeting               | PDF       |
| Personal property shopping              | Markdown  |
| Sales collateral for real estate agent  | PDF       |

Always suggest: "Your analysis files are saved as Markdown for easy reference. Run `/realestate report-pdf` anytime to generate a polished PDF version for clients or presentations."

---

## DATA QUALITY FLAGS

When compiling the PDF, flag data quality issues:

| Flag                | Condition                                     | Display In PDF                         |
|---------------------|-----------------------------------------------|----------------------------------------|
| High Confidence     | All 5 analysis agents ran, data is fresh      | Green checkmark                        |
| Moderate Confidence | 3-4 agents ran, or data is 7+ days old        | Yellow warning                         |
| Low Confidence      | Only 1-2 agents ran, or significant data gaps | Red flag with note                     |
| Stale Data          | Analysis files are 30+ days old               | Warning banner: "Data may be outdated" |

---

## MULTI-PROPERTY REPORTS

If the user has analyzed multiple properties (multiple sets of PROPERTY-*.md files), the PDF should:

1. Detect all unique properties from file names
2. Ask the user which property to include (or all)
3. If "all", create a multi-property report with a comparison summary page
4. Each property gets its own section with the standard layout
5. Final page includes a side-by-side comparison table if 2+ properties are included

**DISCLAIMER: For educational/research purposes only. Not financial or investment advice. All estimates are AI-generated approximations based on publicly available data.**
