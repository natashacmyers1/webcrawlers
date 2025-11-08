
from bs4 import BeautifulSoup
import requests

target_url = "https://crawlme.monzo.com/"

urls_to_visit = [target_url]
urls_visited = []

finished_product = []

def crawler():

    while urls_to_visit:
        # get the page to visit from the list
        current_url = urls_to_visit.pop(0)
        print(current_url, "current_url")

        parent_url = current_url.rsplit("/", 1)[0] + "/"

        # parse the HTML
        response = requests.get(current_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # collect all the links
        link_elements = soup.select("a[href]")

        # store data for later:
        finished_product.append({current_url: link_elements})

        for link_element in link_elements:
            url = link_element["href"]
           
            # convert links to absolute URLs
            if not url.startswith("https"):
                absolute_url = requests.compat.urljoin(parent_url, url)
            else:
                absolute_url = url

            # ensure the crawled link belongs to the target domain and hasn't been visited
            if (
                absolute_url.startswith(target_url)
                and absolute_url not in urls_visited
            ):
                urls_to_visit.append(absolute_url)
                urls_visited.append(absolute_url)

            
    print(urls_to_visit)

crawler()