#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright
import logging
import json
import os
import argparse
from datetime import datetime
import pandas as pd
from pydantic import ValidationError
try:
    from .models import PropertyInfo, RoomInfo, ScrapingResult
    from .station_mapping import get_station_url, get_supported_stations, is_yamanote_station, get_yamanote_stations
except ImportError:
    from models import PropertyInfo, RoomInfo, ScrapingResult
    from station_mapping import get_station_url, get_supported_stations, is_yamanote_station, get_yamanote_stations

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('playwright_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SuumoPlaywrightScraper:
    def __init__(self, stations=["渋谷"], target_count=100, prefecture="tokyo"):
        self.stations = stations if isinstance(stations, list) else [stations]
        self.target_count = target_count
        self.prefecture = prefecture
        self.base_url = "https://suumo.jp"
        self.properties = []
        self.validation_errors = []
        self.current_station = None
        
    async def create_browser(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        self.page = await self.browser.new_page()
        
        await self.page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    async def close_browser(self):
        if hasattr(self, 'browser'):
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
    
    async def extract_property_info(self, property_element):
        try:
            property_data = {}
            
            # 複数のセレクタを試して物件名を取得
            title_selectors = [
                'h2.cassetteitem_content-title',
                'h3.cassetteitem_content-title', 
                'div.cassetteitem_content-title',
                '.cassetteitem_content-title',
                'h2[class*="title"]',
                'h3[class*="title"]',
                'div[class*="title"]'
            ]
            
            property_data['title'] = ''
            for selector in title_selectors:
                title_elem = await property_element.query_selector(selector)
                if title_elem:
                    text = await title_elem.inner_text()
                    if text.strip():
                        property_data['title'] = text.strip()
                        logger.debug(f"Found title with selector '{selector}': {property_data['title']}")
                        break
            
            # 住所を取得
            address_selectors = [
                'li.cassetteitem_detail-col1',
                'div.cassetteitem_detail-col1',
                '.cassetteitem_detail-col1',
                'li[class*="detail-col1"]',
                'div[class*="address"]'
            ]
            
            property_data['address'] = ''
            for selector in address_selectors:
                address_elem = await property_element.query_selector(selector)
                if address_elem:
                    text = await address_elem.inner_text()
                    if text.strip():
                        property_data['address'] = text.strip()
                        break
            
            # アクセス情報を取得
            access_selectors = [
                'li.cassetteitem_detail-col2',
                'div.cassetteitem_detail-col2',
                '.cassetteitem_detail-col2',
                'li[class*="detail-col2"]',
                'div[class*="access"]'
            ]
            
            property_data['access'] = ''
            for selector in access_selectors:
                access_elem = await property_element.query_selector(selector)
                if access_elem:
                    text = await access_elem.inner_text()
                    if text.strip():
                        property_data['access'] = text.strip()
                        break
            
            # 築年数・面積情報を取得
            age_area_selectors = [
                'li.cassetteitem_detail-col3',
                'div.cassetteitem_detail-col3',
                '.cassetteitem_detail-col3',
                'li[class*="detail-col3"]',
                'div[class*="building"]'
            ]
            
            property_data['building_age_area'] = ''
            for selector in age_area_selectors:
                age_area_elem = await property_element.query_selector(selector)
                if age_area_elem:
                    text = await age_area_elem.inner_text()
                    if text.strip():
                        property_data['building_age_area'] = text.strip()
                        break
            
            # デバッグ情報
            if not property_data['title']:
                html_content = await property_element.inner_html()
                logger.warning(f"Could not find title. Element HTML preview: {html_content[:500]}...")
            
            # 部屋情報を取得
            rooms_info = []
            room_rows = await property_element.query_selector_all('tbody tr.js-cassette_link')
            
            for row in room_rows:
                room_data = {}
                
                # 階数
                floor_elem = await row.query_selector('td.ui-text--midium')
                room_data['floor'] = await floor_elem.inner_text() if floor_elem else ''
                
                # 賃料
                rent_elem = await row.query_selector('span.cassetteitem_price--rent')
                room_data['rent'] = await rent_elem.inner_text() if rent_elem else ''
                
                # 管理費
                admin_elem = await row.query_selector('span.cassetteitem_price--administration')
                room_data['admin_fee'] = await admin_elem.inner_text() if admin_elem else ''
                
                # 敷金・礼金
                deposit_elem = await row.query_selector('span.cassetteitem_price--deposit')
                room_data['deposit_key_money'] = await deposit_elem.inner_text() if deposit_elem else ''
                
                # 間取り
                layout_elem = await row.query_selector('span.cassetteitem_madori')
                room_data['layout'] = await layout_elem.inner_text() if layout_elem else ''
                
                # 面積
                area_elem = await row.query_selector('span.cassetteitem_menseki')
                room_data['area'] = await area_elem.inner_text() if area_elem else ''
                
                # 詳細URL
                detail_link = await row.query_selector('a')
                if detail_link:
                    href = await detail_link.get_attribute('href')
                    if href:
                        room_data['detail_url'] = f"{self.base_url}{href}"
                
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
    
    async def scrape_page(self, page_url):
        logger.info(f"Scraping page: {page_url}")
        
        try:
            await self.page.goto(page_url, wait_until="networkidle", timeout=30000)
            await self.page.wait_for_timeout(3000)
            
            # ページタイトルとURL確認
            title = await self.page.title()
            current_url = self.page.url
            logger.info(f"Page title: {title}")
            logger.info(f"Current URL: {current_url}")
            
            # 物件一覧要素の存在確認
            logger.info("Checking for property elements...")
            
            # 複数のセレクタを試行
            selectors_to_try = [
                'div.cassetteitem',
                'div.property',
                'div[class*="cassette"]',
                'div[class*="property"]',
                '.property-item',
                '.bukken-item'
            ]
            
            property_elements = []
            used_selector = None
            
            for selector in selectors_to_try:
                elements = await self.page.query_selector_all(selector)
                logger.info(f"Selector '{selector}': found {len(elements)} elements")
                if elements:
                    property_elements = elements
                    used_selector = selector
                    break
            
            if not property_elements:
                # ページの内容をログに出力
                page_content = await self.page.content()
                logger.warning("No property elements found. Page content preview:")
                logger.warning(page_content[:1000] + "..." if len(page_content) > 1000 else page_content)
                return []
            
            logger.info(f"Using selector '{used_selector}', found {len(property_elements)} property elements")
            
            properties = []
            for i, element in enumerate(property_elements):
                logger.info(f"Processing property element {i+1}/{len(property_elements)}")
                property_info = await self.extract_property_info(element)
                if property_info:
                    properties.append(property_info)
                    logger.info(f"Successfully extracted property: {property_info.title}")
                else:
                    logger.warning(f"Failed to extract property info from element {i+1}")
                    
                # 目標件数に達したら停止
                total_rooms = sum(len(prop.rooms) for prop in self.properties + properties)
                if total_rooms >= self.target_count:
                    logger.info(f"Reached target count of {self.target_count} rooms")
                    break
            
            logger.info(f"Successfully processed {len(properties)} properties from this page")
            return properties
            
        except Exception as e:
            logger.error(f"Error scraping page {page_url}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    async def get_next_page_url(self):
        try:
            # 次のページのリンクを探す
            next_link = await self.page.query_selector('p.pagination-parts + p a')
            if next_link:
                href = await next_link.get_attribute('href')
                if href:
                    return f"{self.base_url}{href}"
            return None
        except Exception as e:
            logger.error(f"Error getting next page URL: {e}")
            return None
    
    async def scrape_station(self, station_name):
        """単一駅のデータを取得"""
        self.current_station = station_name
        try:
            search_url = get_station_url(station_name, self.prefecture)
        except ValueError as e:
            logger.error(f"Error getting URL for station {station_name}: {e}")
            return []
        
        logger.info(f"Scraping station: {station_name} ({search_url})")
        
        current_url = search_url
        page_count = 0
        station_properties = []
        
        while current_url:
            page_properties = await self.scrape_page(current_url)
            valid_properties = [prop for prop in page_properties if prop is not None]
            station_properties.extend(valid_properties)
            
            logger.info(f"Scraped {len(valid_properties)} valid properties from {station_name} page {page_count + 1}")
            
            # 各駅の部屋数をカウント
            station_rooms = sum(len(prop.rooms) for prop in station_properties)
            total_rooms = sum(len(prop.rooms) for prop in self.properties) + station_rooms
            logger.info(f"Station {station_name} rooms: {station_rooms}, Total rooms: {total_rooms}")
            
            if total_rooms >= self.target_count:
                logger.info(f"Target of {self.target_count} rooms reached!")
                # 必要分だけ切り取り
                remaining_needed = self.target_count - sum(len(prop.rooms) for prop in self.properties)
                station_properties = self._limit_properties(station_properties, remaining_needed)
                break
            
            # 次のページを取得
            current_url = await self.get_next_page_url()
            page_count += 1
            
            if current_url:
                await self.page.wait_for_timeout(3000)  # レート制限
        
        # 駅名を各物件に追加
        for prop in station_properties:
            prop.station_name = station_name
        
        return station_properties
    
    def _limit_properties(self, properties, max_rooms):
        """指定された部屋数まで物件を制限"""
        limited_properties = []
        room_count = 0
        
        for prop in properties:
            if room_count + len(prop.rooms) <= max_rooms:
                limited_properties.append(prop)
                room_count += len(prop.rooms)
            else:
                # 部屋を一部だけ取得
                needed_rooms = max_rooms - room_count
                if needed_rooms > 0:
                    prop.rooms = prop.rooms[:needed_rooms]
                    limited_properties.append(prop)
                break
        
        return limited_properties
    
    async def scrape_all_stations(self):
        """すべての指定駅のデータを取得"""
        await self.create_browser()
        
        try:
            for station in self.stations:
                if sum(len(prop.rooms) for prop in self.properties) >= self.target_count:
                    break
                
                station_properties = await self.scrape_station(station)
                self.properties.extend(station_properties)
                
                logger.info(f"Completed station: {station}")
                total_rooms = sum(len(prop.rooms) for prop in self.properties)
                logger.info(f"Total rooms collected: {total_rooms}/{self.target_count}")
            
            logger.info(f"Total properties scraped: {len(self.properties)}")
            total_rooms = sum(len(prop.rooms) for prop in self.properties)
            logger.info(f"Total rooms scraped: {total_rooms}")
            
            if self.validation_errors:
                logger.warning(f"Total validation errors: {len(self.validation_errors)}")
            
            try:
                stations_str = "-".join(self.stations)
                result = ScrapingResult(
                    properties=self.properties,
                    total_count=len(self.properties),
                    pages_scraped=len(self.stations),
                    source_url=f"Multiple stations: {stations_str}"
                )
                return result
            except ValidationError as e:
                logger.error(f"Scraping result validation error: {e}")
                return None
                
        finally:
            await self.close_browser()
    
    def save_to_json(self, scraping_result=None, filename=None):
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            stations_str = "-".join(self.stations[:3])  # 最初の3駅まで
            if len(self.stations) > 3:
                stations_str += f"-etc{len(self.stations)}"
            filename = f'suumo_{stations_str}_{timestamp}.json'
        
        os.makedirs('data', exist_ok=True)
        filepath = os.path.join('data', filename)
        
        data_to_save = scraping_result.dict() if scraping_result else [prop.dict() for prop in self.properties]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2, default=str)
        
        if self.validation_errors:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            error_filepath = os.path.join('data', f'validation_errors_{stations_str}_{timestamp}.json')
            with open(error_filepath, 'w', encoding='utf-8') as f:
                json.dump(self.validation_errors, f, ensure_ascii=False, indent=2)
            logger.info(f"Validation errors saved to {error_filepath}")
        
        logger.info(f"Data saved to {filepath}")
        return filepath
    
    def save_to_csv(self, filename=None):
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            stations_str = "-".join(self.stations[:3])  # 最初の3駅まで
            if len(self.stations) > 3:
                stations_str += f"-etc{len(self.stations)}"
            filename = f'suumo_{stations_str}_{timestamp}.csv'
        
        os.makedirs('data', exist_ok=True)
        filepath = os.path.join('data', filename)
        
        flattened_data = []
        for prop in self.properties:
            base_info = {
                'target_stations': ', '.join(self.stations),
                'search_station': getattr(prop, 'station_name', 'unknown'),
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

def parse_arguments():
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(
        description="SUUMO賃貸物件スクレイピングツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 渋谷駅から100件取得
  python suumo_playwright_scraper.py --stations 渋谷 --count 100
  
  # 渋谷、新宿、池袋から合計200件取得
  python suumo_playwright_scraper.py --stations 渋谷 新宿 池袋 --count 200
  
  # 山手線全駅から500件取得
  python suumo_playwright_scraper.py --yamanote --count 500
  
  # 対応駅一覧を表示
  python suumo_playwright_scraper.py --list-stations
        """
    )
    
    parser.add_argument(
        '--stations', 
        nargs='+',
        default=['渋谷'],
        help='対象駅名のリスト (デフォルト: 渋谷)'
    )
    
    parser.add_argument(
        '--count', 
        type=int, 
        default=100,
        help='取得する部屋数 (デフォルト: 100)'
    )
    
    parser.add_argument(
        '--prefecture',
        choices=['tokyo', 'kanagawa', 'saitama', 'chiba'],
        default='tokyo',
        help='都道府県 (デフォルト: tokyo)'
    )
    
    parser.add_argument(
        '--yamanote',
        action='store_true',
        help='山手線全駅を対象にする'
    )
    
    parser.add_argument(
        '--list-stations',
        action='store_true',
        help='対応している駅名一覧を表示して終了'
    )
    
    parser.add_argument(
        '--output-json',
        help='JSONファイルの出力パス（指定しない場合は自動生成）'
    )
    
    parser.add_argument(
        '--output-csv',
        help='CSVファイルの出力パス（指定しない場合は自動生成）'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='詳細ログを表示'
    )
    
    return parser.parse_args()

async def main():
    args = parse_arguments()
    
    # ログレベル設定
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 対応駅一覧表示
    if args.list_stations:
        stations = get_supported_stations()
        print("対応している駅名一覧:")
        for i, station in enumerate(stations, 1):
            yamanote_mark = " (山手線)" if is_yamanote_station(station) else ""
            print(f"{i:2d}. {station}{yamanote_mark}")
        return
    
    # 山手線全駅指定
    if args.yamanote:
        stations = get_yamanote_stations()
    else:
        stations = args.stations
    
    # 対応駅チェック
    supported_stations = get_supported_stations()
    invalid_stations = [s for s in stations if s not in supported_stations]
    if invalid_stations:
        logger.error(f"対応していない駅名: {invalid_stations}")
        logger.error(f"対応駅一覧を確認するには --list-stations を使用してください")
        return
    
    scraper = SuumoPlaywrightScraper(
        stations=stations,
        target_count=args.count,
        prefecture=args.prefecture
    )
    
    logger.info(f"Starting SUUMO Playwright scraper")
    logger.info(f"Target stations: {', '.join(stations)}")
    logger.info(f"Target rooms: {args.count}")
    logger.info(f"Prefecture: {args.prefecture}")
    
    result = await scraper.scrape_all_stations()
    
    if result and result.properties:
        json_path = scraper.save_to_json(result, args.output_json)
        csv_path = scraper.save_to_csv(args.output_csv)
        
        total_rooms = sum(len(prop.rooms) for prop in result.properties)
        
        logger.info(f"Scraping completed successfully!")
        logger.info(f"Target stations: {', '.join(stations)}")
        logger.info(f"Total properties: {result.total_count}")
        logger.info(f"Total rooms: {total_rooms}")
        logger.info(f"Stations processed: {result.pages_scraped}")
        logger.info(f"Average rent: {result.average_rent:.0f}円" if result.average_rent else "Average rent: N/A")
        logger.info(f"Layout distribution: {result.layout_distribution}")
        logger.info(f"JSON data: {json_path}")
        logger.info(f"CSV data: {csv_path}")
    else:
        logger.warning("No properties were scraped.")

if __name__ == "__main__":
    asyncio.run(main())