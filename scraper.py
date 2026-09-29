import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
import csv
import os
from datetime import datetime
import json
from urllib.parse import urljoin

class Homestra Scraper:
    def __init__(self):
        self.base_url = "https://homestra.com"
        self.properties = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # European cities to search
        self.cities = {
            'Amsterdam': 'nl',
            'Rotterdam': 'nl',
            'Madrid': 'es',
            'Barcelona': 'es',
            'Valencia': 'es',
            'Lisbon': 'pt',
            'Porto': 'pt',
            'Paris': 'fr',
            'Lyon': 'fr',
            'Rome': 'it',
            'Milan': 'it',
            'Florence': 'it',
            'Berlin': 'de',
            'Munich': 'de',
            'Brussels': 'be',
            'Vienna': 'at',
            'Athens': 'gr',
            'Thessaloniki': 'gr',
            'Dublin': 'ie',
            'London': 'uk',
            'Copenhagen': 'dk',
            'Stockholm': 'se',
            'Oslo': 'no',
            'Helsinki': 'fi',
            'Riga': 'lv',
            'Zagreb': 'hr',
            'Sofia': 'bg',
            'Nicosia': 'cy'
        }
        
        self.country_capitals = {
            'nl': 'Amsterdam',
            'es': 'Madrid',
            'pt': 'Lisbon',
            'fr': 'Paris',
            'it': 'Rome',
            'de': 'Berlin',
            'be': 'Brussels',
            'at': 'Vienna',
            'gr': 'Athens',
            'ie': 'Dublin',
            'uk': 'London',
            'dk': 'Copenhagen',
            'se': 'Stockholm',
            'no': 'Oslo',
            'fi': 'Helsinki',
            'lv': 'Riga',
            'hr': 'Zagreb',
            'bg': 'Sofia',
            'cy': 'Nicosia'
        }

    def search_homestra(self, city, country_code, min_price=200000, max_price=400000):
        """Search Homestra for properties in a city within price range"""
        print(f"Searching {city}, {country_code}...")
        
        try:
            # Construct search URL for Homestra
            search_url = f"{self.base_url}/en/search"
            params = {
                'city': city,
                'country': country_code,
                'price_min': min_price,
                'price_max': max_price,
                'property_type': ['apartment', 'house', 'townhouse']
            }
            
            response = self.session.get(search_url, params=params, timeout=10)
            response.raise_for_status()
            
            # Parse results
            soup = BeautifulSoup(response.content, 'lxml')
            self.parse_listings(soup, city, country_code)
            
            time.sleep(2)  # Respectful rate limiting
            
        except Exception as e:
            print(f"Error searching {city}: {str(e)}")

    def parse_listings(self, soup, city, country_code):
        """Parse property listings from Homestra search results"""
        listings = soup.find_all('div', class_='property-card')
        
        for listing in listings:
            try:
                property_data = self.extract_property_data(listing, city, country_code)
                if property_data:
                    self.properties.append(property_data)
            except Exception as e:
                print(f"Error parsing listing: {str(e)}")
                continue

    def extract_property_data(self, listing_element, city, country_code):
        """Extract data from a single property listing"""
        try:
            # Extract basic information
            title = listing_element.find('h2', class_='property-title')
            price_elem = listing_element.find('span', class_='property-price')
            size_elem = listing_element.find('span', class_='property-size')
            bedrooms_elem = listing_element.find('span', class_='property-beds')
            
            if not all([title, price_elem, size_elem]):
                return None
            
            # Parse price
            price_text = price_elem.text.strip()
            price = self.parse_price(price_text)
            
            # Parse size
            size_text = size_elem.text.strip()
            size_m2 = self.parse_size(size_text)
            
            if price is None or size_m2 is None:
                return None
            
            # Parse bedrooms
            bedrooms = None
            if bedrooms_elem:
                bedrooms_text = bedrooms_elem.text.strip()
                bedrooms = self.parse_bedrooms(bedrooms_text)
            
            # Get listing URL
            link_elem = listing_element.find('a', class_='property-link')
            listing_url = link_elem['href'] if link_elem else None
            if listing_url and not listing_url.startswith('http'):
                listing_url = urljoin(self.base_url, listing_url)
            
            # Extract bathrooms if available
            bathrooms_elem = listing_element.find('span', class_='property-baths')
            bathrooms = None
            if bathrooms_elem:
                bathrooms_text = bathrooms_elem.text.strip()
                bathrooms = self.parse_bathrooms(bathrooms_text)
            
            # Determine property type
            property_type = self.determine_property_type(listing_element)
            
            # Calculate price per m²
            price_per_m2 = price / size_m2 if size_m2 > 0 else None
            
            return {
                'country': country_code.upper(),
                'city': city,
                'neighbourhood': self.extract_neighbourhood(listing_element),
                'price_eur': price,
                'size_m2': size_m2,
                'price_per_m2': price_per_m2,
                'bedrooms': bedrooms,
                'bathrooms': bathrooms,
                'property_type': property_type,
                'listing_url': listing_url,
                'listing_date': self.extract_listing_date(listing_element),
                'is_capital': city == self.country_capitals.get(country_code),
                'scrape_date': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error extracting property data: {str(e)}")
            return None

    @staticmethod
    def parse_price(price_text):
        """Extract numeric price from text"""
        try:
            price_text = price_text.replace('€', '').replace(',', '').strip()
            return float(price_text)
        except:
            return None

    @staticmethod
    def parse_size(size_text):
        """Extract numeric size from text"""
        try:
            size_text = size_text.replace('m²', '').replace('m2', '').strip()
            return float(size_text)
        except:
            return None

    @staticmethod
    def parse_bedrooms(bedrooms_text):
        """Extract number of bedrooms"""
        try:
            return int(bedrooms_text.split()[0])
        except:
            return None

    @staticmethod
    def parse_bathrooms(bathrooms_text):
        """Extract number of bathrooms"""
        try:
            return float(bathrooms_text.split()[0])
        except:
            return None

    @staticmethod
    def extract_neighbourhood(listing_element):
        """Extract neighbourhood/area if available"""
        area_elem = listing_element.find('span', class_='property-area')
        return area_elem.text.strip() if area_elem else None

    @staticmethod
    def extract_listing_date(listing_element):
        """Extract listing date if available"""
        date_elem = listing_element.find('span', class_='listing-date')
        return date_elem.text.strip() if date_elem else None

    @staticmethod
    def determine_property_type(listing_element):
        """Determine property type from listing"""
        type_elem = listing_element.find('span', class_='property-type')
        if type_elem:
            type_text = type_elem.text.strip().lower()
            if 'apartment' in type_text or 'flat' in type_text:
                return 'Apartment'
            elif 'house' in type_text:
                return 'House'
            elif 'townhouse' in type_text or 'town house' in type_text:
                return 'Townhouse'
        return 'Residential'

    def scrape_all_cities(self):
        """Scrape all cities"""
        for city, country_code in self.cities.items():
            self.search_homestra(city, country_code)
        
        return self.properties

    def save_to_csv(self, filename='data/homestra_properties_raw.csv'):
        """Save collected properties to CSV"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        if not self.properties:
            print("No properties to save")
            return
        
        df = pd.DataFrame(self.properties)
        df.to_csv(filename, index=False)
        print(f"Saved {len(self.properties)} properties to {filename}")
        
        return df


if __name__ == "__main__":
    scraper = Homestra Scraper()
    properties = scraper.scrape_all_cities()
    scraper.save_to_csv()
    
    print(f"\nTotal properties collected: {len(properties)}")
