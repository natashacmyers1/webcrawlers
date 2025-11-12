# test_crawler.py
import types
import threading
import json
from urllib.parse import urljoin
import pytest

import crawler 


# ---------- helpers ----------

def reset_globals():
    crawler.STOP_EVENT.clear()
    crawler.pages_crawled = 0
    crawler.last_request_time = 0.0

    crawler.urls_processed.clear()
    crawler.urls_discovered.clear()
    crawler.failed_urls.clear()
    crawler.printable_format_pages.clear()

    with crawler.urls_to_visit.mutex:
        crawler.urls_to_visit.queue.clear()
        crawler.urls_to_visit.unfinished_tasks = 0
    crawler.urls_to_visit.put(crawler.START_URL)


# ---------- unit tests for small helpers ----------

def test_to_absolute_url_basic():
    parent = "https://crawlme.monzo.com/products/page.html"
    assert crawler.to_absolute_url(parent, "next.html") == urljoin(parent, "next.html")
    assert crawler.to_absolute_url(parent, "/contact.html") == urljoin(parent, "/contact.html")
    assert crawler.to_absolute_url(parent, "https://example.com/") == "https://example.com/"

def test_should_enqueue_url_scopes_and_dedup():
    reset_globals()
    inside = "https://crawlme.monzo.com/a.html"
    outside = "https://example.com/b.html"

    assert crawler.should_enqueue_url(inside) is True
    assert crawler.should_enqueue_url(outside) is False

    crawler.urls_discovered.add(inside)
    assert crawler.should_enqueue_url(inside) is False

    crawler.urls_discovered.clear()
    crawler.urls_processed.add(inside)
    assert crawler.should_enqueue_url(inside) is False


def test_is_allowed_by_robots_allows_when_none(monkeypatch):
    reset_globals()
    monkeypatch.setattr(crawler, "ROBOTS_RULES", None)
    assert crawler.is_allowed_by_robots(crawler.START_URL) is True

def test_is_allowed_by_robots_respects_parser(monkeypatch):
    reset_globals()

    class DummyRP:
        def can_fetch(self, ua, url):
            return url.endswith("/ok")

    monkeypatch.setattr(crawler, "ROBOTS_RULES", DummyRP())
    assert crawler.is_allowed_by_robots("https://crawlme.monzo.com/ok") is True
    assert crawler.is_allowed_by_robots("https://crawlme.monzo.com/nope") is False


# ---------- fetch_page_links ----------

class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code
    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"status {self.status_code}")

class FakeSession:
    def __init__(self, html_by_url):
        self.html_by_url = html_by_url
    def get(self, url, timeout=20):
        html, status = self.html_by_url.get(url, ("", 404))
        return FakeResponse(html, status)

def test_fetch_page_links_parses_anchors(monkeypatch):
    reset_globals()
    html = """
      <html><body>
        <a href="/a.html">A</a>
        <a href="https://example.com/">Offsite</a>
      </body></html>
    """
    fake = FakeSession({crawler.START_URL: (html, 200)})
    monkeypatch.setattr(crawler, "get_thread_session", lambda: fake)

    links = crawler.fetch_page_links(crawler.START_URL)
    hrefs = sorted(a.get("href") for a in links)
    assert hrefs == ["/a.html", "https://example.com/"]


def test_fetch_page_links_raises_on_error(monkeypatch):
    reset_globals()
    fake = FakeSession({crawler.START_URL: ("not found", 404)})
    monkeypatch.setattr(crawler, "get_thread_session", lambda: fake)

    with pytest.raises(Exception):
        crawler.fetch_page_links(crawler.START_URL)


# ---------- save_results_to_file ----------

def test_save_results_to_file_writes_json(tmp_path, monkeypatch):
    reset_globals()
    crawler.printable_format_pages.append({
        "https://crawlme.monzo.com/index.html": [
            types.SimpleNamespace(get=lambda k: "/a.html" if k == "href" else None),
            types.SimpleNamespace(get=lambda k: "https://example.com/" if k == "href" else None),
        ]
    })
    crawler.pages_crawled = 1

    out = tmp_path / "crawl_output.json"
    crawler.save_results_to_file(str(out))

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["start_url"] == crawler.START_URL
    assert data["pages_crawled"] == 1
    assert len(data["pages"]) == 1
    assert data["pages"][0]["url"].endswith("/index.html")
    assert set(data["pages"][0]["links"]) == {"/a.html", "https://example.com/"}



def test_crawl_worker_enqueues_children_and_respects_max(monkeypatch):
    reset_globals()

    html_by_url = {
        "https://crawlme.monzo.com/": ('<a href="/a.html">A</a><a href="/b.html">B</a>', 200),
        "https://crawlme.monzo.com/a.html": ('<a href="/c.html">C</a>', 200),
        "https://crawlme.monzo.com/b.html": ("<p>no links</p>", 200),
        "https://crawlme.monzo.com/c.html": ("<p>end</p>", 200),
    }
    monkeypatch.setattr(crawler, "REQUEST_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(crawler, "get_thread_session", lambda: FakeSession(html_by_url))
    monkeypatch.setattr(crawler, "is_allowed_by_robots", lambda url: True)

    t = threading.Thread(target=crawler.crawl_worker, args=(2,), daemon=True)
    t.start()
    crawler.urls_to_visit.join()

    t.join(timeout=1)

    # Assertions
    assert crawler.pages_crawled == 2
    discovered = crawler.urls_discovered
    assert any(u.endswith("/a.html") for u in discovered) or any(u.endswith("/b.html") for u in discovered)
    assert crawler.urls_to_visit.unfinished_tasks == 0
