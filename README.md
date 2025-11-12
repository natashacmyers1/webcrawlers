# Monzo Subdomain Crawler

A polite, multithreaded web crawler written in Python that recursively explores links within the https://crawlme.monzo.com/ subdomain.
It obeys robots.txt rules, respects a crawl delay, and includes retry logic, thread safety, and optional persistence to JSON.

### Features

- Thread-safe, multi-worker crawling using Python’s threading and queue.

- Honors robots.txt (unless unavailable or restricted via 401/403).

- Automatic retry/backoff on transient HTTP failures.

- Polite crawling with global request delay.

- Optional maximum page limit (max_pages).

- Saves results to a JSON file (crawl_output.json).

- Collects failed URLs with error messages.

- Can be run locally or in a Docker container.

### Requirements

Python 3.9+

Dependencies included in requirements.txt:

- beautifulsoup4
- requests
- urllib3
- pytest (for testing)

### How it works

Start URL: Begins from https://crawlme.monzo.com/

UrlsToVisit Queue: Tracks pages to visit.

Worker Threads: Fetch pages concurrently using thread-local requests.Session.

Politeness Policy: Global delay between requests to avoid hammering the server.

Retry Logic: Automatically retries transient errors (HTTP 429, 500, 502, 503, 504).

Result Storage: Extracts and saves all discovered links per page.

Persistence: Writes output to crawl_output.json after completion.

### Running in Docker

Run the following docker build commands in your terminal:

To build the docker image itself
`docker build -t webcrawler .`                    

To run the docker crawler in the container against https://crawlme.monzo.com and saving the results on your local machine

`docker run --rm -v "$PWD:/out" -w /app -e OUTPUT_PATH=/out/crawl_output.json webcrawler`


NB: if you want to run the crawler on a different site, simply update the site name in crawler.py

### Running Tests

Run the following inside the docker container:
`source .venv/bin/activate` 
`pip install -U pip`
`pip install -r requirements.txt`
`pytest -v`

### Future improvements

- Politeness & robots.txt: Per-host robots cache: don’t re-fetch robots for every URL. Cache once per netloc, refresh on TTL, and share across threads.

- Observability:
  Structured logs: per fetch {url, status, ms, bytes, retries}.
  Metrics: counters for fetched/enqueued/skipped; histogram for latency; final summary.

- Developer experience: CLI improvements like --max-pages, --workers.

- Tests: More unit tests, integrations tests

- Storage: An actual database would be nice :) 

- Maybe even a nice front end one day