"""
SUUMO データ分析器

スクレイピングしたSUUMOデータの統計分析、価格分析、エリア分析などを行うクラス
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from .utils import load_scraped_data, clean_data, calculate_derived_metrics

logger = logging.getLogger(__name__)

class SuumoAnalyzer:
    """SUUMO データ分析器"""
    
    def __init__(self, data_path: str = "../data", auto_load: bool = True):
        """
        初期化
        
        Args:
            data_path: データディレクトリのパス
            auto_load: 初期化時に自動でデータを読み込むかどうか
        """
        self.data_path = data_path
        self.df = None
        self.analysis_results = {}
        
        if auto_load:
            self.load_and_prepare_data()
    
    def load_and_prepare_data(self, latest_only: bool = False) -> pd.DataFrame:
        """
        データの読み込みと前処理
        
        Args:
            latest_only: 最新ファイルのみ読み込むかどうか
            
        Returns:
            前処理済みDataFrame
        """
        logger.info("Loading and preparing SUUMO data...")
        
        try:
            # データ読み込み
            self.df = load_scraped_data(
                data_path=self.data_path,
                latest_only=latest_only
            )
            
            # データクリーニング
            self.df = clean_data(self.df)
            
            # 派生指標計算
            self.df = calculate_derived_metrics(self.df)
            
            logger.info(f"Data prepared successfully: {len(self.df)} rows")
            return self.df
            
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            raise
    
    def get_basic_stats(self) -> Dict[str, Any]:
        """
        基本統計情報を取得
        
        Returns:
            基本統計の辞書
        """
        if self.df is None:
            raise ValueError("Data not loaded. Call load_and_prepare_data() first.")
        
        stats = {
            'total_properties': len(self.df),
            'date_range': {
                'start': self.df['scraped_at'].min() if 'scraped_at' in self.df.columns else None,
                'end': self.df['scraped_at'].max() if 'scraped_at' in self.df.columns else None
            },
            'stations': {
                'count': self.df['search_station'].nunique() if 'search_station' in self.df.columns else 0,
                'list': self.df['search_station'].unique().tolist() if 'search_station' in self.df.columns else []
            }
        }
        
        # 賃料統計
        if 'rent_numeric' in self.df.columns:
            rent_data = self.df['rent_numeric'].dropna()
            stats['rent'] = {
                'count': len(rent_data),
                'mean': rent_data.mean(),
                'median': rent_data.median(),
                'std': rent_data.std(),
                'min': rent_data.min(),
                'max': rent_data.max(),
                'q25': rent_data.quantile(0.25),
                'q75': rent_data.quantile(0.75)
            }
        
        # 面積統計
        if 'area_numeric' in self.df.columns:
            area_data = self.df['area_numeric'].dropna()
            stats['area'] = {
                'count': len(area_data),
                'mean': area_data.mean(),
                'median': area_data.median(),
                'std': area_data.std(),
                'min': area_data.min(),
                'max': area_data.max()
            }
        
        # 築年数統計
        if 'building_age' in self.df.columns:
            age_data = self.df['building_age'].dropna()
            stats['building_age'] = {
                'count': len(age_data),
                'mean': age_data.mean(),
                'median': age_data.median(),
                'min': age_data.min(),
                'max': age_data.max()
            }
        
        self.analysis_results['basic_stats'] = stats
        return stats
    
    def analyze_rent_by_station(self) -> pd.DataFrame:
        """
        駅別賃料分析
        
        Returns:
            駅別統計DataFrame
        """
        if self.df is None or 'search_station' not in self.df.columns:
            raise ValueError("Data not available for station analysis")
        
        station_stats = self.df.groupby('search_station').agg({
            'rent_numeric': ['count', 'mean', 'median', 'std', 'min', 'max'],
            'area_numeric': ['mean', 'median'],
            'rent_per_sqm': ['mean', 'median'],
            'building_age': ['mean', 'median']
        }).round(2)
        
        # カラム名をフラット化
        station_stats.columns = ['_'.join(col).strip() for col in station_stats.columns]
        station_stats = station_stats.reset_index()
        
        # 価格帯分布も追加
        for station in station_stats['search_station']:
            station_data = self.df[self.df['search_station'] == station]
            if 'rent_range' in station_data.columns:
                rent_dist = station_data['rent_range'].value_counts(normalize=True).to_dict()
                for range_name, ratio in rent_dist.items():
                    station_stats.loc[
                        station_stats['search_station'] == station, 
                        f'rent_ratio_{range_name}'
                    ] = ratio
        
        self.analysis_results['station_analysis'] = station_stats
        return station_stats
    
    def analyze_layout_distribution(self) -> pd.DataFrame:
        """
        間取り分布分析
        
        Returns:
            間取り別統計DataFrame
        """
        if self.df is None or 'layout' not in self.df.columns:
            raise ValueError("Layout data not available")
        
        layout_stats = self.df.groupby('layout').agg({
            'rent_numeric': ['count', 'mean', 'median', 'std'],
            'area_numeric': ['mean', 'median'],
            'rent_per_sqm': ['mean', 'median'],
            'building_age': ['mean', 'median']
        }).round(2)
        
        layout_stats.columns = ['_'.join(col).strip() for col in layout_stats.columns]
        layout_stats = layout_stats.reset_index()
        
        # 比率も追加
        total_count = len(self.df)
        layout_stats['percentage'] = (layout_stats['rent_numeric_count'] / total_count * 100).round(2)
        
        self.analysis_results['layout_analysis'] = layout_stats
        return layout_stats
    
    def analyze_age_impact(self) -> pd.DataFrame:
        """
        築年数が賃料に与える影響分析
        
        Returns:
            築年数別統計DataFrame
        """
        if self.df is None or 'age_category' not in self.df.columns:
            raise ValueError("Age category data not available")
        
        age_stats = self.df.groupby('age_category').agg({
            'rent_numeric': ['count', 'mean', 'median'],
            'rent_per_sqm': ['mean', 'median'],
            'area_numeric': ['mean']
        }).round(2)
        
        age_stats.columns = ['_'.join(col).strip() for col in age_stats.columns]
        age_stats = age_stats.reset_index()
        
        # 新築との比較
        if len(age_stats) > 0:
            newest_rent = age_stats.iloc[0]['rent_numeric_mean']
            age_stats['rent_vs_newest'] = ((age_stats['rent_numeric_mean'] / newest_rent - 1) * 100).round(2)
        
        self.analysis_results['age_analysis'] = age_stats
        return age_stats
    
    def find_deals(self, 
                   rent_percentile: float = 25, 
                   area_percentile: float = 75,
                   max_age: int = 15) -> pd.DataFrame:
        """
        お得物件の発見
        
        Args:
            rent_percentile: 賃料の分位点（この値以下）
            area_percentile: 面積の分位点（この値以上）
            max_age: 最大築年数
            
        Returns:
            お得物件のDataFrame
        """
        if self.df is None:
            raise ValueError("Data not loaded")
        
        # フィルタ条件
        conditions = []
        
        if 'rent_numeric' in self.df.columns:
            rent_threshold = self.df['rent_numeric'].quantile(rent_percentile / 100)
            conditions.append(self.df['rent_numeric'] <= rent_threshold)
        
        if 'area_numeric' in self.df.columns:
            area_threshold = self.df['area_numeric'].quantile(area_percentile / 100)
            conditions.append(self.df['area_numeric'] >= area_threshold)
        
        if 'building_age' in self.df.columns:
            conditions.append(self.df['building_age'] <= max_age)
        
        # 条件を満たす物件
        if conditions:
            deal_mask = conditions[0]
            for condition in conditions[1:]:
                deal_mask = deal_mask & condition
            
            deals = self.df[deal_mask].copy()
            
            # お得度スコア計算
            if 'rent_per_sqm' in deals.columns:
                deals['deal_score'] = (
                    (deals['area_numeric'] / deals['area_numeric'].mean()) * 0.4 +
                    (1 - deals['rent_per_sqm'] / deals['rent_per_sqm'].mean()) * 0.4 +
                    (1 - deals['building_age'] / deals['building_age'].max()) * 0.2
                ).round(3)
                
                deals = deals.sort_values('deal_score', ascending=False)
        else:
            deals = pd.DataFrame()
        
        self.analysis_results['deals'] = deals
        return deals
    
    def compare_stations(self, stations: List[str]) -> pd.DataFrame:
        """
        指定駅間の比較分析
        
        Args:
            stations: 比較する駅名のリスト
            
        Returns:
            比較結果DataFrame
        """
        if self.df is None or 'search_station' not in self.df.columns:
            raise ValueError("Station data not available")
        
        # 指定駅のデータのみ抽出
        station_data = self.df[self.df['search_station'].isin(stations)]
        
        if len(station_data) == 0:
            logger.warning(f"No data found for stations: {stations}")
            return pd.DataFrame()
        
        # 比較統計
        comparison = station_data.groupby('search_station').agg({
            'rent_numeric': ['count', 'mean', 'median'],
            'area_numeric': ['mean', 'median'],
            'rent_per_sqm': ['mean'],
            'building_age': ['mean']
        }).round(2)
        
        comparison.columns = ['_'.join(col).strip() for col in comparison.columns]
        comparison = comparison.reset_index()
        
        # ランキング追加
        comparison['rent_rank'] = comparison['rent_numeric_mean'].rank(ascending=True).astype(int)
        comparison['area_rank'] = comparison['area_numeric_mean'].rank(ascending=False).astype(int)
        comparison['cost_performance_rank'] = comparison['rent_per_sqm_mean'].rank(ascending=True).astype(int)
        
        self.analysis_results['station_comparison'] = comparison
        return comparison
    
    def get_price_trends(self, by: str = 'scraped_at') -> pd.DataFrame:
        """
        価格トレンド分析
        
        Args:
            by: トレンド分析の基準（'scraped_at', 'building_age'など）
            
        Returns:
            トレンドDataFrame
        """
        if self.df is None or by not in self.df.columns:
            raise ValueError(f"Column {by} not available")
        
        if by == 'scraped_at':
            # 日別トレンド
            trends = self.df.groupby(self.df[by].dt.date).agg({
                'rent_numeric': ['count', 'mean', 'median'],
                'area_numeric': ['mean'],
                'rent_per_sqm': ['mean']
            }).round(2)
        else:
            # その他のカラムによるトレンド
            trends = self.df.groupby(by).agg({
                'rent_numeric': ['count', 'mean', 'median'],
                'area_numeric': ['mean'],
                'rent_per_sqm': ['mean']
            }).round(2)
        
        trends.columns = ['_'.join(col).strip() for col in trends.columns]
        trends = trends.reset_index()
        
        self.analysis_results['trends'] = trends
        return trends
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """
        総合分析レポートの生成
        
        Returns:
            分析結果の辞書
        """
        logger.info("Generating comprehensive analysis report...")
        
        summary = {
            'generated_at': datetime.now().isoformat(),
            'data_overview': self.get_basic_stats(),
        }
        
        try:
            summary['station_analysis'] = self.analyze_rent_by_station().to_dict('records')
        except Exception as e:
            logger.warning(f"Station analysis failed: {e}")
            summary['station_analysis'] = []
        
        try:
            summary['layout_analysis'] = self.analyze_layout_distribution().to_dict('records')
        except Exception as e:
            logger.warning(f"Layout analysis failed: {e}")
            summary['layout_analysis'] = []
        
        try:
            summary['age_analysis'] = self.analyze_age_impact().to_dict('records')
        except Exception as e:
            logger.warning(f"Age analysis failed: {e}")
            summary['age_analysis'] = []
        
        try:
            deals = self.find_deals()
            summary['top_deals'] = deals.head(10).to_dict('records') if len(deals) > 0 else []
            summary['deals_count'] = len(deals)
        except Exception as e:
            logger.warning(f"Deal analysis failed: {e}")
            summary['top_deals'] = []
            summary['deals_count'] = 0
        
        # 主要インサイト
        summary['insights'] = self._generate_insights()
        
        self.analysis_results['summary_report'] = summary
        logger.info("Analysis report generated successfully")
        
        return summary
    
    def _generate_insights(self) -> List[str]:
        """
        データから主要インサイトを抽出
        
        Returns:
            インサイトのリスト
        """
        insights = []
        
        if self.df is None:
            return insights
        
        try:
            # 賃料に関するインサイト
            if 'rent_numeric' in self.df.columns:
                mean_rent = self.df['rent_numeric'].mean()
                median_rent = self.df['rent_numeric'].median()
                
                if mean_rent > median_rent * 1.2:
                    insights.append(f"賃料分布に偏りがあり、高額物件が平均を押し上げています（平均{mean_rent:.0f}円 vs 中央値{median_rent:.0f}円）")
            
            # 駅別インサイト
            if 'search_station' in self.df.columns and 'rent_numeric' in self.df.columns:
                station_means = self.df.groupby('search_station')['rent_numeric'].mean()
                if len(station_means) > 1:
                    highest_station = station_means.idxmax()
                    lowest_station = station_means.idxmin()
                    price_diff = station_means.max() - station_means.min()
                    
                    insights.append(f"最も高額な駅は{highest_station}（平均{station_means.max():.0f}円）、最も安価な駅は{lowest_station}（平均{station_means.min():.0f}円）で、差額は{price_diff:.0f}円です")
            
            # 間取り別インサイト
            if 'layout' in self.df.columns:
                layout_counts = self.df['layout'].value_counts()
                most_common = layout_counts.index[0]
                insights.append(f"最も多い間取りは{most_common}で、全体の{layout_counts.iloc[0]/len(self.df)*100:.1f}%を占めています")
            
            # 築年数インサイト
            if 'building_age' in self.df.columns:
                avg_age = self.df['building_age'].mean()
                new_ratio = (self.df['building_age'] <= 5).mean() * 100
                insights.append(f"平均築年数は{avg_age:.1f}年で、築5年以内の物件は{new_ratio:.1f}%です")
        
        except Exception as e:
            logger.warning(f"Error generating insights: {e}")
        
        return insights
    
    def export_analysis_results(self, output_path: str = "analysis/reports/analysis_results.json") -> str:
        """
        分析結果をJSONで出力
        
        Args:
            output_path: 出力ファイルパス
            
        Returns:
            出力ファイルパス
        """
        import json
        import os
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.analysis_results, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"Analysis results exported to {output_path}")
        return output_path