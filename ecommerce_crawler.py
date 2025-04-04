import asyncio
import re
import logging
import random
from urllib.parse import urlparse, urljoin
from typing import List, Dict, Set, Optional
import json
import os
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("crawler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ecommerce_crawler")

# List of realistic user agents to rotate
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36'
]

class EcommerceCrawler:
    """
    Asynchronous web crawler using Playwright to discover product URLs on e-commerce websites.
    """
    
    def __init__(self, domains: List[str], max_pages_per_domain: int = 100, 
                 max_concurrent_tasks: int = 3, request_delay: float = 5.0,
                 random_delay: bool = True):
        """
        Initialize the crawler with a list of domains to crawl.
        
        Args:
            domains: List of e-commerce website domains to crawl
            max_pages_per_domain: Maximum number of pages to crawl per domain
            max_concurrent_tasks: Maximum number of concurrent browser tasks
            request_delay: Base delay between requests to the same domain (in seconds)
            random_delay: Add random delay to appear more human-like
        """
        self.domains = domains
        self.max_pages_per_domain = max_pages_per_domain
        self.max_concurrent_tasks = max_concurrent_tasks
        self.request_delay = request_delay
        self.random_delay = random_delay
        
        # Dictionary to store product URLs and visited URLs for each domain
        self.product_urls: Dict[str, Set[str]] = {domain: set() for domain in domains}
        self.visited_urls: Dict[str, Set[str]] = {domain: set() for domain in domains}
        
        # Common product URL patterns
        self.product_patterns = [
            r'/product/', r'/item/', r'/p/', r'/products/', r'/pd/', 
            r'-pd-', r'/buy/', r'/shop/', r'productdetail', r'/collections/',
            r'/prod-', r'/item-', r'/detail/', r'/sku/', r'/view/', r'/Prod-', r'/productpage'
        ]
        
        # Domain-specific patterns
        self.domain_specific_patterns = {
            'tatacliq.com': [r'/p-mp', r'/product-details/', r'/p-'],
            'nykaafashion.com': [r'/product/', r'/p/', r'/[a-zA-Z0-9-]+/p/\d+']
        }
        
        # Semaphore to limit concurrent tasks
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        
        # Browser context options for stealth
        self.context_options = {
            "viewport": {"width": 1920, "height": 1080},
            "device_scale_factor": 1,
            "java_script_enabled": True,
            "has_touch": False,
            "locale": "en-US",
            "timezone_id": "America/New_York",
        }

    async def is_product_url(self, url: str, domain: str) -> bool:
        """
        Check if a URL is a product URL based on patterns.
        """
        # Check domain-specific patterns first
        domain_key = next((key for key in self.domain_specific_patterns if key in domain), None)
        if domain_key:
            for pattern in self.domain_specific_patterns[domain_key]:
                if re.search(pattern, url):
                    return True
        
        # Check common patterns
        for pattern in self.product_patterns:
            if re.search(pattern, url):
                return True
                
        # Heuristic: Numeric ID in the last path segment, excluding categories
        path = urlparse(url).path
        last_segment = path.split('/')[-1]
        if re.search(r'\d+', last_segment) and 'category' not in path.lower():
            return True
            
        return False

    async def fetch_page(self, url: str, browser_context) -> Optional[str]:
        """
        Fetch a page's HTML content using Playwright with stealth techniques.
        """
        domain = urlparse(url).netloc
        
        try:
            async with self.semaphore:
                # Create a new page with a fresh user agent
                page = await browser_context.new_page()
                
                # Set a random user agent
                await page.set_extra_http_headers({
                    'User-Agent': random.choice(USER_AGENTS),
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0'
                })
                
                # Emulate human-like behavior before navigating
                await asyncio.sleep(random.uniform(1, 3))
                
                logger.info(f"Fetching {url}")
                # Use a longer timeout for initial load
                response = await page.goto(
                    url, 
                    wait_until="networkidle", 
                    timeout=60000
                )
                
                # Check response status
                if not response or response.status >= 400:
                    logger.warning(f"Failed to load {url}: Status {response.status if response else 'No response'}")
                    await page.close()
                    return None
                
                # Wait a bit longer for any dynamic content to load
                await asyncio.sleep(random.uniform(2, 4))
                
                # Scroll down the page to simulate human behavior and load lazy content
                await self._scroll_page(page)
                
                # Get the final HTML content
                html = await page.content()
                await page.close()
                
                # Apply delay with some randomness to appear more human-like
                delay = self.request_delay
                if self.random_delay:
                    delay += random.uniform(1, 5)
                    
                await asyncio.sleep(delay)
                return html
                
        except PlaywrightTimeoutError:
            logger.warning(f"Timeout fetching {url}")
            return None
        except Exception as e:
            logger.warning(f"Error fetching {url}: {str(e)}")
            return None

    async def _scroll_page(self, page):
        """Scroll the page to simulate human behavior and load lazy content."""
        try:
            # Get page height
            height = await page.evaluate('document.body.scrollHeight')
            
            # Scroll in chunks
            view_port_height = 1080
            chunks = int(height / view_port_height)
            
            for i in range(min(chunks, 3)):  # Limit to 3 scrolls to avoid excessive time
                await page.evaluate(f'window.scrollTo(0, {(i+1) * view_port_height})')
                # Random pause between scrolls
                await asyncio.sleep(random.uniform(0.5, 1.5))
                
            # Scroll back to top
            await page.evaluate('window.scrollTo(0, 0)')
            await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.warning(f"Error during page scrolling: {str(e)}")

    async def extract_links(self, html: str, base_url: str) -> List[str]:
        """
        Extract all links from a page's HTML.
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href')
            if href:
                # Skip javascript events and anchors
                if href.startswith('javascript:') or href.startswith('#'):
                    continue
                    
                absolute_url = urljoin(base_url, href)
                base_domain = urlparse(base_url).netloc
                
                # Only include URLs from the same domain
                if urlparse(absolute_url).netloc == base_domain:
                    # Normalize URL by removing fragments
                    normalized_url = absolute_url.split('#')[0]
                    links.append(normalized_url)
                    
        return links

    async def crawl_page(self, url: str, domain: str, browser_context, depth: int = 0) -> None:
        """
        Crawl a page and its links recursively.
        """
        if url in self.visited_urls[domain] or len(self.visited_urls[domain]) >= self.max_pages_per_domain:
            return
            
        self.visited_urls[domain].add(url)
        
        # Check if this is a product URL
        if await self.is_product_url(url, domain):
            self.product_urls[domain].add(url)
            logger.info(f"Found product URL: {url}")
        
        # Fetch the page
        html = await self.fetch_page(url, browser_context)
        if not html:
            return
            
        # Extract links
        links = await self.extract_links(html, url)
        
        # Prioritize links that look like they lead to product listings
        priority_patterns = ['/category/', '/collection/', '/shop/', '/department/', '/collections/', '/products/', '/categories/']
        priority_links = [link for link in links if any(pattern in link for pattern in priority_patterns)]
        other_links = [link for link in links if link not in priority_links]
        
        # Sort links to prioritize product listings first
        sorted_links = priority_links + other_links
        
        # Create tasks for each link
        tasks = []
        for link in sorted_links:
            if link not in self.visited_urls[domain] and depth < 2:  # Limit depth
                task = asyncio.create_task(self.crawl_page(link, domain, browser_context, depth + 1))
                tasks.append(task)
                
        if tasks:
            await asyncio.gather(*tasks)

    async def crawl_domain(self, domain: str, browser) -> None:
        """
        Crawl a single domain with a dedicated browser context.
        """
        base_url = f"https://{domain}" if not domain.startswith(('http://', 'https://')) else domain
        netloc = urlparse(base_url).netloc
        
        logger.info(f"Starting crawl of {domain}")
        
        # Create a fresh browser context with privacy settings
        context = await browser.new_context(**self.context_options)
        
        # Set cookie acceptance to appear more like a normal visitor
        cookies = [
            {"name": "cookie_consent", "value": "accepted", "domain": netloc, "path": "/"},
            {"name": "privacy_settings", "value": "accepted", "domain": netloc, "path": "/"}
        ]
        await context.add_cookies(cookies)
        
        try:
            await self.crawl_page(base_url, netloc, context)
            logger.info(f"Completed crawl of {domain}. Found {len(self.product_urls[netloc])} product URLs.")
        finally:
            await context.close()

    async def run(self) -> Dict[str, List[str]]:
        """
        Run the crawler for all domains.
        """
        async with async_playwright() as p:
            # Launch browser with additional arguments to avoid detection
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--user-agent=' + random.choice(USER_AGENTS),
                    '--disable-http2',
                    '--no-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )
            
            # Process domains sequentially to reduce load
            for domain in self.domains:
                await self.crawl_domain(domain, browser)
                
            await browser.close()
        
        # Convert sets to lists for serialization
        results = {domain: list(urls) for domain, urls in self.product_urls.items()}
        return results

    def save_results(self, output_file: str = "product_urls.json") -> None:
        """
        Save the results to a JSON file.
        """
        results = {domain: list(urls) for domain, urls in self.product_urls.items()}
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {output_file}")

async def main():
    """
    Main function to run the crawler.
    """
    domains = [
        "www.hm.com"
    ]
    
    crawler = EcommerceCrawler(
        domains=domains,
        max_pages_per_domain=5000,    # Start with a smaller number for testing
        max_concurrent_tasks=2,     # Reduced from 5 to avoid overwhelming the server
        request_delay=2.0,          # Increased delay to be more respectful
        random_delay=True           # Add random delays
    )
    
    # Run the crawler
    results = await crawler.run()
    
    # Save the results
    crawler.save_results()
    
    # Print summary
    for domain, urls in results.items():
        print(f"{domain}: Found {len(urls)} product URLs")

if __name__ == "__main__":
    asyncio.run(main())