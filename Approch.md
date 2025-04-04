# Approach for Finding Product URLs on E-commerce Websites

This document outlines the strategy and techniques used by our crawler to efficiently discover product URLs across various e-commerce websites.

## Table of Contents

1. [Overview](#overview)
2. [URL Pattern Recognition](#url-pattern-recognition)
3. [Domain-Specific Patterns](#domain-specific-patterns)
4. [Crawling Strategy](#crawling-strategy)
5. [Avoiding False Positives](#avoiding-false-positives)
6. [Scalability Considerations](#scalability-considerations)
7. [Performance Optimizations](#performance-optimizations)
8. [Site-Specific Analysis](#site-specific-analysis)

## Overview

Finding product URLs on e-commerce websites presents several challenges:

1. Each website uses different URL structures and patterns
2. Websites may have thousands or millions of product pages
3. We need to efficiently crawl while respecting server resources
4. We must avoid crawling non-product pages unnecessarily

Our approach combines multiple techniques to address these challenges.

## URL Pattern Recognition

We identify product URLs through pattern matching against common URL structures used by e-commerce platforms:

### Common Product URL Patterns

```python
PRODUCT_PATTERNS = [
    r'/product/', r'/item/', r'/p/', r'/products/', r'/pd/',
    r'-pd-', r'/buy/', r'/shop/', r'productdetail', r'/collections/',
    r'/prod-', r'/item-', r'/detail/', r'/sku/', r'/view/', r'/Prod-', r'/productpage'
]
```

These patterns appear in most e-commerce platforms and serve as primary indicators of product pages.

### Path-Based Heuristics

In addition to fixed patterns, we look for structural characteristics of product URLs:

1. **Numeric IDs**: Product pages often contain numeric identifiers in their URLs
   ```
   /product/12345
   /p/item_98765
   ```

2. **Segment Depth**: Product pages are typically deeper in the URL hierarchy than category pages
   ```
   /category/subcategory/product-name-12345
   ```

3. **URL Length**: Product URLs tend to be longer than navigation pages

## Domain-Specific Patterns

For each of the required domains, we've analyzed their URL structures and identified domain-specific patterns:

```python
domain_specific_patterns = {
    'virgio.com': [r'/products/'],
    'tatacliq.com': [r'/product-details/', r'/p-'],
    'nykaafashion.com': [r'/product/'],
    'westside.com': [r'/products/']
}
```

### Site-by-Site Analysis

#### Virgio.com
- Product URLs follow the pattern: `https://www.virgio.com/products/product-name`
- Categories follow: `https://www.virgio.com/collections/category-name`

#### TataCliq.com
- Product URLs follow: `https://www.tatacliq.com/product-details/product-name/product-id`
- Alternative product URL pattern: `https://www.tatacliq.com/p-product-name`

#### NykaaFashion.com
- Product URLs follow: `https://nykaafashion.com/product/brand/product-name/p/product-id`

#### Westside.com
- Product URLs follow: `https://www.westside.com/products/category/product-name`

## Crawling Strategy

We implement a breadth-first crawling approach that:

1. Starts from the homepage of each domain
2. Identifies and follows links to category pages and product listings
3. Prioritizes links that match patterns typical of product listing pages
4. Limits crawl depth to avoid going too deep into non-product sections

### Breadth-First Implementation

```python
async def crawl_page(self, url: str, domain: str, session: ClientSession, depth: int = 0):
    # Skip if already visited or max pages reached
    if url in self.visited_urls[domain] or len(self.visited_urls[domain]) >= self.max_pages_per_domain:
        return
        
    # Add to visited URLs
    self.visited_urls[domain].add(url)
    
    # Check if this is a product URL
    if await self.is_product_url(url, domain):
        self.product_urls[domain].add(url)
    
    # Fetch the page
    html = await self.fetch_page(url, session)
    if not html:
        return
        
    # Extract links
    links = await self.extract_links(html, url)
    
    # Create tasks for each link (limited by depth)
    tasks = []
    for link in links:
        if link not in self.visited_urls[domain] and depth < 3:
            task = asyncio.create_task(self.crawl_page(link, domain, session, depth + 1))
            tasks.append(task)
            
    # Wait for all tasks to complete
    if tasks:
        await asyncio.gather(*tasks)
```

## Avoiding False Positives

To ensure high precision in our product URL identification, we:

1. **Exclude known non-product paths**: Filter out URLs containing segments like `category`, `collection`, `search`, `login`, etc.

2. **Filter by URL structure**: Product URLs typically have specific formats that distinguish them from other pages

3. **Context-aware detection**: We consider the source page when evaluating whether a URL is a product page (e.g., links from category pages are more likely to be products)

## Scalability Considerations

Our crawler is designed to scale to hundreds of domains:

1. **Asynchronous architecture**: Uses `asyncio` for concurrent crawling of domains and pages.

2. **Per-domain rate limiting**: Each domain has its own semaphore and rate limiting to ensure fair distribution of crawling resources

3. **Memory efficiency**: Storing only essential data (URLs) and using sets to eliminate duplicates

4. **Configurable limits**: Parameters like max pages per domain and max concurrent requests can be adjusted based on available resources

## Performance Optimizations

To improve crawling efficiency:

1. **Concurrency control**: Using semaphores to limit the number of concurrent requests per domain

2. **Adaptive delays**: Implementing configurable delays between requests to avoid overwhelming servers

3. **Early termination**: Stopping crawling when the maximum number of pages is reached

4. **Efficient data structures**: Using sets for O(1) lookups when checking visited URLs

```python
# Semaphores to limit concurrent requests (per domain)
self.domain_semaphores = {
    domain: asyncio.Semaphore(max_concurrent_requests) for domain in domains
}

# Rate limiting
async with self.domain_semaphores[domain]:
    now = time.time()
    time_since_last_request = now - self.last_request_time[domain]
    if time_since_last_request < self.request_delay:
        await asyncio.sleep(self.request_delay - time_since_last_request)
    self.last_request_time[domain] = time.time()
    
    html = await self.fetch_page(url, session)
```

## Site-Specific Analysis

For each of the required domains, we conducted manual analysis to understand their structure and URL patterns.

### Virgio.com Analysis

- Homepage contains links to collections
- Collection pages list multiple products
- Product URLs follow `/products/product-name` pattern
- Products may also have variant URLs with query parameters

### TataCliq.com Analysis

- Complex site with multiple departments
- Category hierarchy: Department > Category > Subcategory
- Product URLs follow either `/product-details/` or `/p-` patterns
- Product IDs typically alphanumeric

### NykaaFashion.com Analysis

- Fashion e-commerce with brand-focused structure
- Product URLs contain `/product/` followed by brand and product name
- Unique identifier appears after `/p/` segment
- Has multiple product