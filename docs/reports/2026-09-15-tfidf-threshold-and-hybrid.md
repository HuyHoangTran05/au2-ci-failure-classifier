# Báo cáo: chọn lại ngưỡng TF-IDF và bộ phân loại lai LLM → TF-IDF

- **Ngày:** 15/09/2026
- **Dự án:** AU2 - phân loại lỗi CI
- **Phạm vi:** Việc 1 sau buổi rà soát hệ thống: sửa ngưỡng abstain của TF-IDF, thêm phương pháp `hybrid`
- **Commit liên quan:** `d0bc381` (`tune-tfidf`), `d9eaff8` (`hybrid`), commit cấu hình + kết quả + tài liệu
- **Báo cáo gốc:** `results/20260915-112821-tune-tfidf/thresholds.csv`, `results/20260915-112959/`,
  `results/20260915-113027-github-actions/`

## Tóm tắt

- Ngưỡng cũ `abstain_below = 0.4` **làm TF-IDF trông tệ hơn thực tế**. Có 6 loại nên xác suất cao nhất thường chỉ
  0.2–0.3, và ngưỡng 0.4 khiến mô hình trả `unknown` cho 73% mẫu test.
- Ngưỡng mới **0.2** được chọn bằng cross-validation **chỉ trên tập train**. TF-IDF trên test tăng **0.23 → 0.57**
  [0.44, 0.69]. Tuy vậy macro F1 chỉ 0.29, và trên log GitHub Actions chỉ đạt 0.32.
- Phương pháp mới `hybrid` dùng LLM, và khi LLM trả `unknown` thì dùng TF-IDF. Kết quả **0.74** [0.62, 0.83] so với
  0.71 của LLM: đúng thêm 9 mẫu, không sai thêm mẫu nào (McNemar p = 0.004). Cross-validation: 0.75 ± 0.06 so với 0.72 ± 0.07.
- ⚠️ Ý tưởng `hybrid` nảy ra khi phân tích thử trên tập test, nên kết quả trên test **có thể hơi lạc quan**.
  Cần xác nhận lại trên dữ liệu mới.
- **Thứ hạng mới:** hybrid ≥ LLM > TF-IDF > luật. Kết luận cũ "luật ≈ TF-IDF" không còn đúng.

---

## 1. Chọn ngưỡng TF-IDF (`tune-tfidf`)

### Cách làm

- Chỉ dùng **653 mẫu train**, không đọc tập test.
- Chạy `StratifiedGroupKFold` 5 lần, giữ nguyên nhóm (repo, workflow) và phân tầng theo (nguồn, loại lỗi), giống `crossval`.
- Mỗi lần học lại TF-IDF trên 4 phần còn lại, lấy xác suất cho phần bị giữ ra, rồi áp **mọi ngưỡng lên cùng các
  xác suất đó**.
- Quy tắc chọn được định trước: accuracy cao nhất (tính `unknown` là sai). Nếu nhiều ngưỡng bằng nhau thì lấy ngưỡng cao nhất.

Chạy lại: `python -m ci_classifier tune-tfidf` (thêm `--min-precision 0.8` nếu muốn ưu tiên độ chính xác khi trả lời).

### Kết quả trên train (cross-validation)

| Ngưỡng | Accuracy | Trả `unknown` | Đúng khi trả lời | Macro F1 |
| --- | --- | --- | --- | --- |
| 0.0 | 0.594 | 0% | 0.594 | 0.459 |
| **0.2** (chọn) | **0.594** | 0% | 0.594 | 0.459 |
| 0.25 | 0.533 | 18% | 0.653 | 0.435 |
| 0.3 | 0.398 | 49% | 0.778 | 0.368 |
| 0.35 | 0.254 | 72% | 0.912 | 0.282 |
| 0.4 (cũ) | 0.158 | 84% | 0.954 | 0.159 |
| 0.5 | 0.029 | 97% | 0.826 | 0.055 |

- 0.0 và 0.2 cho kết quả như nhau vì xác suất cao nhất trong 6 loại luôn ≥ 1/6. Theo quy tắc chọn thì lấy 0.2.
- Nếu cần TF-IDF **ít sai khi đã trả lời** (≥ 80%), ngưỡng phù hợp là 0.35, nhưng khi đó 72% mẫu bị trả `unknown`.
  Với vai trò dự phòng cho LLM thì ngưỡng thấp hợp lý hơn.

## 2. Phương pháp `hybrid`

Dùng câu trả lời của LLM. Chỉ khi LLM trả `unknown` (8% mẫu test), TF-IDF mới trả lời thay. Mẫu nào LLM chưa có
câu trả lời lưu sẵn thì hybrid cũng chưa có, nên hybrid được chấm trên đúng các mẫu của LLM.
Code: `methods.with_fallback`. Dùng được trong `classify --method hybrid`, `evaluate`, `triage` và cross-validation.

**Nguồn gốc ý tưởng (cần ghi rõ):** khi rà soát hệ thống, tôi thử 2 cách kết hợp **trên tập test**:
- "LLM → TF-IDF": 0.739.
- "luật cho `authentication`/`compilation` → LLM": 0.698. Hai loại này được chọn vì luật có precision ≥ 88% trên train.

Chỉ cách thứ nhất được đưa vào code. Vì đã nhìn tập test khi chọn, con số trên test có thể hơi lạc quan.
Cross-validation bên dưới giúp kiểm tra thêm nhưng chưa độc lập hoàn toàn, vì LLM mới có câu trả lời cho 293 mẫu và
gần như tất cả nằm trong tập test.

## 3. Kết quả trên tập test cố định (291 mẫu)

| Phương pháp | Accuracy [95% CI] | Macro F1 [95% CI] | Trả `unknown` |
| --- | --- | --- | --- |
| Luật từ khóa | 0.30 [0.19, 0.42] | 0.37 [0.19, 0.46] | 54% |
| TF-IDF (ngưỡng cũ 0.4) | 0.23 [0.11, 0.34] | 0.16 [0.10, 0.22] | 73% |
| **TF-IDF (ngưỡng 0.2)** | **0.57** [0.44, 0.69] | 0.29 [0.22, 0.44] | 0% |
| LLM | 0.71 [0.59, 0.80] | 0.67 [0.50, 0.76] | 8% |
| **Hybrid** | **0.74** [0.62, 0.83] | 0.67 [0.50, 0.76] | 0% |

McNemar (cùng 291 mẫu):

| A so với B | Chỉ A đúng | Chỉ B đúng | p-value |
| --- | --- | --- | --- |
| Luật so với TF-IDF | 26 | 105 | 1.9e-12 |
| TF-IDF so với LLM | 33 | 74 | 9.2e-05 |
| LLM so với hybrid | 0 | 9 | 0.0039 |

Cross-validation 5 lần theo nhóm (944 mẫu; LLM và hybrid chỉ 293 mẫu):

| Phương pháp | Accuracy | Macro F1 | Trả `unknown` |
| --- | --- | --- | --- |
| Luật | 0.27 ± 0.04 | 0.33 ± 0.03 | 55% |
| TF-IDF | 0.62 ± 0.07 | 0.42 ± 0.11 | 0% |
| LLM | 0.72 ± 0.07 | 0.62 ± 0.07 | 8% |
| Hybrid | 0.75 ± 0.06 | 0.60 ± 0.06 | 0% |

### Chỉ log GitHub Actions (62 mẫu test, định dạng mục tiêu)

| Phương pháp | Accuracy [95% CI] | Macro F1 |
| --- | --- | --- |
| Luật | 0.37 [0.15, 0.62] | 0.52 |
| TF-IDF | 0.32 [0.16, 0.52] | 0.19 |
| LLM | 0.69 [0.51, 0.86] | 0.71 |
| Hybrid | 0.71 [0.53, 0.87] | 0.70 |

## Cách đọc

- **TF-IDF tăng accuracy chủ yếu nhờ 2 loại phổ biến.** Recall của `test_assertion` là 0.87 và của `other` là 0.72,
  trong khi `compilation`, `dependency`, `authentication` gần như không đoán đúng. Macro F1 thấp (0.29) cho thấy điều đó.
- **TF-IDF chưa hiểu log GitHub Actions** (0.32, thấp hơn cả luật). Mô hình học chủ yếu từ log Travis của LogChunks
  (80% dữ liệu train), nên từ vựng khác.
- **Hybrid chỉ lấp các mẫu LLM trả `unknown`**, nên không bao giờ làm hỏng câu trả lời có sẵn của LLM. Nó tăng accuracy,
  nhưng macro F1 trong cross-validation giảm nhẹ (0.60 so với 0.62), vì TF-IDF hay đoán thành loại phổ biến.
  Trên log GitHub Actions, hybrid chỉ đúng thêm 1 mẫu.
- **Mất khả năng nói "không chắc":** hybrid và TF-IDF mới gần như không trả `unknown`. Nếu người dùng cần biết khi nào
  nên tự đọc log, nên hiện kèm nguồn câu trả lời. Chuỗi `detail` đã ghi `tfidf fallback p=...` cho trường hợp này.

## Hạn chế

- Nhãn vẫn là nhãn nháp của Claude được duyệt hàng loạt (xem việc 2 trong kế hoạch). Ví dụ đáng kiểm tra:
  `logchunks__processone__ejabberd__566947386` được gán `authentication` ("test DB user lacks permission"),
  nhưng đoạn cắt chỉ cho thấy lỗi mạng khi `git clone` (`Connection timed out`). Có thể đoạn lỗi LogChunks nằm ngoài
  đoạn cắt, hoặc nhãn sai.
- Ý tưởng hybrid được chọn sau khi nhìn tập test; con số test là lạc quan.
- 62 mẫu GitHub Actions thì khoảng tin cậy vẫn rất rộng.

## Việc tiếp theo

1. Việc 2: gán nhãn mù lại một phần tập test (`label --blind`) và tính Cohen's kappa với nhãn cũ.
2. `llm-run --split train` theo quota ngày, để có LLM cho cross-validation độc lập với tập test và chọn ngưỡng confidence.
3. Thêm log GitHub Actions vào train để TF-IDF học đúng định dạng mục tiêu.
