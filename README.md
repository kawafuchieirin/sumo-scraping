# SUUMO Scraper

SUUMO（スーモ）から賃貸物件情報を取得するPythonスクレイピングツールです。複数駅対応、件数指定、山手線全駅取得などの機能を備えています。

## 特徴

- 🚉 **複数駅対応**: 64駅から複数駅を同時指定可能
- 📊 **件数指定**: 取得する部屋数を自由に設定
- 🔄 **山手線全駅**: ワンコマンドで山手線全29駅を取得
- 💾 **複数形式出力**: JSON・CSV両形式で保存
- 🛡️ **データ検証**: Pydanticによる型安全なデータ処理
- ⚡ **高性能**: Playwrightによる高速・安定スクレイピング

## インストール

### 必要条件

- Python 3.9以上
- Poetry（推奨）またはpip

### Poetry使用（推奨）

```bash
# リポジトリをクローン
git clone https://github.com/kawafuchieirin/sumo-scraping.git
cd sumo-scraping

# 依存関係をインストール
poetry install

# Playwrightブラウザをセットアップ
poetry run setup-playwright
```

### pip使用

```bash
# 依存関係をインストール
pip install -r requirements.txt

# Playwrightブラウザをセットアップ
python setup_playwright.py
```

## 使用方法

### 基本的な使用例

```bash
# 渋谷駅から100件取得
poetry run python sumo_scraping/suumo_multi_scraper.py --stations 渋谷 --count 100

# 渋谷、新宿、池袋から合計200件取得
poetry run python sumo_scraping/suumo_multi_scraper.py --stations 渋谷 新宿 池袋 --count 200

# 山手線全駅から500件取得
poetry run python sumo_scraping/suumo_multi_scraper.py --yamanote --count 500
```

### 対応駅の確認

```bash
# 対応している駅名一覧を表示
poetry run python sumo_scraping/suumo_multi_scraper.py --list-stations
```

### オプション一覧

| オプション | 説明 | デフォルト |
|------------|------|------------|
| `--stations` | 対象駅名のリスト | 渋谷 |
| `--count` | 取得する部屋数 | 100 |
| `--yamanote` | 山手線全駅を対象 | False |
| `--prefecture` | 都道府県（tokyo/kanagawa/saitama/chiba） | tokyo |
| `--output-json` | JSONファイル出力パス | 自動生成 |
| `--output-csv` | CSVファイル出力パス | 自動生成 |
| `--list-stations` | 対応駅一覧を表示 | False |
| `--verbose` | 詳細ログを表示 | False |

## 対応駅

### 山手線（29駅）
渋谷、新宿、池袋、上野、東京、有楽町、新橋、浜松町、田町、品川、大崎、五反田、目黒、恵比寿、原宿、代々木、新大久保、高田馬場、目白、大塚、巣鴨、駒込、田端、西日暮里、日暮里、鶯谷、御徒町、秋葉原、神田

### その他主要駅（35駅）
中央線、京王線、小田急線、東急線、埼玉・千葉・神奈川方面の主要駅を含む

詳細は `--list-stations` で確認できます。

## 出力データ

### ファイル形式

- **JSON**: 完全な構造化データ（入れ子構造含む）
- **CSV**: 表形式データ（Excel等で開きやすい）

### ファイル名例

```
data/suumo_渋谷-新宿-池袋_20250712_182257.json
data/suumo_渋谷-新宿-池袋_20250712_182257.csv
```

### データ項目

| 項目 | 説明 |
|------|------|
| target_stations | 検索対象駅名 |
| search_station | 実際に取得した駅 |
| building_title | 物件名 |
| address | 住所 |
| access | アクセス情報 |
| building_age | 築年数 |
| rent_numeric | 賃料（数値） |
| layout | 間取り |
| area_numeric | 面積（数値） |
| detail_url | 詳細ページURL |

## 開発者向け

### プロジェクト構造

```
sumo-scraping/
├── sumo_scraping/           # メインスクレイピングパッケージ
│   ├── models.py           # Pydanticデータモデル
│   ├── station_mapping.py  # 駅名→URL変換
│   ├── suumo_scraper.py    # BeautifulSoup版スクレイパー
│   ├── suumo_multi_scraper.py # Playwright版マルチ駅スクレイパー
│   ├── polite_scraper.py   # サーバー負荷配慮版スクレイパー
│   ├── rate_limiter.py     # レート制限・リクエスト管理
│   └── cli.py              # コマンドラインインターフェース
├── analysis/               # データ分析パッケージ
│   ├── __init__.py         # 分析パッケージ初期化
│   ├── analyzer.py         # 総合分析クラス
│   ├── visualizer.py       # データ可視化クラス
│   ├── utils.py            # 分析用ユーティリティ
│   ├── notebooks/          # Jupyter分析ノートブック
│   │   ├── 01_basic_analysis.ipynb    # 基本分析
│   │   └── 02_visualization.ipynb     # 可視化
│   ├── scripts/            # CLI分析スクリプト
│   │   └── run_analysis.py # コマンドライン分析実行
│   ├── reports/            # 分析レポート出力先
│   ├── visualizations/     # 可視化ファイル出力先
│   └── data_processed/     # 処理済みデータ保存先
├── data/                   # 生データ保存先
├── setup_playwright.py     # Playwrightセットアップ
├── pyproject.toml          # Poetry設定
└── README.md              # このファイル
```

### 開発環境セットアップ

```bash
# 開発用依存関係をインストール
poetry install

# コード整形
poetry run black .

# 型チェック
poetry run mypy sumo_scraping/

# Linting
poetry run flake8 sumo_scraping/
```

### Poetryコマンド

```bash
# 基本スクレイパー（山手線沿線）
poetry run suumo-scraper

# 高性能スクレイパー（任意駅・件数指定）
poetry run suumo-playwright

# Playwrightセットアップ
poetry run setup-playwright
```

## データ分析機能

このプロジェクトには、スクレイピングしたデータを分析・可視化する包括的な分析フレームワークが含まれています。

### 🔍 分析機能

- **基本統計分析**: 賃料・面積・築年数の統計情報
- **駅別分析**: 駅ごとの賃料比較・ランキング
- **間取り分析**: 間取りタイプ別の分布・価格分析
- **築年数分析**: 築年数が賃料に与える影響
- **お得物件発見**: 価格・面積・築年数の条件による物件抽出
- **比較分析**: 複数駅間の詳細比較
- **インサイト生成**: データから自動的な洞察抽出

### 📊 可視化機能

- **インタラクティブグラフ**: Plotlyベースの動的チャート
- **ヒストグラム**: 賃料・面積分布
- **ボックスプロット**: 駅別賃料比較
- **散布図**: 面積vs賃料の関係性
- **ヒートマップ**: 駅×間取りの分布
- **総合ダッシュボード**: 複数の可視化を統合

### 分析の実行方法

#### Jupyter Notebookでの対話的分析

```bash
# 基本分析ノートブック
cd analysis/notebooks
jupyter notebook 01_basic_analysis.ipynb

# 可視化ノートブック  
jupyter notebook 02_visualization.ipynb
```

#### コマンドライン分析

```bash
# 基本分析のみ実行
python analysis/scripts/run_analysis.py --data-path data --basic-only

# 完全分析（可視化含む）
python analysis/scripts/run_analysis.py --data-path data --full-analysis --save-html

# 特定駅の比較分析
python analysis/scripts/run_analysis.py --compare-stations 渋谷 新宿 品川

# お得物件検索
python analysis/scripts/run_analysis.py --find-deals --rent-percentile 30 --area-percentile 70
```

#### Pythonスクリプトでの利用

```python
from analysis import SuumoAnalyzer, SuumoVisualizer

# 分析器の初期化
analyzer = SuumoAnalyzer("data/", auto_load=True)

# 基本統計情報
stats = analyzer.get_basic_stats()

# 駅別分析
station_analysis = analyzer.analyze_rent_by_station()

# お得物件発見
deals = analyzer.find_deals(rent_percentile=25, area_percentile=75)

# 可視化
visualizer = SuumoVisualizer(analyzer.df)
visualizer.generate_all_visualizations()
```

### 分析出力ファイル

```
analysis/
├── reports/
│   ├── analysis_results.json     # JSON形式の分析結果
│   └── analysis_report.html      # HTML形式のレポート
├── visualizations/
│   ├── rent_distribution_*.html   # 賃料分布グラフ
│   ├── rent_by_station_*.html     # 駅別賃料比較
│   ├── comprehensive_dashboard_*.html # 総合ダッシュボード
│   └── ...                       # その他の可視化ファイル
└── data_processed/
    └── cleaned_data_*.csv         # クリーニング済みデータ
```

### 分析機能の詳細

| 機能 | 説明 | 出力 |
|------|------|------|
| `get_basic_stats()` | 基本統計情報 | 件数、平均、中央値、最大最小値 |
| `analyze_rent_by_station()` | 駅別分析 | 駅ごとの賃料統計・ランキング |
| `analyze_layout_distribution()` | 間取り分析 | 間取り別件数・価格分布 |
| `analyze_age_impact()` | 築年数分析 | 築年数カテゴリ別の賃料影響 |
| `find_deals()` | お得物件検索 | 条件に合致する物件リスト |
| `compare_stations()` | 駅間比較 | 複数駅の詳細比較表 |
| `generate_summary_report()` | 総合レポート | 全分析結果＋インサイト |

## パフォーマンス

### 実行時間例

- **渋谷駅100件**: 約2分
- **山手線30件**: 約3分（複数駅スキップ含む）
- **複数駅200件**: 約5-8分
- **礼儀正しいモード**: 上記の1.5-2倍程度（サーバー負荷軽減）

### レート制限

- ページ間待機: 3-8秒（通常）/ 5-12秒（礼儀正しいモード）
- 駅間待機: 5-10秒（通常）/ 15-30秒（礼儀正しいモード）
- リクエスト間隔: 適切な間隔で実行
- robots.txt準拠
- User-Agentローテーション
- 自動リトライ機能

### 礼儀正しいスクレイピング

```bash
# サーバー負荷に配慮したスクレイピング
poetry run python sumo_scraping/polite_scraper.py --stations 渋谷 --count 50 --polite
```

## 注意事項

- SUUMOの利用規約を遵守してください
- 過度なアクセスは避けてください
- 取得したデータは個人利用の範囲内でご使用ください
- 商用利用前に利用規約を確認してください

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 貢献

プルリクエストや課題報告を歓迎します。以下の手順で貢献してください：

1. このリポジトリをフォーク
2. 機能ブランチを作成（`git checkout -b feature/AmazingFeature`）
3. 変更をコミット（`git commit -m 'Add some AmazingFeature'`）
4. ブランチにプッシュ（`git push origin feature/AmazingFeature`）
5. プルリクエストを作成

## サポート

問題やバグを発見した場合は、[Issues](https://github.com/kawafuchieirin/sumo-scraping/issues)で報告してください。

---

**⚠️ 免責事項**: このツールは教育・研究目的で作成されています。スクレイピング実行時は必ず対象サイトの利用規約を確認し、適切な間隔でアクセスしてください。