from bs4 import BeautifulSoup
import requests

target_url = "https://crawlme.monzo.com/"

urls_to_visit = [target_url]
urls_visited = []
finished_product = []


def fetch_links(url: str):
    """GET a page and return its <a href> elements."""
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.select("a[href]")


def normalize_url(parent_url: str, href: str) -> str:
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
    while urls_to_visit and count < max_pages:
        count += 1

        current_url = urls_to_visit.pop(0)
        parent_url = current_url.rsplit("/", 1)[0] + "/"

        link_elements = fetch_links(current_url)
        finished_product.append({current_url: link_elements})

        for link in link_elements:
            absolute_url = normalize_url(parent_url, link["href"])
            if should_enqueue(absolute_url):
                urls_to_visit.append(absolute_url)
                urls_visited.append(absolute_url)

    print_results()


# Run
crawl()