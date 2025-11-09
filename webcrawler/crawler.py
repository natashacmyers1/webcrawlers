from bs4 import BeautifulSoup
import requests
import time
import queue
import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib import robotparser
from urllib.parse import urlparse

# ---- Config ----
target_url = "https://crawlme.monzo.com/"
USER_AGENT = "NatashaMyers/1.0 (natashacmyers@gmail.com)"

# ---- Queue & State ----
urls_to_visit = queue.Queue()
urls_to_visit.put(target_url)

visited = set()        # processed
seen = set()           # discovered/enqueued

visited_lock = threading.Lock()
seen_lock = threading.Lock()
count_lock = threading.Lock()

count = 0
finished_product = []

# ---- Simple global politeness delay ----
DEFAULT_DELAY = 0.5
last_hit_ts = 0.0


_thread_local = threading.local()
def get_session():
    if not hasattr(_thread_local, "session"):
        s = requests.Session()
        s.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml"
        })

        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retries)
        s.mount("http://", adapter)
        s.mount("https://", adapter)

        _thread_local.session = s
    return _thread_local.session

def robots_parser_for(url: str):
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    robots_url = base + "/robots.txt"
    rp = robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        resp = requests.get(robots_url, timeout=10, headers={"User-Agent": USER_AGENT})
        if resp.status_code in (401, 403):
            print(f"[robots] {resp.status_code} — assuming allow all")
            return None
        rp.parse((resp.text or "").splitlines())
    except Exception:
        return None
    return rp

ROBOTS = robots_parser_for(target_url)

def allowed(url: str) -> bool:
    if ROBOTS is None:
        return True
    return ROBOTS.can_fetch(USER_AGENT, url)

def fetch_links(url: str):
    sess = get_session()
    resp = sess.get(url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.select("a[href]")

def short_wait():
    global last_hit_ts
    now = time.monotonic()
    wait = max(0.0, last_hit_ts + DEFAULT_DELAY - now)
    if wait > 0:
        time.sleep(wait)
    last_hit_ts = time.monotonic()

def create_absolute_url(parent_url: str, href: str) -> str:
    if href.startswith("https"):
        return href
    return requests.compat.urljoin(parent_url, href)

def should_enqueue(url: str) -> bool:
    return url.startswith(target_url) and (url not in visited) and (url not in seen)

def print_results():
    print("Here is a list of all the sites within the subdomain https://crawlme.monzo.com/ "
          "along with the sites found on each page")
    for item in finished_product:
        for current_url, link_elements in item.items():
            print(f"\n{current_url}")
            for link in link_elements:
                print(f"  - {link['href']}")


def worker(max_pages: int = 10):
    global count
    if not allowed(target_url):
        print("This subdomain does not allow webcrawlers")
        return

    while True:
        try:
            current_url = urls_to_visit.get(timeout=1)
        except queue.Empty:
            return

        with count_lock:
            if count >= max_pages:
                urls_to_visit.task_done()
                return

        with visited_lock:
            if current_url in visited:
                urls_to_visit.task_done()
                continue
            visited.add(current_url)

        parent_url = current_url.rsplit("/", 1)[0] + "/"
        short_wait()

        try:
            link_elements = fetch_links(current_url)
        except Exception:
            urls_to_visit.task_done()
            continue

        try:
            with count_lock:
                count += 1
            finished_product.append({current_url: link_elements})

            for link in link_elements:
                href = link.get("href")
                if not href:
                    continue
                absolute_url = create_absolute_url(parent_url, href)
                with visited_lock, seen_lock:
                    if should_enqueue(absolute_url):
                        urls_to_visit.put(absolute_url)
                        seen.add(absolute_url)  # discovered, not visited
        finally:
            urls_to_visit.task_done()

def main(max_pages: int = 10, workers: int = 2):
    threads = [threading.Thread(target=worker, args=(max_pages,), daemon=True) for _ in range(workers)]
    for t in threads:
        t.start()
    urls_to_visit.join()
    for t in threads:
        t.join(timeout=0.1)
    print_results()

if __name__ == "__main__":
    main(max_pages=20, workers=4)
