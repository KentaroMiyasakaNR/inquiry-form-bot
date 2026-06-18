import sys
import os

import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from form_analyzer import analyze_form
from draft_generator import generate_draft


def _find_value(draft: dict, field: dict) -> str | None:
    """ラベル・name・placeholderを部分一致でdraftから値を探す。"""
    candidates = [
        field.get("label", ""),
        field.get("name", ""),
        field.get("placeholder", ""),
    ]
    for draft_key, draft_val in draft.items():
        if not draft_val:
            continue
        for cand in candidates:
            if not cand:
                continue
            # 完全一致 または どちらかが相手を含む
            if cand == draft_key or cand in draft_key or draft_key in cand:
                return str(draft_val)
    return None


def _build_selector(field: dict) -> str | None:
    """name → id → placeholder の順でselectorを組み立てる。"""
    if field.get("name"):
        return f"[name='{field['name']}']"
    # selectorがNoneの場合、idで試みる
    inp_id = None
    # fieldにidが保存されていないため、labelのfor属性から類推できないが
    # placeholder で代替する
    if field.get("placeholder"):
        return f"[placeholder='{field['placeholder']}']"
    return None


def _fill_element(el, field_type: str, value: str) -> str:
    """要素の種類に応じて適切な入力メソッドを使う。✅/❌ を返す。"""
    tag = el.evaluate("el => el.tagName.toLowerCase()")
    if tag == "select":
        try:
            el.select_option(value=value)
            return "select_value"
        except Exception:
            try:
                el.select_option(label=value)
                return "select_label"
            except Exception:
                return "select_failed"
    else:
        el.fill(value)
        return "fill"


def _run_fill(form_url: str, fields: list[dict], draft: dict) -> dict:
    """フォームを開いて入力する。ブラウザは別スレッドで10分間開いたままにする。"""
    import threading
    from playwright.sync_api import sync_playwright

    log = []
    result: dict = {"success": False, "filled": 0, "log": log, "error": ""}

    def _worker():
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                page.goto(form_url, wait_until="networkidle", timeout=30000)

                skip_types = {"hidden", "submit", "button", "image", "checkbox", "radio", "file"}
                filled = 0

                for field in fields:
                    if field.get("type") in skip_types:
                        continue

                    selector = _build_selector(field)
                    label_str = field.get("label") or field.get("name") or field.get("placeholder") or "(不明)"

                    if not selector:
                        log.append(f"⚠️ selector なし: {label_str}")
                        continue

                    value = _find_value(draft, field)
                    if not value:
                        log.append(f"⚠️ draft に対応値なし: {label_str}")
                        continue

                    try:
                        el = page.query_selector(selector)
                        if el:
                            method = _fill_element(el, field.get("type", ""), value)
                            if "failed" not in method:
                                filled += 1
                                log.append(f"✅ 入力 ({method}): {label_str} = {value[:30]}")
                            else:
                                log.append(f"❌ 選択肢が一致しない: {label_str} = {value[:30]}")
                        else:
                            log.append(f"❌ 要素が見つからない: {label_str} ({selector})")
                    except Exception as e:
                        log.append(f"❌ 入力エラー: {label_str} — {str(e).split('Call log')[0].strip()}")

                result["filled"] = filled
                result["success"] = True

                # ブラウザを10分間開いたまま保持（ユーザーが確認・送信できる）
                page.wait_for_timeout(600_000)
                browser.close()

        except Exception as e:
            result["error"] = str(e)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout=30)  # 入力完了まで最大30秒待つ（その後はバックグラウンドで動き続ける）

    return result


# ──────────────────────────────────────────────
# ページ設定
# ──────────────────────────────────────────────
st.set_page_config(page_title="問い合わせアシスタント", page_icon="📧", layout="centered")

st.title("📧 問い合わせ自動下書きアシスタント")
st.caption("企業サイトのURLを入力するだけで、問い合わせ文を自動生成します")

# ──────────────────────────────────────────────
# 入力フォーム
# ──────────────────────────────────────────────
with st.form("input_form"):
    url = st.text_input(
        "企業サイトURL",
        placeholder="https://example.com  （トップページでもお問い合わせページでもOK）",
    )
    purpose = st.text_area(
        "問い合わせの目的",
        placeholder="例：感染管理VR研修の無料トライアルについて相談したい。病院規模は約100床。",
        height=100,
    )

    st.markdown("**送信者情報**")
    col1, col2 = st.columns(2)
    with col1:
        company = st.text_input("会社名 / 施設名")
        name = st.text_input("担当者名")
    with col2:
        email = st.text_input("メールアドレス")
        phone = st.text_input("電話番号")

    submitted = st.form_submit_button(
        "🚀 フォーム解析 → 下書き生成", use_container_width=True, type="primary"
    )

# ──────────────────────────────────────────────
# 実行
# ──────────────────────────────────────────────
if submitted:
    if not url or not purpose:
        st.error("URLと問い合わせ目的を入力してください")
        st.stop()

    sender_info = {
        "会社名": company,
        "担当者名": name,
        "メールアドレス": email,
        "電話番号": phone,
    }

    with st.spinner("🔍 ページを開いて問い合わせフォームを探しています..."):
        try:
            fields, form_url, nav_status = analyze_form(url)
        except Exception as e:
            st.error(f"フォーム解析エラー: {e}")
            st.stop()

    skip_types = {"hidden", "submit", "button", "image"}
    visible = [f for f in fields if f["type"] not in skip_types]

    # ナビゲーション結果を表示
    if nav_status.startswith("✅"):
        st.success(nav_status)
    elif nav_status.startswith("⚠️"):
        st.warning(nav_status)
    else:
        st.error(nav_status)

    if not visible:
        st.warning("フォームのフィールドが見つかりませんでした。URLを確認してください。")
        st.stop()

    st.info(f"{len(visible)} 個のフィールドを検出")

    with st.expander("検出されたフィールド一覧"):
        for f in visible:
            label = f["label"] or f["name"] or f["placeholder"] or "(不明)"
            badge = "🔴 必須" if f["required"] else "⚪ 任意"
            st.write(f"{badge} **{label}** `{f['type']}`")

    with st.spinner("🤖 qwen2.5:7b で下書きを生成中（30秒ほどかかります）..."):
        try:
            draft = generate_draft(fields, purpose, sender_info)
        except Exception as e:
            st.error(f"下書き生成エラー: {e}")
            st.stop()

    st.session_state["fields"] = fields
    st.session_state["form_url"] = form_url
    st.session_state["draft"] = draft

# ──────────────────────────────────────────────
# 下書き表示・編集
# ──────────────────────────────────────────────
if "draft" in st.session_state:
    st.divider()
    st.subheader("📝 生成された下書き（編集できます）")

    draft = st.session_state["draft"]
    edited: dict = {}

    if "raw_response" in draft:
        edited["raw_response"] = st.text_area(
            "生成結果（JSON解析失敗 — 手動でコピーしてください）",
            draft["raw_response"],
            height=250,
        )
    else:
        for key, value in draft.items():
            height = 150 if len(str(value)) > 80 else 70
            edited[key] = st.text_area(key, str(value), height=height)

    st.divider()
    st.subheader("🖥️ フォームへの自動入力")
    st.info("ボタンを押すとブラウザが起動してフォームに自動入力します（**送信はしません**）")

    if st.button("ブラウザを開いて自動入力する", use_container_width=True):
        with st.spinner("ブラウザを起動中..."):
            result = _run_fill(
                st.session_state["form_url"],
                st.session_state["fields"],
                edited,
            )
        if result["success"]:
            if result["filled"] > 0:
                st.success(f"✅ {result['filled']} フィールドへの入力が完了しました（ブラウザを確認・送信してください）")
            else:
                st.warning("⚠️ 入力できたフィールドが0件でした。下のログを確認してください。")
        else:
            st.error(f"エラー: {result['error']}")

        if result.get("log"):
            with st.expander("入力ログ（デバッグ）", expanded=result["filled"] == 0):
                for line in result["log"]:
                    st.write(line)
