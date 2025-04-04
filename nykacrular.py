from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin
import random

# Product URL patterns
PRODUCT_PATTERNS = [
    r'/product/', r'/item/', r'/p/', r'/products/', r'/pd/',
    r'-pd-', r'/buy/', r'/shop/', r'productdetail', r'/collections/',
    r'/prod-', r'/item-', r'/detail/', r'/sku/', r'/view/', r'/Prod-', r'/productpage'
]

# Set up Selenium with headless Chrome
def initialize_driver():
    options = Options()
    options.add_argument("--headless")  # Run without opening a browser window
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--no-sandbox")  # Improve stability in some environments
    options.add_argument("--disable-dev-shm-usage")  # Avoid memory issues
    try:
        driver = webdriver.Chrome(options=options)  # Add executable_path if needed
        return driver
    except WebDriverException as e:
        print(f"Failed to initialize WebDriver: {e}")
        return None

# Base settings
base_url = "https://www.tatacliq.com/"
visited_urls = set()
product_urls = set()
urls_to_crawl = {base_url}

# Function to check if a URL is a product URL
def is_product_url(url):
    return any(pattern in url for pattern in PRODUCT_PATTERNS)

# Function to extract links from a page
def extract_links(driver, page_url):
    if page_url in visited_urls:
        return True
    
    print(f"Crawling: {page_url}")
    try:
        driver.get(page_url)
        time.sleep(random.uniform(2, 5))  # Random delay
        soup = BeautifulSoup(driver.page_source, "html.parser")
        visited_urls.add(page_url)

        # Find all <a> tags
        for link in soup.find_all("a", href=True):
            href = link["href"]
            full_url = urljoin(base_url, href)

            # Skip unwanted URLs
            if not full_url.startswith("https://www.tatacliq.com"):
                continue
            if any(x in full_url for x in ["login", "signup", "cart", "checkout", "account"]):
                continue

            # Check for product URLs
            if is_product_url(full_url) and full_url not in product_urls:
                product_urls.add(full_url)
                print(f"Found product: {full_url}")
            elif full_url not in visited_urls and full_url not in urls_to_crawl:
                urls_to_crawl.add(full_url)
        return True
    except WebDriverException as e:
        print(f"WebDriver error at {page_url}: {e}")
        return False
    except Exception as e:
        print(f"General error at {page_url}: {e}")
        return True  # Continue despite minor errors

# Main crawling loop
driver = initialize_driver()
if driver is None:
    print("Exiting due to driver initialization failure.")
    exit()

max_urls = 1000  # Adjust as needed
while urls_to_crawl and len(visited_urls) < max_urls:
    current_url = urls_to_crawl.pop()
    success = extract_links(driver, current_url)
    if not success:
        print("Restarting WebDriver due to failure...")
        driver.quit()
        driver = initialize_driver()
        if driver is None:
            print("Failed to restart WebDriver. Exiting.")
            break
        continue
    time.sleep(random.uniform(1, 3))  # Delay between pages

# Clean up
if driver:
    driver.quit()

# Save product URLs to a file
with open("nykaafashion_all_product_urls.txt", "w") as file:
    for url in sorted(product_urls):
        file.write(url + "\n")

print(f"Crawled {len(visited_urls)} pages. Found {len(product_urls)} product URLs.")
print("Results saved to nykaafashion_all_product_urls.txt")