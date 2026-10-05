#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crawler thu thập dữ liệu công thức nấu ăn từ monngonmoingay.com

Thu thập: tên công thức, ảnh món ăn, khẩu phần, thời gian nấu, độ khó,
nguyên liệu (tên + số lượng + đơn vị), các bước sơ chế/thực hiện, mách nhỏ,
và các thẻ phân loại (vùng miền, bữa ăn, cách nấu...).

CÁCH DÙNG NHANH (chạy thử với phạm vi nhỏ):
    pip install -r requirements.txt
    python crawl_monngonmoingay.py --max-pages 3 --delay 1.5

CÁC THAM SỐ CHÍNH:
    --max-pages N        Số trang danh mục tối đa sẽ quét (mỗi trang ~12 công thức).
                          Mặc định: 3 (dùng để test).
    --max-recipes N       Giới hạn tổng số công thức chi tiết sẽ crawl (dừng sớm
                          nếu đạt số này, dù --max-pages chưa hết). None = không giới hạn.
    --category-url URL   URL trang danh mục để bắt đầu quét thay vì trang tổng
                          "tim-kiem-mon-ngon" (ví dụ trang "Món chay",
                          "Món Á"...). Trang danh mục PHẢI hỗ trợ dạng phân
                          trang .../page/2/, .../page/3/... giống trang gốc.
    --delay SECONDS       Thời gian nghỉ giữa các request (mặc định 1.5s) để
                          lịch sự với server, tránh bị chặn IP.
    --output-dir DIR      Thư mục lưu kết quả (mặc định ./output).
    --resume              Bỏ qua các công thức đã có trong file JSON cũ (nếu có)
                          thay vì crawl lại từ đầu.

LƯU Ý QUAN TRỌNG:
- Script được viết dựa trên việc phân tích cấu trúc trang thực tế (tháng 9/2026).
  Nếu website đổi giao diện/HTML, một số selector có thể cần điều chỉnh
  (xem các hàm parse_listing_page / parse_recipe_page bên dưới, có comment rõ).
- Script tự đọc /robots.txt của site trước khi chạy và sẽ DỪNG nếu đường dẫn
  bị Disallow, trừ khi bạn chạy với --ignore-robots (không khuyến khích).
- Chỉ nên dùng dữ liệu thu thập được cho mục đích cá nhân/phi thương mại,
  tôn trọng bản quyền nội dung của Ajinomoto Việt Nam / monngonmoingay.com.
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://monngonmoingay.com"
DEFAULT_CATEGORY_URL = f"{BASE_URL}/tim-kiem-mon-ngon/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
    "MonNgonMoiNgayResearchCrawler/1.0 (+contact: dat cua ban)"
)

# Các đơn vị thường gặp trong nguyên liệu Việt Nam, dùng để tách số lượng/đơn vị.
KNOWN_UNITS = [
    "muỗng canh", "muỗng cà phê", "muỗng cafe", "muỗng", "m.canh", "m.cf",
    "kg", "g", "gram", "ml", "lít", "l",
    "quả", "trái", "củ", "cây", "lá", "tép", "nhánh", "con",
    "miếng", "hộp", "gói", "chén", "tô", "ổ", "cái", "bó", "cm",
]
# Sắp theo độ dài giảm dần để regex khớp cụm dài trước (vd "muỗng canh" trước "muỗng")
KNOWN_UNITS.sort(key=len, reverse=True)
UNIT_PATTERN = "|".join(re.escape(u) for u in KNOWN_UNITS)

# Regex tách "Thịt bò 200g" -> name="Thịt bò", amount="200", unit="g"
# hoặc "Tỏi băm 1 muỗng cà phê" -> name="Tỏi băm", amount="1", unit="muỗng cà phê"
INGREDIENT_RE = re.compile(
    r"^(?P<name>.*?)\s*[:\-]?\s*"
    r"(?P<amount>\d+(?:[.,]\d+)?(?:\s*[-–~]\s*\d+(?:[.,]\d+)?)?(?:/\d+)?)"
    r"\s*(?P<unit>" + UNIT_PATTERN + r")?\s*$",
    re.IGNORECASE,
)


def make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    })
    return s


def check_robots_allowed(session, url):
    """Kiểm tra robots.txt trước khi crawl. Trả về True nếu được phép."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    try:
        resp = session.get(robots_url, timeout=15)
        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
        else:
            # Không có robots.txt -> coi như cho phép
            return True
    except requests.RequestException:
        print(f"[CẢNH BÁO] Không tải được robots.txt ({robots_url}), tiếp tục thận trọng.")
        return True
    return rp.can_fetch(USER_AGENT, url) or rp.can_fetch("*", url)


def fetch(session, url, delay, max_retries=3):
    """GET một URL với retry + delay lịch sự."""
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code == 200:
                time.sleep(delay)
                return resp.text
            elif resp.status_code == 404:
                print(f"  [404] {url}")
                return None
            else:
                print(f"  [HTTP {resp.status_code}] {url} (lần {attempt}/{max_retries})")
        except requests.RequestException as e:
            last_err = e
            print(f"  [Lỗi kết nối] {url}: {e} (lần {attempt}/{max_retries})")
        time.sleep(delay * attempt)  # backoff tăng dần
    if last_err:
        print(f"  [BỎ QUA sau {max_retries} lần thử] {url}")
    return None


def text_or_none(tag):
    return tag.get_text(strip=True) if tag else None


def parse_listing_page(html, page_url):
    """
    Parse 1 trang danh mục (dạng .../tim-kiem-mon-ngon/page/N/) và trả về
    danh sách dict thông tin sơ bộ mỗi công thức (đủ để tới bước crawl chi tiết).

    Chiến lược chọn phần tử: mỗi thẻ công thức có tiêu đề nằm trong <h3><a href=...>.
    Đây là cấu trúc ổn định quan sát được trên trang, độc lập với tên class CSS
    (vốn có thể đổi theo theme/deploy). Từ thẻ <h3> ta đi ngược lên container
    cha gần nhất có chứa <img> để lấy ảnh, số người ăn, thời gian, độ khó.
    """
    soup = BeautifulSoup(html, "lxml")
    results = []
    seen_urls = set()

    for h3 in soup.find_all("h3"):
        a = h3.find("a", href=True)
        if not a:
            continue
        href = urljoin(BASE_URL, a["href"])
        # chỉ nhận link công thức thật (1 segment path, cùng domain, không phải trang hệ thống)
        parsed = urlparse(href)
        if parsed.netloc and BASE_URL not in href:
            continue
        path = parsed.path.strip("/")
        if not path or "/" in path:
            continue
        if href in seen_urls:
            continue

        name = a.get_text(strip=True)
        if not name:
            continue

        # Tìm container cha chứa cả <img> lẫn text (đi tối đa 5 cấp lên)
        container = h3
        card = None
        node = h3
        for _ in range(5):
            node = node.parent
            if node is None:
                break
            if node.find("img"):
                card = node
                break
        if card is None:
            card = h3.parent or h3

        img_tag = card.find("img")
        image_url = None
        if img_tag:
            image_url = img_tag.get("src") or img_tag.get("data-src")
            if image_url:
                image_url = urljoin(BASE_URL, image_url)

        card_text = card.get_text(" ", strip=True)
        servings_m = re.search(r"(\d+)\s*Người", card_text, re.IGNORECASE)
        time_m = re.search(r"(\d+)\s*Phút", card_text, re.IGNORECASE)
        # icon độ khó thường có text đi kèm ngay sau: "Dễ" / "Trung bình" / "Khó"
        difficulty_m = re.search(r"\b(Dễ|Trung bình|Khó)\b", card_text)

        results.append({
            "url": href,
            "name": name,
            "thumbnail_url": image_url,
            "servings_hint": servings_m.group(1) if servings_m else None,
            "time_minutes_hint": time_m.group(1) if time_m else None,
            "difficulty_hint": difficulty_m.group(1) if difficulty_m else None,
        })
        seen_urls.add(href)

    return results


def get_total_pages(html):
    """Cố gắng đọc số trang cuối cùng từ khối phân trang. Trả về None nếu không rõ."""
    soup = BeautifulSoup(html, "lxml")
    max_page = 1
    for a in soup.find_all("a", href=True):
        m = re.search(r"/page/(\d+)/?", a["href"])
        if m:
            max_page = max(max_page, int(m.group(1)))
    return max_page


def parse_amount_unit(raw_text):
    """
    Tách 1 dòng nguyên liệu thô thành (name, amount, unit).
    Nếu không tách được số lượng/đơn vị, trả amount=unit=None và giữ nguyên name.
    """
    raw_text = raw_text.strip(" -\u2022\t")
    if not raw_text:
        return None
    m = INGREDIENT_RE.match(raw_text)
    if m and m.group("amount"):
        name = m.group("name").strip(" -,:")
        amount = m.group("amount").strip()
        unit = (m.group("unit") or "").strip()
        # nếu number dính liền đơn vị kiểu "200g" mà regex unit rỗng vì
        # unit không nằm trong KNOWN_UNITS (vd đơn vị lạ), thử tách hậu tố chữ
        if not unit:
            m2 = re.match(r"^([\d.,/\-–~ ]+)([A-Za-zÀ-ỹ]+)$", amount + "")
        return {
            "name": name if name else raw_text,
            "amount": amount if amount else None,
            "unit": unit if unit else None,
            "raw_text": raw_text,
        }
    return {"name": raw_text, "amount": None, "unit": None, "raw_text": raw_text}


def parse_recipe_page(html, url):
    """Parse trang chi tiết 1 công thức."""
    soup = BeautifulSoup(html, "lxml")
    data = {"url": url}

    # --- Tên công thức: ưu tiên meta og:title, fallback h1 ---
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        name = og_title["content"]
        name = re.sub(r"\s*-\s*Món Ngon Mỗi Ngày\s*$", "", name).strip()
    else:
        h1 = soup.find("h1")
        name = text_or_none(h1)
        if name:
            name = re.sub(r"\s*Chef Recommend\s*$", "", name).strip()
    data["name"] = name

    # --- Ảnh chính món ăn: meta og:image ---
    og_image = soup.find("meta", property="og:image")
    data["image_url"] = og_image["content"].strip() if og_image and og_image.get("content") else None

    # --- Mô tả ngắn (meta description) ---
    meta_desc = soup.find("meta", attrs={"name": "description"})
    data["description"] = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else None

    page_text = soup.get_text("\n", strip=True)

    # --- Khẩu phần / thời gian / độ khó ---
    servings_m = re.search(r"Khẩu\s*Phần:?\s*(\d+)\s*ngư[oờ]i", page_text, re.IGNORECASE)
    data["servings"] = int(servings_m.group(1)) if servings_m else None

    time_m = re.search(r"Thời\s*gian\s*thực\s*hiện:?\s*(\d+)\s*Phút", page_text, re.IGNORECASE)
    data["time_minutes"] = int(time_m.group(1)) if time_m else None

    diff_m = re.search(r"Độ\s*khó:?\s*(Dễ|Trung bình|Khó)", page_text, re.IGNORECASE)
    data["difficulty"] = diff_m.group(1) if diff_m else None

    # --- Nguyên liệu ---
    # Ưu tiên tìm theo id neo (id="section-nguyenlieu") quan sát được từ mục lục trang;
    # fallback: tìm heading có text chứa "Nguyên liệu".
    ingredients_container = soup.find(id="section-nguyenlieu")
    if ingredients_container is None:
        heading = soup.find(lambda t: t.name in ("h2", "h3") and t.get_text(strip=True).lower().startswith("nguyên liệu"))
        ingredients_container = heading.parent if heading else None

    ingredients = []
    if ingredients_container is not None:
        # Lấy tất cả <li> nằm trong container này (hoặc trong các <ul> ngay sau heading
        # cho tới khi gặp heading tiếp theo, tuỳ cấu trúc thực tế của trang).
        li_tags = ingredients_container.find_all("li")
        if not li_tags:
            # fallback: quét các <li> xuất hiện ngay sau heading "Nguyên liệu"
            heading = ingredients_container if ingredients_container.name in ("h2", "h3") else ingredients_container.find(["h2", "h3"])
            if heading:
                for sib in heading.find_all_next():
                    if sib.name in ("h2",):  # gặp heading lớn tiếp theo -> dừng
                        break
                    if sib.name == "li":
                        li_tags.append(sib)

        seen_raw = set()
        for li in li_tags:
            raw = li.get_text(" ", strip=True)
            if not raw or raw in seen_raw:
                continue
            seen_raw.add(raw)
            # bỏ qua nhãn điều khiển toggle đơn vị, không phải nguyên liệu thật
            if raw in ("Muỗng", "Gram") or raw.startswith("M: muỗng canh"):
                continue
            # dòng "Gia vị: A, B, C" -> tách thành các nguyên liệu con không định lượng
            gv_m = re.match(r"^Gia vị:?\s*(.+)$", raw, re.IGNORECASE)
            if gv_m:
                for part in gv_m.group(1).split(","):
                    part = part.strip(" .")
                    if part:
                        ingredients.append({
                            "name": part, "amount": None, "unit": None,
                            "raw_text": part, "group": "Gia vị",
                        })
                continue
            parsed_ing = parse_amount_unit(raw)
            if parsed_ing:
                parsed_ing["group"] = None
                ingredients.append(parsed_ing)

    # Loại trùng lặp hoàn toàn (trang có thể lặp lại 2 lần list cho 2 tab đơn vị
    # "Muỗng"/"Gram" khi nội dung 2 tab giống nhau)
    dedup = []
    seen_keys = set()
    for ing in ingredients:
        key = (ing["name"], ing["amount"], ing["unit"])
        if key not in seen_keys:
            seen_keys.add(key)
            dedup.append(ing)
    data["ingredients"] = dedup

    # --- Các bước: Sơ chế / Thực hiện / Cách dùng / Mách nhỏ ---
    def extract_steps(section_id, heading_text_startswith):
        """
        Lấy danh sách bước (li) hoặc đoạn văn (p) gắn với 1 mục (Sơ chế/Thực hiện/...).
        Xử lý cả 2 trường hợp cấu trúc HTML có thể gặp:
          (a) id nằm trên 1 <div>/<section> BAO NGOÀI toàn bộ nội dung mục đó
              -> tìm <li>/<p> bên trong (descendants).
          (b) id nằm trực tiếp trên thẻ heading (<h2 id="...">), nội dung
              (ul/li hoặc p) là các SIBLING đứng sau heading, không phải con
              -> phải duyệt find_all_next() tới khi gặp heading lớn tiếp theo.
        """
        anchor = soup.find(id=section_id)
        if anchor is None:
            anchor = soup.find(lambda t: t.name in ("h2", "h3") and t.get_text(strip=True).lower().startswith(heading_text_startswith.lower()))
        if anchor is None:
            return []

        # Trường hợp (a): anchor là container bao ngoài, thử tìm con trực tiếp trước
        if anchor.name not in ("h1", "h2", "h3", "h4"):
            lis = anchor.find_all("li")
            if lis:
                return [li.get_text(" ", strip=True) for li in lis if li.get_text(strip=True)]
            p = anchor.find("p")
            if p and p.get_text(strip=True):
                return [p.get_text(" ", strip=True)]
            # nếu container rỗng, coi anchor như 1 mốc và rơi xuống trường hợp (b)

        # Trường hợp (b): duyệt các phần tử tiếp theo tới khi gặp heading cấp cao hơn/bằng
        steps = []
        stop_level = int(anchor.name[1]) if anchor.name and anchor.name[0] == "h" and anchor.name[1].isdigit() else 2
        for el in anchor.find_all_next():
            if el.name and re.match(r"^h[1-6]$", el.name):
                el_level = int(el.name[1])
                if el_level <= stop_level:
                    break
            if el.name == "li":
                t = el.get_text(" ", strip=True)
                if t:
                    steps.append(t)
            elif el.name == "p" and not steps:
                t = el.get_text(" ", strip=True)
                if t:
                    steps.append(t)
        return steps

    data["prep_steps"] = extract_steps("section-soche", "Sơ chế")
    data["cooking_steps"] = extract_steps("section-thuchien", "Thực hiện")
    data["usage_notes"] = extract_steps("section-howtouse", "Cách dùng")
    data["tips"] = extract_steps("section-tips", "Mách nhỏ")

    # --- Thẻ phân loại (vùng miền, bữa ăn, cách nấu...) ở cuối trang ---
    tags = []
    tag_area = soup.find(lambda t: t.name == "h4" and "phát sóng" in t.get_text(strip=True).lower())
    if tag_area:
        # các thẻ tag thường là 1 dãy <a> ngay sau khu vực lịch phát sóng
        for a in tag_area.find_all_next("a", href=True, limit=25):
            t = a.get_text(strip=True)
            if t and len(t) < 40 and not t.startswith("Xem"):
                tags.append(t)
            if a.get_text(strip=True).lower() in ("về mnmn",):
                break
    data["tags"] = tags

    return data


def load_existing(output_json_path):
    if output_json_path.exists():
        try:
            with open(output_json_path, "r", encoding="utf-8") as f:
                return {r["url"]: r for r in json.load(f)}
        except (json.JSONDecodeError, KeyError):
            return {}
    return {}


def save_outputs(records, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "recipes.json"
    csv_path = output_dir / "recipes.csv"
    ingredients_csv_path = output_dir / "ingredients.csv"
    images_csv_path = output_dir / "image_urls.csv"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    # CSV cấp công thức (1 dòng / công thức, nguyên liệu gộp thành text)
    fieldnames = [
        "url", "name", "image_url", "servings", "time_minutes", "difficulty",
        "description", "ingredients_summary", "num_ingredients",
        "prep_steps", "cooking_steps", "usage_notes", "tips", "tags",
    ]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            ing_summary = "; ".join(
                f"{i['name']} {i['amount'] or ''}{i['unit'] or ''}".strip()
                for i in r.get("ingredients", [])
            )
            writer.writerow({
                "url": r.get("url"),
                "name": r.get("name"),
                "image_url": r.get("image_url"),
                "servings": r.get("servings"),
                "time_minutes": r.get("time_minutes"),
                "difficulty": r.get("difficulty"),
                "description": r.get("description"),
                "ingredients_summary": ing_summary,
                "num_ingredients": len(r.get("ingredients", [])),
                "prep_steps": " | ".join(r.get("prep_steps", [])),
                "cooking_steps": " | ".join(r.get("cooking_steps", [])),
                "usage_notes": " | ".join(r.get("usage_notes", [])),
                "tips": " | ".join(r.get("tips", [])),
                "tags": ", ".join(r.get("tags", [])),
            })

    # CSV cấp nguyên liệu (1 dòng / nguyên liệu) -- dễ phân tích/định lượng nhất
    with open(ingredients_csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["recipe_name", "recipe_url", "ingredient_name", "amount", "unit", "group", "raw_text"])
        for r in records:
            for ing in r.get("ingredients", []):
                writer.writerow([
                    r.get("name"), r.get("url"),
                    ing.get("name"), ing.get("amount"), ing.get("unit"),
                    ing.get("group"), ing.get("raw_text"),
                ])

    # CSV link ảnh (1 dòng / công thức, đúng thứ tự crawl)
    with open(images_csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["stt", "name", "image_url"])
        for idx, r in enumerate(records, start=1):
            writer.writerow([idx, r.get("name"), r.get("image_url")])

    print(f"\nĐã lưu:\n  - {json_path}\n  - {csv_path}\n  - {ingredients_csv_path}\n  - {images_csv_path}")


def main():
    ap = argparse.ArgumentParser(description="Crawl công thức nấu ăn từ monngonmoingay.com")
    ap.add_argument("--max-pages", type=int, default=3, help="Số trang danh mục tối đa (mặc định 3, để test)")
    ap.add_argument("--max-recipes", type=int, default=None, help="Giới hạn tổng số công thức crawl chi tiết")
    ap.add_argument("--category-url", type=str, default=DEFAULT_CATEGORY_URL, help="URL trang danh mục bắt đầu")
    ap.add_argument("--delay", type=float, default=1.5, help="Giây nghỉ giữa các request")
    ap.add_argument("--output-dir", type=str, default="output", help="Thư mục lưu kết quả")
    ap.add_argument("--resume", action="store_true", help="Bỏ qua công thức đã có trong recipes.json cũ")
    ap.add_argument("--ignore-robots", action="store_true", help="Bỏ qua kiểm tra robots.txt (không khuyến khích)")
    args = ap.parse_args()

    session = make_session()
    output_dir = Path(args.output_dir)

    if not args.ignore_robots:
        allowed = check_robots_allowed(session, args.category_url)
        if not allowed:
            print("robots.txt của site KHÔNG cho phép crawl đường dẫn này. Dừng lại.")
            print("(Chạy với --ignore-robots nếu bạn chắc chắn muốn bỏ qua — không khuyến khích.)")
            sys.exit(1)

    existing = {}
    if args.resume:
        existing = load_existing(output_dir / "recipes.json")
        print(f"[Resume] Đã có {len(existing)} công thức từ lần chạy trước, sẽ bỏ qua các URL này.")

    # 1) Thu thập danh sách URL công thức từ các trang danh mục
    print(f"== Bước 1: Quét danh sách công thức từ {args.category_url} ==")
    all_listing_items = []
    seen_recipe_urls = set()

    page = 1
    while page <= args.max_pages:
        page_url = args.category_url if page == 1 else urljoin(args.category_url, f"page/{page}/")
        print(f"[Trang {page}] {page_url}")
        html = fetch(session, page_url, args.delay)
        if html is None:
            print("  Không tải được trang, dừng quét danh mục.")
            break

        items = parse_listing_page(html, page_url)
        if not items:
            print("  Không tìm thấy công thức nào trên trang này, dừng.")
            break

        new_count = 0
        for it in items:
            if it["url"] not in seen_recipe_urls:
                seen_recipe_urls.add(it["url"])
                all_listing_items.append(it)
                new_count += 1
        print(f"  -> tìm thấy {len(items)} thẻ công thức ({new_count} mới).")

        if args.max_recipes and len(all_listing_items) >= args.max_recipes:
            all_listing_items = all_listing_items[: args.max_recipes]
            break

        page += 1

    print(f"\nTổng cộng thu thập được {len(all_listing_items)} URL công thức để crawl chi tiết.\n")

    # 2) Crawl chi tiết từng công thức
    print("== Bước 2: Crawl chi tiết từng công thức ==")
    records = list(existing.values())
    for idx, item in enumerate(all_listing_items, 1):
        url = item["url"]
        if url in existing:
            print(f"[{idx}/{len(all_listing_items)}] (đã có, bỏ qua) {url}")
            continue

        print(f"[{idx}/{len(all_listing_items)}] {url}")
        html = fetch(session, url, args.delay)
        if html is None:
            continue
        try:
            detail = parse_recipe_page(html, url)
        except Exception as e:
            print(f"  [Lỗi parse] {url}: {e}")
            continue

        # dùng thông tin từ trang danh mục làm fallback nếu trang chi tiết thiếu
        if not detail.get("image_url"):
            detail["image_url"] = item.get("thumbnail_url")
        if not detail.get("servings") and item.get("servings_hint"):
            detail["servings"] = int(item["servings_hint"])
        if not detail.get("time_minutes") and item.get("time_minutes_hint"):
            detail["time_minutes"] = int(item["time_minutes_hint"])
        if not detail.get("difficulty") and item.get("difficulty_hint"):
            detail["difficulty"] = item["difficulty_hint"]

        records.append(detail)
        n_ing = len(detail.get("ingredients", []))
        print(f"   -> '{detail.get('name')}' | {n_ing} nguyên liệu | ảnh: {'có' if detail.get('image_url') else 'không'}")

        # lưu tăng dần mỗi 10 công thức để tránh mất dữ liệu nếu script bị dừng giữa chừng
        if idx % 10 == 0:
            save_outputs(records, output_dir)

    save_outputs(records, output_dir)
    print(f"\nHoàn tất. Tổng số công thức đã crawl: {len(records)}")


if __name__ == "__main__":
    main()
