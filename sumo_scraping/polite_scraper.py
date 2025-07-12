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
import random

try:
    from .models import PropertyInfo, RoomInfo, ScrapingResult
    from .station_mapping import get_station_url, get_supported_stations, is_yamanote_station, get_yamanote_stations
    from .rate_limiter import PoliteRequestManager, RateLimitConfig
except ImportError:
    from models import PropertyInfo, RoomInfo, ScrapingResult
    from station_mapping import get_station_url, get_supported_stations, is_yamanote_station, get_yamanote_stations
    from rate_limiter import PoliteRequestManager, RateLimitConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('polite_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PoliteSuumoScraper:
    """サーバー負荷を配慮した礼儀正しいSUUMOスクレイパー"""
    
    def __init__(self, stations=["渋谷"], target_count=100, prefecture="tokyo", polite_mode=True):
        self.stations = stations if isinstance(stations, list) else [stations]
        self.target_count = target_count
        self.prefecture = prefecture
        self.base_url = "https://suumo.jp"
        self.properties = []
        self.validation_errors = []
        self.current_station = None
        
        # 礼儀正しいモードの設定
        if polite_mode:
            config = RateLimitConfig(
                min_delay=5.0,      # より長い待機時間
                max_delay=12.0,
                page_delay=8.0,     # ページ間待機を長く
                station_delay=15.0, # 駅間待機を長く
                max_retries=3,
                retry_delay=10.0,   # リトライ間隔を長く
                concurrent_limit=1  # 同時実行を1つに制限
            )
        else:
            config = RateLimitConfig()  # デフォルト設定
        
        self.request_manager = PoliteRequestManager(config)
        
    async def create_browser(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox', 
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',  # 自動化検出回避
                '--disable-extensions',
                '--disable-plugins',
                '--disable-images',  # 画像読み込み無効化で負荷軽減
                '--disable-javascript',  # 必要最小限のJS以外無効化
            ]
        )
        
        # コンテキスト作成時に設定
        context = await self.browser.new_context(
            user_agent=self.request_manager.get_current_user_agent(),
            viewport={'width': 1366, 'height': 768},  # 一般的な解像度
            locale='ja-JP',
            timezone_id='Asia/Tokyo'
        )
        
        self.page = await context.new_page()
        
        # ナビゲーション時のタイムアウトを長めに設定
        self.page.set_default_navigation_timeout(60000)
        self.page.set_default_timeout(30000)
        
    async def close_browser(self):
        if hasattr(self, 'page'):
            await self.page.close()
        if hasattr(self, 'browser'):
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
    
    async def extract_property_info(self, property_element):
        """物件情報の抽出（エラーハンドリング強化版）"""
        try:
            property_data = {}
            
            # より堅牢なセレクタ検索
            async def safe_extract_text(selectors, default=""):
                for selector in selectors:
                    try:
                        elem = await property_element.query_selector(selector)
                        if elem:
                            text = await elem.inner_text()
                            if text and text.strip():
                                return text.strip()
                    except Exception as e:
                        logger.debug(f"Selector failed {selector}: {e}")
                        continue
                return default
            
            # 物件名
            title_selectors = [
                'h2.cassetteitem_content-title',
                'h3.cassetteitem_content-title', 
                'div.cassetteitem_content-title',
                '.cassetteitem_content-title',
                'h2[class*="title"]',
                'h3[class*="title"]',
                'div[class*="title"]'
            ]
            property_data['title'] = await safe_extract_text(title_selectors)
            
            # 住所
            address_selectors = [
                'li.cassetteitem_detail-col1',
                'div.cassetteitem_detail-col1',
                '.cassetteitem_detail-col1'
            ]
            property_data['address'] = await safe_extract_text(address_selectors)
            
            # アクセス情報
            access_selectors = [
                'li.cassetteitem_detail-col2',
                'div.cassetteitem_detail-col2',
                '.cassetteitem_detail-col2'
            ]
            property_data['access'] = await safe_extract_text(access_selectors)
            
            # 築年数・面積情報
            age_area_selectors = [
                'li.cassetteitem_detail-col3',
                'div.cassetteitem_detail-col3',
                '.cassetteitem_detail-col3'
            ]
            property_data['building_age_area'] = await safe_extract_text(age_area_selectors)
            
            # 部屋情報の抽出（より安全に）
            rooms_info = []
            try:
                room_rows = await property_element.query_selector_all('tbody tr.js-cassette_link')
                
                for row in room_rows:
                    room_data = {}
                    
                    # 各部屋データを安全に抽出
                    room_data['floor'] = await safe_extract_text(['td.ui-text--midium'], default="")
                    room_data['rent'] = await safe_extract_text(['span.cassetteitem_price--rent'], default="")
                    room_data['admin_fee'] = await safe_extract_text(['span.cassetteitem_price--administration'], default="")
                    room_data['deposit_key_money'] = await safe_extract_text(['span.cassetteitem_price--deposit'], default="")
                    room_data['layout'] = await safe_extract_text(['span.cassetteitem_madori'], default="")
                    room_data['area'] = await safe_extract_text(['span.cassetteitem_menseki'], default="")
                    
                    # 詳細URL
                    try:
                        detail_link = await row.query_selector('a')
                        if detail_link:
                            href = await detail_link.get_attribute('href')
                            if href:
                                room_data['detail_url'] = f"{self.base_url}{href}"
                    except Exception:
                        room_data['detail_url'] = None
                    
                    # 部屋データのバリデーション
                    try:
                        room = RoomInfo(**room_data)
                        rooms_info.append(room)
                    except ValidationError as e:
                        logger.debug(f"Room validation error: {e}")
                        self.validation_errors.append({"type": "room", "data": room_data, "error": str(e)})
            
            except Exception as e:
                logger.debug(f"Error extracting room info: {e}")
            
            property_data['rooms'] = rooms_info
            
            # 物件データのバリデーション
            try:
                property_obj = PropertyInfo(**property_data)
                return property_obj
            except ValidationError as e:
                logger.debug(f"Property validation error: {e}")
                self.validation_errors.append({"type": "property", "data": property_data, "error": str(e)})
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error in extract_property_info: {e}")
            return None
    
    async def safe_goto_page(self, url):
        """安全なページ遷移"""
        async def _goto():
            try:
                # User-Agentをローテーション
                await self.page.set_extra_http_headers({
                    'User-Agent': self.request_manager.get_current_user_agent(),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                })
                
                # より長いタイムアウトで安全にナビゲート
                response = await self.page.goto(
                    url, 
                    wait_until="domcontentloaded",  # networkidleより軽量
                    timeout=60000
                )
                
                if response and response.status >= 400:
                    raise Exception(f"HTTP {response.status}: {response.status_text}")
                
                return response
                
            except Exception as e:
                logger.warning(f"Navigation failed for {url}: {e}")
                raise e
        
        # リクエストマネージャーを通して実行
        return await self.request_manager.make_request(_goto, "page")
    
    async def scrape_page(self, page_url):
        """ページスクレイピング（負荷軽減版）"""
        logger.info(f"Politely scraping page: {page_url}")
        
        try:
            # 安全なページ遷移
            await self.safe_goto_page(page_url)
            
            # ページ読み込み後の追加待機（人間らしい行動をシミュレート）
            await asyncio.sleep(random.uniform(2.0, 4.0))
            
            # ページタイトルとURL確認
            title = await self.page.title()
            current_url = self.page.url
            logger.info(f"Page loaded: {title}")
            
            # 物件一覧を安全に取得
            try:
                property_elements = await self.page.query_selector_all('div.cassetteitem')
                logger.info(f"Found {len(property_elements)} property elements")
            except Exception as e:
                logger.warning(f"Failed to find property elements: {e}")
                return []
            
            if not property_elements:
                logger.warning("No property elements found on page")
                return []
            
            properties = []
            for i, element in enumerate(property_elements):
                logger.debug(f"Processing property element {i+1}/{len(property_elements)}")
                
                # 各物件の処理間にも小さな待機を入れる
                if i > 0:
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                
                property_info = await self.extract_property_info(element)
                if property_info:
                    properties.append(property_info)
                    
                # 目標件数チェック
                total_rooms = sum(len(prop.rooms) for prop in self.properties + properties)
                if total_rooms >= self.target_count:
                    logger.info(f"Target count {self.target_count} reached during page processing")
                    break
            
            logger.info(f"Successfully extracted {len(properties)} properties from page")
            return properties
            
        except Exception as e:
            logger.error(f"Error scraping page {page_url}: {e}")
            return []
    
    async def get_next_page_url(self):
        """次ページURL取得（エラーハンドリング強化）"""
        try:
            await asyncio.sleep(random.uniform(1.0, 2.0))  # UI操作前の待機
            
            next_link = await self.page.query_selector('p.pagination-parts + p a')
            if next_link:
                href = await next_link.get_attribute('href')
                if href and href.strip():
                    next_url = f"{self.base_url}{href}"
                    logger.debug(f"Found next page: {next_url}")
                    return next_url
            
            logger.debug("No next page found")
            return None
            
        except Exception as e:
            logger.warning(f"Error getting next page URL: {e}")
            return None
    
    async def scrape_station(self, station_name):
        """単一駅のスクレイピング（負荷配慮版）"""
        self.current_station = station_name
        
        try:
            search_url = get_station_url(station_name, self.prefecture)
        except ValueError as e:
            logger.error(f"Invalid station {station_name}: {e}")
            return []
        
        logger.info(f"Starting polite scraping for station: {station_name}")
        
        current_url = search_url
        page_count = 0
        station_properties = []
        
        # 駅間の長めの待機
        if self.current_station != station_name:
            logger.info(f"Switching to new station, waiting...")
            await asyncio.sleep(random.uniform(10.0, 20.0))
        
        while current_url and page_count < 10:  # ページ数制限で負荷軽減
            try:
                page_properties = await self.scrape_page(current_url)
                valid_properties = [prop for prop in page_properties if prop is not None]
                station_properties.extend(valid_properties)
                
                logger.info(f"Scraped {len(valid_properties)} properties from {station_name} page {page_count + 1}")
                
                # 統計情報
                station_rooms = sum(len(prop.rooms) for prop in station_properties)
                total_rooms = sum(len(prop.rooms) for prop in self.properties) + station_rooms
                logger.info(f"Station {station_name}: {station_rooms} rooms, Total: {total_rooms}")
                
                # 目標達成チェック
                if total_rooms >= self.target_count:
                    logger.info(f"Target {self.target_count} rooms reached!")
                    remaining_needed = self.target_count - sum(len(prop.rooms) for prop in self.properties)
                    station_properties = self._limit_properties(station_properties, remaining_needed)
                    break
                
                # 次ページ取得
                current_url = await self.get_next_page_url()
                page_count += 1
                
                # ページ間の待機（より長く）
                if current_url:
                    wait_time = random.uniform(8.0, 15.0)
                    logger.info(f"Waiting {wait_time:.1f}s before next page...")
                    await asyncio.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Error processing page {page_count + 1} for {station_name}: {e}")
                break
        
        # 駅名を各物件に追加
        for prop in station_properties:
            prop.station_name = station_name
        
        logger.info(f"Completed station {station_name}: {len(station_properties)} properties")
        return station_properties
    
    def _limit_properties(self, properties, max_rooms):
        """部屋数制限（既存のロジック）"""
        limited_properties = []
        room_count = 0
        
        for prop in properties:
            if room_count + len(prop.rooms) <= max_rooms:
                limited_properties.append(prop)
                room_count += len(prop.rooms)
            else:
                needed_rooms = max_rooms - room_count
                if needed_rooms > 0:
                    prop.rooms = prop.rooms[:needed_rooms]
                    limited_properties.append(prop)
                break
        
        return limited_properties
    
    async def scrape_all_stations(self):
        """全駅スクレイピング（負荷配慮版）"""
        await self.create_browser()
        
        try:
            logger.info(f"Starting polite scraping session for {len(self.stations)} stations")
            
            for i, station in enumerate(self.stations):
                if sum(len(prop.rooms) for prop in self.properties) >= self.target_count:
                    logger.info("Target reached, stopping station iteration")
                    break
                
                logger.info(f"Processing station {i+1}/{len(self.stations)}: {station}")
                
                try:
                    station_properties = await self.scrape_station(station)
                    self.properties.extend(station_properties)
                    
                    total_rooms = sum(len(prop.rooms) for prop in self.properties)
                    logger.info(f"Station {station} completed. Total rooms: {total_rooms}/{self.target_count}")
                    
                    # 駅間の長めの待機
                    if i < len(self.stations) - 1:  # 最後の駅でなければ
                        wait_time = random.uniform(15.0, 30.0)
                        logger.info(f"Waiting {wait_time:.1f}s before next station...")
                        await asyncio.sleep(wait_time)
                        
                except Exception as e:
                    logger.error(f"Failed to scrape station {station}: {e}")
                    continue
            
            # セッション統計
            total_rooms = sum(len(prop.rooms) for prop in self.properties)
            logger.info(f"Scraping session completed:")
            logger.info(f"  Total properties: {len(self.properties)}")
            logger.info(f"  Total rooms: {total_rooms}")
            logger.info(f"  Validation errors: {len(self.validation_errors)}")
            
            # リクエスト統計
            self.request_manager.log_session_stats()
            
            # 結果オブジェクト作成
            try:
                stations_str = "-".join(self.stations)
                result = ScrapingResult(
                    properties=self.properties,
                    total_count=len(self.properties),
                    pages_scraped=len(self.stations),
                    source_url=f"Polite scraping: {stations_str}"
                )
                return result
            except ValidationError as e:
                logger.error(f"Result validation error: {e}")
                return None
                
        finally:
            await self.close_browser()
    
    def save_to_json(self, scraping_result=None, filename=None):
        """JSON保存（既存と同様）"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            stations_str = "-".join(self.stations[:3])
            if len(self.stations) > 3:
                stations_str += f"-etc{len(self.stations)}"
            filename = f'suumo_polite_{stations_str}_{timestamp}.json'
        
        os.makedirs('data', exist_ok=True)
        filepath = os.path.join('data', filename)
        
        data_to_save = scraping_result.model_dump() if scraping_result else [prop.model_dump() for prop in self.properties]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2, default=str)
        
        if self.validation_errors:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            error_filepath = os.path.join('data', f'validation_errors_polite_{stations_str}_{timestamp}.json')
            with open(error_filepath, 'w', encoding='utf-8') as f:
                json.dump(self.validation_errors, f, ensure_ascii=False, indent=2)
            logger.info(f"Validation errors saved to {error_filepath}")
        
        logger.info(f"Data saved to {filepath}")
        return filepath
    
    def save_to_csv(self, filename=None):
        """CSV保存（既存と同様）"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            stations_str = "-".join(self.stations[:3])
            if len(self.stations) > 3:
                stations_str += f"-etc{len(self.stations)}"
            filename = f'suumo_polite_{stations_str}_{timestamp}.csv'
        
        os.makedirs('data', exist_ok=True)
        filepath = os.path.join('data', filename)
        
        flattened_data = []
        for prop in self.properties:
            base_info = {
                'scraping_mode': 'polite',
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
    """コマンドライン引数パース（拡張版）"""
    parser = argparse.ArgumentParser(
        description="SUUMO賃貸物件スクレイピングツール（サーバー負荷配慮版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 礼儀正しいモードで渋谷駅から50件取得
  python polite_scraper.py --stations 渋谷 --count 50 --polite
  
  # 通常モードで複数駅から100件取得
  python polite_scraper.py --stations 渋谷 新宿 --count 100
  
  # 山手線から少量取得（サーバー負荷最小限）
  python polite_scraper.py --yamanote --count 30 --polite
        """
    )
    
    parser.add_argument('--stations', nargs='+', default=['渋谷'],
                       help='対象駅名のリスト (デフォルト: 渋谷)')
    parser.add_argument('--count', type=int, default=100,
                       help='取得する部屋数 (デフォルト: 100)')
    parser.add_argument('--prefecture', choices=['tokyo', 'kanagawa', 'saitama', 'chiba'],
                       default='tokyo', help='都道府県 (デフォルト: tokyo)')
    parser.add_argument('--yamanote', action='store_true',
                       help='山手線全駅を対象にする')
    parser.add_argument('--polite', action='store_true',
                       help='礼儀正しいモード（待機時間長め、サーバー負荷配慮）')
    parser.add_argument('--list-stations', action='store_true',
                       help='対応している駅名一覧を表示して終了')
    parser.add_argument('--output-json', help='JSONファイルの出力パス')
    parser.add_argument('--output-csv', help='CSVファイルの出力パス')
    parser.add_argument('--verbose', action='store_true', help='詳細ログを表示')
    
    return parser.parse_args()

async def main():
    args = parse_arguments()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.list_stations:
        stations = get_supported_stations()
        print("対応している駅名一覧:")
        for i, station in enumerate(stations, 1):
            yamanote_mark = " (山手線)" if is_yamanote_station(station) else ""
            print(f"{i:2d}. {station}{yamanote_mark}")
        return
    
    if args.yamanote:
        stations = get_yamanote_stations()
    else:
        stations = args.stations
    
    # 対応駅チェック
    supported_stations = get_supported_stations()
    invalid_stations = [s for s in stations if s not in supported_stations]
    if invalid_stations:
        logger.error(f"対応していない駅名: {invalid_stations}")
        logger.error("対応駅一覧を確認するには --list-stations を使用してください")
        return
    
    # 礼儀正しいモードの場合は件数を制限することを推奨
    if args.polite and args.count > 200:
        logger.warning(f"礼儀正しいモードでは大量取得({args.count}件)は非推奨です")
        response = input("続行しますか？ (y/N): ")
        if response.lower() not in ['y', 'yes']:
            logger.info("スクレイピングを中止しました")
            return
    
    scraper = PoliteSuumoScraper(
        stations=stations,
        target_count=args.count,
        prefecture=args.prefecture,
        polite_mode=args.polite
    )
    
    mode_name = "礼儀正しいモード" if args.polite else "通常モード"
    logger.info(f"SUUMO Polite Scraper 開始 ({mode_name})")
    logger.info(f"対象駅: {', '.join(stations)}")
    logger.info(f"目標部屋数: {args.count}")
    logger.info(f"都道府県: {args.prefecture}")
    
    if args.polite:
        logger.info("📈 サーバー負荷配慮モード有効:")
        logger.info("  - 長めの待機時間")
        logger.info("  - User-Agentローテーション")
        logger.info("  - 自動リトライ機能")
        logger.info("  - リクエスト監視")
    
    try:
        result = await scraper.scrape_all_stations()
        
        if result and result.properties:
            json_path = scraper.save_to_json(result, args.output_json)
            csv_path = scraper.save_to_csv(args.output_csv)
            
            total_rooms = sum(len(prop.rooms) for prop in result.properties)
            
            logger.info("🎉 スクレイピング完了!")
            logger.info(f"📊 結果統計:")
            logger.info(f"  対象駅: {', '.join(stations)}")
            logger.info(f"  物件数: {result.total_count}")
            logger.info(f"  部屋数: {total_rooms}")
            logger.info(f"  処理駅数: {result.pages_scraped}")
            if result.average_rent:
                logger.info(f"  平均賃料: {result.average_rent:.0f}円")
            logger.info(f"  間取り分布: {result.layout_distribution}")
            logger.info(f"📁 保存ファイル:")
            logger.info(f"  JSON: {json_path}")
            logger.info(f"  CSV: {csv_path}")
        else:
            logger.warning("物件データを取得できませんでした")
    
    except KeyboardInterrupt:
        logger.info("ユーザーによって中断されました")
    except Exception as e:
        logger.error(f"予期しないエラーが発生しました: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())