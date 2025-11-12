from bs4 import BeautifulSoup
import requests
import queue
import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib import robotparser
from urllib.parse import urlparse, urljoin
from typing import Optional
import json, os, time



START_URL = "https://crawlme.monzo.com/"
REQUEST_USER_AGENT = "NatashaMyers/1.0 (natashacmyers@gmail.com)"

urls_to_visit = queue.Queue()
urls_to_visit.put(START_URL)

urls_processed = set()  
urls_discovered = set() 

STOP_EVENT = threading.Event()
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
    global last_request_time
    current_time = time.monotonic()
    time_since_last_request = current_time - last_request_time
    time_to_wait = REQUEST_DELAY_SECONDS - time_since_last_request
    if time_to_wait > 0:
        time.sleep(time_to_wait)
    last_request_time = time.monotonic()

def to_absolute_url(parent_url: str, href_value: str) -> str:
    return urljoin(parent_url, href_value) 

def should_enqueue_url(url: str) -> bool:
    return url.startswith(START_URL) and (url not in urls_processed) and (url not in urls_discovered)

def save_results_to_file(path="crawl_output.json"):
    abs_path = os.path.abspath(path)
    print(f"[save] cwd={os.getcwd()}")
    print(f"[save] writing to {abs_path}")

    pages = []
    for entry in printable_format_pages:
        for page_url, link_elements in entry.items():
            pages.append({
                "url": page_url,
                "links": [a.get("href") for a in link_elements],
            })

    payload = {
        "start_url": START_URL,
        "pages_crawled": pages_crawled,
        "pages": pages,
        "failures": failed_urls,
        "generated_at": time.time(),
    }

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"[save] OK → {abs_path}")
    except Exception as e:
        print(f"[save] ERROR: {e!r}")

def print_crawl_results():
    print("Here is a list of all the sites within the subdomain https://crawlme.monzo.com/ "
          "along with the sites found on each page")
    for entry in printable_format_pages:
        for page_url, link_elements in entry.items():
            print(f"\n{page_url}")
            for link_element in link_elements:
                print(f"  - {link_element['href']}")
    if failed_urls:
        print("\nThese pages could not be fetched:")
        for entry in failed_urls:
            print(f"  - {entry['url']}  ({entry['error']})")

def crawl_worker(max_pages: Optional[int] = None):
    global pages_crawled

    while True:
        try:
            page_url = urls_to_visit.get(timeout=1)
        except queue.Empty:
            return

        if not is_allowed_by_robots(page_url):
            print("This subdomain does not allow webcrawlers")
            continue

        if STOP_EVENT.is_set():
            urls_to_visit.task_done()
            continue

        with pages_count_lock:
             if max_pages is not None and pages_crawled >= max_pages:
                STOP_EVENT.set()
                urls_to_visit.task_done()
                continue

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
                failed_urls.append({"url": page_url, "error": str(e)})
            urls_to_visit.task_done()
            continue

        try:
            with pages_count_lock:
                pages_crawled += 1
                if max_pages is not None and pages_crawled >= max_pages:
                    STOP_EVENT.set()

            printable_format_pages.append({page_url: link_elements})

            for link_element in link_elements:
                href_value = link_element.get("href")
                if not href_value:
                    continue
                absolute_url = to_absolute_url(page_parent_url, href_value)
                with processed_lock, discovered_lock:
                    if not STOP_EVENT.is_set() and should_enqueue_url(absolute_url):
                        urls_to_visit.put(absolute_url)
                        urls_discovered.add(absolute_url)  
        finally:
            urls_to_visit.task_done()


def main(max_pages: int = None, worker_count: int = 3):
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
    output_path = os.getenv("OUTPUT_PATH", "crawl_output.json")
    save_results_to_file(output_path)


if __name__ == "__main__":
    main()
