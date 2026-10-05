# Crawler công thức nấu ăn — monngonmoingay.com

Script Python để thu thập dữ liệu công thức nấu ăn từ trang
[monngonmoingay.com](https://monngonmoingay.com/): tên món, ảnh, khẩu phần,
thời gian nấu, độ khó, nguyên liệu (tên + số lượng + đơn vị), các bước
sơ chế/thực hiện/cách dùng/mách nhỏ, và thẻ phân loại.

## 1. Cài đặt

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Chạy thử (khuyến nghị luôn chạy thử trước với phạm vi nhỏ)

```bash
python crawl_monngonmoingay.py --max-pages 3 --delay 1.5
```

Lệnh trên sẽ quét 3 trang danh mục đầu tiên (mỗi trang ~12 công thức, tổng
~36 công thức), lưu kết quả vào thư mục `output/`:

- `output/recipes.json` — dữ liệu đầy đủ, có cấu trúc (nguyên liệu là mảng object).
- `output/recipes.csv` — 1 dòng/công thức, nguyên liệu gộp thành text dễ đọc.
- `output/ingredients.csv` — 1 dòng/nguyên liệu (recipe, tên nguyên liệu,
  số lượng, đơn vị) — dùng file này nếu bạn cần phân tích/đếm nguyên liệu.
- `output/image_urls.csv` — link ảnh của từng món (cột `stt`, `name`, `image_url`),
  xếp đúng thứ tự các món được crawl.

## 3. Chạy crawl toàn bộ ~2.500 công thức

```bash
python crawl_monngonmoingay.py --max-pages 212 --delay 1.5
```

Ước tính thời gian: ~2.500 công thức × (~2 request/công thức: trang danh mục
đã tính riêng + trang chi tiết) × 1.5s delay ≈ **1–1.5 giờ**, tuỳ tốc độ
mạng và độ ổn định của server. Bạn có thể:

- Tăng `--delay` nếu bị chặn/lỗi 429 nhiều.
- Dùng `--resume` để chạy lại từ chỗ dừng (script tự lưu tạm sau mỗi 10 công
  thức, không cần chạy lại từ đầu nếu bị ngắt giữa chừng):

```bash
python crawl_monngonmoingay.py --max-pages 212 --resume
```

## 4. Chỉ crawl 1 danh mục cụ thể

Ví dụ chỉ lấy "Món chay":

```bash
python crawl_monngonmoingay.py --category-url "https://monngonmoingay.com/cac-mon-chay-ngon/" --max-pages 50
```

(Giả định trang danh mục con cũng hỗ trợ `.../page/2/`, `.../page/3/`...
giống trang tổng — cần bạn kiểm tra thực tế, script sẽ tự dừng nếu 1 trang
không trả về công thức nào.)

## 5. Cấu trúc dữ liệu ngõ ra (JSON)

```json
{
  "url": "https://monngonmoingay.com/thit-bo-xao-dau-rong-sa-te/",
  "name": "Thịt Bò Xào Đậu Rồng Sa Tế",
  "image_url": "https://monngonmoingay.com/wp-content/uploads/.../Thit-Bo.png",
  "description": "...",
  "servings": 4,
  "time_minutes": 10,
  "difficulty": "Dễ",
  "ingredients": [
    {"name": "Thịt bò", "amount": "200", "unit": "g", "raw_text": "Thịt bò 200g", "group": null},
    {"name": "Tỏi băm", "amount": null, "unit": null, "raw_text": "Tỏi băm", "group": null},
    {"name": "dầu ăn", "amount": null, "unit": null, "raw_text": "dầu ăn", "group": "Gia vị"}
  ],
  "prep_steps": ["..."],
  "cooking_steps": ["..."],
  "usage_notes": ["..."],
  "tips": ["..."],
  "tags": ["Món Á", "Bắc", "Món mặn"]
}
```

Lưu ý: nguyên liệu không ghi số lượng cụ thể trên trang gốc (ví dụ "Tỏi băm",
"Ngò rí", hoặc các nguyên liệu trong nhóm "Gia vị: ...") sẽ có
`amount = null, unit = null` — đây là đúng với dữ liệu gốc, không phải lỗi
crawl.

## 6. Giới hạn / điều cần biết

- **Chưa test trực tiếp trên site thật**: môi trường viết script này không
  có quyền truy cập mạng ra `monngonmoingay.com`, nên logic được kiểm chứng
  bằng HTML giả lập mô phỏng đúng cấu trúc đã quan sát (qua công cụ fetch
  trang thật) — không phải chạy trực tiếp. **Bạn cần chạy `--max-pages 1`
  trước tiên và mở `output/recipes.json` kiểm tra vài công thức đầu** để
  chắc chắn selector còn khớp với HTML thực tế trước khi crawl số lượng lớn.
- Script tôn trọng `robots.txt` của site (tự kiểm tra trước khi chạy).
- Có delay + retry + backoff để hạn chế gây tải cho server / bị chặn IP.
  Đừng hạ `--delay` xuống quá thấp.
- Chỉ nên dùng dữ liệu cho mục đích cá nhân, học tập, phi thương mại — tôn
  trọng bản quyền nội dung thuộc Ajinomoto Việt Nam / monngonmoingay.com.
- Nếu site đổi giao diện, các hàm `parse_listing_page()` và
  `parse_recipe_page()` trong `crawl_monngonmoingay.py` là nơi cần sửa
  (mỗi bước đều có comment giải thích logic).

## 7. Nếu selector bị sai khi chạy thật

Mở 1 trang công thức bất kỳ bằng trình duyệt, "View Page Source" (không phải
Inspect, để tránh xem DOM đã bị JS chỉnh sửa), tìm đoạn HTML quanh mục
"Nguyên Liệu" và gửi lại đoạn đó — tôi có thể chỉnh selector chính xác theo
HTML thật.
