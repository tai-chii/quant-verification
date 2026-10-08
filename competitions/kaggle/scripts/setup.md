# Kaggle API セットアップ（初回のみ）

> **重要（2026-09-08 実測）**: Claude のシェル（device_bash / クラウド）からは **kaggle.com に到達できない**（egress遮断）。
> このページのコマンドは **taichi 自身の Terminal.app** で実行すること。
> 日常の学習・提出は Kaggle Notebook 上で行うので、CLI が無くても詰まらない。CLIは主にNotebook収集用。

```bash
pip3 install kaggle
```

1. https://www.kaggle.com/settings > API > "Create New Token" で `kaggle.json` を取得
2. 配置:

```bash
mkdir -p ~/.kaggle
mv ~/ワークスペース/受信箱/ダウンロード/kaggle.json ~/.kaggle/
chmod 600 ~/.kaggle/kaggle.json
```

3. 確認:

```bash
kaggle competitions list
```

## よく使うコマンド

```bash
# データ取得
kaggle competitions download -c <slug> -p <コンペ>/data

# 提出（CSV型のコンペのみ。Notebook型・評価API型は Kaggle 上の Notebook から Submit する）
kaggle competitions submit -c <slug> -f submissions/exp_007.csv -m "exp_007"

# 自分の提出履歴
kaggle competitions submissions -c <slug>
```
