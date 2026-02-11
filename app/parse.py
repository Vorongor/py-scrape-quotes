import csv
import logging
import re
import sys
from urllib.parse import urljoin

import requests
from dataclasses import dataclass, fields, astuple

import unicodedata
from bs4 import BeautifulSoup, Tag

BASE_URL = "https://quotes.toscrape.com/"
AUTHOR_URL = urljoin(BASE_URL, "author/")


@dataclass
class Quote:
    text: str
    author: str
    tags: list[str]


@dataclass
class Author:
    fullname: str
    born_date: str
    born_location: str
    description: str


QUOTE_FIELDS = [field.name for field in fields(Quote)]
AUTHOR_FIELDS = [field.name for field in fields(Author)]

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)8s]: %(message)s",
    handlers=[
        logging.FileHandler("pars.log"),
        logging.StreamHandler(sys.stdout),
    ]
)

AUTHORS_CACHE = set()


def create_quote(data: Tag) -> Quote:
    quote = Quote(
        text=data.select_one(".text").text,
        author=data.select_one(".author").text,
        tags=[tag.text for tag in data.select(".tag")],
    )
    author_name = quote.author
    if author_name not in AUTHORS_CACHE:
        AUTHORS_CACHE.add(author_name)
        logging.debug(f"New author added to cache: {author_name}")

    return quote


def scrap_single_page(url: str, session: requests.Session) -> list[Quote]:
    logging.info(f"Scraping page:{url}")
    response = session.get(url)
    if response.status_code != 200:
        return []
    soup = BeautifulSoup(response.content, "html.parser")
    return [create_quote(quote_data) for quote_data in soup.select(".quote")]


def slugify_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    nfkd_form = unicodedata.normalize("NFKD", name)
    name = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    name = name.replace("'", "")
    name = name.replace(".", "-").replace(" ", "-")
    name = re.sub(r"-+", "-", name)

    return name.strip("-")


def scrap_author_page(url: str, session: requests.Session) -> Author | None:
    logging.info(f"Scraping page:{url}")
    response = session.get(url)
    if response.status_code != 200:
        return
    soup = BeautifulSoup(response.content, "html.parser")
    details = soup.select_one(".author-details")
    return Author(
        fullname=details.select_one(".author-title").text,
        born_date=details.select_one(".author-born-date").text,
        born_location=details.select_one(".author-born-location").text,
        description=details.select_one(".author-description").text.strip(
            "\n", ).strip(),
    )


def write_data_to_file(
        data: list[Quote] | list[Author],
        fields_row: list[str],
        file_name: str
) -> None:
    with open(file_name, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(fields_row)
        writer.writerows(
            [astuple(quote) for quote in data]
        )


def main(output_csv_path: str) -> None:
    with requests.Session() as session:
        result = []
        page = 1
        while True:
            url = urljoin(BASE_URL, f"page/{page}/")
            scraped_data = scrap_single_page(url, session)
            if not scraped_data:
                break
            result.extend(scraped_data)
            page += 1
        author_data = []
        for author in AUTHORS_CACHE:
            slug = slugify_name(author)
            author_url = urljoin(AUTHOR_URL, f"{slug}/")
            response = scrap_author_page(author_url, session)
            if response:
                author_data.append(response)
    logging.info(
        f"Scraping end. Quotes: {len(result)}, Authors: {len(author_data)}")
    write_data_to_file(result, QUOTE_FIELDS, output_csv_path)
    write_data_to_file(author_data, AUTHOR_FIELDS, "authors.csv")
    logging.info("All done!")


if __name__ == "__main__":
    main("quotes.csv")
