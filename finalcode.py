import asyncio
import re
import logging
import random
from urllib.parse import urlparse, urljoin
from typing import List, Dict, Set, Optional
import json
import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("crawler.log"), logging.StreamHandler()]
)
logger = logging.getLogger("ecommerce_crawler")

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
]

class EcommerceCrawler:
    def __init__(self, domains: List[str], max_pages_per_domain: int = 10000,
                 max_concurrent_tasks: int = 4, request_delay: float = 3.0,
                 random_delay: bool = True):
        self.domains = domains
        self.max_pages_per_domain = max_pages_per_domain
        self.max_concurrent_tasks = max_concurrent_tasks
        self.request_delay = request_delay
        self.random_delay = random_delay
        
        self.product_urls: Dict[str, Set[str]] = {domain: set() for domain in domains}
        self.visited_urls: Dict[str, Set[str]] = {domain: set() for domain in domains}
        
        self.product_patterns = [
            r'/product/', r'/item/', r'/p/', r'/products/', r'/pd/', 
            r'-pd-', r'/buy/', r'/shop/', r'productdetail', r'/collections/',
            r'/prod-', r'/item-', r'/detail/', r'/sku/', r'/view/', 
            r'/Prod-', r'/productpage', r'[a-zA-Z0-9-]+-p-\d+'
        ]
        
        self.domain_specific_patterns = {
            'tatacliq.com': [r'/p-mp', r'/product-details/', r'/p-'],
            'nykaafashion.com': [r'/product/', r'/p/', r'/[a-zA-Z0-9-]+/p/\d+'],
            'virgio.com': [r'/shop/', r'/[a-zA-Z0-9-]+-p-\d+'],
            'westside.com': [r'/products/', r'/[a-zA-Z0-9-]+-pid-\d+']
        }
        
        self.pagination_patterns = [
            r'page=\d+', r'/page/\d+', r'p=\d+', r'offset=\d+', 
            r'pageNumber=\d+', r'pg=\d+'
        ]
        
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._shutdown = False

    def _initialize_driver(self):
        options = Options()
        options.add_argument("--headless")
        options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        try:
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(60)
            return driver
        except WebDriverException as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            return None

    async def is_product_url(self, url: str, domain: str) -> bool:
        if self._shutdown:
            return False
        domain_key = next((key for key in self.domain_specific_patterns if key in domain), None)
        if domain_key:
            for pattern in self.domain_specific_patterns[domain_key]:
                if re.search(pattern, url):
                    return True
        
        for pattern in self.product_patterns:
            if re.search(pattern, url):
                return True
                
        path = urlparse(url).path
        last_segment = path.split('/')[-1]
        if (re.search(r'\d+', last_segment) and 
            'category' not in path.lower() and 
            'collection' not in path.lower()):
            return True
        return False

    async def is_pagination_url(self, url: str) -> bool:
        if self._shutdown:
            return False
        return any(re.search(pattern, url) for pattern in self.pagination_patterns)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_page(self, url: str, driver) -> Optional[str]:
        if self._shutdown:
            return None
            
        domain = urlparse(url).netloc
        
        async with self.semaphore:
            try:
                await asyncio.sleep(random.uniform(1, 3))
                logger.info(f"Fetching {url}")
                
                driver.get(url)
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                await self._scroll_page(driver)
                html = driver.page_source
                
                delay = self.request_delay + (random.uniform(1, 5) if self.random_delay else 0)
                await asyncio.sleep(delay)
                return html
                
            except TimeoutException:
                logger.warning(f"Timeout fetching {url}")
                raise
            except Exception as e:
                logger.error(f"Error fetching {url}: {str(e)}")
                return None

    async def _scroll_page(self, driver):
        try:
            height = driver.execute_script("return document.body.scrollHeight")
            view_port_height = 1080
            chunks = min(int(height / view_port_height), 5)
            
            for i in range(chunks):
                driver.execute_script(f"window.scrollTo(0, {(i+1) * view_port_height})")
                await asyncio.sleep(random.uniform(0.5, 1.5))
                
            driver.execute_script("window.scrollTo(0, 0)")
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.warning(f"Error during page scrolling: {str(e)}")

    async def extract_links(self, html: str, base_url: str) -> List[str]:
        if self._shutdown:
            return []
            
        soup = BeautifulSoup(html, 'html.parser')
        links = set()
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href')
            if not href or href.startswith(('javascript:', '#')):
                continue
                
            absolute_url = urljoin(base_url, href).split('#')[0]
            if urlparse(absolute_url).netloc == urlparse(base_url).netloc:
                links.add(absolute_url)
                
        return list(links)

    async def crawl_page(self, url: str, domain: str, driver, depth: int = 0, priority: int = 0) -> None:
        if self._shutdown or url in self.visited_urls[domain] or len(self.visited_urls[domain]) >= self.max_pages_per_domain:
            return
            
        self.visited_urls[domain].add(url)
        
        is_product = await self.is_product_url(url, domain)
        if is_product:
            self.product_urls[domain].add(url)
            logger.info(f"Found product URL: {url}")
        
        html = await self.fetch_page(url, driver)
        if not html:
            return
            
        links = await self.extract_links(html, url)
        
        priority_links = []
        pagination_links = []
        other_links = []
        
        for link in links:
            if await self.is_pagination_url(link):
                pagination_links.append((link, 3))
            elif any(p in link for p in ['/category/', '/collection/', '/shop/', '/products/']):
                priority_links.append((link, 2))
            else:
                other_links.append((link, 1))
        
        sorted_links = (pagination_links + priority_links + other_links)
        sorted_links.sort(key=lambda x: x[1], reverse=True)
        
        tasks = []
        for link, _ in sorted_links[:50]:
            if link not in self.visited_urls[domain] and depth < 3:
                tasks.append(asyncio.create_task(self.crawl_page(link, domain, driver, depth + 1)))
                
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def crawl_domain(self, domain: str) -> None:
        if self._shutdown:
            return
            
        base_url = f"https://{domain}" if not domain.startswith(('http://', 'https://')) else domain
        netloc = urlparse(base_url).netloc
        
        logger.info(f"Starting crawl of {domain}")
        driver = self._initialize_driver()
        if not driver:
            return
            
        try:
            await self.crawl_page(base_url, netloc, driver)
            logger.info(f"Completed crawl of {domain}. Found {len(self.product_urls[netloc])} product URLs.")
        except Exception as e:
            logger.error(f"Error crawling {domain}: {str(e)}")
        finally:
            driver.quit()

    async def run(self) -> Dict[str, List[str]]:
        tasks = [self.crawl_domain(domain) for domain in self.domains]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return {domain: list(urls) for domain, urls in self.product_urls.items()}

    def save_results(self, output_file: str = "product_urls.json") -> None:
        if self._shutdown:
            return
        results = {domain: list(urls) for domain, urls in self.product_urls.items()}
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {output_file}")

    async def shutdown(self):
        self._shutdown = True
        await asyncio.sleep(1)

async def main():
    domains = [
        "www.virgio.com",
        "www.tatacliq.com",
        "nykaafashion.com",
        "www.westside.com"
    ]
    
    crawler = EcommerceCrawler(
        domains=domains,
        max_pages_per_domain=10,
        max_concurrent_tasks=4,
        request_delay=3.0,
        random_delay=True
    )
    
    try:
        results = await crawler.run()
        crawler.save_results()
        
        for domain, urls in results.items():
            print(f"{domain}: Found {len(urls)} product URLs")
    except Exception as e:
        logger.error(f"Main execution failed: {str(e)}")
    finally:
        await crawler.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Program failed: {str(e)}")
    finally:
        if 'crawler' in locals():
            asyncio.run(crawler.shutdown())
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.stop()
        sys.exit(0)


