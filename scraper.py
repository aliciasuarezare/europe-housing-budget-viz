import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://homestra.com"


class HomestraScraper:
    """Scraper for publicly accessible Homestra listing pages."""

    def __init__(self, delay=2.0, max_pages=5):
        self.delay = delay
        self.max_pages = max_pages
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; university-research/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        self.properties = []

    def _get(self, url, params=None, timeout=30):
        """Make HTTP request with retry logic."""
        for attempt in range(3):
            try:
                response = self.session.get(url, params=params, timeout=timeout)
                response.raise_for_status()
                time.sleep(self.delay)
                return response
            except requests.RequestException as e:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        return None

    @staticmethod
    def _parse_price(text):
        """Extract numeric price from text."""
        if not text:
            return None
        digits = re.sub(r'[^\d]', '', str(text))
        return float(digits) if digits else None

    @staticmethod
    def _parse_size(text):
        """Extract numeric size from text."""
        if not text:
            return None
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*m[²2]?', str(text), re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(',', '.'))
            except ValueError:
                return None
        return None

    @staticmethod
    def _extract_text(element):
        """Safely extract text from element."""
        return element.get_text(strip=True) if element else None

    def _scrape_search_page(self, url, params):
        """Scrape a single search results page."""
        try:
            response = self._get(url, params=params)
            if not response:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            listing_urls = set()
            
            for link in soup.select('a[href*="/property/"]'):
                href = link.get('href', '')
                if href:
                    full_url = urljoin(BASE_URL, href).split('#')[0].rstrip('/')
                    if 'property' in full_url:
                        listing_urls.add(full_url)
            
            return list(listing_urls)
        except Exception as e:
            print(f"Error scraping search page: {e}")
            return []

    def _extract_property_detail(self, url):
        """Extract property details from a Homestra listing page."""
        try:
            response = self._get(url, timeout=20)
            if not response:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text(' ', strip=True)

            # Title
            title = None
            h1 = soup.select_one('h1')
            if h1:
                title = self._extract_text(h1)

            # Price
            price = None
            for pattern in [r'€\s*([\d.,]+)', r'Price:?\s*€?\s*([\d.,]+)']:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    price = self._parse_price(match.group(1))
                    if price:
                        break

            # Size
            size = None
            match = re.search(r'(\d+(?:[.,]\d+)?)\s*m[²2]', text, re.IGNORECASE)
            if match:
                size = self._parse_size(match.group(0))

            # Bedrooms
            bedrooms = None
            match = re.search(r'(\d+)\s*(?:bedroom|bed|chambre|schlafzimmer)', text, re.IGNORECASE)
            if match:
                try:
                    bedrooms = int(match.group(1))
                except ValueError:
                    pass

            # City detection
            city = None
            common_cities = [
                'amsterdam', 'rotterdam', 'madrid', 'barcelona', 'valencia', 'lisbon', 'porto',
                'paris', 'lyon', 'rome', 'milan', 'florence', 'berlin', 'munich', 'brussels',
                'vienna', 'athens', 'dublin', 'london', 'copenhagen', 'stockholm', 'oslo',
                'helsinki', 'riga', 'zagreb', 'sofia'
            ]
            for c in common_cities:
                if c in text.lower():
                    city = c.capitalize()
                    break
            if not city:
                for c in common_cities:
                    if c in url.lower():
                        city = c.capitalize()
                        break

            # Country detection
            country = None
            country_map = {
                'netherlands': 'NL', 'spain': 'ES', 'portugal': 'PT', 'france': 'FR',
                'italy': 'IT', 'germany': 'DE', 'belgium': 'BE', 'austria': 'AT',
                'greece': 'GR', 'ireland': 'IE', 'united kingdom': 'UK', 'denmark': 'DK',
                'sweden': 'SE', 'norway': 'NO', 'finland': 'FI', 'latvia': 'LV',
                'croatia': 'HR', 'bulgaria': 'BG', 'cyprus': 'CY'
            }
            for name, code in country_map.items():
                if name in text.lower():
                    country = code
                    break

            # Require the fields we need
            if not (price and size and city):
                return None
            if not (200000 <= price <= 400000 and 10 <= size <= 5000):
                return None

            clean = {
                'country': country,
                'city': city,
                'neighbourhood': None,
                'price_eur': price,
                'size_m2': size,
                'price_per_m2': round(price / size, 2),
                'bedrooms': bedrooms,
                'bathrooms': None,
                'property_type': 'Residential',
                'listing_url': url,
                'listing_date': None,
                'latitude': None,
                'longitude': None,
                'is_capital': False,
                'scrape_date': datetime.now(timezone.utc).isoformat(),
                'title': title,
            }
            return clean
        except Exception as e:
            print(f"Error extracting from {url}: {e}")
            return None

    def scrape(self, output_path='data/homestra_properties_raw.csv'):
        """Run the complete scraper."""
        print('Starting Homestra public listing scraper...')
        urls = set()
        for page in range(1, self.max_pages + 1):
            print(f'Scraping page {page}...')
            search_url = f'{BASE_URL}/list/houses-for-sale/'
            params = {'minimum-price': 200000, 'maximum-price': 400000, 'page': page}
            response = self._get(search_url, params=params)
            if not response:
                break
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.select('a[href*="/property/"]'):
                href = link.get('href')
                if href:
                    full_url = urljoin(BASE_URL, href).split('#')[0].rstrip('/')
                    if 'property' in full_url:
                        urls.add(full_url)
            if not urls:
                break
            if page >= 3:
                break
        print(f'Found {len(urls)} candidate property URLs')

        for url in sorted(urls):
            prop = self._extract_property_detail(url)
            if prop:
                self.properties.append(prop)

        if self.properties:
            df = pd.DataFrame(self.properties).drop_duplicates(subset=['listing_url'])
        else:
            df = pd.DataFrame(columns=[
                'country', 'city', 'neighbourhood', 'price_eur', 'size_m2', 'price_per_m2',
                'bedrooms', 'bathrooms', 'property_type', 'listing_url', 'listing_date',
                'latitude', 'longitude', 'is_capital', 'scrape_date', 'title'
            ])

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f'Saved {len(df)} records to {output_path}')
        return df


if __name__ == '__main__':
    delay = float(os.getenv('HOMESTRA_DELAY', '2.0'))
    max_pages = int(os.getenv('HOMESTRA_MAX_PAGES', '3'))
    HomestraScraper(delay=delay, max_pages=max_pages).scrape()
