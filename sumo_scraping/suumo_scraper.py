#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import json
from datetime import datetime
import os
from urllib.parse import urljoin, urlparse
import logging
from pydantic import ValidationError
try:
    from .models import PropertyInfo, RoomInfo, ScrapingResult
except ImportError:
    from models import PropertyInfo, RoomInfo, ScrapingResult

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SuumoScraper:
    def __init__(self, base_url="https://suumo.jp/chintai/tokyo/en_yamanotesen/"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.properties = []
        self.validation_errors = []
        
    def get_soup(self, url):
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'lxml')
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def extract_property_info(self, property_elem):
        try:
            property_data = {}
            
            title_elem = property_elem.find('h2', class_='cassetteitem_content-title')
            property_data['title'] = title_elem.text.strip() if title_elem else ''
            
            address_elem = property_elem.find('li', class_='cassetteitem_detail-col1')
            property_data['address'] = address_elem.text.strip() if address_elem else ''
            
            access_elem = property_elem.find('li', class_='cassetteitem_detail-col2')
            property_data['access'] = access_elem.text.strip() if access_elem else ''
            
            age_area_elem = property_elem.find('li', class_='cassetteitem_detail-col3')
            property_data['building_age_area'] = age_area_elem.text.strip() if age_area_elem else ''
            
            rooms_info = []
            tbody = property_elem.find('tbody')
            if tbody:
                for tr in tbody.find_all('tr', class_='js-cassette_link'):
                    room_data = {}
                    
                    floor_elem = tr.find('td', class_='ui-text--midium')
                    room_data['floor'] = floor_elem.text.strip() if floor_elem else ''
                    
                    rent_elem = tr.find('span', class_='cassetteitem_price--rent')
                    room_data['rent'] = rent_elem.text.strip() if rent_elem else ''
                    
                    admin_elem = tr.find('span', class_='cassetteitem_price--administration')
                    room_data['admin_fee'] = admin_elem.text.strip() if admin_elem else ''
                    
                    deposit_key_elem = tr.find('span', class_='cassetteitem_price--deposit')
                    room_data['deposit_key_money'] = deposit_key_elem.text.strip() if deposit_key_elem else ''
                    
                    layout_elem = tr.find('span', class_='cassetteitem_madori')
                    room_data['layout'] = layout_elem.text.strip() if layout_elem else ''
                    
                    area_elem = tr.find('span', class_='cassetteitem_menseki')
                    room_data['area'] = area_elem.text.strip() if area_elem else ''
                    
                    detail_link_elem = tr.find('a')
                    if detail_link_elem and detail_link_elem.get('href'):
                        room_data['detail_url'] = urljoin(self.base_url, detail_link_elem['href'])
                    
                    try:
                        room = RoomInfo(**room_data)
                        rooms_info.append(room)
                    except ValidationError as e:
                        logger.warning(f"Room validation error: {e}")
                        self.validation_errors.append({"type": "room", "data": room_data, "error": str(e)})
            
            property_data['rooms'] = rooms_info
            
            try:
                property_obj = PropertyInfo(**property_data)
                return property_obj
            except ValidationError as e:
                logger.warning(f"Property validation error: {e}")
                self.validation_errors.append({"type": "property", "data": property_data, "error": str(e)})
                return None
            
        except Exception as e:
            logger.error(f"Error extracting property info: {e}")
            return None
    
    def scrape_page(self, url):
        logger.info(f"Scraping page: {url}")
        soup = self.get_soup(url)
        if not soup:
            return []
        
        properties = []
        property_units = soup.find_all('div', class_='cassetteitem')
        
        for unit in property_units:
            property_info = self.extract_property_info(unit)
            if property_info:
                properties.append(property_info)
        
        return properties
    
    def get_next_page_url(self, soup):
        next_link = soup.find('p', class_='pagination-parts')
        if next_link:
            next_a = next_link.find_next_sibling('p')
            if next_a and next_a.find('a'):
                return urljoin(self.base_url, next_a.find('a')['href'])
        return None
    
    def scrape_all_pages(self, max_pages=None):
        current_url = self.base_url
        page_count = 0
        
        while current_url and (max_pages is None or page_count < max_pages):
            soup = self.get_soup(current_url)
            if not soup:
                break
                
            page_properties = self.scrape_page(current_url)
            valid_properties = [prop for prop in page_properties if prop is not None]
            self.properties.extend(valid_properties)
            
            logger.info(f"Scraped {len(valid_properties)} valid properties from page {page_count + 1}")
            
            current_url = self.get_next_page_url(soup)
            page_count += 1
            
            if current_url:
                time.sleep(2)
        
        logger.info(f"Total properties scraped: {len(self.properties)}")
        if self.validation_errors:
            logger.warning(f"Total validation errors: {len(self.validation_errors)}")
        
        try:
            result = ScrapingResult(
                properties=self.properties,
                total_count=len(self.properties),
                pages_scraped=page_count,
                source_url=self.base_url
            )
            return result
        except ValidationError as e:
            logger.error(f"Scraping result validation error: {e}")
            return None
    
    def save_to_json(self, scraping_result=None, filename=None):
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'suumo_properties_{timestamp}.json'
        
        os.makedirs('data', exist_ok=True)
        filepath = os.path.join('data', filename)
        
        data_to_save = scraping_result.dict() if scraping_result else [prop.dict() for prop in self.properties]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2, default=str)
        
        if self.validation_errors:
            error_filepath = os.path.join('data', f'validation_errors_{timestamp}.json')
            with open(error_filepath, 'w', encoding='utf-8') as f:
                json.dump(self.validation_errors, f, ensure_ascii=False, indent=2)
            logger.info(f"Validation errors saved to {error_filepath}")
        
        logger.info(f"Data saved to {filepath}")
        return filepath
    
    def save_to_csv(self, filename=None):
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'suumo_properties_{timestamp}.csv'
        
        os.makedirs('data', exist_ok=True)
        filepath = os.path.join('data', filename)
        
        flattened_data = []
        for prop in self.properties:
            base_info = {
                'building_title': prop.title,
                'address': prop.address,
                'access': prop.access,
                'building_age_area': prop.building_age_area,
                'building_age': prop.building_age,
                'station_info': ', '.join(prop.station_info),
                'min_rent': prop.min_rent,
                'max_rent': prop.max_rent,
                'scraped_at': prop.scraped_at.isoformat()
            }
            
            for room in prop.rooms:
                room_data = base_info.copy()
                room_data.update({
                    'floor': room.floor,
                    'rent': room.rent,
                    'rent_numeric': room.rent_numeric,
                    'admin_fee': room.admin_fee,
                    'admin_fee_numeric': room.admin_fee_numeric,
                    'deposit_key_money': room.deposit_key_money,
                    'layout': room.layout,
                    'area': room.area,
                    'area_numeric': room.area_numeric,
                    'detail_url': room.detail_url
                })
                flattened_data.append(room_data)
        
        df = pd.DataFrame(flattened_data)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        logger.info(f"Data saved to {filepath}")
        return filepath

def main():
    scraper = SuumoScraper()
    
    logger.info("Starting SUUMO scraper...")
    result = scraper.scrape_all_pages(max_pages=3)
    
    if result and result.properties:
        json_path = scraper.save_to_json(result)
        csv_path = scraper.save_to_csv()
        
        logger.info(f"Scraping completed successfully!")
        logger.info(f"Total properties: {result.total_count}")
        logger.info(f"Pages scraped: {result.pages_scraped}")
        logger.info(f"Average rent: {result.average_rent:.0f}円" if result.average_rent else "Average rent: N/A")
        logger.info(f"Layout distribution: {result.layout_distribution}")
        logger.info(f"JSON data: {json_path}")
        logger.info(f"CSV data: {csv_path}")
    else:
        logger.warning("No properties were scraped.")

if __name__ == "__main__":
    main()