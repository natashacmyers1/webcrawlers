import sys

def _crawl():
    from webcrawler.crawler import main as crawl_main
    crawl_main(max_pages=10, worker_count=3) 

def main():
    print("[crawler] Starting crawl...")
    _crawl()

if __name__ == "__main__":
    main()