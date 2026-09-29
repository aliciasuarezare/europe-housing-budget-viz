import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config import CITIES, COUNTRY_CAPITALS

BASE_URL = "https://homestra.com"
SEARCH_URL = f"{BASE_URL}/list/houses-for-sale/"
PROPERTY_TYPES = {"house", "apartment", "flat", "townhouse", "maison", "villa"}


class HomestraScraper:
    """Conservative scraper for publicly accessible Homestra listing pages.

    It uses the public search/detail pages only, identifies JSON-LD and visible
    listing data, waits between requests, and never invents missing values.
    """

    def __init__(self, delay=1.5, max_pages=20):
        self.delay = delay
        self.max_pages = max_pages
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; university-data-project/1.0; +https://github.com/aliciasuarezare/europe-housing-budget-viz)",
            "Accept": "text/html,application/xhtml+xml",
        })
        self.properties = []

    def _get(self, url, params=None):
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        time.sleep(self.delay)
        return response

    @staticmethod
    def _number(value):
        if value is None:
            return None
        text = str(value).replace("\xa0", " ").strip()
        numbers = re.findall(r"\d+(?:[.,]\d+)?", text.replace(".", "").replace(",", "."))
        if not numbers:
            return None
        try:
            return float(numbers[0])
        except ValueError:
            return None

    @staticmethod
    def _price(value):
        if value is None:
            return None
        text = str(value).replace("\xa0", " ")
        digits = re.sub(r"[^0-9]", "", text)
        return float(digits) if digits else None

    @staticmethod
    def _text(node):
        return node.get_text(" ", strip=True) if node else None

    def _json_ld(self, soup):
        records = []
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                import json
                value = json.loads(script.string or script.get_text())
                values = value if isinstance(value, list) else value.get("@graph", [value]) if isinstance(value, dict) else []
                records.extend(v for v in values if isinstance(v, dict))
            except (ValueError, TypeError):
                continue
        return records

    def _listing_urls(self, soup):
        urls = set()
        for link in soup.select('a[href*="/property/"]'):
            href = urljoin(BASE_URL, link.get("href", "")).split("#")[0]
            if urlparse(href).netloc.endswith("homestra.com"):
                urls.add(href.rstrip("/") + "/")
        return urls

    def _extract_detail(self, url, fallback_city=None, fallback_country=None):
        soup = BeautifulSoup(self._get(url).text, "lxml")
        records = self._json_ld(soup)
        data = next((x for x in records if x.get("@type") in {"Product", "Residence", "RealEstateListing", "Offer"}), {})
        text = soup.get_text(" ", strip=True)
        title = data.get("name") or self._text(soup.select_one("h1"))
        offers = data.get("offers", {}) if isinstance(data.get("offers"), dict) else {}
        price = self._price(offers.get("price") or data.get("price"))
        if price is None:
            price = self._price(re.search(r"€\s?[\d.,]+", text).group(0)) if re.search(r"€\s?[\d.,]+", text) else None
        address = data.get("address")
        if isinstance(address, dict):
            address = ", ".join(str(address.get(k)) for k in ("addressLocality", "addressRegion", "addressCountry") if address.get(k))
        address = address or self._text(soup.select_one('[itemprop="address"], .address, [class*="address"]'))
        city = fallback_city or self._city_from_address(address)
        country = fallback_country or self._country_from_address(address)
        size = self._number(data.get("floorSize") or data.get("size"))
        if size is None:
            match = re.search(r"(\d+(?:[.,]\d+)?)\s*m(?:²|2)", text, re.I)
            size = self._number(match.group(1)) if match else None
        geo = data.get("geo") if isinstance(data.get("geo"), dict) else {}
        return {
            "source_id": data.get("productID") or data.get("sku"),
            "country": country,
            "city": city,
            "neighbourhood": None,
            "price_eur": price,
            "size_m2": size,
            "price_per_m2": price / size if price and size else None,
            "bedrooms": self._number(data.get("numberOfBedrooms")),
            "bathrooms": self._number(data.get("numberOfBathrooms")),
            "property_type": data.get("additionalType") or data.get("@type"),
            "listing_url": url,
            "listing_date": data.get("datePosted") or data.get("datePublished"),
            "latitude": geo.get("latitude"),
            "longitude": geo.get("longitude"),
            "is_capital": city == COUNTRY_CAPITALS.get((country or "").lower()),
            "scrape_date": datetime.now(timezone.utc).isoformat(),
            "title": title,
        }

    @staticmethod
    def _city_from_address(address):
        if not address:
            return None
        lowered = address.lower()
        return next((city for city in CITIES if city.lower() in lowered), None)

    @staticmethod
    def _country_from_address(address):
        if not address:
            return None
        lowered = address.lower()
        country_names = {"netherlands":"NL", "spain":"ES", "portugal":"PT", "france":"FR", "italy":"IT", "germany":"DE", "belgium":"BE", "austria":"AT", "greece":"GR", "ireland":"IE", "united kingdom":"UK", "denmark":"DK", "sweden":"SE", "norway":"NO", "finland":"FI", "latvia":"LV", "croatia":"HR", "bulgaria":"BG", "cyprus":"CY"}
        return next((code for name, code in country_names.items() if name in lowered), None)

    def scrape(self, output="data/homestra_properties_raw.csv"):
        for page in range(1, self.max_pages + 1):
            response = self._get(SEARCH_URL, params={"minimum-price": 200000, "maximum-price": 400000, "page": page})
            soup = BeautifulSoup(response.text, "lxml")
            urls = self._listing_urls(soup)
            if not urls:
                break
            for url in sorted(urls):
                try:
                    item = self._extract_detail(url)
                    if item["price_eur"] and item["size_m2"] and 200000 <= item["price_eur"] <= 400000:
                        self.properties.append(item)
                except requests.RequestException as exc:
                    print(f"Skipping inaccessible listing {url}: {exc}")
        df = pd.DataFrame(self.properties).drop_duplicates(subset=["listing_url"])
        os.makedirs(os.path.dirname(output), exist_ok=True)
        df.to_csv(output, index=False)
        print(f"Saved {len(df)} verified Homestra listings to {output}")
        return df


if __name__ == "__main__":
    HomestraScraper(delay=float(os.getenv("HOMESTRA_DELAY", "1.5")), max_pages=int(os.getenv("HOMESTRA_MAX_PAGES", "20"))).scrape()
