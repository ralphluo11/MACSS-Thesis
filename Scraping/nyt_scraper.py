"""
NYT Article Scraper for the thesis corpus (2020-2024).

Pipeline:
  1. Iterate month-by-month over the NYT Archive API.
  2. Filter to relevant news desks and apply keyword matching against a
     keyword CSV (combined_china_keywords.csv or combined_russia_keywords.csv)
     to identify articles related to the target country.
  3. Scrape full text for the filtered subset using a dual approach:
     (a) requests + browser_cookie3 cookies; (b) headless Selenium fallback.

Usage:
  1. Get a NYT Developer API key: https://developer.nytimes.com
  2. export NYT_API_KEY=your_key_here
  3. pip install requests pandas beautifulsoup4 browser_cookie3 selenium fake-useragent
  4. Ensure Chrome is installed (Selenium requires it).
  5. Be logged into nytimes.com in the same Chrome profile (browser_cookie3
     reads cookies from disk to bypass the paywall on subscriber-accessible
     content).
  6. Run from the command line:
        python nyt_scraper.py --start 2020-01 --end 2020-12 \\
            --keywords combined_china_keywords.csv

Output:
  - all_article_metadata_<year>.csv          (full metadata for each year)
  - <subset>_articles_fulltext_<start>_to_<end>.csv  (filtered corpus with full text)

The full corpus (China + Russia, 2020-2024) was produced by running this
script year-by-year for each keyword subset, yielding:
  - 5,396 China-related articles
  - 7,009 Russia-related articles

References:
  - NYT Archive API: https://developer.nytimes.com/docs/archive-product/1/overview
  - Selenium: https://selenium-python.readthedocs.io/
  - browser_cookie3: https://pypi.org/project/browser-cookie3/
  - fake-useragent: https://pypi.org/project/fake-useragent/

AI was used only for code comments and minor refactoring.
"""

import argparse
import datetime
import logging
import os
import re
import time

import browser_cookie3
import pandas as pd
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# API configuration
API_KEY = os.environ.get('NYT_API_KEY')
if not API_KEY:
    raise RuntimeError(
        "NYT_API_KEY environment variable not set. "
        "Get a key at https://developer.nytimes.com and run "
        "`export NYT_API_KEY=your_key` before invoking this script."
    )

ARCHIVE_BASE_URL = 'https://api.nytimes.com/svc/archive/v1'

# Academic User-Agent that identifies the project transparently to NYT.
# Replace the email with your own contact address before running.
ACADEMIC_UA = (
    "MACSS-Thesis-Research/1.0 "
    "(jiahangluo@uchicago.edu; non-commercial academic research)"
)

# Load NYT cookies from local Chrome profile (requires you to be logged in)
nyt_cookies = browser_cookie3.chrome(domain_name='nytimes.com')
NYT_COOKIES = {cookie.name: cookie.value for cookie in nyt_cookies}


# Load keyword list from CSV
def load_keywords(csv_file):
    """Load and return a list of lowercased keywords from a CSV file.

    The CSV is expected to have a column named 'keyword'.
    """
    df = pd.read_csv(csv_file)
    return df["keyword"].str.lower().tolist()


# Text normalization
def normalize_text(text):
    """Lowercase the text and strip non-word characters."""
    if text:
        return ' '.join(re.findall(r'\b\w+\b', text.lower())).strip()
    return ''


# Relevant news desks for the analysis (drops Style, Sports, Arts, etc.)
relevant_news_desks = {
    "Foreign", "Politics", "Opinion", "World", "National", "Washington",
    "Business", "Technology", "Science", "Climate", "Investigative",
    "Editorial", "Upshot", "SundayBusiness", "Real Estate", "Podcasts",
    "Briefing", "Photos", "Business Day", "NYTNow", "Election Analytics"
}


def is_relevant_article(article):
    """Check whether the article belongs to one of the relevant news desks."""
    news_desk = article.get("news_desk", "").strip()
    return not news_desk or news_desk in relevant_news_desks


def is_keyword_match(article, keywords):
    """Determine whether the article matches the keyword list in headline or
    abstract."""
    headline = article.get("headline", {}).get("main", "")
    abstract = article.get("abstract", "")

    normalized_headline = normalize_text(headline)
    normalized_abstract = normalize_text(abstract)

    headline_match = any(
        re.search(rf'\b{re.escape(keyword)}\b', normalized_headline)
        for keyword in keywords
    )
    abstract_match = any(
        re.search(rf'\b{re.escape(keyword)}\b', normalized_abstract)
        for keyword in keywords
    )

    return headline_match or abstract_match


# Headless Chrome WebDriver (used as fallback when direct requests fail)
def init_headless_selenium():
    """Initialize a headless Chrome WebDriver with anti-detection settings."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-notifications")

    # Identify the scraper transparently to NYT for academic purposes
    options.add_argument(f"user-agent={ACADEMIC_UA}")
    options.add_argument("--window-size=1920,1080")

    # Disable image loading for performance
    prefs = {
        "profile.managed_default_content_settings.images": 2,
    }
    options.add_experimental_option("prefs", prefs)

    return webdriver.Chrome(options=options)


# Full-text scraping with dual-approach fallback
def scrape_full_text(url, document_type, max_retries=3):
    """Scrape full text from a NYT URL.

    First attempts a direct HTTP request with cookies; on failure or paywall,
    falls back to headless Selenium with retry and exponential backoff.
    """
    if document_type == "multimedia":
        return None

    # First try with requests for efficiency
    try:
        response = requests.get(
            url,
            headers={"User-Agent": ACADEMIC_UA},
            cookies=NYT_COOKIES,
            timeout=10
        )

        if response.status_code == 200 and "verify you're not a robot" not in response.text.lower():
            return extract_text_from_response(response.content)
    except Exception as e:
        logging.warning(f"Initial request failed, switching to headless: {e}")

    # Fallback: headless browser with retries
    for attempt in range(max_retries):
        driver = None
        try:
            driver = init_headless_selenium()
            driver.set_page_load_timeout(20)
            driver.get(url)

            # Wait for paragraphs to load
            wait = WebDriverWait(driver, 20)
            wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "p")))

            # Handle bot verification if it appears
            if "verify you're not a robot" in driver.page_source.lower():
                logging.warning(f"Verification detected on attempt {attempt + 1}")
                handle_verification(driver)

            full_text = extract_text_from_driver(driver)

            if is_valid_text(full_text):
                return full_text

        except Exception as e:
            logging.error(f"Attempt {attempt + 1} failed: {e}", exc_info=True)
            if attempt == max_retries - 1:
                return None
            time.sleep(2 ** attempt)  # Exponential backoff

        finally:
            if driver:
                driver.quit()


# Helper functions for text extraction
def extract_text_from_response(content):
    """Extract joined paragraph text from raw HTML response content."""
    soup = BeautifulSoup(content, "html.parser")
    paragraphs = soup.find_all("p")
    return " ".join(p.get_text().strip() for p in paragraphs if p.text.strip())


def extract_text_from_driver(driver):
    """Extract joined paragraph text from a Selenium WebDriver instance."""
    paragraphs = driver.find_elements(By.TAG_NAME, "p")
    return " ".join(p.text for p in paragraphs if p.text.strip())


def is_valid_text(text):
    """Validate that the extracted text is substantive (>= 10 words)."""
    return text and len(text.split()) >= 10


def handle_verification(driver):
    """Pause to allow time for bot-verification to clear."""
    logging.warning("Verification handling...")
    time.sleep(5)


# Fetch articles from NYT Archive API
def fetch_articles_with_archive(year, month):
    """Fetch all articles for a given month from the NYT Archive API.

    Implements exponential backoff on rate-limit (HTTP 429) responses.
    """
    logging.info(f"Fetching articles for {year}-{month:02d}...")
    url = f"{ARCHIVE_BASE_URL}/{year}/{month}.json"
    params = {'api-key': API_KEY}

    retries = 0
    max_retries = 10
    base_delay = 2

    while retries < max_retries:
        response = requests.get(url, params=params)

        if response.status_code == 200:
            return response.json()['response']['docs']
        elif response.status_code == 429:
            wait_time = min(base_delay * (2 ** retries), 60)
            logging.warning(
                f"Rate limit exceeded for {year}-{month:02d}. "
                f"Retrying in {wait_time} seconds..."
            )
            time.sleep(wait_time)
            retries += 1
        else:
            logging.error(f"Error {response.status_code} for {year}-{month:02d}")
            return []

    logging.error(
        f"Failed to fetch articles for {year}-{month:02d} after {max_retries} retries."
    )
    return []


# Parse article metadata
def parse_articles_first_pass(articles, keywords):
    """Extract structured metadata from raw API article records.

    Each row carries a boolean `is_keyword_match` flag indicating whether the
    article's headline or abstract matches the supplied keyword list.
    """
    parsed_articles = []
    seen_urls = set()

    for article in articles:
        if is_relevant_article(article):
            web_url = article.get("web_url", "")
            if web_url in seen_urls:
                continue
            seen_urls.add(web_url)

            document_type = article.get("document_type", "").lower()
            news_desk = article.get("news_desk", "").strip() or "Unknown"

            article_info = {
                'headline': article.get("headline", {}).get("main", None),
                'pub_date': article.get('pub_date', None),
                'web_url': web_url,
                'news_desk': news_desk,
                'document_type': document_type,
                'snippet': article.get('snippet', None),
                'abstract': article.get('abstract', None),
                'lead_paragraph': article.get('lead_paragraph', None),
                'is_keyword_match': is_keyword_match(article, keywords)
            }
            parsed_articles.append(article_info)

    return pd.DataFrame(parsed_articles)


# Add full text to filtered article subset
def add_full_text_to_all_articles(df):
    """Fetch full text for every article in the DataFrame.

    Adds a `full_text` column. Articles for which extraction fails (paywall,
    geo-block, removed pages, multimedia) are retained with NaN.
    """
    logging.info("Fetching full text for all articles...")

    df = df.copy()
    total = len(df)
    for i, (idx, row) in enumerate(df.iterrows(), 1):
        date = row['pub_date'].split('T')[0] if row['pub_date'] else 'Unknown'
        full_text = scrape_full_text(row['web_url'], row['document_type'])
        df.at[idx, 'full_text'] = full_text

        if full_text:
            logging.info(f"Article {i}/{total} [{date}]: Success ({len(full_text.split())} words)")
        else:
            logging.warning(f"Article {i}/{total} [{date}]: Failed")

        time.sleep(1)  # Throttle to avoid rate-limit bans
    return df


# Main pipeline
def main(start_year, start_month, end_year, end_month, keyword_csv, subset_label):
    """Run the full scrape pipeline for a date range and a keyword list.

    Parameters
    ----------
    start_year, start_month : int
    end_year, end_month : int
    keyword_csv : str
        Path to a CSV with a 'keyword' column (e.g. combined_china_keywords.csv).
    subset_label : str
        Short label for output filenames (e.g. 'China', 'Russia').
    """
    keywords = load_keywords(keyword_csv)
    logging.info(f"Loaded {len(keywords)} keywords from {keyword_csv}")

    start_date = datetime.date(start_year, start_month, 1)
    end_date = datetime.date(end_year, end_month, 1)

    current = start_date
    all_articles = []
    month_count = 0

    # Phase 1: iterate over months and fetch article metadata via the API
    while current <= end_date:
        month_count += 1
        year, month = current.year, current.month
        logging.info(f"Fetching articles for {year}-{month:02d}...")
        all_articles.extend(fetch_articles_with_archive(year, month))

        if month_count % 3 == 0:
            logging.info("Pausing for 10 seconds to respect API rate limits...")
            time.sleep(10)

        if month == 12:
            current = datetime.date(year + 1, 1, 1)
        else:
            current = datetime.date(year, month + 1, 1)

    # Phase 2: parse metadata, filter by keywords, and scrape full text
    if all_articles:
        logging.info("Parsing all articles (metadata only)...")
        all_articles_df = parse_articles_first_pass(all_articles, keywords)

        # Save a metadata-only backup (no full text)
        meta_filename = f'all_article_metadata_{start_year}.csv'
        all_articles_df.to_csv(meta_filename, index=False)
        logging.info(f"Metadata saved to {meta_filename}. "
                     f"Total articles found: {len(all_articles_df)}")

        # Filter to keyword-matching articles
        filtered_df = all_articles_df[all_articles_df['is_keyword_match'] == True].copy()
        filtered_count = len(filtered_df)

        logging.info(
            f"Filtered down to {filtered_count} {subset_label}-related articles."
        )

        if filtered_count > 0:
            # Scrape full text only for the filtered subset
            logging.info(f"Starting full-text scraping for {filtered_count} articles...")
            with_text = add_full_text_to_all_articles(filtered_df)

            # Save final results
            filename = (
                f'{subset_label}_articles_fulltext_'
                f'{start_year}{start_month:02d}_to_{end_year}{end_month:02d}.csv'
            )
            with_text.to_csv(filename, index=False)
            logging.info(f"Done. Saved to {filename}")
        else:
            logging.info(f"No {subset_label}-related articles found in this period.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="NYT Archive API scraper with keyword filtering and full-text retrieval."
    )
    parser.add_argument(
        "--start", required=True,
        help="Start year-month, format YYYY-MM (e.g. 2020-01)"
    )
    parser.add_argument(
        "--end", required=True,
        help="End year-month, format YYYY-MM (e.g. 2020-12)"
    )
    parser.add_argument(
        "--keywords", required=True,
        help="Path to keyword CSV (combined_china_keywords.csv or combined_russia_keywords.csv)"
    )
    parser.add_argument(
        "--label", default=None,
        help="Subset label for output filenames (default: inferred from keyword filename)"
    )
    args = parser.parse_args()

    sy, sm = map(int, args.start.split("-"))
    ey, em = map(int, args.end.split("-"))

    # Infer label from keyword filename if not given
    # (e.g. combined_china_keywords.csv -> "China")
    label = args.label
    if label is None:
        base = os.path.basename(args.keywords).lower()
        if "china" in base:
            label = "China"
        elif "russia" in base:
            label = "Russia"
        else:
            label = "Subset"

    main(sy, sm, ey, em, args.keywords, label)
