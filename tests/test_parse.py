# -*- coding: utf-8 -*-
"""Test bóc tách logic với HTML giả lập mô phỏng cấu trúc trang thật."""
import json
from crawl_monngonmoingay import parse_listing_page, parse_recipe_page

LISTING_HTML = """
<html><body>
<div class="grid">
  <div class="recipe-card">
    <a href="/thit-bo-xao-dau-rong-sa-te/">
      <img src="/wp-content/uploads/2026/09/Thit-Bo.png" alt="thumb">
    </a>
    <h3><a href="/thit-bo-xao-dau-rong-sa-te/">Thịt Bò Xào Đậu Rồng Sa Tế</a></h3>
    <div class="meta">4 Người</div>
    <div class="diff"><img alt="Dễ" src="chef-hat.svg"> Dễ</div>
    <div class="time">10 Phút</div>
  </div>
  <div class="recipe-card">
    <a href="/gyoza-chien-gion/">
      <img src="/wp-content/uploads/2026/09/Gyoza.png" alt="thumb">
    </a>
    <h3><a href="/gyoza-chien-gion/">Gyoza Chiên Giòn</a></h3>
    <div class="meta">4 Người</div>
    <div class="diff"><img alt="Dễ" src="chef-hat.svg"> Dễ</div>
    <div class="time">10 Phút</div>
  </div>
</div>
</body></html>
"""

RECIPE_HTML = """
<html><head>
<meta property="og:title" content="Thịt Bò Xào Đậu Rồng Sa Tế - Món Ngon Mỗi Ngày">
<meta property="og:image" content="https://monngonmoingay.com/wp-content/uploads/2026/09/Thit-Bo.png">
<meta name="description" content="Món ăn ngon dễ làm.">
</head>
<body>
<h1>Thịt Bò Xào Đậu Rồng Sa Tế Chef Recommend</h1>

<h2 id="section-nguyenlieu">Nguyên Liệu:</h2>
<ul>
  <li>Muỗng</li>
  <li>Gram</li>
  <li>Thịt bò 200g</li>
  <li>Đậu rồng 250g</li>
  <li>Cà rốt 50g</li>
  <li>Tỏi băm</li>
  <li>Ngò rí</li>
  <li>Gia vị: Nước tương "Phú Sĩ", dầu ăn, tiêu, sa tế, Bột ngọt AJI-NO-MOTO®</li>
  <li>Bông cải xanh <span>&#9;&#9;50g</span> <span>&#9;luộc chín, cắt hạt lựu</span></li>
  <li>Phomai mozzarella<span>&#9;&#9;32g</span> <span>&#9;Cắt que cỡ đầu đũa</span></li>
</ul>

<h2 id="section-soche">Sơ Chế:</h2>
<ul>
  <li>Đậu rồng tước bỏ phần xơ già, rửa sạch rồi cắt vát thành miếng vừa ăn.</li>
  <li>Thịt bò cắt lát mỏng, ướp cùng 1 muỗng cà phê Hạt nêm Aji-ngon.</li>
</ul>

<h2 id="section-thuchien">Thực Hiện:</h2>
<ul>
  <li>Phi thơm tỏi, cho thịt bò vào xào nhanh trên lửa lớn.</li>
  <li>Tiếp tục cho cà rốt và đậu rồng vào xào.</li>
</ul>

<h2 id="section-howtouse">Cách Dùng:</h2>
<ul><li>Cho thịt bò xào sa tế ra đĩa, trang trí thêm ngò rí.</li></ul>

<h2 id="section-tips">Mách Nhỏ:</h2>
<ul><li>Xào thịt bò trên lửa lớn trong thời gian ngắn.</li></ul>

<p>Khẩu Phần: 4 người</p>
<p>Thời gian thực hiện: 10 Phút</p>
<p>Độ khó: Dễ</p>

<h4>Được phát sóng trên:</h4>
<a href="/mon-a/">Món Á</a>
<a href="/mon-ngon-mien-bac/">Bắc</a>
<a href="/mon-man/">Món mặn</a>
</body></html>
"""

print("=== TEST parse_listing_page ===")
items = parse_listing_page(LISTING_HTML, "https://monngonmoingay.com/tim-kiem-mon-ngon/")
print(json.dumps(items, ensure_ascii=False, indent=2))
assert len(items) == 2, f"Kỳ vọng 2 items, được {len(items)}"
assert items[0]["name"] == "Thịt Bò Xào Đậu Rồng Sa Tế"
assert items[0]["servings_hint"] == "4"
assert items[0]["time_minutes_hint"] == "10"
assert items[0]["difficulty_hint"] == "Dễ"
assert items[0]["thumbnail_url"].startswith("https://monngonmoingay.com/")
print("OK: parse_listing_page\n")

print("=== TEST parse_recipe_page ===")
detail = parse_recipe_page(RECIPE_HTML, "https://monngonmoingay.com/thit-bo-xao-dau-rong-sa-te/")
print(json.dumps(detail, ensure_ascii=False, indent=2))

assert detail["name"] == "Thịt Bò Xào Đậu Rồng Sa Tế"
assert detail["image_url"] == "https://monngonmoingay.com/wp-content/uploads/2026/09/Thit-Bo.png"
assert detail["servings"] == 4
assert detail["time_minutes"] == 10
assert detail["difficulty"] == "Dễ"

ing_names = [i["name"] for i in detail["ingredients"]]
print("Ingredient names:", ing_names)
assert "Thịt bò" in ing_names
assert "Đậu rồng" in ing_names
assert "Tỏi băm" in ing_names  # không có số lượng, vẫn giữ lại

thit_bo = next(i for i in detail["ingredients"] if i["name"] == "Thịt bò")
assert thit_bo["amount"] == "200", thit_bo
assert thit_bo["unit"] == "g", thit_bo

# kiểm tra "Muỗng"/"Gram" (nhãn toggle) bị loại bỏ, không lẫn vào nguyên liệu
assert "Muỗng" not in ing_names
assert "Gram" not in ing_names

# kiểm tra "Gia vị: ..." được tách thành các nguyên liệu con
gia_vi_items = [i for i in detail["ingredients"] if i.get("group") == "Gia vị"]
print("Gia vị items:", [i["name"] for i in gia_vi_items])
assert len(gia_vi_items) >= 4

# kiểm tra case có tab/newline lẫn trong HTML + ghi chú sơ chế dính liền sau unit
bong_cai = next(i for i in detail["ingredients"] if "Bông cải xanh" in i["name"])
print("Bông cải xanh parsed:", bong_cai)
assert bong_cai["name"] == "Bông cải xanh", bong_cai
assert bong_cai["amount"] == "50", bong_cai
assert bong_cai["unit"] == "g", bong_cai
assert "\t" not in bong_cai["raw_text"], "Vẫn còn tab chưa được làm sạch!"
assert bong_cai["note"] == "luộc chín, cắt hạt lựu", bong_cai

phomai = next(i for i in detail["ingredients"] if "mozzarella" in i["name"])
print("Phomai mozzarella parsed:", phomai)
assert phomai["amount"] == "32", phomai
assert phomai["unit"] == "g", phomai
assert phomai["note"] == "Cắt que cỡ đầu đũa", phomai

assert len(detail["prep_steps"]) == 2
assert len(detail["cooking_steps"]) == 2
assert detail["tags"] == ["Món Á", "Bắc", "Món mặn"], detail["tags"]

print("\nOK: parse_recipe_page — TẤT CẢ ASSERTIONS PASS")
