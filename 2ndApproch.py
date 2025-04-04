import asyncio
import re
import logging
from urllib.parse import urlparse, urljoin
from typing import List, Dict, Set, Optional
import aiohttp
from bs4 import BeautifulSoup
import json
import os
import time
from aiohttp import ClientSession

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

class EcommerceCrawler:
    """
    Asynchronous web crawler designed to discover product URLs on e-commerce websites.
    """
    
    def __init__(self, domains: List[str], max_pages_per_domain: int = 1000, 
                 max_concurrent_requests: int = 20, request_delay: float = 0.5):
        """
        Initialize the crawler with a list of domains to crawl.
        
        Args:
            domains: List of e-commerce website domains to crawl
            max_pages_per_domain: Maximum number of pages to crawl per domain
            max_concurrent_requests: Maximum number of concurrent requests
            request_delay: Delay between requests to the same domain (in seconds)
        """
        self.domains = domains
        self.max_pages_per_domain = max_pages_per_domain
        self.max_concurrent_requests = max_concurrent_requests
        self.request_delay = request_delay
        
        # Dictionary to store product URLs for each domain
        self.product_urls: Dict[str, Set[str]] = {domain: set() for domain in domains}
        
        # Dictionary to track visited URLs for each domain
        self.visited_urls: Dict[str, Set[str]] = {domain: set() for domain in domains}
        
        # Common product URL patterns
        self.product_patterns = [
            r'/product/', r'/item/', r'/p/', r'/products/', r'/pd/', 
            r'-pd-', r'/buy/', r'/shop/', r'productdetail', r'/collections/',
            r'/prod-', r'/item-', r'/detail/', r'/sku/', r'/view/', r'/Prod-', r'/sitemaps'
        ]
        
        # Domain-specific patterns
        self.domain_specific_patterns = {
            'virgio.com': [r'/products/'],
            'tatacliq.com': [r'/product-details/', r'/p-'],
            'nykaafashion.com': [r'/product/', r'/p/'],
            'westside.com': [r'/products/', r'/collections/']
        }
        
        # Semaphores to limit concurrent requests (per domain)
        self.domain_semaphores = {
            domain: asyncio.Semaphore(max_concurrent_requests) for domain in domains
        }
        
        # Keep track of the last request time for each domain
        self.last_request_time = {domain: 0 for domain in domains}

    async def is_product_url(self, url: str, domain: str) -> bool:
        """
        Check if a URL is a product URL based on patterns.
        
        Args:
            url: URL to check
            domain: Domain the URL belongs to
            
        Returns:
            bool: True if URL is a product URL, False otherwise
        """
        # Check domain-specific patterns first
        domain_key = None
        for key in self.domain_specific_patterns:
            if key in domain:
                domain_key = key
                break
        
        if domain_key:
            for pattern in self.domain_specific_patterns[domain_key]:
                if re.search(pattern, url):
                    return True
        
        # Check common patterns
        for pattern in self.product_patterns:
            if re.search(pattern, url):
                return True
                
        # Additional heuristics
        # Check for numeric IDs in the last path segment
        path = urlparse(url).path
        last_segment = path.split('/')[-1]
        if re.search(r'\d+', last_segment) and ('category' not in path.lower() and 'collection' not in path.lower()):
            return True
            
        return False

    async def fetch_page(self, url: str, session: ClientSession) -> Optional[str]:
        """
        Fetch a page's HTML content.
        
        Args:
            url: URL to fetch
            session: aiohttp ClientSession
            
        Returns:
            str: HTML content or None if request failed
        """
        domain = urlparse(url).netloc
        
        # Rate limiting per domain
        now = time.time()
        time_since_last_request = now - self.last_request_time[domain]
        if time_since_last_request < self.request_delay:
            await asyncio.sleep(self.request_delay - time_since_last_request)
        self.last_request_time[domain] = time.time()
        
        try:
            async with session.get(url, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5'
            }) as response:
                if response.status != 200:
                    logger.warning(f"Failed to fetch {url}: HTTP {response.status}")
                    return None
                    
                # Check if the content type is HTML
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' not in content_type:
                    logger.debug(f"Skipping non-HTML content: {url} (Content-Type: {content_type})")
                    return None
                    
                return await response.text()
        except asyncio.TimeoutError:
            logger.warning(f"Timeout when fetching {url}")
            return None
        except Exception as e:
            logger.warning(f"Error fetching {url}: {str(e)}")
            return None

    async def extract_links(self, html: str, base_url: str) -> List[str]:
        """
        Extract all links from a page.
        
        Args:
            html: HTML content
            base_url: Base URL for resolving relative links
            
        Returns:
            List[str]: List of absolute URLs found
        """
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href')
            if href:
                absolute_url = urljoin(base_url, href)
                # Ensure the URL is from the same domain
                if urlparse(absolute_url).netloc == urlparse(base_url).netloc:
                    links.append(absolute_url)
                    
        return links

    async def crawl_page(self, url: str, domain: str, session: ClientSession, depth: int = 0) -> None:
        """
        Crawl a page and its links recursively.
        
        Args:
            url: URL to crawl
            domain: Domain the URL belongs to
            session: aiohttp ClientSession
            depth: Current crawl depth
        """
        # Skip if we've already visited this URL
        if url in self.visited_urls[domain]:
            return
            
        # Skip if we've reached the maximum number of pages for this domain
        if len(self.visited_urls[domain]) >= self.max_pages_per_domain:
            return
            
        # Add to visited URLs
        self.visited_urls[domain].add(url)
        
        # Check if this is a product URL
        if await self.is_product_url(url, domain):
            self.product_urls[domain].add(url)
            logger.info(f"Found product URL: {url}")
        
        # Fetch the page
        async with self.domain_semaphores[domain]:
            html = await self.fetch_page(url, session)
            
        if not html:
            return
            
        # Extract links
        links = await self.extract_links(html, url)
        
        # Create tasks for each link
        tasks = []
        for link in links:
            # Skip URLs we've already visited
            if link in self.visited_urls[domain]:
                continue
                
            # Limit crawl depth
            if depth < 3:  # Adjust max depth as needed
                task = asyncio.create_task(self.crawl_page(link, domain, session, depth + 1))
                tasks.append(task)
                
        # Wait for all tasks to complete
        if tasks:
            await asyncio.gather(*tasks)

    async def crawl_domain(self, domain: str) -> None:
        """
        Crawl a single domain.
        
        Args:
            domain: Domain to crawl
        """
        base_url = f"https://{domain}" if not domain.startswith(('http://', 'https://')) else domain
        parsed_url = urlparse(base_url)
        netloc = parsed_url.netloc
        
        logger.info(f"Starting crawl of {domain}")
        
        async with aiohttp.ClientSession() as session:
            await self.crawl_page(base_url, netloc, session)
            
        logger.info(f"Completed crawl of {domain}")
        logger.info(f"Found {len(self.product_urls[netloc])} product URLs for {domain}")

    async def run(self) -> Dict[str, List[str]]:
        """
        Run the crawler for all domains.
        
        Returns:
            Dict[str, List[str]]: Dictionary mapping domains to lists of product URLs
        """
        tasks = []
        for domain in self.domains:
            # Ensure the domain is properly formatted
            domain = domain.strip('/')
            if domain.startswith(('http://', 'https://')):
                parsed = urlparse(domain)
                domain_key = parsed.netloc
            else:
                domain_key = domain
                
            task = asyncio.create_task(self.crawl_domain(domain))
            tasks.append(task)
            
        await asyncio.gather(*tasks)
        
        # Convert sets to lists for easy serialization
        results = {domain: list(urls) for domain, urls in self.product_urls.items()}
        
        return results

    def save_results(self, output_file: str = "product_urls.json") -> None:
        """
        Save the results to a JSON file.
        
        Args:
            output_file: Output file path
        """
        # Convert sets to lists for serialization
        results = {domain: list(urls) for domain, urls in self.product_urls.items()}
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
            
        logger.info(f"Results saved to {output_file}")

async def main():
    """
    Main function to run the crawler.
    """
    # List of domains to crawl
    domains = [
        "nykaafashion.com",
        "www.tatacliq.com"
    ]
    
    # Create the crawler
    crawler = EcommerceCrawler(
        domains=domains,
        max_pages_per_domain=1000,  # Adjust as needed
        max_concurrent_requests=10,  # Adjust based on server capacity
        request_delay=1.0  # Be respectful to the servers
    )
    
    # Run the crawler
    await crawler.run()
    
    # Save the results
    crawler.save_results()

if __name__ == "__main__":
    # Run the crawler
    asyncio.run(main())