FROM python:3.12-alpine

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pytest

COPY webcrawler ./webcrawler
ENV PYTHONPATH=/app

EXPOSE 8000
# Run the package as a module; we’ll pass subcommands like "serve" or "crawl"
ENTRYPOINT ["python", "-m", "webcrawler.__main__"]
# Optional default subcommand:
# CMD ["crawl"]