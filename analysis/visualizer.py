"""
SUUMO データ可視化器

スクレイピングしたSUUMOデータの可視化とグラフ生成を行うクラス
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

from typing import Dict, List, Optional, Tuple, Any
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# 日本語フォント設定
plt.rcParams['font.family'] = ['DejaVu Sans', 'Hiragino Sans', 'Yu Gothic', 'Meiryo', 'Takao', 'IPAexGothic', 'IPAPGothic', 'VL PGothic', 'Noto Sans CJK JP']
sns.set_style("whitegrid")
sns.set_palette("husl")

class SuumoVisualizer:
    """SUUMO データ可視化器"""
    
    def __init__(self, df: pd.DataFrame, output_dir: str = "analysis/visualizations"):
        """
        初期化
        
        Args:
            df: 分析対象のDataFrame
            output_dir: 出力ディレクトリ
        """
        self.df = df
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 可視化用のカラーパレット
        self.colors = px.colors.qualitative.Set3
        self.station_colors = {}
        
    def _save_plot(self, fig, filename: str, format: str = 'png') -> str:
        """
        図を保存
        
        Args:
            fig: matplotlib/plotly figure
            filename: ファイル名
            format: 保存形式
            
        Returns:
            保存パス
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = os.path.join(self.output_dir, f"{filename}_{timestamp}.{format}")
        
        try:
            if hasattr(fig, 'write_html'):  # Plotly
                if format == 'html':
                    fig.write_html(filepath)
                else:
                    fig.write_image(filepath, engine="kaleido")
            else:  # Matplotlib
                fig.savefig(filepath, dpi=300, bbox_inches='tight', 
                           facecolor='white', edgecolor='none')
                plt.close(fig)
                
            logger.info(f"Plot saved: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving plot: {e}")
            return ""
    
    def plot_rent_distribution(self, by_station: bool = False, save: bool = True) -> go.Figure:
        """
        賃料分布のヒストグラム
        
        Args:
            by_station: 駅別に分けるかどうか
            save: ファイルに保存するかどうか
            
        Returns:
            Plotly figure
        """
        if 'rent_numeric' not in self.df.columns:
            raise ValueError("rent_numeric column not found")
        
        if by_station and 'search_station' in self.df.columns:
            fig = px.histogram(
                self.df, 
                x='rent_numeric',
                color='search_station',
                title='駅別賃料分布',
                labels={'rent_numeric': '賃料 (円)', 'count': '件数'},
                nbins=30,
                opacity=0.7
            )
        else:
            fig = px.histogram(
                self.df, 
                x='rent_numeric',
                title='賃料分布',
                labels={'rent_numeric': '賃料 (円)', 'count': '件数'},
                nbins=30,
                color_discrete_sequence=[self.colors[0]]
            )
        
        fig.update_layout(
            xaxis_title="賃料 (円)",
            yaxis_title="件数",
            title_x=0.5,
            showlegend=by_station
        )
        
        if save:
            self._save_plot(fig, "rent_distribution", "html")
        
        return fig
    
    def plot_rent_by_station(self, save: bool = True) -> go.Figure:
        """
        駅別賃料比較（ボックスプロット）
        
        Args:
            save: ファイルに保存するかどうか
            
        Returns:
            Plotly figure
        """
        if 'search_station' not in self.df.columns or 'rent_numeric' not in self.df.columns:
            raise ValueError("Required columns not found")
        
        # 駅別平均賃料でソート
        station_order = self.df.groupby('search_station')['rent_numeric'].mean().sort_values(ascending=False).index
        
        fig = px.box(
            self.df,
            x='search_station',
            y='rent_numeric',
            title='駅別賃料分布',
            labels={'search_station': '駅', 'rent_numeric': '賃料 (円)'},
            category_orders={'search_station': station_order.tolist()}
        )
        
        fig.update_layout(
            xaxis_title="駅",
            yaxis_title="賃料 (円)",
            title_x=0.5,
            xaxis_tickangle=-45
        )
        
        if save:
            self._save_plot(fig, "rent_by_station", "html")
        
        return fig
    
    def plot_area_vs_rent(self, color_by: str = 'layout', save: bool = True) -> go.Figure:
        """
        面積と賃料の散布図
        
        Args:
            color_by: 色分けする列（'layout', 'search_station', など）
            save: ファイルに保存するかどうか
            
        Returns:
            Plotly figure
        """
        if 'area_numeric' not in self.df.columns or 'rent_numeric' not in self.df.columns:
            raise ValueError("Required columns not found")
        
        color_column = color_by if color_by in self.df.columns else None
        
        fig = px.scatter(
            self.df,
            x='area_numeric',
            y='rent_numeric',
            color=color_column,
            title=f'面積と賃料の関係 ({color_by}別)',
            labels={'area_numeric': '面積 (㎡)', 'rent_numeric': '賃料 (円)'},
            hover_data=['building_title', 'address'] if 'building_title' in self.df.columns else None
        )
        
        fig.update_layout(
            xaxis_title="面積 (㎡)",
            yaxis_title="賃料 (円)",
            title_x=0.5
        )
        
        if save:
            self._save_plot(fig, f"area_vs_rent_{color_by}", "html")
        
        return fig
    
    def plot_rent_per_sqm_by_station(self, save: bool = True) -> go.Figure:
        """
        駅別平米単価比較
        
        Args:
            save: ファイルに保存するかどうか
            
        Returns:
            Plotly figure
        """
        if 'search_station' not in self.df.columns or 'rent_per_sqm' not in self.df.columns:
            raise ValueError("Required columns not found")
        
        # 駅別平米単価統計
        station_stats = self.df.groupby('search_station')['rent_per_sqm'].agg(['mean', 'median', 'std']).reset_index()
        station_stats = station_stats.sort_values('mean', ascending=False)
        
        fig = go.Figure()
        
        # 平均値
        fig.add_trace(go.Bar(
            x=station_stats['search_station'],
            y=station_stats['mean'],
            name='平均',
            marker_color=self.colors[0]
        ))
        
        # 中央値
        fig.add_trace(go.Bar(
            x=station_stats['search_station'],
            y=station_stats['median'],
            name='中央値',
            marker_color=self.colors[1],
            opacity=0.7
        ))
        
        fig.update_layout(
            title='駅別平米単価比較',
            xaxis_title='駅',
            yaxis_title='平米単価 (円/㎡)',
            title_x=0.5,
            xaxis_tickangle=-45,
            barmode='group'
        )
        
        if save:
            self._save_plot(fig, "rent_per_sqm_by_station", "html")
        
        return fig
    
    def plot_layout_distribution(self, save: bool = True) -> go.Figure:
        """
        間取り分布円グラフ
        
        Args:
            save: ファイルに保存するかどうか
            
        Returns:
            Plotly figure
        """
        if 'layout' not in self.df.columns:
            raise ValueError("layout column not found")
        
        layout_counts = self.df['layout'].value_counts()
        
        fig = px.pie(
            values=layout_counts.values,
            names=layout_counts.index,
            title='間取り分布',
            color_discrete_sequence=self.colors
        )
        
        fig.update_layout(title_x=0.5)
        
        if save:
            self._save_plot(fig, "layout_distribution", "html")
        
        return fig
    
    def plot_age_vs_rent(self, save: bool = True) -> go.Figure:
        """
        築年数と賃料の関係
        
        Args:
            save: ファイルに保存するかどうか
            
        Returns:
            Plotly figure
        """
        if 'building_age' not in self.df.columns or 'rent_numeric' not in self.df.columns:
            raise ValueError("Required columns not found")
        
        # 築年数を5年刻みでグループ化
        self.df['age_group'] = (self.df['building_age'] // 5) * 5
        age_stats = self.df.groupby('age_group').agg({
            'rent_numeric': ['mean', 'count'],
            'rent_per_sqm': 'mean'
        }).round(2)
        
        age_stats.columns = ['rent_mean', 'count', 'rent_per_sqm_mean']
        age_stats = age_stats.reset_index()
        
        # 件数が少ないグループは除外
        age_stats = age_stats[age_stats['count'] >= 3]
        
        fig = go.Figure()
        
        # 平均賃料
        fig.add_trace(go.Scatter(
            x=age_stats['age_group'],
            y=age_stats['rent_mean'],
            mode='lines+markers',
            name='平均賃料',
            yaxis='y',
            line=dict(color=self.colors[0])
        ))
        
        # 平米単価（右軸）
        fig.add_trace(go.Scatter(
            x=age_stats['age_group'],
            y=age_stats['rent_per_sqm_mean'],
            mode='lines+markers',
            name='平米単価',
            yaxis='y2',
            line=dict(color=self.colors[1])
        ))
        
        fig.update_layout(
            title='築年数と賃料の関係',
            xaxis_title='築年数 (年)',
            yaxis=dict(title='平均賃料 (円)', side='left'),
            yaxis2=dict(title='平米単価 (円/㎡)', side='right', overlaying='y'),
            title_x=0.5
        )
        
        if save:
            self._save_plot(fig, "age_vs_rent", "html")
        
        return fig
    
    def plot_heatmap_station_layout(self, save: bool = True) -> go.Figure:
        """
        駅×間取りのヒートマップ
        
        Args:
            save: ファイルに保存するかどうか
            
        Returns:
            Plotly figure
        """
        if 'search_station' not in self.df.columns or 'layout' not in self.df.columns:
            raise ValueError("Required columns not found")
        
        # クロス集計
        cross_tab = pd.crosstab(self.df['search_station'], self.df['layout'])
        
        fig = px.imshow(
            cross_tab.values,
            x=cross_tab.columns,
            y=cross_tab.index,
            title='駅×間取り 物件数ヒートマップ',
            labels={'x': '間取り', 'y': '駅', 'color': '物件数'},
            text_auto=True,
            color_continuous_scale='Blues'
        )
        
        fig.update_layout(title_x=0.5)
        
        if save:
            self._save_plot(fig, "heatmap_station_layout", "html")
        
        return fig
    
    def plot_price_range_distribution(self, save: bool = True) -> go.Figure:
        """
        価格帯分布のスタックドバー
        
        Args:
            save: ファイルに保存するかどうか
            
        Returns:
            Plotly figure
        """
        if 'search_station' not in self.df.columns or 'rent_range' not in self.df.columns:
            raise ValueError("Required columns not found")
        
        # 駅別価格帯分布
        cross_tab = pd.crosstab(self.df['search_station'], self.df['rent_range'], normalize='index') * 100
        
        fig = go.Figure()
        
        for i, price_range in enumerate(cross_tab.columns):
            fig.add_trace(go.Bar(
                x=cross_tab.index,
                y=cross_tab[price_range],
                name=price_range,
                marker_color=self.colors[i % len(self.colors)]
            ))
        
        fig.update_layout(
            title='駅別価格帯分布',
            xaxis_title='駅',
            yaxis_title='割合 (%)',
            title_x=0.5,
            barmode='stack',
            xaxis_tickangle=-45
        )
        
        if save:
            self._save_plot(fig, "price_range_distribution", "html")
        
        return fig
    
    def plot_comprehensive_dashboard(self, save: bool = True) -> go.Figure:
        """
        総合ダッシュボード
        
        Args:
            save: ファイルに保存するかどうか
            
        Returns:
            Plotly figure
        """
        # サブプロット作成
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('賃料分布', '駅別平均賃料', '面積vs賃料', '間取り分布'),
            specs=[[{"type": "xy"}, {"type": "xy"}],
                   [{"type": "xy"}, {"type": "domain"}]]
        )
        
        # 1. 賃料分布
        rent_hist = np.histogram(self.df['rent_numeric'].dropna(), bins=20)
        fig.add_trace(
            go.Bar(x=rent_hist[1][:-1], y=rent_hist[0], name="賃料分布"),
            row=1, col=1
        )
        
        # 2. 駅別平均賃料
        if 'search_station' in self.df.columns:
            station_means = self.df.groupby('search_station')['rent_numeric'].mean().sort_values(ascending=False)
            fig.add_trace(
                go.Bar(x=station_means.index, y=station_means.values, name="駅別平均賃料"),
                row=1, col=2
            )
        
        # 3. 面積vs賃料散布図
        if 'area_numeric' in self.df.columns:
            fig.add_trace(
                go.Scatter(
                    x=self.df['area_numeric'],
                    y=self.df['rent_numeric'],
                    mode='markers',
                    name="面積vs賃料",
                    opacity=0.6
                ),
                row=2, col=1
            )
        
        # 4. 間取り分布（円グラフ）
        if 'layout' in self.df.columns:
            layout_counts = self.df['layout'].value_counts()
            fig.add_trace(
                go.Pie(
                    values=layout_counts.values,
                    labels=layout_counts.index,
                    name="間取り分布"
                ),
                row=2, col=2
            )
        
        fig.update_layout(
            height=800,
            title_text="SUUMO データ分析ダッシュボード",
            title_x=0.5,
            showlegend=False
        )
        
        if save:
            self._save_plot(fig, "comprehensive_dashboard", "html")
        
        return fig
    
    def create_interactive_map(self, save: bool = True) -> go.Figure:
        """
        インタラクティブ地図（今後の拡張用）
        
        Args:
            save: ファイルに保存するかどうか
            
        Returns:
            Plotly figure
        """
        # 現在は東京駅を中心とした基本的な地図
        # 将来的には住所から緯度経度を取得して物件位置をプロット
        
        fig = go.Figure(go.Scattermapbox(
            lat=[35.6762],
            lon=[139.6503],
            mode='markers',
            marker=go.scattermapbox.Marker(size=9),
            text=["東京駅周辺エリア"],
        ))
        
        fig.update_layout(
            mapbox_style="open-street-map",
            mapbox=dict(
                center=go.layout.mapbox.Center(
                    lat=35.6762,
                    lon=139.6503
                ),
                zoom=10
            ),
            showlegend=False,
            title="物件分布マップ（開発中）",
            title_x=0.5
        )
        
        if save:
            self._save_plot(fig, "interactive_map", "html")
        
        return fig
    
    def generate_all_visualizations(self) -> Dict[str, str]:
        """
        全ての可視化を生成
        
        Returns:
            生成したファイルパスの辞書
        """
        logger.info("Generating all visualizations...")
        
        generated_files = {}
        
        try:
            self.plot_rent_distribution()
            generated_files['rent_distribution'] = "賃料分布"
        except Exception as e:
            logger.warning(f"Failed to generate rent distribution: {e}")
        
        try:
            self.plot_rent_by_station()
            generated_files['rent_by_station'] = "駅別賃料比較"
        except Exception as e:
            logger.warning(f"Failed to generate rent by station: {e}")
        
        try:
            self.plot_area_vs_rent()
            generated_files['area_vs_rent'] = "面積と賃料の関係"
        except Exception as e:
            logger.warning(f"Failed to generate area vs rent: {e}")
        
        try:
            self.plot_layout_distribution()
            generated_files['layout_distribution'] = "間取り分布"
        except Exception as e:
            logger.warning(f"Failed to generate layout distribution: {e}")
        
        try:
            self.plot_comprehensive_dashboard()
            generated_files['dashboard'] = "総合ダッシュボード"
        except Exception as e:
            logger.warning(f"Failed to generate dashboard: {e}")
        
        logger.info(f"Generated {len(generated_files)} visualizations")
        return generated_files