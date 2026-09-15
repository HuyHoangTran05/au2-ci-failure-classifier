# Báo cáo: duyệt nhãn và đánh giá có kiểm định thống kê

- **Ngày:** 15/09/2026
- **Dự án:** AU2 - phân loại lỗi CI
- **Phạm vi:** Bước 1 (ghi nhận việc duyệt nhãn) và Bước 2 (khoảng tin cậy, kiểm định McNemar, cross-validation)
- **Commit liên quan:** `df3211a`, `41081da` (bước 1); `f8811ff`, `28fc772`, `7a1b9a9` (bước 2)
- **Báo cáo gốc:** `results/20260915-094355/report.md`, `metrics.json`, `predictions.csv`, `cv_folds.csv`

## Tóm tắt

- Toàn bộ **944 nhãn** đã được người duyệt: 926 nhãn nháp được ghi nhận là giữ nguyên, 18 nhãn được duyệt từng mẫu trước đó.
- Trên tập test cố định 291 mẫu, **LLM đạt accuracy 0.71 [0.59, 0.80]**, cao hơn luật từ khóa (0.30) và TF-IDF (0.23).
- **Kiểm định McNemar** xác nhận LLM hơn hai phương pháp còn lại có ý nghĩa thống kê (p < 1e-20).
  Luật và TF-IDF **chưa khác nhau có ý nghĩa** (p = 0.067).
- **Cross-validation 5 lần** cho thứ hạng giống tập test cố định, nên kết luận ổn định với cách chia dữ liệu.
- Khoảng tin cậy còn **rộng khoảng ±0.1**, vì tập test chỉ có khoảng 39 nhóm workflow.

---

## Bước 1 - Ghi nhận việc duyệt nhãn

### Bối cảnh

Nhãn trong `data/labels.jsonl` ban đầu do Claude gán nháp (`labeler: claude-draft`) để tăng tốc. Báo cáo đánh giá
cảnh báo khi tập test còn nhãn nháp, vì con số chỉ đúng khi đáp án đúng. Người duyệt (HuyHoangTran) đã kiểm tra nhãn
nháp và giữ nguyên toàn bộ.

### Thay đổi

| Commit | Nội dung |
| --- | --- |
| `df3211a` | Thêm `python -m ci_classifier label --accept-drafts <tên>`: với mỗi nhãn nháp, ghi thêm một bản ghi `labeler: human`, **giữ nguyên giá trị nhãn**, `note` = `reviewed: bulk accepted by <tên> (draft kept)` kèm ghi chú nháp cũ. Có test. |
| `41081da` | Chạy lệnh trên với người duyệt `HuyHoangTran`. |

Vì `labels.jsonl` chỉ ghi thêm (append-only), lịch sử nhãn nháp vẫn còn nguyên trong file.

### Kết quả

| | Số nhãn |
| --- | --- |
| Tổng số mẫu có nhãn | 944 |
| Duyệt từng mẫu bằng `label --review` (trước đó) | 18 |
| Ghi nhận giữ nguyên sau khi kiểm tra (`--accept-drafts`) | 926 |
| Còn nhãn nháp | **0** |

Phân bố nhãn không đổi: `other` 328, `test_assertion` 325, `dependency` 114, `compilation` 85, `infrastructure` 61,
`authentication` 31.

### Hạn chế

- Việc duyệt diễn ra khi **đã thấy nhãn nháp**, nên dễ bị ảnh hưởng theo nhãn có sẵn (anchoring). Nhãn nháp lại do một LLM
  viết, vì vậy điểm của phương pháp LLM vẫn **có thể hơi cao** hơn thực tế.
- Chưa đo mức đồng thuận giữa hai người gán nhãn. Đề xuất: nhờ một người thứ hai **gán mù** khoảng 50 mẫu test rồi
  tính Cohen's kappa.

---

## Bước 2 - Đánh giá có kiểm định thống kê

### Vì sao cần

Lần đánh giá trước chỉ có **một con số trên một lần chia**. Với tập test nhỏ, con số dao động theo cách chia
(đã quan sát: accuracy của luật đổi từ 0.24 lên 0.30 chỉ vì chia lại). Cần trả lời hai câu hỏi:

1. Con số chắc chắn đến đâu? → **khoảng tin cậy**
2. Phương pháp A hơn B thật, hay chỉ do may? → **kiểm định McNemar**

Ngoài ra, kết luận có đứng vững khi đổi cách chia không? → **cross-validation**

### Phương pháp

| Kỹ thuật | Cách làm | Commit |
| --- | --- | --- |
| Khoảng tin cậy 95% | **Bootstrap theo nhóm**: lấy mẫu lại có hoàn lại **cả nhóm (repo, workflow)**, 1000 lần, lấy phân vị 2.5% và 97.5%. Lấy theo nhóm vì các run của cùng workflow có log gần giống nhau, không độc lập. | `f8811ff` |
| So sánh cặp phương pháp | **McNemar chính xác** (hai phía): chỉ xét các mẫu mà đúng một trong hai phương pháp đúng; kiểm tra số "chỉ A đúng" và "chỉ B đúng" có lệch quá mức ngẫu nhiên không. | `f8811ff` |
| Cross-validation | `StratifiedGroupKFold` 5 lần trên toàn bộ 944 mẫu: mỗi nhóm workflow nằm trọn trong một phần, phân tầng theo (nguồn, loại lỗi). Luật không cần học; TF-IDF học lại trên 4 phần còn lại; LLM chấm từ câu trả lời đã lưu. | `28fc772` |

Chạy lại: `python -m ci_classifier evaluate --cv 5`.

### Kết quả 1 - Tập test cố định (291 mẫu)

| Phương pháp | Accuracy [95% CI] | Macro F1 [95% CI] | Trả lời `unknown` | Đúng khi trả lời |
| --- | --- | --- | --- | --- |
| Luật từ khóa | 0.30 [0.19, 0.42] | 0.37 [0.19, 0.46] | 54% | 65% |
| TF-IDF + logistic regression | 0.23 [0.11, 0.34] | 0.16 [0.10, 0.22] | 73% | 83% |
| LLM `nvidia/nemotron-3-super-120b-a12b:free` | **0.71 [0.59, 0.80]** | **0.67 [0.50, 0.76]** | 8% | 77% |

Khoảng tin cậy của LLM **không chồng lên** khoảng của hai phương pháp còn lại; khoảng của luật và TF-IDF chồng lên nhau.

### Kết quả 2 - Kiểm định McNemar (291 mẫu)

| A so với B | Chỉ A đúng | Chỉ B đúng | p-value | Kết luận |
| --- | --- | --- | --- | --- |
| Luật so với TF-IDF | 64 | 44 | 0.067 | Chưa đủ bằng chứng khác nhau |
| Luật so với LLM | 17 | 137 | 1.7e-24 | LLM tốt hơn |
| TF-IDF so với LLM | 20 | 160 | 2.6e-28 | LLM tốt hơn |

Lưu ý: McNemar coi các mẫu là độc lập, trong khi mẫu cùng workflow có tương quan. Với p cực nhỏ như trên, kết luận
không đổi; với p gần ngưỡng (0.067) cần đọc thận trọng.

### Kết quả 3 - Cross-validation 5 lần (944 mẫu)

| Phương pháp | Accuracy (mean ± sd) | Macro F1 (mean ± sd) | Trả lời `unknown` | Số mẫu được chấm |
| --- | --- | --- | --- | --- |
| Luật từ khóa | 0.27 ± 0.04 | 0.33 ± 0.03 | 55% | 944 |
| TF-IDF | 0.21 ± 0.07 | 0.17 ± 0.07 | 78% | 944 |
| LLM | 0.72 ± 0.07 | 0.62 ± 0.07 | 8% | 293 |

Accuracy từng phần (fold):

| Fold | Luật | TF-IDF | LLM (số mẫu) |
| --- | --- | --- | --- |
| 1 | 0.30 | 0.11 | 0.84 (38) |
| 2 | 0.24 | 0.27 | 0.68 (71) |
| 3 | 0.29 | 0.21 | 0.72 (32) |
| 4 | 0.22 | 0.28 | 0.68 (114) |
| 5 | 0.29 | 0.16 | 0.68 (38) |

LLM chỉ được chấm trên 293 mẫu đã có câu trả lời (291 mẫu test + 2 mẫu thử), nên số mẫu mỗi phần không đều.
TF-IDF dao động mạnh nhất (0.11 đến 0.28): mô hình học từ ít dữ liệu nên nhạy với việc nhóm nào nằm ở train.

### LLM theo từng loại lỗi (tập test)

| Loại lỗi | Precision | Recall | F1 | Số mẫu |
| --- | --- | --- | --- | --- |
| other | 0.97 | 0.72 | 0.83 | 96 |
| test_assertion | 0.77 | 0.79 | 0.78 | 103 |
| dependency | 0.69 | 0.69 | 0.69 | 32 |
| compilation | 0.65 | 0.69 | 0.67 | 29 |
| authentication | 0.75 | 0.60 | 0.67 | 10 |
| infrastructure | 0.40 | 0.38 | **0.39** | 21 |

`infrastructure` yếu nhất: 8/21 mẫu bị đoán thành `test_assertion` (test fail do mạng hoặc môi trường).

---

## Kết luận

1. **Thứ hạng LLM > luật ≈ TF-IDF là đáng tin**: có ý nghĩa thống kê và giữ nguyên qua cross-validation.
2. **Độ chính xác tuyệt đối còn chưa chắc**: khoảng tin cậy rộng, và nhãn có thể thiên vị về phía LLM.
3. **Luật và TF-IDF chưa nên xếp hạng với nhau**: khác biệt chưa có ý nghĩa thống kê.

## Hạn chế

- Tập test nhỏ về số nhóm (khoảng 39 workflow), nên khoảng tin cậy rộng.
- Nhãn gốc do LLM gán, duyệt khi đã thấy nhãn nháp; chưa có mức đồng thuận giữa hai người.
- LLM trong cross-validation chỉ phủ khoảng 31% số mẫu.
- Cả 3 phương pháp chỉ thấy đoạn log đã cắt; bước cắt bỏ sót nguyên nhân thì mọi phương pháp đều sai
  (chỉ 41% đoạn cắt LogChunks chứa đủ đoạn lỗi được đánh dấu).

## Việc tiếp theo

1. **Bước 3:** đo triage time với người không tham gia gán nhãn.
2. **Bước 4:** cải thiện bước cắt log và đo lại chất lượng đoạn cắt cùng điểm của 3 phương pháp.
3. Gán mù khoảng 50 mẫu test bởi người thứ hai để đo Cohen's kappa.
4. Chạy `llm-run --split train` dần theo giới hạn lượt để LLM phủ đủ cross-validation.
