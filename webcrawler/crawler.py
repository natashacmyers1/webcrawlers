from bs4 import BeautifulSoup
import requests
import time
import queue
import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib import robotparser
from urllib.parse import urlparse

START_URL = "https://crawlme.monzo.com/"
REQUEST_USER_AGENT = "NatashaMyers/1.0 (natashacmyers@gmail.com)"

urls_to_visit = queue.Queue()
urls_to_visit.put(START_URL)

urls_processed = set()  
urls_discovered = set() 

processed_lock = threading.Lock()
discovered_lock = threading.Lock()
pages_count_lock = threading.Lock() 

pages_crawled = 0
failed_urls = []
failed_urls_lock = threading.Lock()

printable_format_pages = []  

REQUEST_DELAY_SECONDS = 0.5
last_request_time = 0.0

local_thread_storage = threading.local()

def get_thread_session() -> requests.Session: 
    if not hasattr(local_thread_storage, "session"):
        session = requests.Session()
        session.headers.update({
            "User-Agent": REQUEST_USER_AGENT, 
            "Accept": "text/html,application/xhtml+xml" 
        })
        retry_policy = Retry(
            total=3,
            backoff_factor=0.5, 
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_policy) 
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        local_thread_storage.session = session 
    return local_thread_storage.session

def load_robots_rules(url: str):
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rules = robotparser.RobotFileParser()
    rules.set_url(robots_url)
    try:
        resp = requests.get(robots_url, timeout=10, headers={"User-Agent": REQUEST_USER_AGENT})
        if resp.status_code in (401, 403):
            print(f"[robots] {resp.status_code} — assuming allow all")
            return None  # None means: allow all
        rules.parse((resp.text or "").splitlines())
    except Exception:
        return None
    return rules

ROBOTS_RULES = load_robots_rules(START_URL)

def is_allowed_by_robots(url: str) -> bool:
    if ROBOTS_RULES is None:
        return True
    return ROBOTS_RULES.can_fetch(REQUEST_USER_AGENT, url)

def fetch_page_links(page_url: str):
    """Fetch a page and return its <a href> elements."""
    session = get_thread_session()
    response = session.get(page_url, timeout=20)  
    response.raise_for_status() 
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.select("a[href]")

def wait():
    """Simple shared delay so we don't hammer the host."""
    global last_request_time
    current_time = time.monotonic()
    time_since_last_request = current_time - last_request_time
    time_to_wait = REQUEST_DELAY_SECONDS - time_since_last_request
    if time_to_wait > 0:
        time.sleep(time_to_wait)
    last_request_time = time.monotonic()

def to_absolute_url(parent_url: str, href_value: str) -> str:

    """Convert relative links to absolute URLs; keep absolute URLs as-is."""
    if not href_value.startswith("https"):
        absolute_url = requests.compat.urljoin(parent_url, href_value)
    else:
        absolute_url = href_value
    return absolute_url

def should_enqueue_url(url: str) -> bool:
    """Only enqueue URLs within scope that we haven't discovered or processed."""
    return url.startswith(START_URL) and (url not in urls_processed) and (url not in urls_discovered)

def print_crawl_results():
    print("Here is a list of all the sites within the subdomain https://crawlme.monzo.com/ "
          "along with the sites found on each page")
    for entry in printable_format_pages:
        for page_url, link_elements in entry.items():
            print(f"\n{page_url}")
            for link_el in link_elements:
                print(f"  - {link_el['href']}")
    if failed_urls:
        print("\nThese pages could not be fetched:")
        for entry in failed_urls:
            print(f"  - {entry['url']}  ({entry['error']})")

def crawl_worker(max_pages):
    global pages_crawled
    if not is_allowed_by_robots(START_URL):
        print("This subdomain does not allow webcrawlers")
        return

    while True:
        try:
            page_url = urls_to_visit.get(timeout=1)
        except queue.Empty:
            return

        with pages_count_lock:
            if pages_crawled >= max_pages:
                urls_to_visit.task_done()
                return

        with processed_lock:
            if page_url in urls_processed:
                urls_to_visit.task_done()
                continue
            urls_processed.add(page_url)

        page_parent_url = page_url.rsplit("/", 1)[0] + "/"

        wait()

        try:
            link_elements = fetch_page_links(page_url)
        except Exception as e:
            with failed_urls_lock:
                failed_urls.append({"url": current_url, "error": str(e)})
            urls_to_visit.task_done()
            continue

        try:
            with pages_count_lock:
                pages_crawled += 1
            printable_format_pages.append({page_url: link_elements})

            for link_element in link_elements:
                href_value = link_element.get("href")
                if not href_value:
                    continue
                absolute_url = to_absolute_url(page_parent_url, href_value)
                with processed_lock, discovered_lock:
                    if should_enqueue_url(absolute_url):
                        urls_to_visit.put(absolute_url)
                        urls_discovered.add(absolute_url)  
        finally:
            urls_to_visit.task_done()


def main(max_pages: int = 100, worker_count: int = 10): 
    worker_threads = []
    for i in range(worker_count):
        thread = threading.Thread(
            target=crawl_worker,
            args=(max_pages,),
            daemon=True 
        )
        worker_threads.append(thread)
    
    for thread in worker_threads:
        thread.start()

    urls_to_visit.join() 

    for thread in worker_threads:
        thread.join(timeout=0.1) 

    print_crawl_results()

if __name__ == "__main__":
    main(max_pages=100, worker_count=10)
