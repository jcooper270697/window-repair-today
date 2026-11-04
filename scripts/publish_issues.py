import os
import re
import json
import html
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone

import markdown
from bs4 import BeautifulSoup

REPOSITORY = os.environ["GH_REPOSITORY"]
TOKEN = os.environ["GH_TOKEN"]

BASE_PATH = "/window-repair-today/"
ARTICLES_DIR = Path("articles")
ARTICLES_DIR.mkdir(exist_ok=True)

API = f"https://api.github.com/repos/{REPOSITORY}/issues"


def get_issues():
    issues = []
    page = 1

    while True:
        url = API + "?" + urllib.parse.urlencode({
            "state": "all",
            "per_page": 100,
            "page": page
        })

        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "WindowRepairTodayPublisher"
            }
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)

        if not data:
            break

        issues.extend(
            item for item in data
            if "pull_request" not in item
        )

        if len(data) < 100:
            break

        page += 1

    return issues


def clean_html(content):
    rendered = markdown.markdown(
        content or "",
        extensions=["extra", "sane_lists"]
    )

    soup = BeautifulSoup(rendered, "html.parser")

    for tag in soup.find_all([
        "script", "style", "iframe", "object",
        "embed", "form", "input", "button",
        "svg", "math", "meta", "link"
    ]):
        tag.decompose()

    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr.lower().startswith("on"):
                del tag.attrs[attr]

        if tag.name == "a":
            href = str(tag.get("href", "")).strip()
            parsed = urllib.parse.urlsplit(href)

            if parsed.scheme not in ("http", "https"):
                tag.unwrap()
                continue

            tag["href"] = href
            tag["rel"] = "noopener noreferrer"

        elif tag.name == "img":
            src = str(tag.get("src", "")).strip()
            parsed = urllib.parse.urlsplit(src)

            if parsed.scheme not in ("http", "https"):
                tag.decompose()
                continue

            tag["src"] = src
            tag.attrs.pop("srcset", None)
            tag.attrs.pop("style", None)
            tag["loading"] = "lazy"
            tag["alt"] = str(tag.get("alt", ""))

        else:
            tag.attrs = {}

    return str(soup)


def create_article(issue):
    number = issue["number"]
    title = issue.get("title") or f"Article {number}"
    body = issue.get("body") or ""
    date = (issue.get("created_at") or "")[:10]

    filename = f"issue-{number}.html"
    canonical = (
        f"https://{REPOSITORY.split('/')[0]}.github.io"
        f"{BASE_PATH}articles/{filename}"
    )

    safe_title = html.escape(title)
    safe_date = html.escape(date)
    safe_body = clean_html(body)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="index, follow">
<meta name="description" content="{html.escape(title, quote=True)}">
<link rel="canonical" href="{canonical}">
<title>{safe_title} | Window Repair Today</title>
<style>
body {{
  margin: 0;
  background: #f7f9f7;
  color: #29352f;
  font: 16px/1.8 Arial, sans-serif;
}}
header, footer {{
  padding: 24px;
  text-align: center;
  background: white;
}}
header a {{
  color: #315b43;
  text-decoration: none;
  font-weight: bold;
}}
main {{
  max-width: 800px;
  margin: 40px auto;
  padding: 35px;
  background: white;
  border-radius: 12px;
}}
h1 {{ color: #315b43; line-height: 1.3; }}
img {{ max-width: 100%; height: auto; }}
a {{ color: #315b43; }}
time {{ color: #66756b; font-size: 14px; }}
</style>
</head>
<body>
<header>
<a href="{BASE_PATH}">Window Repair Today</a>
</header>
<main>
<article>
<h1>{safe_title}</h1>
<p><time datetime="{safe_date}">{safe_date}</time></p>
<div class="article-content">
{safe_body}
</div>
</article>
</main>
<footer>Window Repair Today &copy; 2026</footer>
</body>
</html>
"""

    (ARTICLES_DIR / filename).write_text(
        page, encoding="utf-8"
    )

    return {
        "title": title,
        "url": f"{BASE_PATH}articles/{filename}",
        "date": date,
        "number": number
    }


def update_homepage(articles):
    path = Path("index.html")
    soup = BeautifulSoup(
        path.read_text(encoding="utf-8"),
        "html.parser"
    )

    container = soup.select_one(".article-list")

    if container is None:
        raise RuntimeError("Article list not found")

    container.clear()

    for article in articles:
        paragraph = soup.new_tag("p")
        link = soup.new_tag(
            "a", href=article["url"]
        )
        link.string = article["title"]
        paragraph.append(link)
        container.append(paragraph)

    path.write_text(
        str(soup), encoding="utf-8"
    )


def main():
    issues = get_issues()

    issues.sort(
        key=lambda x: x.get("created_at", ""),
        reverse=True
    )

    articles = []

    for issue in issues:
        articles.append(create_article(issue))

    update_homepage(articles)

    print(f"Published {len(articles)} articles")


if __name__ == "__main__":
    main()
