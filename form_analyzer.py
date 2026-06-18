from playwright.sync_api import sync_playwright, Page

# リンクテキスト・URL で問い合わせページを示すキーワード
CONTACT_LINK_KEYWORDS = [
    "お問い合わせ", "問い合わせ", "お問合せ", "問合せ",
    "contact", "inquiry", "ご連絡", "資料請求", "お申し込み",
]

# 問い合わせページであることを示すURL・見出しのキーワード
CONTACT_PAGE_KEYWORDS = [
    "contact", "inquiry", "inquire", "form", "お問い合わせ", "問い合わせ",
    "お問合せ", "問合せ", "資料請求", "お申し込み",
]


def _is_contact_page(page: Page) -> bool:
    """URLと見出しから、問い合わせページかどうかを判定する。"""
    url_lower = page.url.lower()
    if any(kw in url_lower for kw in CONTACT_PAGE_KEYWORDS):
        return True

    # h1/h2 の見出しテキストを確認
    for tag in ["h1", "h2"]:
        els = page.query_selector_all(tag)
        for el in els:
            text = (el.inner_text() or "").strip()
            if any(kw in text for kw in CONTACT_PAGE_KEYWORDS):
                return True

    return False


def _has_form(page: Page) -> bool:
    """ページに入力フォームがあるか確認する。"""
    return page.query_selector("input:not([type='hidden']), textarea") is not None


def _score_link(text: str, href: str) -> int:
    """問い合わせリンクらしさをスコアリングする（高いほど優先）。"""
    score = 0
    text_lower = text.lower()
    href_lower = href.lower()
    for kw in CONTACT_LINK_KEYWORDS:
        if kw in text_lower:
            score += 2
        if kw in href_lower:
            score += 1
    return score


def find_contact_url(page: Page) -> str | None:
    """現在のページから問い合わせリンクを探してURLを返す。見つからなければNone。"""
    candidates = []
    for a in page.query_selector_all("a"):
        text = (a.inner_text() or "").strip()
        href = a.get_attribute("href") or ""
        if not href or href.startswith("mailto:") or href.startswith("tel:") or href.startswith("#"):
            continue
        score = _score_link(text, href)
        if score > 0:
            try:
                abs_url = page.evaluate(f"() => new URL({repr(href)}, location.href).href")
                candidates.append((score, abs_url))
            except Exception:
                pass

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def navigate_to_form(url: str, page: Page) -> tuple[str, str]:
    """
    指定URLを開き、問い合わせフォームページへナビゲートする。
    戻り値: (到達したURL, ステータスメッセージ)
    """
    page.goto(url, wait_until="networkidle", timeout=30000)

    # すでに問い合わせページ＆フォームあり → そのまま
    if _is_contact_page(page) and _has_form(page):
        return page.url, f"✅ 指定URLが問い合わせページです: {page.url}"

    # フォームはあるが問い合わせページか不明
    if _has_form(page) and not _is_contact_page(page):
        # 一応リンクも探して、より確実な問い合わせページがあれば移動
        contact_url = find_contact_url(page)
        if contact_url:
            page.goto(contact_url, wait_until="networkidle", timeout=30000)
            if _is_contact_page(page) and _has_form(page):
                return page.url, f"✅ 問い合わせページに移動しました: {page.url}"
        # 移動しても改善しなければ元のページのフォームを使う
        return page.url, f"⚠️ フォームは見つかりましたが問い合わせページか不明です: {page.url}"

    # フォームなし → リンクを探して移動
    contact_url = find_contact_url(page)
    if not contact_url:
        return page.url, f"❌ 問い合わせリンクが見つかりませんでした: {page.url}"

    page.goto(contact_url, wait_until="networkidle", timeout=30000)

    if _is_contact_page(page) and _has_form(page):
        return page.url, f"✅ 問い合わせページに移動しました: {page.url}"

    # もう一段階探す
    if not _has_form(page):
        contact_url2 = find_contact_url(page)
        if contact_url2 and contact_url2 != contact_url:
            page.goto(contact_url2, wait_until="networkidle", timeout=30000)

    if _has_form(page):
        label = "✅" if _is_contact_page(page) else "⚠️ フォームあり（問い合わせページか不明）"
        return page.url, f"{label}: {page.url}"

    return page.url, f"❌ フォームが見つかりませんでした。到達ページ: {page.url}"


def extract_fields(page: Page) -> list[dict]:
    """現在のページからフォームフィールドを抽出する。"""
    inputs = page.query_selector_all(
        "input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='image']), textarea, select"
    )

    fields = []
    for inp in inputs:
        tag = inp.evaluate("el => el.tagName.toLowerCase()")
        field_type = inp.get_attribute("type") or tag
        name = inp.get_attribute("name") or inp.get_attribute("id") or ""
        placeholder = inp.get_attribute("placeholder") or ""
        required = inp.get_attribute("required") is not None

        label = ""
        input_id = inp.get_attribute("id")
        if input_id:
            label_el = page.query_selector(f"label[for='{input_id}']")
            if label_el:
                label = label_el.inner_text().strip()

        if not label:
            label = inp.evaluate("""el => {
                const parentLabel = el.closest('label');
                if (parentLabel) return parentLabel.innerText.replace(el.value, '').trim();
                const prev = el.previousElementSibling;
                if (prev && prev.tagName === 'LABEL') return prev.innerText.trim();
                const parent = el.parentElement;
                if (parent) {
                    const prevSib = parent.previousElementSibling;
                    if (prevSib) return prevSib.innerText.trim().split('\\n')[0];
                }
                return '';
            }""")

        inp_id = inp.get_attribute("id") or ""
        if name:
            selector = f"[name='{name}']"
        elif inp_id:
            selector = f"#{inp_id}"
        elif placeholder:
            selector = f"[placeholder='{placeholder}']"
        else:
            selector = None

        fields.append({
            "type": field_type,
            "name": name,
            "id": inp_id,
            "label": label,
            "placeholder": placeholder,
            "required": required,
            "selector": selector,
        })

    return fields


def analyze_form(url: str) -> tuple[list[dict], str, str]:
    """
    URLからフォームを解析する。企業サイトのトップページでもOK。
    戻り値: (フィールドリスト, 実際のフォームURL, ステータスメッセージ)
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        form_url, status = navigate_to_form(url, page)
        fields = extract_fields(page)

        browser.close()
        return fields, form_url, status
