from pydantic import BaseModel, Field, validator, model_validator
from typing import List, Optional
import re
from datetime import datetime

class RoomInfo(BaseModel):
    floor: str = Field(default="", description="階数情報")
    rent: str = Field(default="", description="賃料")
    admin_fee: str = Field(default="", description="管理費")
    deposit_key_money: str = Field(default="", description="敷金・礼金")
    layout: str = Field(default="", description="間取り")
    area: str = Field(default="", description="面積")
    detail_url: Optional[str] = Field(default=None, description="詳細ページURL")
    
    rent_numeric: Optional[float] = Field(default=None, description="賃料の数値部分")
    admin_fee_numeric: Optional[float] = Field(default=None, description="管理費の数値部分")
    area_numeric: Optional[float] = Field(default=None, description="面積の数値部分")
    
    @validator('detail_url')
    def validate_url(cls, v):
        if v and not v.startswith('http'):
            raise ValueError('URLは http または https で始まる必要があります')
        return v
    
    @validator('layout')
    def validate_layout(cls, v):
        if v and not re.match(r'^[0-9]*[SLDK]+$', v.replace('R', '').replace('K', 'K').replace('DK', 'DK').replace('LDK', 'LDK')):
            return v
        return v
    
    def __init__(self, **data):
        super().__init__(**data)
        self.rent_numeric = self._extract_numeric_value(self.rent)
        self.admin_fee_numeric = self._extract_numeric_value(self.admin_fee)
        self.area_numeric = self._extract_area_value(self.area)
    
    @staticmethod
    def _extract_numeric_value(value: str) -> Optional[float]:
        if not value or value in ['-', '']:
            return None
        
        value = value.replace('万円', '').replace('円', '').replace(',', '').replace('万', '')
        
        try:
            if '万' in value:
                return float(value) * 10000
            else:
                numeric_match = re.search(r'[\d.]+', value)
                if numeric_match:
                    num = float(numeric_match.group())
                    if num < 100:
                        return num * 10000
                    return num
        except (ValueError, AttributeError):
            pass
        return None
    
    @staticmethod
    def _extract_area_value(value: str) -> Optional[float]:
        if not value:
            return None
        
        try:
            area_match = re.search(r'([\d.]+)', value.replace('m²', '').replace('㎡', ''))
            if area_match:
                return float(area_match.group(1))
        except (ValueError, AttributeError):
            pass
        return None

class PropertyInfo(BaseModel):
    title: str = Field(default="", description="物件名")
    address: str = Field(default="", description="住所")
    access: str = Field(default="", description="アクセス情報")
    building_age_area: str = Field(default="", description="築年数・面積情報")
    rooms: List[RoomInfo] = Field(default_factory=list, description="部屋情報のリスト")
    scraped_at: datetime = Field(default_factory=datetime.now, description="スクレイピング日時")
    
    building_age: Optional[int] = Field(default=None, description="築年数（年）")
    station_info: List[str] = Field(default_factory=list, description="最寄り駅情報")
    station_name: Optional[str] = Field(default=None, description="検索対象駅名")
    
    @validator('title')
    def validate_title(cls, v):
        if not v or v.strip() == "":
            raise ValueError('物件名は必須項目です')
        return v.strip()
    
    @validator('address')
    def validate_address(cls, v):
        if not v or v.strip() == "":
            raise ValueError('住所は必須項目です')
        return v.strip()
    
    @validator('rooms')
    def validate_rooms(cls, v):
        if not v:
            raise ValueError('最低1つの部屋情報が必要です')
        return v
    
    def __init__(self, **data):
        super().__init__(**data)
        self.building_age = self._extract_building_age(self.building_age_area)
        self.station_info = self._extract_station_info(self.access)
    
    @staticmethod
    def _extract_building_age(building_info: str) -> Optional[int]:
        if not building_info:
            return None
        
        try:
            age_match = re.search(r'築(\d+)年', building_info)
            if age_match:
                return int(age_match.group(1))
            
            if '新築' in building_info:
                return 0
        except (ValueError, AttributeError):
            pass
        return None
    
    @staticmethod
    def _extract_station_info(access_info: str) -> List[str]:
        if not access_info:
            return []
        
        stations = []
        try:
            station_matches = re.findall(r'([^/\n]+駅)', access_info)
            stations = [station.strip() for station in station_matches]
        except AttributeError:
            pass
        return stations
    
    @property
    def min_rent(self) -> Optional[float]:
        rents = [room.rent_numeric for room in self.rooms if room.rent_numeric is not None]
        return min(rents) if rents else None
    
    @property
    def max_rent(self) -> Optional[float]:
        rents = [room.rent_numeric for room in self.rooms if room.rent_numeric is not None]
        return max(rents) if rents else None
    
    @property
    def available_layouts(self) -> List[str]:
        return list(set([room.layout for room in self.rooms if room.layout]))

class ScrapingResult(BaseModel):
    properties: List[PropertyInfo] = Field(description="スクレイピングした物件のリスト")
    total_count: int = Field(description="総物件数")
    pages_scraped: int = Field(description="スクレイピングしたページ数")
    scraped_at: datetime = Field(default_factory=datetime.now, description="スクレイピング完了日時")
    source_url: str = Field(description="スクレイピング元URL")
    
    @validator('properties')
    def validate_properties(cls, v):
        if not v:
            raise ValueError('最低1つの物件が必要です')
        return v
    
    @model_validator(mode='after')
    def validate_counts(self):
        if len(self.properties) != self.total_count:
            raise ValueError('total_countとpropertiesの数が一致しません')
        return self
    
    @property
    def average_rent(self) -> Optional[float]:
        all_rents = []
        for prop in self.properties:
            for room in prop.rooms:
                if room.rent_numeric is not None:
                    all_rents.append(room.rent_numeric)
        
        return sum(all_rents) / len(all_rents) if all_rents else None
    
    @property
    def layout_distribution(self) -> dict:
        layout_count = {}
        for prop in self.properties:
            for room in prop.rooms:
                if room.layout:
                    layout_count[room.layout] = layout_count.get(room.layout, 0) + 1
        return layout_count