# AU2 - Phân loại lỗi CI (CI failure classifier)

Đọc log của một job CI bị fail đã lưu, cho biết **vì sao nó fail** và **chỉ tới runbook** phù hợp:
`compilation`, `test_assertion`, `dependency`, `authentication`, `infrastructure`, `other`,
hoặc `unknown` khi không chắc (abstain).

Dữ liệu là log **công khai** của GitHub Actions từ các repo mã nguồn mở. Dự án không dùng dữ liệu
nội bộ công ty. Dự án thuộc "side-project bank" trong `../ASSIGNMENT.md` (mục AU2), đã được mentor đồng ý,
và bổ trợ cho dự án 3 (phân loại sự cố ứng dụng).

## Đối chiếu với đề bài

| Đề bài AU2 | Trong dự án | Trạng thái |
| --- | --- | --- |
| Luật regex (Python) | `ci_classifier/rules.py` | ✅ |
| scikit-learn TF-IDF + logistic regression | `ci_classifier/tfidf.py` | ✅ |
| Log đã gán nhãn dạng JSONL | `data/manifest.jsonl`, `data/labels.jsonl` | ✅ (đang gán nhãn) |
| pytest cho regression cases | `tests/`, `tests/regression_cases.jsonl` | ✅ |
| So sánh với LLM client | — | ⏳ chờ mentor xác nhận API LLM được dùng |
| Metrics qua pandas | `ci_classifier/evaluate.py` | ✅ |
| CLI / tóm tắt bằng Jinja2 | `python -m ci_classifier ...`, `templates/report.md.j2` | ✅ |
| Link tới runbook | `config.toml [runbooks]`, `docs/runbooks/` | ✅ runbook mẫu |
| Precision/recall theo loại, abstention | `evaluate` | ✅ |
| Triage time | `triage` + mục "Triage time" trong báo cáo | ✅ |
| Adapter `httpx` tải artifact CI | — | ⏸ chỉ làm **sau khi** bộ phân loại offline chạy tốt |

`fetch` dùng `gh` CLI để **thu thập bộ dữ liệu một lần**, không phải adapter tích hợp với CI thật.

## Cài đặt

Cần Python 3.11+ và [GitHub CLI](https://cli.github.com/) đã đăng nhập (`gh auth login`).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # từ giờ "python" là Python của .venv
pip install -r requirements.txt
pytest                                 # kiểm tra mọi thứ chạy được
```

Nếu PowerShell chặn `Activate.ps1`, chạy trực tiếp: `.\.venv\Scripts\python.exe -m ci_classifier ...`

## Quy trình

Tất cả lệnh chạy trong thư mục này, sau khi đã kích hoạt `.venv`. Gõ `python -m ci_classifier` để xem danh sách lệnh.

```powershell
# 1. Tải log các run bị fail (danh sách repo trong config.toml). Chạy lại được nếu bị ngắt giữa chừng.
python -m ci_classifier fetch

# 2. Cắt mỗi log (có thể vài chục MB) còn vài trăm dòng quan trọng -> data/excerpts/
python -m ci_classifier excerpt

# 3. Gán nhãn bằng tay (đọc docs/labeling-guide.md trước). Mục tiêu: 200-300 mẫu.
python -m ci_classifier label

# 4. Chia train/test MỘT LẦN, sau khi đã gán nhãn xong
python -m ci_classifier split

# 5. Cải thiện luật từ khóa, CHỈ nhìn vào tập train; thêm mỗi lỗi đã sửa vào tests/regression_cases.jsonl
python -m ci_classifier rules --split train
pytest

# 6. Chấm điểm trên tập test -> results/<thời gian>/report.md, metrics.json, predictions.csv
python -m ci_classifier evaluate

# 7. Đo triage time: người phân loại có/không có gợi ý (tốt nhất nhờ người KHÔNG gán nhãn làm)
python -m ci_classifier triage --participant <tên> --count 20
python -m ci_classifier evaluate      # báo cáo có thêm mục "Triage time"
```

Phân loại một log bất kỳ (đây là MVP của đề bài):

```powershell
gh run view <run-id> -R owner/repo --log-failed > job.log
python -m ci_classifier classify job.log          # loại lỗi + dòng bằng chứng + runbook
python -m ci_classifier classify job.log --json   # kết quả dạng JSON cho công cụ khác
```

## Nguyên tắc để kết quả đáng tin

- **Không bao giờ chỉnh luật hay ngưỡng khi đang nhìn tập test.** Làm vậy thì điểm test không còn ý nghĩa.
- **Train/test chia theo (repo, workflow).** Các run của cùng một workflow có log gần giống nhau; nếu
  chúng nằm cả hai bên thì điểm TF-IDF sẽ cao ảo.
- `unknown` được tính là sai trong accuracy, nhưng báo riêng thành "abstention rate". Một bộ phân loại
  biết nói "không chắc" có ích hơn một bộ đoán bừa.
- Mỗi báo cáo lưu cấu hình, số mẫu và mã băm của `labels.jsonl`, để biết nó được tạo từ dữ liệu nào.
- Kết quả "không cải thiện" cũng là kết quả có giá trị. Hãy ghi lại, đừng giấu.

## Cấu trúc

```
config.toml                 loại lỗi, runbook, repo cần tải, thông số cắt log, tỉ lệ chia, ngưỡng
ci_classifier/
  __main__.py               CLI: python -m ci_classifier <lệnh>
  fetch.py                  tải log bằng gh -> data/raw/*.log.gz + data/manifest.jsonl
  excerpt.py                cắt log -> data/excerpts/*.txt
  label.py                  công cụ gán nhãn -> data/labels.jsonl
  split.py                  chia train/test -> data/split.json
  rules.py                  baseline 1: luật regex
  tfidf.py                  baseline 2: TF-IDF + logistic regression
  methods.py                tạo bộ phân loại theo tên phương pháp
  classify.py               phân loại một log đã lưu + runbook
  triage.py                 đo thời gian triage của người -> data/triage_sessions.jsonl
  evaluate.py               metrics bằng pandas, báo cáo bằng Jinja2
  templates/report.md.j2    mẫu báo cáo
docs/labeling-guide.md      định nghĩa nhãn và quy tắc khi phân vân
docs/runbooks/              runbook mẫu cho từng loại lỗi
tests/                      pytest; regression_cases.jsonl = log thật phải phân loại đúng
```

`data/raw/` và `data/excerpts/` tái tạo được nên không cần lưu vào git. `labels.jsonl`, `split.json`,
`manifest.jsonl` và `triage_sessions.jsonl` là công sức của bạn, **phải giữ lại**.
