# 問い合わせ自動入力アシスタント

企業サイトのURLを入力するだけで、ローカルLLM（Ollama）がフォームの内容を自動解析し、問い合わせ文を生成・自動入力するツールです。

- **APIキー不要・完全ローカル動作**（プライバシー安全）
- Apple Silicon (M1/M2/M3) 対応・Metal GPU加速

---

## 動作環境

| 項目 | 要件 |
|------|------|
| OS | macOS（Apple Silicon推奨） |
| Python | 3.10 以上 |
| メモリ | 8GB以上（16GB推奨） |
| Ollama | 0.3.0 以上 |

---

## セットアップ

### 1. Homebrew のインストール（未インストールの場合）

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. Ollama のインストール

```bash
brew install ollama
```

インストール後、メニューバーのOllamaアイコンからアプリを起動してください。

### 3. LLMモデルのダウンロード

```bash
# 日本語精度・速度バランス型（推奨・約5GB）
ollama pull qwen2.5:7b

# 高精度版（約9GB・16GBメモリ推奨）
ollama pull qwen2.5:14b
```

### 4. リポジトリのクローン

```bash
git clone https://github.com/KentaroMiyasakaNR/inquiry-form-bot.git
cd inquiry-form-bot
```

### 5. Python パッケージのインストール

```bash
pip3 install playwright streamlit requests
playwright install chromium
```

---

## 設定

`config.py` を開いて以下を編集します：

```python
TARGET_URL = "https://example.com"       # 問い合わせ先のURL（トップページでもOK）
INQUIRY_PURPOSE = "VR研修の導入について相談したい"  # 問い合わせの目的

SENDER_INFO = {
    "会社名": "株式会社○○",
    "担当者名": "山田 太郎",
    "メールアドレス": "yamada@example.com",
    "電話番号": "090-0000-0000",
}

OLLAMA_MODEL = "qwen2.5:7b"  # ダウンロードしたモデル名に合わせる
```

---

## 使い方

### Streamlit UI（推奨）

```bash
streamlit run app.py
```

ブラウザで `http://localhost:8501` が自動で開きます。

1. URLを入力（企業トップページでもお問い合わせページでもOK）
2. 問い合わせの目的を入力
3. 送信者情報を入力
4. **「🚀 フォーム解析 → 下書き生成」** ボタンを押す
5. 生成された下書きを画面上で編集
6. **「ブラウザを開いて自動入力する」** でフォームに流し込み（送信はしない）

### CLI版

```bash
python3 main.py
```

---

## ファイル構成

```
inquiry-form-bot/
├── app.py              # Streamlit UI
├── main.py             # CLI版
├── form_analyzer.py    # Playwright によるフォーム自動検出・解析
├── draft_generator.py  # Ollama による下書き生成
└── config.py           # 設定ファイル（URL・目的・送信者情報）
```

---

## トラブルシューティング

### 下書き生成がタイムアウトする

Ollamaサーバーが停止している可能性があります。再起動してください：

```bash
pkill -f "ollama serve"
# メニューバーの Ollama アイコン → Quit → 再起動
```

再起動後、以下でモデルが動くか確認：

```bash
ollama ps
ollama run qwen2.5:7b "テスト"
```

### フォームが見つからない / 0件で自動入力される

- **フォームが見つからない** → お問い合わせページのURLを直接 `config.py` に指定してみてください
- **0件** → Streamlit の「入力ログ」を展開して原因を確認してください

### Playwright のエラー

```bash
playwright install chromium
```

---

## 処理の流れ

```
入力URL
  ↓
[Playwright] ページを開く
  ↓
お問い合わせリンクを自動検出 → 移動
  ↓
フォームフィールドを抽出（ラベル・name・type・必須かどうか）
  ↓
[Ollama / qwen2.5] フィールド構造 + 目的 → 各フィールドの文章を生成
  ↓
Streamlit UI で確認・編集
  ↓
[Playwright] ブラウザでフォームに自動入力（送信はしない）
```
