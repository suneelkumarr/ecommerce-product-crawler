# E-commerce Product URL Crawler

This repository contains a scalable, robust web crawler designed to discover product URLs on e-commerce websites. The crawler can efficiently process multiple domains in parallel and identify product pages based on URL patterns and heuristics.

## Features

- **Intelligent URL Discovery**: Identifies product pages using common URL patterns and domain-specific rules
- **Scalability**: Can handle hundreds of domains and thousands of pages per domain
- **Asynchronous Execution**: Utilizes async I/O for maximum performance
- **Configurable Rate Limiting**: Respects website resources with customizable delay between requests
- **Robust Error Handling**: Gracefully handles network errors, timeouts, and malformed pages
- **Comprehensive Logging**: Detailed logs for monitoring and debugging

## Approach for Finding Product URLs

The crawler uses multiple strategies to identify product URLs:

1. **URL Pattern Recognition**: The crawler looks for common URL patterns that indicate product pages, such as:
   - `/product/`
   - `/item/`
   - `/p/`
   - `/pd/`
   - etc.

2. **Domain-Specific Patterns**: Custom patterns for specific e-commerce platforms:
   - Virgio: `/products/`
   - TataCliq: `/product-details/`, `/p-`
   - Nykaa Fashion: `/product/`
   - Westside: `/products/`

3. **Structural Heuristics**: Identification based on URL structure, such as numeric IDs in the path that are typically used for product pages

4. **Breadth-First Crawling**: The crawler starts from the homepage and follows links in a breadth-first manner, prioritizing discovery of product listings and categories

## Requirements

- Python 3.7+
- Required packages:
  - aiohttp
  - beautifulsoup4
  - asyncio
  - selenium
  - tenacity
  - playwright

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/ecommerce-product-crawler.git
   cd ecommerce-product-crawler
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Basic Usage

```bash
python finalcode.py
```

This will run the crawler on the default set of domains:
- www.virgio.com
- www.tatacliq.com
- nykaafashion.com
- www.westside.com


### Configuration Options

- `-o, --output`: Output file path (default: `product_urls.json`)
- `-m, --max-pages`: Maximum pages to crawl per domain (default: 1000)
- `-c, --concurrent`: Maximum concurrent requests (default: 10)
- `-d, --delay`: Delay between requests to the same domain in seconds (default: 1.0)
- `-v, --verbose`: Enable verbose logging


## Output Format

The crawler produces a JSON file with the following structure:

```json
{
  "domain1.com": [
    "https://domain1.com/product/123",
    "https://domain1.com/product/456",
    ...
  ],
  "domain2.com": [
    "https://domain2.com/item/789",
    "https://domain2.com/item/012",
    ...
  ],
  ...
}
```

## Performance Considerations

- **Rate Limiting**: The crawler includes a configurable delay between requests to the same domain to avoid overwhelming the target servers.
- **Concurrency Control**: The number of concurrent requests is limited both globally and per domain.
- **Memory Management**: The crawler stores only essential information (URLs) to minimize memory usage.
- **Error Recovery**: Failed requests are logged but don't stop the overall crawling process.

## Future Improvements

- Implement a proper robots.txt parser
- Add support for sitemaps
- Improve product detection with machine learning approaches
- Add resumable crawling capability
- Implement distributed crawling with a message queue


## Author

Suneel Kumar