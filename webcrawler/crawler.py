from bs4 import BeautifulSoup
import requests
import time

from urllib import robotparser
from urllib.parse import urlparse

target_url = "https://crawlme.monzo.com/"

urls_to_visit = [target_url]
urls_visited = []
finished_product = []

DEFAULT_DELAY = 0.5
last_hit_ts = 0.0

USER_AGENT = "NatashaMyers/1.0 (natashacmyers@gmail.com)"

session = requests.Session()
session.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml"
})

def robots_parser_for(url: str):
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    robots_url = base + "/robots.txt"
    rp = robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        response = requests.get(robots_url, timeout=10)
        if response.status_code in (401, 403):
            # Treat as "allow all" for restricted robots.txt (e.g. test sites)
            print(f"[robots] {response.status_code} received — assuming allow all")
            return None
        rp.parse(response.text.splitlines())
    except Exception:
        pass
    return rp

ROBOTS = robots_parser_for(target_url)

def allowed(url: str) -> bool:
    if ROBOTS is None:
        return True 
    return ROBOTS.can_fetch(USER_AGENT, url)


def fetch_links(url: str):
    """GET a page and return its <a href> elements."""
    response = session.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.select("a[href]")

def short_wait():
    print("waiting...")
    global last_hit_ts
    now = time.monotonic()
    wait = max(0.0, last_hit_ts + DEFAULT_DELAY - now)
    if wait > 0:
        time.sleep(wait)
    last_hit_ts = time.monotonic()


def create_absolute_url(parent_url: str, href: str) -> str:
    """Turn relative links into absolute URLs (leave absolute as-is)."""
    if href.startswith("https"):
        return href
    return requests.compat.urljoin(parent_url, href)


def should_enqueue(url: str) -> bool:
    """Keep within domain and avoid revisits."""
    return url.startswith(target_url) and url not in urls_visited


def print_results():
    print(
        "Here is a list of all the sites within the subdomain https://crawlme.monzo.com/ "
        "along with the sites found on each page"
    )
    for item in finished_product:
        for current_url, link_elements in item.items():
            print(f"\n{current_url}")
            for link in link_elements:
                print(f"  - {link['href']}")


def crawl(max_pages: int = 10):
    count = 0
    if not allowed(target_url):
        print("This subdomain does not allow webcrawlers")
        return

    while urls_to_visit and count < max_pages:
        current_url = urls_to_visit.pop(0)
        count += 1
        parent_url = current_url.rsplit("/", 1)[0] + "/"

        short_wait()
        link_elements = fetch_links(current_url)
        finished_product.append({current_url: link_elements})

        for link in link_elements:
            absolute_url = create_absolute_url(parent_url, link["href"])
            if should_enqueue(absolute_url):
                urls_to_visit.append(absolute_url)
                urls_visited.append(absolute_url)

    print_results()


# Run
crawl()