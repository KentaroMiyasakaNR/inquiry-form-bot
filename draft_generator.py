import json
import requests
from config import OLLAMA_HOST, OLLAMA_MODEL


def generate_draft(fields: list[dict], purpose: str, sender_info: dict) -> dict:
    skip_types = {"hidden", "submit", "button", "image", "checkbox", "radio", "file"}
    visible_fields = [f for f in fields if f["type"] not in skip_types]

    fields_text = "\n".join([
        f"- {f['label'] or f['name'] or f['placeholder']} "
        f"({'必須' if f['required'] else '任意'}, タイプ: {f['type']})"
        for f in visible_fields
    ])

    sender_text = "\n".join([f"{k}: {v}" for k, v in sender_info.items()])

    prompt = f"""あなたは企業への問い合わせフォームの入力内容を作成するアシスタントです。

【問い合わせの目的】
{purpose}

【送信者情報】
{sender_text}

【フォームのフィールド一覧】
{fields_text}

上記のフォームの各フィールドに入力する適切な内容をJSONで出力してください。
- キー: フィールドのラベルまたは名前（上記リストと完全一致させること）
- 値: そのフィールドに入力する日本語テキスト
- 本文・メッセージ欄は丁寧で自然なビジネス日本語で書くこと
- 名前・メール・電話は送信者情報から使うこと

JSONのみ出力し、説明文は不要です。"""

    # stream=True でトークンを受け取りながら結合（read timeout を回避）
    response = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True},
        timeout=(10, 600),  # (接続タイムアウト, 読み込みタイムアウト)
        stream=True,
    )
    response.raise_for_status()

    raw = ""
    for line in response.iter_lines():
        if line:
            chunk = json.loads(line)
            raw += chunk.get("response", "")
            if chunk.get("done"):
                break

    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        return json.loads(raw[start:end])
    except Exception:
        return {"raw_response": raw}
