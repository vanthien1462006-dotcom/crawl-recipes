# MonNgonMoiNgay Recipe Crawler

Crawler Python thu thập thông tin công thức từ [monngonmoingay.com](https://monngonmoingay.com/), hỗ trợ xuất dữ liệu JSON và CSV. Đây là dự án độc lập, không phải sản phẩm chính thức hay được Ajinomoto Việt Nam/monngonmoingay.com bảo trợ.

## Tính năng

- Quét trang danh mục và tải trang chi tiết công thức.
- Trích xuất tên, URL, ảnh, khẩu phần, thời gian, độ khó, nguyên liệu, các bước nấu, ghi chú và thẻ phân loại.
- Phân tích số lượng/đơn vị nguyên liệu khi có thể; giữ nguyên dòng nguyên liệu nếu không tách được.
- Kiểm tra `robots.txt`, đặt thời gian nghỉ giữa các request và thử lại khi có lỗi tạm thời.
- Lưu định kỳ, hỗ trợ tiếp tục crawl từ dữ liệu JSON đã có.

## Yêu cầu

- Python 3.9 trở lên.
- Kết nối Internet tới website nguồn.

## Cài đặt

Từ thư mục dự án, tạo và kích hoạt môi trường ảo, sau đó cài dependencies:

```powershell
# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Sử dụng

Nên bắt đầu với phạm vi nhỏ và kiểm tra file kết quả trước khi tăng số trang:

```bash
python crawl_monngonmoingay.py --max-pages 1 --delay 1.5
```

Ví dụ giới hạn tối đa 15 trang danh mục và 150 công thức chi tiết:

```bash
python crawl_monngonmoingay.py --max-pages 15 --max-recipes 150 --delay 1.5
```

Crawl một danh mục cụ thể:

```bash
python crawl_monngonmoingay.py --category-url "https://monngonmoingay.com/cac-mon-chay-ngon/" --max-pages 3 --delay 1.5
```

Tiếp tục từ những URL đã có trong `output/recipes.json`:

```bash
python crawl_monngonmoingay.py --max-pages 15 --resume --delay 1.5
```

`--resume` cần file JSON kết quả hiện có. Nếu không truyền `--output-dir`, các kết quả được ghi vào `output/`.

### Tham số

| Tham số | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `--max-pages N` | `3` | Số trang danh mục tối đa cần quét. |
| `--max-recipes N` | Không giới hạn | Giới hạn số URL công thức thu thập từ danh mục. |
| `--category-url URL` | Danh mục tổng | URL danh mục bắt đầu. Phân trang của danh mục cần tương thích với website. |
| `--delay SECONDS` | `1.5` | Thời gian nghỉ giữa các request; không nên đặt quá thấp. |
| `--output-dir DIR` | `output` | Thư mục lưu các file kết quả. |
| `--resume` | Tắt | Bỏ qua URL đã có trong `recipes.json`. |
| `--ignore-robots` | Tắt | Bỏ qua kiểm tra `robots.txt`; không khuyến khích sử dụng. |

## Kết quả

Sau khi chạy, thư mục output gồm:

- `recipes.json`: dữ liệu đầy đủ, mỗi công thức là một object; nguyên liệu là danh sách object.
- `recipes.csv`: một dòng mỗi công thức; các bước, nguyên liệu và thẻ được gộp thành chuỗi.
- `ingredients.csv`: một dòng mỗi nguyên liệu, kèm tên công thức, số lượng, đơn vị và ghi chú.

Một số trường số lượng hoặc đơn vị có thể là `null` khi trang nguồn không cung cấp thông tin đó. Kết quả crawl là bản trích xuất tự động và cần được kiểm tra trước khi dùng.

## Kiểm thử

Các bài kiểm tra hiện dùng HTML giả lập, không gửi request đến website:

```bash
python -m tests.test_parse
```

Đây là kiểm thử parser, không xác nhận rằng cấu trúc website trực tiếp vẫn còn tương thích. Hãy chạy giới hạn nhỏ và kiểm tra dữ liệu thực tế trước mỗi lần crawl quy mô lớn.

## Cấu trúc repository

```text
.
├── crawl_monngonmoingay.py   # CLI và logic crawl/parse
├── tests/
│   ├── __init__.py
│   └── test_parse.py         # Kiểm thử parser bằng HTML giả lập
├── output/
│   └── .gitkeep              # Giữ thư mục; dữ liệu crawl không commit
├── requirements.txt
├── .gitignore
├── LICENSE
└── README.md
```

File JSON/CSV tạo ra, môi trường ảo, cache Python và file tạm được loại khỏi Git theo `.gitignore`. Không commit dữ liệu thu thập được nếu chưa xác nhận quyền sử dụng và mục đích chia sẻ.

## Crawl có trách nhiệm và lưu ý pháp lý

- Trước khi crawl, hãy đọc điều khoản sử dụng và `robots.txt` hiện hành của website. Chỉ thu thập đường dẫn được cho phép; tùy chọn `--ignore-robots` không thay thế sự cho phép của chủ website.
- Giữ delay ở mức hợp lý, giảm phạm vi hoặc dừng nếu máy chủ phản hồi lỗi hay có dấu hiệu quá tải. Script không bảo đảm website sẽ luôn cho phép truy cập.
- Nội dung công thức, hình ảnh, nhãn hiệu và dữ liệu trên website thuộc quyền của chủ sở hữu tương ứng. Giấy phép MIT trong repository này **chỉ áp dụng cho mã nguồn do dự án cung cấp**, không cấp quyền với nội dung đã crawl hoặc website nguồn.
- Người sử dụng chịu trách nhiệm xác minh quyền, điều khoản và quy định pháp luật áp dụng trước khi lưu trữ, tái phân phối hoặc sử dụng dữ liệu, đặc biệt trong hoạt động thương mại.
- Phần mềm được cung cấp "nguyên trạng", không có bảo đảm về độ chính xác, tính liên tục hoặc sự phù hợp cho một mục đích cụ thể.

## Giấy phép

Mã nguồn dự án được cấp phép theo [MIT License](LICENSE). Giấy phép này không bao gồm nội dung bên thứ ba được lấy từ website nguồn.
