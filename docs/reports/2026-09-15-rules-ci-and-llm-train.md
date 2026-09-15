# Báo cáo: luật từ khóa mới, CI cho repo, LLM trên tập train

- **Ngày:** 15/09/2026
- **Dự án:** AU2 - phân loại lỗi CI
- **Phạm vi:** các việc làm được mà không cần người thứ hai, trong lúc chờ gán nhãn mù
- **Commit liên quan:** `55f48d0` (CI), `fdb765e` (luật), commit kết quả + tài liệu
- **Báo cáo gốc:** `results/20260915-115444/`, `results/20260915-115512-github-actions/`
  (so với `results/20260915-112959/` trước khi đổi luật)

## Tóm tắt

- **CI cho repo:** GitHub Actions chạy `pytest` mỗi lần push hoặc mở PR. Lần chạy đầu thành công sau 32 giây.
- **Luật từ khóa** được sửa **chỉ dựa trên tập train**. Trên train: accuracy **0.26 → 0.45**, riêng `other` từ 0/232 lên
  97/232 mẫu đúng. Trên test mức tăng nhỏ hơn nhiều: **0.30 → 0.34** [0.23, 0.46], McNemar p = 0.015.
  Nhiều luật mới khớp các loại lỗi chỉ phổ biến ở một vài repo trong train (awesome-list, LaTeX), nên ít gặp trên test.
- **LLM trên train:** đã hỏi thêm 40 mẫu GitHub Actions trong train (trước đó chỉ có 2 mẫu). LLM chỉ khớp nhãn
  **23/40 (0.58)**, thấp hơn 0.69 trên 62 mẫu GitHub Actions của tập test. Mẫu còn nhỏ, nhưng đây là dấu hiệu cần
  thận trọng với con số test của LLM trên log GitHub Actions.

---

## 1. Luật từ khóa

### Cách làm

Chỉ đọc các mẫu train mà luật đoán sai hoặc không trả lời. Mỗi mẫu regex mới được đo precision trên train trước khi
thêm vào; mẫu nào precision thấp thì bỏ (ví dụ `Connection timed out`: 0/8 mẫu train là `infrastructure`;
`htmlproofer`, `shellcheck`, `broken links` cũng khớp nhiều log thuộc loại khác).

### Thay đổi chính

| Vấn đề tìm thấy trên train | Sửa |
| --- | --- |
| `npm ERR!` xuất hiện ở **mọi** npm script bị fail (lint, test), nên 33 mẫu `other` và 16 mẫu `test_assertion` bị đoán thành `dependency` | Chỉ tính lỗi kiểu cài đặt: `npm ERR! code E...` (trừ `ELIFECYCLE`), `Failed at the ... postinstall script`, `gyp ERR!` |
| `Unauthorized` khớp nhầm vào `rejectUnauthorized` (tùy chọn TLS trong log Node) | Thêm ranh giới từ `\bUnauthorized\b` |
| `The operation was canceled` khớp vào `TaskCanceledException` bên trong test | Chỉ khớp thông báo huỷ của runner `##[error]The operation was canceled` |
| `Build FAILED` của MSBuild cũng xuất hiện khi test fail | Hạ ưu tiên: chỉ quyết định khi không luật nào cụ thể hơn khớp |
| `other` gần như không có luật | Thêm công cụ lint/format (`awesome_bot`, `markdownlint`, `stylelint`, `perlcritic`, `rubocop`, `gofmt`...), `pre-commit`, LaTeX `Overfull \hbox`, file sinh ra chưa commit, `Found N errors in N files` |
| `infrastructure` gần như không có luật | Thêm GitHub API 5xx, `aborted due to timeout`, hết quota, lỗi kết nối HTTP, trình duyệt test bị ngắt kết nối, `exited with 124` (lệnh `timeout`) |

Thêm 10 ca vào `tests/regression_cases.jsonl`, đều là dòng log thật lấy từ tập train. Trong đó có 3 ca kiểm tra luật
**không** được khớp nhầm (`npm ERR! code ELIFECYCLE`, `rejectUnauthorized`, `TaskCanceledException`).

### Kết quả

| | Train (653) | Test (291) | Test: LogChunks (229) | Test: GitHub Actions (55) |
| --- | --- | --- | --- | --- |
| Luật cũ | 0.26 | 0.30 [0.19, 0.42] | 0.28 | 0.31 |
| Luật mới | 0.45 | **0.34** [0.23, 0.46] | 0.34 | 0.29 |

Cột GitHub Actions không tính 7 mẫu lấy có mục tiêu (`targeted-auth`); tính cả chúng thì luật mới đạt 0.35 trên 62 mẫu.
Khi luật chịu trả lời, tỷ lệ đúng trên test tăng từ 0.65 lên 0.79.

Theo từng loại trên test (số mẫu đoán đúng, và precision khi luật trả lời):

| Loại | Số mẫu | Đúng (cũ → mới) | Precision (cũ → mới) |
| --- | --- | --- | --- |
| `test_assertion` | 103 | 58 → 65 | 0.79 → 0.78 |
| `other` | 96 | 0 → 12 | 0.00 → 0.92 |
| `dependency` | 32 | 12 → 6 | 0.33 → **1.00** |
| `compilation` | 29 | 10 → 10 | 0.62 → 0.62 |
| `authentication` | 10 | 6 → 6 | 1.00 → 1.00 |
| `infrastructure` | 21 | 0 → 0 | – |

Cách đọc:

- **Khoảng cách giữa train và test là dấu hiệu luật đang quá khớp với train.** Luật `other` mới đúng 97 mẫu train nhưng
  chỉ 12 mẫu test, vì mỗi repo có công cụ kiểm tra riêng. `infrastructure` trên test vẫn 0/21.
- **Luật giờ chính xác hơn khi đã trả lời.** Precision của `dependency` tăng từ 0.33 lên 1.00, `other` từ 0 lên 0.92.
  Đổi lại, `dependency` bị bỏ sót nhiều hơn (12 → 6), vì bỏ luật `npm ERR!` chung chung.
- Tỷ lệ trả lời `unknown` gần như không đổi (54% → 57%). Luật vẫn là phương pháp yếu nhất, nhưng hợp làm bước đầu
  precision cao trước LLM.
- Cross-validation có dùng cả các mẫu train đã dùng để sửa luật, nên con số CV của luật (xem báo cáo gốc) là lạc quan.
  Con số test mới là con số dùng để báo cáo.

## 2. CI cho repo

`.github/workflows/tests.yml`: Ubuntu, Python 3.13, `pip install -r requirements.txt`, `pytest -q`. Test không gọi
mạng hay API LLM, nên không cần secret.

## 3. LLM trên tập train

`llm-run --split train --source github-actions --limit 40` (ưu tiên log GitHub Actions, là định dạng mục tiêu).
Không có lỗi API; chi phí 0 USD; mất khoảng 25 phút vì model miễn phí giới hạn lượt gọi.

| | Số mẫu | LLM khớp nhãn |
| --- | --- | --- |
| GitHub Actions, tập train (mới) | 40 | 23 (0.58) |
| GitHub Actions, tập test | 62 | 43 (0.69) |

- 6/17 lỗi là LLM đoán `infrastructure` trong khi nhãn là `test_assertion` hoặc `other`. Phần lớn là log của các
  workflow review bằng AI hoặc script gọi GitHub API. Ranh giới này đã được ghi là mơ hồ trong pain points, nên nên
  kiểm tra lại khi gán nhãn mù.
- Cross-validation trên toàn bộ dữ liệu giờ chấm LLM trên 333 mẫu (trước là 293): LLM 0.70 ± 0.08, hybrid 0.73 ± 0.06.
  Riêng GitHub Actions (104 mẫu): LLM 0.58 ± 0.21, hybrid 0.61 ± 0.18. Độ lệch rất lớn vì mỗi phần chỉ có vài chục mẫu.

## Việc tiếp theo

1. **(Bạn)** Gán nhãn mù 80 mẫu test, chạy `agreement`, phân xử, rồi `evaluate --cv 5`.
2. Chạy thêm `llm-run --split train --limit 40` mỗi ngày theo quota.
3. Sau khi nhãn đã chốt: prompt v2 (few-shot lấy từ train) và thêm log GitHub Actions. Làm trước thì phải chấm lại khi nhãn đổi.
