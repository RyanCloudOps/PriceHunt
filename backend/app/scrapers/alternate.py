from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from app.scrapers.base import ScrapedItem, Scraper, parse_price


class AlternateScraper(Scraper):
    key = "alternate"
    base = "https://www.alternate.es"

    def search(self, query: str) -> list[ScrapedItem]:
        # 24 productos por página; se para cuando una página ya no aporta nada nuevo
        items: list[ScrapedItem] = []
        seen: set[str] = set()
        for page in range(1, self.settings.max_pages + 1):
            suffix = f"&page={page}" if page > 1 else ""
            html = self.fetch(f"{self.base}/listing.xhtml?q={quote_plus(query)}{suffix}")
            batch = [i for i in self.parse(html) if i.external_id not in seen]
            if not batch:
                break
            seen.update(i.external_id for i in batch)
            items.extend(batch)
        return items

    @classmethod
    def parse(cls, html: str) -> list[ScrapedItem]:
        soup = BeautifulSoup(html, "html.parser")
        items: list[ScrapedItem] = []
        for box in soup.select("a.productBox"):
            href = box.get("href", "")
            name = box.select_one(".product-name")
            price_el = box.select_one(".price")
            if not (href and name and price_el):
                continue
            # Sin stock ("El artículo no puede ser comprado"): el precio no es una oferta real
            delivery = box.select_one(".delivery-info")
            if delivery and "no puede ser comprado" in delivery.get_text():
                continue
            price = parse_price(price_el.get_text(""))
            if price is None:
                continue
            old_el = box.select_one(".line-through")
            sub = box.select_one(".product-name-sub")
            img = box.select_one("img.productPicture")
            title = name.get_text(" ", strip=True)
            items.append(
                ScrapedItem(
                    external_id=href.rstrip("/").rsplit("/", 1)[-1],
                    title=f"{title} {sub.get_text(' ', strip=True)}" if sub else title,
                    url=urljoin(cls.base, href),
                    price=price,
                    original_price=parse_price(old_el.get_text("")) if old_el else None,
                    image_url=urljoin(cls.base, img["src"]) if img and img.get("src") else None,
                    description=" ".join(
                        li.get_text(" ", strip=True) for li in box.select(".product-bullet-list li")
                    )
                    or None,
                )
            )
        return items
