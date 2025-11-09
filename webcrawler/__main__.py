import sys

def _serve():
    # lazy import so we don't pull server deps for crawl-only runs
    from webcrawler.app import run as serve_run
    serve_run()

def _crawl():
    from webcrawler.crawler import main as crawl_main
    crawl_main()  # implement your crawl logic inside crawler.main()

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "crawl"  # default to crawling
    if cmd == "serve":
        _serve()
    elif cmd == "crawl":
        _crawl()
    else:
        print(f"Unknown command: {cmd}\nUsage: webcrawler [serve|crawl]", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()