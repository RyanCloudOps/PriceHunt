from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from app.scrapers.base import ScrapedItem, Scraper, parse_price


class LdlcScraper(Scraper):
    key = "ldlc"
    base = "https://www.ldlc.com"

    def search(self, query: str) -> list[ScrapedItem]:
        html = self.fetch(f"{self.base}/es-es/buscar/{quote(query)}/")
        return self.parse(html)

    @classmethod
    def parse(cls, html: str) -> list[ScrapedItem]:
        soup = BeautifulSoup(html, "html.parser")
        items: list[ScrapedItem] = []
        for li in soup.select("li.pdt-item"):
            link = li.select_one(".title-3 a")
            price_el = li.select_one(".new-price") or li.select_one(".price")
            pid = li.get("data-id")
            if not (link and price_el and pid):
                continue
            price = parse_price(price_el.get_text(""))
            if price is None:
                continue
            old_el = li.select_one(".old-price")
            img = li.select_one(".pic img")
            items.append(
                ScrapedItem(
                    external_id=str(pid),
                    title=link.get_text(" ", strip=True),
                    url=urljoin(cls.base, link["href"]),
                    price=price,
                    original_price=parse_price(old_el.get_text("")) if old_el else None,
                    image_url=img.get("src") if img else None,
                )
            )
        return items
