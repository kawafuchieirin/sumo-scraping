#!/usr/bin/env python3
"""
SUUMO データ分析スクリプト

コマンドラインから実行可能な分析スクリプト
Jupyter Notebookを使わずに分析を実行したい場合に使用
"""

import sys
import os
import argparse
from datetime import datetime
import logging

# パスの設定
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer import SuumoAnalyzer
from visualizer import SuumoVisualizer

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('analysis.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def parse_arguments():
    """コマンドライン引数の解析"""
    parser = argparse.ArgumentParser(
        description="SUUMO データ分析スクリプト",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 基本分析のみ実行
  python run_analysis.py --data-path ../../data --basic-only
  
  # 完全分析（可視化含む）
  python run_analysis.py --data-path ../../data --full-analysis
  
  # 特定駅の比較分析
  python run_analysis.py --data-path ../../data --compare-stations 渋谷 新宿 品川
  
  # お得物件分析
  python run_analysis.py --data-path ../../data --find-deals --rent-percentile 30 --area-percentile 70
        """
    )
    
    parser.add_argument('--data-path', default='../../data',
                       help='データディレクトリのパス (デフォルト: ../../data)')
    parser.add_argument('--output-dir', default='../reports',
                       help='出力ディレクトリ (デフォルト: ../reports)')
    parser.add_argument('--latest-only', action='store_true',
                       help='最新ファイルのみ使用')
    
    # 分析モード
    parser.add_argument('--basic-only', action='store_true',
                       help='基本分析のみ実行')
    parser.add_argument('--full-analysis', action='store_true',
                       help='完全分析（可視化含む）を実行')
    parser.add_argument('--visualize-only', action='store_true',
                       help='可視化のみ実行')
    
    # 特定分析
    parser.add_argument('--compare-stations', nargs='+',
                       help='比較する駅名のリスト')
    parser.add_argument('--find-deals', action='store_true',
                       help='お得物件分析を実行')
    parser.add_argument('--rent-percentile', type=float, default=25,
                       help='お得物件の賃料分位点 (デフォルト: 25)')
    parser.add_argument('--area-percentile', type=float, default=75,
                       help='お得物件の面積分位点 (デフォルト: 75)')
    parser.add_argument('--max-age', type=int, default=20,
                       help='お得物件の最大築年数 (デフォルト: 20)')
    
    # 出力設定
    parser.add_argument('--save-html', action='store_true',
                       help='HTML形式でレポート出力')
    parser.add_argument('--save-json', action='store_true',
                       help='JSON形式で分析結果出力')
    parser.add_argument('--verbose', action='store_true',
                       help='詳細ログを表示')
    
    return parser.parse_args()

def print_section_header(title):
    """セクションヘッダーの出力"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def run_basic_analysis(analyzer):
    """基本分析の実行"""
    print_section_header("基本統計分析")
    
    # 基本統計
    basic_stats = analyzer.get_basic_stats()
    
    print(f"📊 データ概要:")
    print(f"   総物件数: {basic_stats['total_properties']:,} 件")
    print(f"   対象駅数: {basic_stats['stations']['count']} 駅")
    print(f"   対象駅: {', '.join(basic_stats['stations']['list'])}")
    
    if 'rent' in basic_stats:
        rent_stats = basic_stats['rent']
        print(f"\n💰 賃料統計:")
        print(f"   平均: {rent_stats['mean']:,.0f} 円")
        print(f"   中央値: {rent_stats['median']:,.0f} 円")
        print(f"   最小-最大: {rent_stats['min']:,.0f} - {rent_stats['max']:,.0f} 円")
    
    if 'area' in basic_stats:
        area_stats = basic_stats['area']
        print(f"\n📐 面積統計:")
        print(f"   平均: {area_stats['mean']:.1f} ㎡")
        print(f"   中央値: {area_stats['median']:.1f} ㎡")
    
    # 駅別分析
    try:
        print_section_header("駅別分析")
        station_analysis = analyzer.analyze_rent_by_station()
        
        print("💰 賃料TOP5駅:")
        top_stations = station_analysis.nlargest(5, 'rent_numeric_mean')
        for i, (_, row) in enumerate(top_stations.iterrows(), 1):
            print(f"  {i}. {row['search_station']}: {row['rent_numeric_mean']:,.0f}円")
        
        print("\n💸 賃料安価TOP5駅:")
        bottom_stations = station_analysis.nsmallest(5, 'rent_numeric_mean')
        for i, (_, row) in enumerate(bottom_stations.iterrows(), 1):
            print(f"  {i}. {row['search_station']}: {row['rent_numeric_mean']:,.0f}円")
            
    except Exception as e:
        logger.warning(f"駅別分析でエラー: {e}")
    
    # 間取り分析
    try:
        print_section_header("間取り分析")
        layout_analysis = analyzer.analyze_layout_distribution()
        
        print("🏠 間取り分布:")
        for _, row in layout_analysis.head(10).iterrows():
            print(f"  {row['layout']}: {row['rent_numeric_count']}件 ({row['percentage']:.1f}%)")
            
    except Exception as e:
        logger.warning(f"間取り分析でエラー: {e}")
    
    return basic_stats

def run_deal_analysis(analyzer, rent_percentile, area_percentile, max_age):
    """お得物件分析の実行"""
    print_section_header("お得物件分析")
    
    try:
        deals = analyzer.find_deals(
            rent_percentile=rent_percentile,
            area_percentile=area_percentile,
            max_age=max_age
        )
        
        print(f"🎯 検索条件:")
        print(f"   賃料: 下位{rent_percentile}%以下")
        print(f"   面積: 上位{100-area_percentile}%以上")
        print(f"   築年数: {max_age}年以内")
        
        if len(deals) > 0:
            print(f"\n✨ 発見されたお得物件: {len(deals)}件")
            
            # TOP10表示
            print("\n🏆 お得度TOP10:")
            top_deals = deals.head(10)
            
            for i, (_, deal) in enumerate(top_deals.iterrows(), 1):
                title = deal.get('building_title', '不明')
                station = deal.get('search_station', '不明')
                rent = deal.get('rent_numeric', 0)
                area = deal.get('area_numeric', 0)
                score = deal.get('deal_score', 0)
                
                print(f"  {i:2d}. {title[:20]:<20} | {station:<8} | {rent:>8,.0f}円 | {area:>5.1f}㎡ | {score:.3f}")
        else:
            print("\n😔 条件に合うお得物件は見つかりませんでした")
            
    except Exception as e:
        logger.error(f"お得物件分析でエラー: {e}")

def run_station_comparison(analyzer, stations):
    """駅間比較分析の実行"""
    print_section_header(f"駅間比較分析: {', '.join(stations)}")
    
    try:
        comparison = analyzer.compare_stations(stations)
        
        if len(comparison) > 0:
            print("📊 比較結果:")
            print(f"{'駅名':<10} {'件数':<6} {'平均賃料':<10} {'平米単価':<10} {'コスパ順位':<8}")
            print("-" * 60)
            
            for _, row in comparison.iterrows():
                station = row['search_station']
                count = row['rent_numeric_count']
                avg_rent = row['rent_numeric_mean']
                rent_per_sqm = row.get('rent_per_sqm_mean', 0)
                cp_rank = row.get('cost_performance_rank', 0)
                
                print(f"{station:<10} {count:<6.0f} {avg_rent:<10,.0f} {rent_per_sqm:<10,.0f} {cp_rank:<8.0f}")
        else:
            print("⚠️ 指定された駅のデータが見つかりませんでした")
            
    except Exception as e:
        logger.error(f"駅間比較分析でエラー: {e}")

def run_visualization(analyzer, output_dir):
    """可視化の実行"""
    print_section_header("データ可視化")
    
    try:
        visualizer = SuumoVisualizer(analyzer.df, output_dir=os.path.join(output_dir, "visualizations"))
        generated_files = visualizer.generate_all_visualizations()
        
        print("📊 生成された可視化:")
        for key, description in generated_files.items():
            print(f"   ✅ {description}")
        
        print(f"\n📂 保存先: {visualizer.output_dir}")
        return True
        
    except Exception as e:
        logger.error(f"可視化でエラー: {e}")
        return False

def save_results(analyzer, output_dir, save_json, save_html):
    """結果の保存"""
    print_section_header("結果保存")
    
    os.makedirs(output_dir, exist_ok=True)
    
    if save_json:
        try:
            json_path = analyzer.export_analysis_results(
                os.path.join(output_dir, "analysis_results.json")
            )
            print(f"💾 JSON結果保存: {json_path}")
        except Exception as e:
            logger.error(f"JSON保存でエラー: {e}")
    
    if save_html:
        try:
            from utils import export_report
            html_path = export_report(
                analyzer.df,
                os.path.join(output_dir, "analysis_report.html"),
                "SUUMO データ分析レポート"
            )
            print(f"💾 HTMLレポート保存: {html_path}")
        except Exception as e:
            logger.error(f"HTMLレポート保存でエラー: {e}")

def main():
    """メイン処理"""
    args = parse_arguments()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("🔄 SUUMO データ分析スクリプト開始")
    print(f"📅 実行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 データパス: {args.data_path}")
    print(f"📤 出力パス: {args.output_dir}")
    
    try:
        # データ読み込みと分析器初期化
        print_section_header("データ読み込み")
        analyzer = SuumoAnalyzer(
            data_path=args.data_path,
            auto_load=True
        )
        
        if analyzer.df is None:
            logger.error("データの読み込みに失敗しました")
            return 1
        
        print(f"✅ データ読み込み完了: {len(analyzer.df)} 件")
        
        # 分析実行
        if args.basic_only or args.full_analysis or (not any([args.visualize_only, args.compare_stations, args.find_deals])):
            run_basic_analysis(analyzer)
        
        if args.compare_stations:
            run_station_comparison(analyzer, args.compare_stations)
        
        if args.find_deals:
            run_deal_analysis(analyzer, args.rent_percentile, args.area_percentile, args.max_age)
        
        if args.visualize_only or args.full_analysis:
            run_visualization(analyzer, args.output_dir)
        
        # 結果保存
        if args.save_json or args.save_html:
            save_results(analyzer, args.output_dir, args.save_json, args.save_html)
        
        # 総合レポート生成
        if args.full_analysis:
            print_section_header("総合レポート")
            summary = analyzer.generate_summary_report()
            
            print("🔍 主要インサイト:")
            for i, insight in enumerate(summary.get('insights', []), 1):
                print(f"  {i}. {insight}")
        
        print_section_header("分析完了")
        print("✅ すべての分析が正常に完了しました")
        return 0
        
    except KeyboardInterrupt:
        logger.info("ユーザーによって中断されました")
        return 1
    except Exception as e:
        logger.error(f"予期しないエラーが発生しました: {e}")
        return 1

if __name__ == "__main__":
    exit(main())