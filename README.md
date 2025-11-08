# WebCrawlers
An application to test my ability to make a web crawler and what not.

### Local Setup

Run the following docker build commands in your terminal:

To build the docker container itself
`docker build -t webcrawler .`                    

To run the docker container in interactive mode
`docker run -it --rm webcrawler sh`

To run the crawler against https://crawlme.monzo.com
`python webcrawler/crawler.py`
NB: if you want to run the crawler on a different site, simply update the site name in crawler.py