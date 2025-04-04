import scrapy
from scrapy.crawler import CrawlerProcess
from pybloom_live import BloomFilter
import json
import xml.etree.ElementTree as ET

# Custom pipeline to write items to separate JSON files per domain
class DomainPipeline:
    def __init__(self):
        self.files = {}

    def open_spider(self, spider):
        filename = f'{spider.domain}.json'
        file = open(filename, 'w', encoding='utf-8')
        self.files[spider.domain] = file
        file.write('[\n')

    def process_item(self, item, spider):
        line = json.dumps(dict(item)) + ",\n"
        self.files[spider.domain].write(line)
        return item

    def close_spider(self, spider):
        file = self.files[spider.domain]
        file.seek(0, 2)  # Move to the end of the file
        pos = file.tell()
        if pos > 2:  # If items were written, remove the last comma and newline
            file.seek(pos - 2)
            file.truncate()
        file.write('\n]')
        file.close()

# E-commerce spider to extract product URLs
class EcommerceSpider(scrapy.Spider):
    name = 'ecommerce'

    def __init__(self, domain='', *args, **kwargs):
        super(EcommerceSpider, self).__init__(*args, **kwargs)
        self.domain = domain
        self.start_urls = [f'https://{domain}']
        self.allowed_domains = [domain, f'www.{domain}']  # Handle both variants
        self.product_patterns = ['/products/', '/p/', '/item/', '/sku/', '/details/', '/collections/']
        self.seen_urls = BloomFilter(capacity=1000000, error_rate=0.001)  # Memory-efficient URL tracking

    def start_requests(self):
        # Try fetching the sitemap and start crawling from the homepage
        sitemap_url = f'https://{self.domain}/sitemap.xml'
        yield scrapy.Request(sitemap_url, callback=self.parse_sitemap, errback=self.handle_error)
        yield scrapy.Request(self.start_urls[0], callback=self.parse_page)

    def parse_sitemap(self, response):
        try:
            root = ET.fromstring(response.body)
            namespaces = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            urls = [loc.text for loc in root.findall('ns:url/ns:loc', namespaces)]
            for url in urls:
                if any(pattern in url for pattern in self.product_patterns):
                    if url not in self.seen_urls:
                        self.seen_urls.add(url)
                        yield {'url': url}
        except Exception as e:
            self.logger.error(f"Error parsing sitemap: {e}")

    def handle_error(self, failure):
        # Log the error when fetching sitemap fails
        self.logger.error(f"Error fetching sitemap: {failure}")

    def parse_page(self, response):
        # Extract all links from the page
        links = response.css('a::attr(href)').getall()
        for link in links:
            absolute_url = response.urljoin(link)
            # Check if the URL matches product patterns and hasn't been seen
            if any(pattern in absolute_url for pattern in self.product_patterns):
                if absolute_url not in self.seen_urls:
                    self.seen_urls.add(absolute_url)
                    yield {'url': absolute_url}
            # Check uniqueness before following the link to avoid duplicate crawling
            if absolute_url not in self.seen_urls:
                self.seen_urls.add(absolute_url)
                yield response.follow(absolute_url, callback=self.parse_page)

    def close_spider(self, spider):
        # Log the number of URLs crawled
        self.logger.info(f"Finished crawling {spider.domain}. Crawled {len(self.seen_urls)} URLs.")

def run_spiders(domains):
    process = CrawlerProcess(settings={
        'ITEM_PIPELINES': {'__main__.DomainPipeline': 300},
        'CONCURRENT_REQUESTS': 16,
        'DOWNLOAD_DELAY': 1,
        'DEPTH_LIMIT': 10,  # Increased depth limit
        'RETRY_ENABLED': True,
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 408],
        'USER_AGENT': 'Mozilla/5.0 (compatible; EcommerceCrawler/1.0)',
    })
    for domain in domains:
        process.crawl(EcommerceSpider, domain=domain)
    process.start()

if __name__ == '__main__':
    # List of domains to crawl
    domains = ['nykaafashion.com']
    run_spiders(domains)