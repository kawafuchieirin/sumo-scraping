"""
駅名からSUUMO URLへのマッピング
"""

# 山手線駅のマッピング
YAMANOTE_STATIONS = {
    "渋谷": "ek_17640",
    "新宿": "ek_19670", 
    "池袋": "ek_02060",
    "上野": "ek_04530",
    "東京": "ek_30140",
    "有楽町": "ek_41680",
    "新橋": "ek_20370",
    "浜松町": "ek_33030",
    "田町": "ek_22790",
    "品川": "ek_17630",
    "大崎": "ek_06280",
    "五反田": "ek_14840",
    "目黒": "ek_39210",
    "恵比寿": "ek_04150",
    "原宿": "ek_33060",
    "代々木": "ek_40960",
    "新大久保": "ek_20220",
    "高田馬場": "ek_22470",
    "目白": "ek_39220",
    "大塚": "ek_06380",
    "巣鴨": "ek_18120",
    "駒込": "ek_14990",
    "田端": "ek_22870",
    "西日暮里": "ek_29230",
    "日暮里": "ek_33330",
    "鶯谷": "ek_04590",
    "御徒町": "ek_39070",
    "秋葉原": "ek_01090",
    "神田": "ek_09950",
}

# 主要駅のマッピング
MAJOR_STATIONS = {
    # 山手線
    **YAMANOTE_STATIONS,
    
    # 中央線
    "中野": "ek_27280",
    "吉祥寺": "ek_11640",
    "三鷹": "ek_36880",
    "荻窪": "ek_06640",
    "阿佐ヶ谷": "ek_01070",
    "高円寺": "ek_22290",
    "国分寺": "ek_15330",
    "立川": "ek_23520",
    
    # 京王線
    "調布": "ek_24440",
    "府中": "ek_34370",
    "聖蹟桜ヶ丘": "ek_17890",
    "多摩センター": "ek_22760",
    
    # 小田急線
    "下北沢": "ek_16770",
    "経堂": "ek_12020",
    "成城学園前": "ek_18380",
    "登戸": "ek_30130",
    "新百合ヶ丘": "ek_20930",
    "町田": "ek_34220",
    
    # 東急線
    "自由が丘": "ek_16900",
    "二子玉川": "ek_32270",
    "溝の口": "ek_36850",
    "武蔵小杉": "ek_38720",
    "日吉": "ek_33150",
    
    # 埼玉方面
    "大宮": "ek_06310",
    "浦和": "ek_04710",
    "川口": "ek_09870",
    "赤羽": "ek_01020",
    
    # 千葉方面
    "船橋": "ek_34480",
    "津田沼": "ek_24780",
    "西船橋": "ek_29360",
    "市川": "ek_02990",
    
    # 神奈川方面
    "横浜": "ek_40940",
    "川崎": "ek_09920",
    "鶴見": "ek_25070",
    "新横浜": "ek_20390",
}

def get_station_url(station_name: str, prefecture: str = "tokyo") -> str:
    """
    駅名からSUUMO URLを生成
    
    Args:
        station_name: 駅名
        prefecture: 都道府県 (tokyo, kanagawa, saitama, chiba)
    
    Returns:
        SUUMO URL
    
    Raises:
        ValueError: 対応していない駅名の場合
    """
    if station_name not in MAJOR_STATIONS:
        raise ValueError(f"駅名 '{station_name}' は対応していません。対応駅: {list(MAJOR_STATIONS.keys())}")
    
    station_code = MAJOR_STATIONS[station_name]
    return f"https://suumo.jp/chintai/{prefecture}/{station_code}/"

def get_supported_stations() -> list:
    """対応している駅名のリストを取得"""
    return sorted(MAJOR_STATIONS.keys())

def is_yamanote_station(station_name: str) -> bool:
    """山手線の駅かどうか判定"""
    return station_name in YAMANOTE_STATIONS

def get_yamanote_stations() -> list:
    """山手線の駅名リストを取得"""
    return sorted(YAMANOTE_STATIONS.keys())