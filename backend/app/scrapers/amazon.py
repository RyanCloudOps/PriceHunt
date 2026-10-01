"""Amazon vía Product Advertising API 5.

Amazon.es protege las páginas de búsqueda con un challenge anti-bot, así que el
scraping HTML no es viable (ni permitido por sus condiciones). La vía oficial es
PA-API 5, que requiere una cuenta de Amazon Afiliados con ventas cualificadas.
Sin credenciales este scraper se desactiva y la tienda queda como acceso directo.
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.config import Settings
from app.scrapers.base import BlockedError, ScrapedItem, Scraper, ScraperError

_SERVICE = "ProductAdvertisingAPI"
_TARGET = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
_PATH = "/paapi5/searchitems"
_RESOURCES = [
    "ItemInfo.Title",
    "Images.Primary.Large",
    "Offers.Listings.Price",
    "Offers.Listings.SavingBasis",
]


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def sigv4_headers(
    *, access_key: str, secret_key: str, host: str, region: str, body: str, now: datetime
) -> dict[str, str]:
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    headers = {
        "content-encoding": "amz-1.0",
        "content-type": "application/json; charset=utf-8",
        "host": host,
        "x-amz-date": amz_date,
        "x-amz-target": _TARGET,
    }
    signed = ";".join(sorted(headers))
    canonical_headers = "".join(f"{k}:{headers[k]}\n" for k in sorted(headers))
    canonical_request = "\n".join(
        ["POST", _PATH, "", canonical_headers, signed, hashlib.sha256(body.encode()).hexdigest()]
    )
    scope = f"{datestamp}/{region}/{_SERVICE}/aws4_request"
    to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ]
    )
    key = _sign(f"AWS4{secret_key}".encode(), datestamp)
    for part in (region, _SERVICE, "aws4_request"):
        key = _sign(key, part)
    signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    headers["Authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
        f"SignedHeaders={signed}, Signature={signature}"
    )
    return headers


def _amount(node: dict | None) -> Decimal | None:
    if not node:
        return None
    # Offers (v1): {"Amount": 1.0}; OffersV2: {"Money": {"Amount": 1.0}}
    value = node.get("Amount", (node.get("Money") or {}).get("Amount"))
    return Decimal(str(value)).quantize(Decimal("0.01")) if value is not None else None


class AmazonPaapiScraper(Scraper):
    key = "amazon"

    @classmethod
    def available(cls, settings: Settings) -> bool:
        return bool(
            settings.amazon_access_key
            and settings.amazon_secret_key
            and settings.amazon_partner_tag
        )

    def search(self, query: str) -> list[ScrapedItem]:
        s = self.settings
        body = json.dumps(
            {
                "Keywords": query,
                "SearchIndex": "All",
                "ItemCount": 10,
                "MinSavingPercent": int(s.min_discount_pct),
                "PartnerTag": s.amazon_partner_tag,
                "PartnerType": "Associates",
                "Marketplace": s.amazon_marketplace,
                "Resources": _RESOURCES,
            }
        )
        headers = sigv4_headers(
            access_key=s.amazon_access_key or "",
            secret_key=s.amazon_secret_key or "",
            host=s.amazon_host,
            region=s.amazon_region,
            body=body,
            now=datetime.now(UTC),
        )
        try:
            resp = self.client.post(
                f"https://{s.amazon_host}{_PATH}", content=body, headers=headers
            )
        except httpx.HTTPError as exc:
            raise ScraperError(f"amazon: error de red {exc!r}") from exc
        if resp.status_code == 429:
            raise BlockedError("amazon: PA-API limitó la petición (429)")
        if resp.status_code >= 400:
            raise ScraperError(f"amazon: PA-API HTTP {resp.status_code}: {resp.text[:300]}")
        return self.parse(resp.json())

    @staticmethod
    def parse(data: dict) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        for item in (data.get("SearchResult") or {}).get("Items", []):
            offers = item.get("Offers") or item.get("OffersV2") or {}
            listing = (offers.get("Listings") or [{}])[0]
            price_node = listing.get("Price") or {}
            price = _amount(price_node)
            title = ((item.get("ItemInfo") or {}).get("Title") or {}).get("DisplayValue")
            if price is None or not title:
                continue
            basis = listing.get("SavingBasis") or price_node.get("SavingBasis")
            image = ((item.get("Images") or {}).get("Primary") or {}).get("Large") or {}
            items.append(
                ScrapedItem(
                    external_id=item["ASIN"],
                    title=title,
                    url=item.get("DetailPageURL", f"https://www.amazon.es/dp/{item['ASIN']}"),
                    price=price,
                    original_price=_amount(basis),
                    image_url=image.get("URL"),
                )
            )
        return items
