# WebCrawlers
An application to test my ability to make a web crawler and what not.

### Local Setup

Run the following docker build commands in your terminal:

To build the docker container itself
`docker build -t webcrawler .`                    

To run the docker crawler in the container against https://crawlme.monzo.com
`docker run --rm webcrawler crawl`

NB: if you want to run the crawler on a different site, simply update the site name in crawler.py