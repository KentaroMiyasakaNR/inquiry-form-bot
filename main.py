import json
from config import TARGET_URL, INQUIRY_PURPOSE, SENDER_INFO
from form_analyzer import analyze_form
from draft_generator import generate_draft


def main():
    print(f"[1/3] ページを解析中: {TARGET_URL}")
    fields, form_url, nav_status = analyze_form(TARGET_URL)
    print(f"ナビゲーション結果: {nav_status}")

    skip_types = {"hidden", "submit", "button", "image"}
    visible = [f for f in fields if f["type"] not in skip_types]

    if not visible:
        print("フォームが見つかりませんでした。URLを確認してください。")
        return

    print(f"\n{len(visible)}個のフィールドを検出 (フォームURL: {form_url}):")
    for f in visible:
        label = f["label"] or f["name"] or f["placeholder"] or "(不明)"
        req = "必須" if f["required"] else "任意"
        print(f"  [{req}] {label} ({f['type']})")

    print(f"\n[2/3] qwen2.5:7b で下書きを生成中...")
    draft = generate_draft(fields, INQUIRY_PURPOSE, SENDER_INFO)

    print("\n[3/3] 生成された下書き:")
    print("-" * 40)
    print(json.dumps(draft, ensure_ascii=False, indent=2))
    print("-" * 40)

    answer = input("\nフォームに自動入力しますか？（送信はしません）[y/N]: ")
    if answer.strip().lower() == "y":
        fill_form(form_url, fields, draft)


def fill_form(form_url: str, fields: list[dict], draft: dict):
    from playwright.sync_api import sync_playwright

    print("\nブラウザを起動して自動入力します（送信はしません）...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(form_url, wait_until="networkidle", timeout=30000)

        filled = 0
        for field in fields:
            if not field["selector"]:
                continue
            label = field["label"] or field["name"] or field["placeholder"]
            value = draft.get(label)
            if not value:
                continue
            try:
                el = page.query_selector(field["selector"])
                if el:
                    el.fill(str(value))
                    print(f"  ✓ {label}")
                    filled += 1
            except Exception as e:
                print(f"  ✗ {label}: {e}")

        print(f"\n{filled}フィールドへの入力が完了しました（送信はしていません）")
        print("ブラウザを確認してください。Enterキーで終了します。")
        input()
        browser.close()


if __name__ == "__main__":
    main()
