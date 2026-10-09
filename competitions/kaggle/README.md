# kaggle-work — 作業層

Kaggleのコード・データ・生Notebook・提出ファイルを置く。**vault外**。

## 知識層はこちら（正本）

`~/ワークスペース/検証/コンペ/kaggle/知識/`

- 判断・数値・メモの正本は**すべて知識層**にある
- ここには**再生成可能なものだけ**を置く。ここが消えても知識層があれば復元できる状態を保つ
- 逆に、ここにしか無い考察を作らないこと

## 構成

```
kaggle-work/
├── scripts/              収集・補助スクリプト
└── <コンペslug>/
    ├── data/             コンペデータ（gitにもvaultにも入れない）
    ├── notebooks/        自分のNotebook（Kaggle上が主、ここはバックアップ）
    ├── raw_solutions/    上位者の生Notebook（参照用・Claudeには読ませない）
    └── submissions/      提出ファイル。exp_id と同じ名前にする
```

## 重要

`raw_solutions/` は**参照用の付録**であって知識ではない。
Claudeにここのコードをまとめて読ませると、根拠のない mashup を作る。
価値は蒸留した `コンペ/kaggle/知識/_playbook/解法メモ/` の1枚ノートのほうにある。
