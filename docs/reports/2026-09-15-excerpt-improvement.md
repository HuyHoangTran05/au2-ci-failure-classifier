# Báo cáo: cải thiện bước cắt log

- **Ngày:** 15/09/2026
- **Dự án:** AU2 - phân loại lỗi CI
- **Phạm vi:** Bước 4 - đo chất lượng đoạn cắt, thử 3 chiến lược cắt log mới, đo ảnh hưởng tới bộ phân loại
- **Commit liên quan:** `62ec124` (đo lường), `be92bac` (profile + hints), `09f9576`, `6c18fa9`, `d83a3b8` (baseline-diff),
  `4b30077`, `0e87f72` (công cụ so sánh), `9cd10e8` (kết quả)
- **Báo cáo gốc:** `results/20260915-105944-github-actions/`, `results/20260915-105957-wide80-github-actions/`,
  `results/20260915-110011-diff-github-actions/`

## Tóm tắt

- **Cách đo cũ bị sai:** chất lượng đoạn cắt thật là **56%** đoạn lỗi được giữ trọn, không phải 41%.
  Lỗi nằm ở cách so khớp văn bản LogChunks, không phải ở đoạn cắt.
- **Nguyên nhân bỏ sót chính:** đoạn lỗi nằm **cách dấu lỗi hơn 40 dòng** (173/797 mẫu).
- **Chiến lược "hints"** (chọn cụm dòng có từ khóa lỗi): **kém hơn** cách cũ ở cùng kích thước (52% so với 56%). Kết quả âm tính.
- **Cửa sổ rộng 80 dòng:** giữ trọn đoạn lỗi tăng lên 62–66%, nhưng đoạn cắt dài gấp đôi.
- **So với run thành công (`diff`):** trên 62 mẫu GitHub Actions, LLM đạt **0.74** so với 0.69 của cách cũ,
  với **ít hơn 30% số dòng**. Tuy vậy mức cải thiện **chưa có ý nghĩa thống kê** (p = 0.58).
- **Khuyến nghị:** giữ cách cắt mặc định; tiếp tục thu thập thêm log GitHub Actions để kiểm chứng `diff`.

---

## 1. Đo chất lượng đoạn cắt (`excerpt-eval`)

### Vì sao cần

Cả 3 bộ phân loại chỉ nhìn thấy đoạn cắt. Đoạn cắt bỏ sót nguyên nhân thì không phương pháp nào đoán đúng được.
LogChunks có **đoạn lỗi do con người đánh dấu** cho 797 log, nên dùng làm "đáp án" để đo đoạn cắt giữ được bao nhiêu.

### Phát hiện: cách đo cũ sai

Phân tích 149 mẫu "không tìm thấy đoạn lỗi trong log gốc" cho thấy văn bản đoạn lỗi của LogChunks đã bị hỏng:
mất ký tự `<` (`Promisevoid>` thay vì `Promise<void>`) và còn sót mã màu mất ký tự ESC (`[31m`).
Sau khi chuẩn hoá cả hai phía (commit `62ec124`), **đoạn cắt không đổi** nhưng kết quả đo thay đổi:

| | Trước khi sửa cách đo | Sau khi sửa |
| --- | --- | --- |
| Giữ trọn đoạn lỗi | 329/797 (41%) | **446/797 (56%)** |
| Độ phủ dòng trung bình | 55% | 68% |

### Lý do bỏ sót (cách cắt mặc định)

| Lý do | Số mẫu |
| --- | --- |
| Giữ trọn | 446 |
| Đoạn lỗi cách dấu lỗi hơn 40 dòng | 173 |
| Job không có dấu lỗi (chỉ lấy 40 dòng cuối) | 64 |
| Nằm trong cửa sổ nhưng bị cắt vì giới hạn dòng | 40 |
| Đoạn lỗi dài hơn cửa sổ | 36 |
| Đoạn lỗi nằm sau dấu lỗi cuối | 20 |
| Dòng quá dài bị cắt | 12 |
| Không tìm thấy trong log gốc | 6 |

Chạy lại: `python -m ci_classifier excerpt-eval`.

---

## 2. Các chiến lược đã thử

Mỗi chiến lược là một **profile** trong `config.toml` (`[excerpt.profiles.<tên>]`), chọn bằng biến môi trường
`CI_EXCERPT_PROFILE`. Đoạn cắt của từng profile được lưu riêng vào `data/excerpts-<tên>/`, nên so sánh được mà không ghi đè.

| Profile | Cách làm |
| --- | --- |
| `default` | Cửa sổ 40 dòng trước tối đa 3 dấu lỗi cuối và tối đa 15 dòng khớp mẫu lỗi rõ ràng |
| `wide80` | Như trên, cửa sổ 80 dòng |
| `hints` | Chấm điểm các cụm dòng có từ khóa lỗi (error, fail, exception, denied…), ưu tiên cụm gần cuối log, chọn đến khi hết số dòng cho phép |
| `diff` | Tải **run thành công gần nhất** của cùng workflow (ưu tiên cùng nhánh), bỏ các dòng có mẫu cũng xuất hiện trong job thành công cùng tên (số, id, đường dẫn được thay bằng ký hiệu chung), rồi cắt cửa sổ như `default` trên phần còn lại |

### 2.1 Độ phủ đoạn lỗi trên LogChunks (chỉ tinh chỉnh trên train)

| Cấu hình | Giữ trọn (train) | Giữ trọn (test) | Số dòng trung vị |
| --- | --- | --- | --- |
| `default` (cửa sổ 40) | 56.0% | 54.6% | 42 |
| cửa sổ 80 | 61.8% | 66.4% | 81 |
| cửa sổ 120 | 66.6% | 67.7% | 118 |
| `hints`, 40 dòng | 35.7% | 44.5% | 42 |
| `hints`, 80 dòng | 39.9% | 46.3% | 81 |
| `hints` + giữ 30 dòng trước dấu lỗi, 40 dòng | 52.4% | – | 41 |

- Cửa sổ rộng hơn giữ được nhiều đoạn lỗi hơn, nhưng **tốn thêm dòng tương ứng**.
- `hints` **thua** `default` ở mọi mức kích thước: nhiều dòng có chữ "error/fail" không phải nguyên nhân
  (log cài đặt, tên file, test pass) chiếm hết số dòng cho phép.
- Profile `diff` không đo được trên LogChunks vì log Travis không có run thành công đi kèm.

### 2.2 Baseline cho log GitHub Actions (`fetch-baselines`)

| Kết quả | Số mẫu có nhãn |
| --- | --- |
| Có baseline | **157 / 194** (104 cùng nhánh, 53 nhánh khác) |
| Không có job thành công cùng tên | 28 |
| Không có run thành công trước đó | 8 |
| Lỗi tải | 1 |

Trên log GitHub Actions có nhãn, kích thước đoạn cắt (trung vị):

| Profile | Số dòng | Số ký tự |
| --- | --- | --- |
| `default` | 76 | 5.293 |
| `wide80` | 96 | 8.287 |
| `diff` | **54** | 5.127 |

`diff` bỏ được khoảng 30% số dòng. Số ký tự gần như không đổi vì các dòng bị bỏ thường ngắn (checkout, cài đặt),
còn dòng lỗi thường dài.

---

## 3. Ảnh hưởng tới bộ phân loại (62 mẫu GitHub Actions trong tập test)

Cả 3 profile được chấm **trên cùng 62 mẫu**, khoảng tin cậy 95% bằng bootstrap theo nhóm workflow.

| Profile | Luật từ khóa | TF-IDF | LLM | LLM trả `unknown` | Token prompt LLM (TB) |
| --- | --- | --- | --- | --- | --- |
| `default` | 0.37 [0.15, 0.62] | 0.10 [0.01, 0.23] | 0.69 [0.51, 0.86] | 10% | 2.307 |
| `wide80` | 0.37 [0.15, 0.62] | 0.06 [0.01, 0.15] | 0.73 [0.56, 0.87] | 10% | 3.141 |
| `diff` | 0.37 [0.15, 0.62] | 0.03 [0.00, 0.10] | **0.74 [0.56, 0.88]** | **6%** | 2.441 |

Kiểm định McNemar cho LLM (cùng 62 mẫu):

| So sánh | Chỉ `default` đúng | Chỉ profile mới đúng | p-value |
| --- | --- | --- | --- |
| `default` so với `wide80` | 3 | 5 | 0.73 |
| `default` so với `diff` | 5 | 8 | 0.58 |

Cách đọc:

- **Luật từ khóa không đổi:** luật chỉ cần một dòng khớp, và dòng đó thường đã có trong đoạn cắt mặc định.
- **TF-IDF giảm:** mô hình được huấn luyện trên đoạn cắt kiểu khác (chủ yếu LogChunks), nên đoạn cắt thay đổi làm
  lệch từ vựng. TF-IDF vốn đã rất yếu trên log GitHub Actions, nên không nên kết luận từ số này.
- **LLM tăng 4–5 điểm** với cả `wide80` và `diff`. `diff` đạt mức tương đương `wide80` nhưng **không tốn thêm token**
  (2.4k so với 3.1k) và ít trả `unknown` hơn. Tuy nhiên chỉ có 8–13 mẫu khác biệt, nên **chưa đủ bằng chứng thống kê**.

Cross-validation trên riêng log GitHub Actions không dùng để kết luận: LLM chỉ có câu trả lời cho 62 mẫu test,
nên mỗi phần chỉ có vài mẫu và độ lệch rất lớn (± 0.2–0.4).

---

## Kết luận

1. **Đo lường là phần giá trị nhất của bước này:** phát hiện cách đo cũ đánh giá thấp chất lượng đoạn cắt 15 điểm,
   và chỉ ra nguyên nhân bỏ sót chính (đoạn lỗi xa dấu lỗi).
2. **Chọn cụm theo từ khóa không hiệu quả** trên dữ liệu này (kết quả âm tính, giữ trong code dưới dạng thử nghiệm).
3. **So với run thành công là hướng hứa hẹn:** LLM chính xác hơn một chút, ít dòng hơn, ít `unknown` hơn,
   nhưng cần thêm dữ liệu để khẳng định.
4. **Chưa đổi cách cắt mặc định**, vì chưa có cải thiện có ý nghĩa thống kê.

## Hạn chế

- Chỉ 62 mẫu GitHub Actions trong tập test; khoảng tin cậy rộng khoảng ±0.15.
- Độ phủ đoạn lỗi chỉ đo được trên LogChunks (log Travis năm 2019), khác định dạng log mục tiêu.
- 37/194 mẫu không có baseline và 53 baseline lấy từ nhánh khác, có thể khác cấu hình với run fail.
- LLM là model miễn phí, có lúc quá tải (1 lần lỗi 502 được chạy lại).

## Việc tiếp theo

1. Thu thập thêm log GitHub Actions có baseline (mục tiêu vài trăm mẫu test) để kiểm định lại `diff`.
2. Kết hợp `diff` với cửa sổ rộng hơn (vì `diff` đã bỏ bớt dòng, có thể mở rộng cửa sổ mà không tăng token).
3. Với job không có dấu lỗi (64 mẫu LogChunks), thử lấy đoạn cuối của step thất bại thay vì 40 dòng cuối cả job.

## Cách chạy lại

```powershell
python -m ci_classifier excerpt-eval                                   # độ phủ đoạn lỗi (LogChunks)
python -m ci_classifier excerpt-eval --set context_before_error=80     # thử một thông số
python -m ci_classifier fetch-baselines --labelled-only --workers 4    # tải run thành công
$env:CI_EXCERPT_PROFILE = "diff"                                       # chọn profile
python -m ci_classifier excerpt
python -m ci_classifier llm-run --source github-actions
python -m ci_classifier evaluate --source github-actions --cv 5
Remove-Item Env:\CI_EXCERPT_PROFILE
```
