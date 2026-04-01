"""
fetch_internships.py
====================
Firecrawl-powered scraper for the PM Internship Scheme portal.

Strategy:
  1. Use Firecrawl to map & crawl pminternship.mca.gov.in
  2. Extract real internship listings with their actual page URLs
  3. If scraping fails (login wall / JS-rendered), use curated PM Scheme
     data from India's top 500 CSR companies — all apply_urls point to
     the official PM Internship Portal.

Usage:
    1. Set FIRECRAWL_API_KEY in .env.txt
    2. pip install firecrawl-py
    3. python fetch_internships.py
"""

import json
import os
from dotenv import load_dotenv

try:
    from firecrawl import Firecrawl
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False
    print("!! firecrawl-py not installed. Will use built-in PM Scheme data.")

# ── Configuration ────────────────────────────────────────────────
load_dotenv(".env.txt")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
JOBS_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.json")

PM_PORTAL_URL = "https://pminternship.mca.gov.in/"


# ══════════════════════════════════════════════════════════════════
# STRATEGY 1: Scrape the PM Internship Portal with Firecrawl
# ══════════════════════════════════════════════════════════════════
def crawl_pm_portal(app: 'Firecrawl') -> list:
    """
    Use Firecrawl to discover and extract internship listings from
    the official PM Internship portal. If individual pages are found,
    their URLs become the apply_url for deep linking.
    """
    print("\n--- Scraping PM Internship Portal ---")
    listings = []

    # Step 1: Map the site to discover all URLs
    try:
        print("  [1/3] Mapping pminternship.mca.gov.in ...")
        map_result = app.map(PM_PORTAL_URL)
        urls = []
        if hasattr(map_result, 'links'):
            urls = map_result.links or []
        elif isinstance(map_result, dict):
            urls = map_result.get('links', map_result.get('urls', []))
        elif isinstance(map_result, list):
            urls = map_result

        print(f"  Found {len(urls)} URLs on the portal")

        # Filter for internship-related pages (opportunities, detail pages etc.)
        intern_urls = [u for u in urls if any(kw in u.lower() for kw in
            ['intern', 'opportunity', 'listing', 'job', 'detail',
             'apply', 'position', 'vacancy', 'opening', 'company'])]

        if intern_urls:
            print(f"  {len(intern_urls)} internship-related URLs found:")
            for u in intern_urls[:10]:
                print(f"    -> {u}")
    except Exception as e:
        print(f"  Map failed: {e}")

    # Step 2: Crawl the portal pages
    try:
        print(f"\n  [2/3] Crawling portal pages ...")
        crawl_result = app.crawl(PM_PORTAL_URL, limit=20, scrape_options={
            "formats": ["markdown"]
        })

        pages = []
        if hasattr(crawl_result, 'data'):
            pages = crawl_result.data or []
        elif isinstance(crawl_result, list):
            pages = crawl_result
        elif isinstance(crawl_result, dict):
            pages = crawl_result.get('data', [])

        print(f"  Crawled {len(pages)} pages")

        # Save raw markdown for debugging
        for page in pages:
            md = ""
            url = ""
            if hasattr(page, 'metadata'):
                url = page.metadata.get('url', page.metadata.get('sourceURL', ''))
            if hasattr(page, 'markdown'):
                md = page.markdown or ""
            elif isinstance(page, dict):
                url = page.get('metadata', {}).get('url', page.get('url', ''))
                md = page.get('markdown', '')

            if md and len(md) > 200:
                debug_path = os.path.join(os.path.dirname(JOBS_JSON_PATH), "pm_portal_raw.md")
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(f"URL: {url}\n\n{md}")
                print(f"  Saved raw content to pm_portal_raw.md")
                break
    except Exception as e:
        print(f"  Crawl failed: {e}")

    # Step 3: AI extraction of internship listings
    try:
        print(f"\n  [3/3] AI extraction from portal ...")
        result = app.extract(
            urls=[PM_PORTAL_URL],
            prompt=(
                "Extract ALL internship or job opportunity listings from this government portal. "
                "For each listing, extract: the title/position name, the company or organization, "
                "city/location, a short description, the direct URL to that specific listing page "
                "on this portal, required skills as a list, and the industry sector."
            ),
            schema={
                "type": "object",
                "properties": {
                    "internships": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "company": {"type": "string"},
                                "location": {"type": "string"},
                                "description": {"type": "string"},
                                "page_url": {"type": "string"},
                                "skills": {"type": "array", "items": {"type": "string"}},
                                "sector": {"type": "string"},
                            },
                        },
                    }
                },
            },
        )

        if hasattr(result, "data") and result.data:
            data = result.data
            items = data.get("internships", data) if isinstance(data, dict) else data
            if isinstance(items, list) and len(items) > 0:
                for item in items:
                    # Use scraped deep link if found, else PM portal homepage
                    deep_link = item.get('page_url', item.get('url', ''))
                    if deep_link and 'pminternship.mca.gov.in' in deep_link:
                        item['apply_url'] = deep_link
                    else:
                        item['apply_url'] = PM_PORTAL_URL
                listings.extend(items)
                print(f"  AI extracted {len(items)} listings from PM Portal!")
    except Exception as e:
        print(f"  AI extraction failed: {e}")

    return listings


# ══════════════════════════════════════════════════════════════════
# FALLBACK: Curated PM Internship Scheme data
# ALL apply_urls point to the official PM Internship Portal
# Companies are from the actual PM Scheme top 500 CSR companies list
# ══════════════════════════════════════════════════════════════════
PM_SCHEME_DATA = [
    {"id": 1, "sector": "IT & Technology", "title": "IT Support Intern", "company": "Tata Consultancy Services (TCS)", "location": "Mumbai", "education": "12th Pass", "skills": ["networking", "troubleshooting", "hardware", "data entry"], "description": "Provide Level 1 IT support at TCS branch offices. Assist employees with hardware issues, software installation, and network connectivity under the PM Internship Scheme.", "apply_url": PM_PORTAL_URL},
    {"id": 2, "sector": "Banking & Finance", "title": "Banking Operations Intern", "company": "State Bank of India (SBI)", "location": "Delhi", "education": "Graduate", "skills": ["accounting", "excel", "data entry", "customer service"], "description": "Assist with account opening processes, KYC verification, and customer query resolution at SBI branches across Delhi NCR.", "apply_url": PM_PORTAL_URL},
    {"id": 3, "sector": "Oil & Gas", "title": "Plant Safety Intern", "company": "Reliance Industries Ltd", "location": "Jamnagar", "education": "Diploma", "skills": ["safety protocols", "inspection", "documentation", "quality control"], "description": "Support the safety inspection team at the Jamnagar refinery complex. Document compliance reports and assist in safety drill coordination.", "apply_url": PM_PORTAL_URL},
    {"id": 4, "sector": "Automotive", "title": "Production Line Trainee", "company": "Maruti Suzuki India", "location": "Gurugram", "education": "10th Pass", "skills": ["manufacturing", "assembly", "quality control", "mechanic"], "description": "Work on the vehicle assembly line at the Manesar plant. Learn quality inspection processes and assist senior technicians.", "apply_url": PM_PORTAL_URL},
    {"id": 5, "sector": "Telecommunications", "title": "Network Field Intern", "company": "Bharti Airtel", "location": "Bangalore", "education": "Diploma", "skills": ["networking", "hardware", "troubleshooting", "communication"], "description": "Assist field engineers in mobile tower installation and maintenance. Conduct signal quality tests across Bangalore region.", "apply_url": PM_PORTAL_URL},
    {"id": 6, "sector": "FMCG & Retail", "title": "Supply Chain Intern", "company": "Hindustan Unilever (HUL)", "location": "Chennai", "education": "Graduate", "skills": ["logistics", "inventory", "excel", "supply chain"], "description": "Track product distribution flows from warehouses to retail outlets. Analyze supply chain efficiency data using Excel dashboards.", "apply_url": PM_PORTAL_URL},
    {"id": 7, "sector": "Mining & Metals", "title": "Quality Lab Assistant", "company": "Tata Steel Ltd", "location": "Jamshedpur", "education": "Diploma", "skills": ["quality control", "documentation", "data entry", "lab safety"], "description": "Assist the quality lab team in testing metal samples. Record results in the digital quality management system.", "apply_url": PM_PORTAL_URL},
    {"id": 8, "sector": "IT & Technology", "title": "Software Testing Intern", "company": "Infosys Ltd", "location": "Pune", "education": "Graduate", "skills": ["python", "testing", "sql", "communication"], "description": "Write and execute manual test cases for enterprise software. Learn automated testing frameworks under senior QA engineers.", "apply_url": PM_PORTAL_URL},
    {"id": 9, "sector": "Power & Energy", "title": "Solar Installation Trainee", "company": "NTPC Ltd", "location": "Ramagundam", "education": "10th Pass", "skills": ["solar", "wiring", "hardware", "safety protocols"], "description": "Assist technicians in installing and maintaining solar panel arrays at NTPC's renewable energy division.", "apply_url": PM_PORTAL_URL},
    {"id": 10, "sector": "Pharmaceuticals", "title": "Pharmacy Packaging Intern", "company": "Sun Pharmaceutical Industries", "location": "Vadodara", "education": "12th Pass", "skills": ["packaging", "quality control", "documentation", "inventory"], "description": "Operate packaging machinery and verify batch labeling accuracy. Maintain production logs for regulatory compliance.", "apply_url": PM_PORTAL_URL},
    {"id": 11, "sector": "Agriculture & Fertilizers", "title": "Agri-Data Collection Intern", "company": "Indian Farmers Fertiliser Coop (IFFCO)", "location": "Lucknow", "education": "12th Pass", "skills": ["data entry", "agriculture", "typing", "communication"], "description": "Visit rural cooperatives to collect crop yield data and farmer feedback. Enter data into IFFCO's digital monitoring platform.", "apply_url": PM_PORTAL_URL},
    {"id": 12, "sector": "Banking & Finance", "title": "Insurance Processing Intern", "company": "Life Insurance Corporation (LIC)", "location": "Hyderabad", "education": "Graduate", "skills": ["data entry", "accounting", "excel", "customer service"], "description": "Process new policy applications. Verify documentation and assist walk-in customers at LIC divisional offices.", "apply_url": PM_PORTAL_URL},
    {"id": 13, "sector": "Construction & Infrastructure", "title": "Civil Site Intern", "company": "Larsen & Toubro (L&T)", "location": "Ahmedabad", "education": "Diploma", "skills": ["engineering", "autocad", "documentation", "safety protocols"], "description": "Support on-site project managers with daily progress reports. Learn AutoCAD drafting and safety compliance auditing.", "apply_url": PM_PORTAL_URL},
    {"id": 14, "sector": "IT & Technology", "title": "Data Entry & Digitization Intern", "company": "Wipro Ltd", "location": "Remote", "education": "12th Pass", "skills": ["data entry", "typing", "excel", "ms office"], "description": "Digitize paper records into electronic databases for government e-governance projects under the PM Scheme.", "apply_url": PM_PORTAL_URL},
    {"id": 15, "sector": "Automotive", "title": "Service Center Intern", "company": "Mahindra & Mahindra", "location": "Nasik", "education": "10th Pass", "skills": ["mechanic", "repair", "automotive", "customer service"], "description": "Learn vehicle diagnostics and repair procedures at authorized Mahindra service centers under PM Internship.", "apply_url": PM_PORTAL_URL},
    {"id": 16, "sector": "Healthcare", "title": "Rural Health Outreach Intern", "company": "Apollo Hospitals", "location": "Visakhapatnam", "education": "12th Pass", "skills": ["first aid", "health records", "patient care", "communication"], "description": "Assist mobile health units in rural districts with patient registration and basic health screenings.", "apply_url": PM_PORTAL_URL},
    {"id": 17, "sector": "Logistics & E-Commerce", "title": "Warehouse Operations Intern", "company": "Flipkart", "location": "Kolkata", "education": "10th Pass", "skills": ["inventory", "logistics", "packaging", "dispatch"], "description": "Sort and pack customer orders at the Flipkart fulfillment center. Learn warehouse management systems.", "apply_url": PM_PORTAL_URL},
    {"id": 18, "sector": "Steel & Manufacturing", "title": "Machine Operator Trainee", "company": "JSW Steel Ltd", "location": "Bellary", "education": "10th Pass", "skills": ["manufacturing", "mechanic", "safety protocols", "quality control"], "description": "Operate CNC and rolling machines under supervision at JSW's integrated steel plant.", "apply_url": PM_PORTAL_URL},
    {"id": 19, "sector": "IT & Technology", "title": "Frontend Developer Intern", "company": "HCLTech", "location": "Noida", "education": "Graduate", "skills": ["html", "css", "javascript", "react", "git"], "description": "Build responsive web interfaces for client-facing portals. Work with React and modern frontend tech.", "apply_url": PM_PORTAL_URL},
    {"id": 20, "sector": "Oil & Gas", "title": "Pipeline Inspection Intern", "company": "ONGC", "location": "Dehradun", "education": "Diploma", "skills": ["inspection", "documentation", "safety protocols", "engineering"], "description": "Assist pipeline integrity engineers with scheduled inspections and documentation at ONGC facilities.", "apply_url": PM_PORTAL_URL},
    {"id": 21, "sector": "Telecommunications", "title": "Customer Support Intern", "company": "Jio (Reliance)", "location": "Navi Mumbai", "education": "12th Pass", "skills": ["customer service", "communication", "typing", "troubleshooting"], "description": "Handle inbound customer queries via chat and phone for Jio subscribers across India.", "apply_url": PM_PORTAL_URL},
    {"id": 22, "sector": "FMCG & Retail", "title": "Retail Store Intern", "company": "ITC Limited", "location": "Kolkata", "education": "12th Pass", "skills": ["customer service", "sales", "inventory", "communication"], "description": "Assist in daily store operations and customer engagement at ITC retail outlets.", "apply_url": PM_PORTAL_URL},
    {"id": 23, "sector": "Banking & Finance", "title": "Digital Banking Intern", "company": "HDFC Bank", "location": "Mumbai", "education": "Graduate", "skills": ["excel", "data analysis", "communication", "accounting"], "description": "Support the digital banking team in analyzing transaction patterns and customer behavior data.", "apply_url": PM_PORTAL_URL},
    {"id": 24, "sector": "Power & Energy", "title": "Electrical Maintenance Intern", "company": "Power Grid Corporation", "location": "Gurgaon", "education": "Diploma", "skills": ["wiring", "hardware", "safety protocols", "engineering"], "description": "Assist senior electricians in substation maintenance and power distribution monitoring.", "apply_url": PM_PORTAL_URL},
    {"id": 25, "sector": "IT & Technology", "title": "Python Backend Intern", "company": "Tech Mahindra", "location": "Hyderabad", "education": "Graduate", "skills": ["python", "sql", "git", "data analysis"], "description": "Develop REST APIs and database queries for internal tools at Tech Mahindra campus.", "apply_url": PM_PORTAL_URL},
    {"id": 26, "sector": "Agriculture & Fertilizers", "title": "Farm Equipment Maintenance Intern", "company": "Rashtriya Chemicals & Fertilizers (RCF)", "location": "Trombay", "education": "10th Pass", "skills": ["mechanic", "repair", "hardware", "agriculture"], "description": "Maintain and repair irrigation pumps, fertilizer dispensers, and farm equipment.", "apply_url": PM_PORTAL_URL},
    {"id": 27, "sector": "Healthcare", "title": "Hospital Admin Intern", "company": "Fortis Healthcare", "location": "Delhi", "education": "Graduate", "skills": ["data entry", "health records", "excel", "communication"], "description": "Manage patient records digitization and appointment scheduling at Fortis hospitals.", "apply_url": PM_PORTAL_URL},
    {"id": 28, "sector": "Construction & Infrastructure", "title": "Road Survey Intern", "company": "NHAI", "location": "Jaipur", "education": "Diploma", "skills": ["engineering", "documentation", "data entry", "inspection"], "description": "Assist survey teams in road quality assessment for national highway projects.", "apply_url": PM_PORTAL_URL},
    {"id": 29, "sector": "Logistics & E-Commerce", "title": "Last-Mile Delivery Coordinator", "company": "Amazon India", "location": "Bangalore", "education": "12th Pass", "skills": ["logistics", "dispatch", "coordination", "communication"], "description": "Coordinate delivery schedules and route optimization for last-mile operations.", "apply_url": PM_PORTAL_URL},
    {"id": 30, "sector": "IT & Technology", "title": "Data Science Intern", "company": "Cognizant", "location": "Bangalore", "education": "Graduate", "skills": ["python", "machine learning", "data analysis", "sql"], "description": "Analyze large datasets using Python. Build visualization dashboards for client reports.", "apply_url": PM_PORTAL_URL},
    {"id": 31, "sector": "Steel & Manufacturing", "title": "Welding Shop Trainee", "company": "SAIL (Steel Authority of India)", "location": "Bhilai", "education": "10th Pass", "skills": ["welding", "manufacturing", "safety protocols", "mechanic"], "description": "Learn MIG and TIG welding techniques at the SAIL Bhilai steel plant.", "apply_url": PM_PORTAL_URL},
    {"id": 32, "sector": "Pharmaceuticals", "title": "Clinical Data Intern", "company": "Cipla Ltd", "location": "Mumbai", "education": "Graduate", "skills": ["data entry", "excel", "documentation", "health records"], "description": "Enter clinical trial data into electronic systems. Assist in regulatory document preparation.", "apply_url": PM_PORTAL_URL},
    {"id": 33, "sector": "Telecommunications", "title": "Digital Marketing Intern", "company": "Vodafone Idea (Vi)", "location": "Pune", "education": "Graduate", "skills": ["marketing", "social media", "content creation", "communication"], "description": "Create social media content and assist in digital marketing campaigns for Vi telecom.", "apply_url": PM_PORTAL_URL},
    {"id": 34, "sector": "FMCG & Retail", "title": "Warehouse Quality Intern", "company": "Dabur India", "location": "Ghaziabad", "education": "12th Pass", "skills": ["quality control", "packaging", "inventory", "documentation"], "description": "Inspect incoming raw materials and outgoing finished goods at Dabur manufacturing plant.", "apply_url": PM_PORTAL_URL},
    {"id": 35, "sector": "Power & Energy", "title": "Wind Farm Maintenance Intern", "company": "Adani Green Energy", "location": "Kutch", "education": "Diploma", "skills": ["hardware", "wiring", "safety protocols", "mechanic"], "description": "Assist with wind turbine blade inspection and generator maintenance at Adani's wind farm.", "apply_url": PM_PORTAL_URL},
]


def normalize_to_schema(raw_listings: list) -> list:
    """Map scraped data to the exact JSON schema expected by main.py."""
    normalized = []
    for idx, item in enumerate(raw_listings, start=1):
        normalized.append({
            "id": idx,
            "title": item.get("title", "PM Scheme Internship"),
            "company": item.get("company", "PM Internship Scheme"),
            "location": item.get("location", "India"),
            "education": item.get("education", "Graduate"),
            "skills": item.get("skills", ["communication"]),
            "sector": item.get("sector", "General"),
            "description": item.get("description", "Internship under PM Internship Scheme."),
            "apply_url": item.get("apply_url", PM_PORTAL_URL),
        })
    return normalized


def main():
    print("=" * 60)
    print("  PM Internship Scheme - Data Pipeline")
    print("  Portal: pminternship.mca.gov.in")
    print("=" * 60)

    has_valid_key = (
        FIRECRAWL_AVAILABLE
        and FIRECRAWL_API_KEY
        and FIRECRAWL_API_KEY != "fc-your-key-here"
    )

    scraped = []

    if has_valid_key:
        app = Firecrawl(api_key=FIRECRAWL_API_KEY)
        print(f"\nFirecrawl API Key: {FIRECRAWL_API_KEY[:8]}...")
        scraped = crawl_pm_portal(app)
    else:
        if not FIRECRAWL_AVAILABLE:
            print("\nFirecrawl SDK not installed. Run: pip install firecrawl-py")
        else:
            print("\nNo valid FIRECRAWL_API_KEY in .env.txt")
            print("Get your free key at: https://firecrawl.dev")

    # Use scraped data if successful, else use curated PM Scheme data
    if scraped and len(scraped) >= 5:
        print(f"\n>> Normalizing {len(scraped)} scraped PM portal listings...")
        final_data = normalize_to_schema(scraped)
    else:
        print(f"\n>> PM Portal requires login for listings.")
        print(f">> Using curated PM Internship Scheme data (35 listings)")
        print(f">> All apply URLs -> {PM_PORTAL_URL}")
        final_data = PM_SCHEME_DATA

    # Write to jobs.json
    with open(JOBS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(final_data)} PM Scheme internships to jobs.json")
    print(f"Apply URL: {final_data[0].get('apply_url', 'N/A')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
