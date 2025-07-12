"""
データ分析用ユーティリティ関数
"""

import pandas as pd
import json
import glob
import os
from typing import List, Dict, Optional, Union
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def load_scraped_data(
    data_path: str = "../data",
    file_pattern: str = "suumo_*.csv",
    latest_only: bool = False
) -> pd.DataFrame:
    """
    スクレイピングデータを読み込む
    
    Args:
        data_path: データディレクトリのパス
        file_pattern: ファイルパターン
        latest_only: 最新ファイルのみ読み込む
    
    Returns:
        統合されたDataFrame
    """
    
    # ファイル検索
    search_pattern = os.path.join(data_path, file_pattern)
    files = glob.glob(search_pattern)
    
    if not files:
        raise FileNotFoundError(f"No files found matching {search_pattern}")
    
    # 最新ファイルのみの場合
    if latest_only:
        files = [max(files, key=os.path.getctime)]
    
    logger.info(f"Loading {len(files)} files from {data_path}")
    
    # データフレームのリスト
    dataframes = []
    
    for file_path in files:
        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            df['source_file'] = os.path.basename(file_path)
            df['loaded_at'] = datetime.now()
            dataframes.append(df)
            logger.debug(f"Loaded {len(df)} rows from {file_path}")
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            continue
    
    if not dataframes:
        raise ValueError("No valid data files could be loaded")
    
    # 統合
    combined_df = pd.concat(dataframes, ignore_index=True)
    logger.info(f"Combined dataset: {len(combined_df)} rows, {len(combined_df.columns)} columns")
    
    return combined_df

def load_json_data(
    data_path: str = "../data", 
    file_pattern: str = "suumo_*.json",
    latest_only: bool = False
) -> List[Dict]:
    """
    JSONデータを読み込む
    
    Args:
        data_path: データディレクトリのパス
        file_pattern: ファイルパターン
        latest_only: 最新ファイルのみ読み込む
    
    Returns:
        JSONデータのリスト
    """
    
    search_pattern = os.path.join(data_path, file_pattern)
    files = glob.glob(search_pattern)
    
    if not files:
        raise FileNotFoundError(f"No files found matching {search_pattern}")
    
    if latest_only:
        files = [max(files, key=os.path.getctime)]
    
    all_data = []
    
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # ScrapingResultオブジェクトの場合
            if isinstance(data, dict) and 'properties' in data:
                all_data.extend(data['properties'])
            # 物件リストの場合
            elif isinstance(data, list):
                all_data.extend(data)
            else:
                logger.warning(f"Unknown data format in {file_path}")
                
        except Exception as e:
            logger.error(f"Error loading JSON {file_path}: {e}")
            continue
    
    logger.info(f"Loaded {len(all_data)} properties from JSON files")
    return all_data

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    データクリーニングを実行
    
    Args:
        df: 元のDataFrame
        
    Returns:
        クリーニング済みDataFrame
    """
    
    logger.info("Starting data cleaning...")
    original_rows = len(df)
    
    # コピーを作成
    cleaned_df = df.copy()
    
    # 1. 重複除去
    duplicates_before = cleaned_df.duplicated().sum()
    cleaned_df = cleaned_df.drop_duplicates()
    logger.info(f"Removed {duplicates_before} duplicate rows")
    
    # 2. 数値カラムの型変換と異常値処理
    numeric_columns = ['rent_numeric', 'admin_fee_numeric', 'area_numeric', 'building_age']
    
    for col in numeric_columns:
        if col in cleaned_df.columns:
            # 文字列から数値への変換
            cleaned_df[col] = pd.to_numeric(cleaned_df[col], errors='coerce')
            
            # 異常値フィルタリング（rent_numericの例）
            if col == 'rent_numeric':
                # 賃料が極端に高い/低い場合を除外
                q1 = cleaned_df[col].quantile(0.01)
                q99 = cleaned_df[col].quantile(0.99)
                before_filter = len(cleaned_df)
                cleaned_df = cleaned_df[
                    (cleaned_df[col].isna()) | 
                    ((cleaned_df[col] >= q1) & (cleaned_df[col] <= q99))
                ]
                logger.info(f"Filtered {before_filter - len(cleaned_df)} outlier rows for {col}")
    
    # 3. 欠損値の処理
    for col in cleaned_df.columns:
        missing_count = cleaned_df[col].isna().sum()
        if missing_count > 0:
            logger.debug(f"Column {col}: {missing_count} missing values")
    
    # 4. カテゴリカルデータの正規化
    if 'layout' in cleaned_df.columns:
        # 間取りの正規化
        layout_mapping = {
            'ワンルーム': '1R',
            'one room': '1R',
            'studio': '1R'
        }
        cleaned_df['layout_normalized'] = cleaned_df['layout'].replace(layout_mapping)
    
    # 5. 日付カラムの処理
    date_columns = ['scraped_at', 'loaded_at']
    for col in date_columns:
        if col in cleaned_df.columns:
            cleaned_df[col] = pd.to_datetime(cleaned_df[col], errors='coerce')
    
    # 6. 地域情報の抽出
    if 'address' in cleaned_df.columns:
        # 区の抽出
        cleaned_df['ward'] = cleaned_df['address'].str.extract(r'(.*?[区市町村])')
        # 路線情報の抽出
        if 'access' in cleaned_df.columns:
            cleaned_df['main_line'] = cleaned_df['access'].str.extract(r'(.*?線)')
    
    cleaned_rows = len(cleaned_df)
    logger.info(f"Data cleaning completed: {original_rows} -> {cleaned_rows} rows ({cleaned_rows/original_rows:.1%} retained)")
    
    return cleaned_df

def calculate_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    派生指標を計算
    
    Args:
        df: 元のDataFrame
        
    Returns:
        派生指標追加済みDataFrame
    """
    
    df = df.copy()
    
    # 1. 賃料関連指標
    if 'rent_numeric' in df.columns and 'area_numeric' in df.columns:
        # 平米単価
        df['rent_per_sqm'] = df['rent_numeric'] / df['area_numeric']
        df['rent_per_sqm'] = df['rent_per_sqm'].replace([float('inf'), -float('inf')], None)
    
    # 2. 築年数カテゴリ
    if 'building_age' in df.columns:
        df['age_category'] = pd.cut(
            df['building_age'],
            bins=[-1, 5, 10, 20, 30, float('inf')],
            labels=['新築・築浅', '築6-10年', '築11-20年', '築21-30年', '築30年超']
        )
    
    # 3. 賃料レンジ
    if 'rent_numeric' in df.columns:
        df['rent_range'] = pd.cut(
            df['rent_numeric'],
            bins=[0, 50000, 100000, 150000, 200000, float('inf')],
            labels=['5万未満', '5-10万', '10-15万', '15-20万', '20万超']
        )
    
    # 4. 面積レンジ
    if 'area_numeric' in df.columns:
        df['area_range'] = pd.cut(
            df['area_numeric'],
            bins=[0, 20, 30, 50, 70, float('inf')],
            labels=['20㎡未満', '20-30㎡', '30-50㎡', '50-70㎡', '70㎡超']
        )
    
    logger.info("Calculated derived metrics")
    return df

def export_report(
    df: pd.DataFrame,
    output_path: str = "reports/analysis_report.html",
    title: str = "SUUMO データ分析レポート"
) -> str:
    """
    分析レポートを出力
    
    Args:
        df: 分析データ
        output_path: 出力パス
        title: レポートタイトル
        
    Returns:
        出力ファイルパス
    """
    
    # ディレクトリ作成
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 基本統計
    basic_stats = df.describe()
    
    # カテゴリカル変数の統計
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns
    categorical_stats = {}
    for col in categorical_cols:
        categorical_stats[col] = df[col].value_counts().head(10)
    
    # HTMLレポート生成
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{title}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1, h2 {{ color: #333; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .summary {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <h1>{title}</h1>
        <div class="summary">
            <h2>データ概要</h2>
            <p>総レコード数: {len(df):,}</p>
            <p>カラム数: {len(df.columns)}</p>
            <p>生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}</p>
        </div>
        
        <h2>基本統計</h2>
        {basic_stats.to_html()}
        
        <h2>カテゴリカル変数の分布</h2>
    """
    
    for col, stats in categorical_stats.items():
        html_content += f"<h3>{col}</h3>\n{stats.to_frame().to_html()}\n"
    
    html_content += """
    </body>
    </html>
    """
    
    # ファイル保存
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    logger.info(f"Report exported to {output_path}")
    return output_path

def get_data_summary(df: pd.DataFrame) -> Dict:
    """
    データの要約統計を取得
    
    Args:
        df: 分析対象のDataFrame
        
    Returns:
        要約統計の辞書
    """
    
    summary = {
        'basic_info': {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'memory_usage': df.memory_usage(deep=True).sum(),
            'duplicates': df.duplicated().sum()
        },
        'missing_data': df.isnull().sum().to_dict(),
        'data_types': df.dtypes.astype(str).to_dict()
    }
    
    # 数値カラムの統計
    numeric_cols = df.select_dtypes(include=['number']).columns
    if len(numeric_cols) > 0:
        summary['numeric_summary'] = df[numeric_cols].describe().to_dict()
    
    # カテゴリカルカラムの統計
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns
    if len(categorical_cols) > 0:
        summary['categorical_summary'] = {}
        for col in categorical_cols:
            summary['categorical_summary'][col] = {
                'unique_count': df[col].nunique(),
                'top_values': df[col].value_counts().head(5).to_dict()
            }
    
    return summary