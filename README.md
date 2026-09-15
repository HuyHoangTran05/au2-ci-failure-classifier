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
| So sánh với LLM client | `ci_classifier/llm.py` (OpenRouter, model miễn phí) | ✅ |
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

### API key cho LLM

Phương pháp LLM gọi [OpenRouter](https://openrouter.ai) và chỉ dùng model miễn phí (đuôi `:free`, chọn trong
`config.toml [llm]`). Tạo file `.env` ở thư mục này (đã nằm trong `.gitignore`, **không bao giờ commit**):

```
OPENROUTER_API_KEY=sk-or-v1-...
```

Giới hạn cần biết: model miễn phí bị giới hạn số lượt mỗi phút và mỗi ngày, và đôi khi bị nhà cung cấp chặn tạm thời.
Vì vậy mọi câu trả lời được lưu trong `data/llm_predictions.jsonl` (theo model, phiên bản prompt và mã băm đoạn log);
`llm-run` bỏ qua mẫu đã có câu trả lời, còn `evaluate` chỉ đọc file này và chấm LLM trên các mẫu đã trả lời.
Log công khai gửi lên OpenRouter là chấp nhận được; **log nội bộ DMS thì phải hỏi mentor trước**.

## Quy trình

Tất cả lệnh chạy trong thư mục này, sau khi đã kích hoạt `.venv`. Gõ `python -m ci_classifier` để xem danh sách lệnh.

```powershell
# 1. Tải log các run bị fail (danh sách repo trong config.toml). Chạy lại được nếu bị ngắt giữa chừng.
python -m ci_classifier fetch

# 2. Cắt mỗi log (có thể vài chục MB) còn vài trăm dòng quan trọng -> data/excerpts/
python -m ci_classifier excerpt

# 2b. (Tuỳ chọn) Thêm 797 log Travis CI từ bộ LogChunks, đã có sẵn đoạn lỗi do con người đánh dấu
python -m ci_classifier import-logchunks
python -m ci_classifier excerpt-eval                    # đo đoạn cắt giữ được bao nhiêu đoạn lỗi đã đánh dấu

# 2c. (Tuỳ chọn) Tải run thành công gần nhất cho profile cắt log "diff"
python -m ci_classifier fetch-baselines --labelled-only --workers 4

# 3. Gán nhãn bằng tay (đọc docs/labeling-guide.md trước). Mục tiêu: 200-300 mẫu GitHub Actions.
python -m ci_classifier label --source logchunks       # nhanh: chỉ cần đọc đoạn lỗi đã đánh dấu
python -m ci_classifier label --source github-actions
python -m ci_classifier label --review                 # duyệt nhãn nháp (labeler = claude-draft)

# 4. Chia train/test MỘT LẦN, sau khi đã gán nhãn xong
python -m ci_classifier split

# 5. Cải thiện luật từ khóa, CHỈ nhìn vào tập train; thêm mỗi lỗi đã sửa vào tests/regression_cases.jsonl
python -m ci_classifier rules --split train
pytest

# 5a. Chọn ngưỡng abstain của TF-IDF bằng cross-validation trên train; chép giá trị vào config.toml [tfidf]
python -m ci_classifier tune-tfidf

# 5b. Hỏi LLM về các mẫu test (lưu vào data/llm_predictions.jsonl; chạy lại để làm tiếp nếu hết lượt trong ngày)
python -m ci_classifier llm-run

# 6. Chấm điểm trên tập test -> results/<thời gian>/report.md, metrics.json, predictions.csv
#    Báo cáo có khoảng tin cậy 95% (bootstrap theo nhóm) và kiểm định McNemar giữa các phương pháp.
python -m ci_classifier evaluate
python -m ci_classifier evaluate --cv 5    # thêm cross-validation 5 lần theo nhóm -> cv_folds.csv

# 7. Đo triage time: người phân loại có/không có gợi ý (tốt nhất nhờ người KHÔNG gán nhãn làm)
python -m ci_classifier triage --participant <tên> --count 20
python -m ci_classifier evaluate      # báo cáo có thêm mục "Triage time"
```

Phân loại một log bất kỳ (đây là MVP của đề bài):

```powershell
gh run view <run-id> -R owner/repo --log-failed > job.log
python -m ci_classifier classify job.log          # loại lỗi + dòng bằng chứng + runbook
python -m ci_classifier classify job.log --json   # kết quả dạng JSON cho công cụ khác
python -m ci_classifier classify job.log --method hybrid   # LLM, TF-IDF trả lời thay khi LLM không chắc
```

## Dữ liệu

| Nguồn | Số mẫu | Ghi chú |
| --- | --- | --- |
| GitHub Actions (`fetch`) | tuỳ cấu hình (~300) | Log mới, đúng định dạng mục tiêu. **Tập test chính nên dựa trên nguồn này.** |
| [LogChunks](https://doi.org/10.5281/zenodo.3632351) (`import-logchunks`) | 797 | Travis CI khoảng năm 2019, 80 repo, 29 ngôn ngữ. Mỗi log có đoạn lỗi do con người đánh dấu, nhưng **không có loại lỗi**, nên vẫn phải gán nhãn (nhanh hơn nhiều). |

LogChunks: Brandt, Panichella, Zaidman, Beller, *"LogChunks: A Data Set for Build Log Analysis"*, MSR 2020,
license CC BY 4.0. Bộ phân loại **không bao giờ thấy** đoạn lỗi đã đánh dấu; đoạn đó chỉ là gợi ý khi gán nhãn.

Các dataset khác đã xem nhưng không dùng:
- [Zheng et al., TOSEM 2025](https://github.com/zhengly1/workflow_failure): 375 job có nhãn, nhưng không kèm log và log gốc đã bị xoá. Chỉ dùng tham khảo cách chia loại lỗi.
- [GHALogs](https://doi.org/10.5281/zenodo.10154920): 142 GB, không có nhãn.
- Java Travis MSR'17: nhãn sinh tự động bằng regex, không dùng làm đáp án được.

Chất lượng bước `excerpt` trên LogChunks (đoạn lỗi đã đánh dấu có nằm trọn trong đoạn cắt không), đo bằng
`excerpt-eval`: 446/797 log (56%), độ phủ dòng trung bình 68%. Nguyên nhân bỏ sót chính là đoạn lỗi nằm xa dấu lỗi.

### Profile cắt log

`config.toml [excerpt.profiles.<tên>]` định nghĩa các cách cắt thử nghiệm; chọn bằng biến môi trường `CI_EXCERPT_PROFILE`
(mọi lệnh đều đọc biến này, đoạn cắt lưu riêng vào `data/excerpts-<tên>/`):
- `wide80`: cửa sổ 80 dòng trước dấu lỗi.
- `diff`: bỏ các dòng cũng có trong run thành công gần nhất (cần `fetch-baselines` trước).
- `hints`: chọn cụm dòng có từ khoá lỗi (kết quả kém hơn mặc định, chỉ để tham khảo).

### Nhãn nháp

Mỗi nhãn trong `data/labels.jsonl` có trường `labeler`:
- `claude-draft`: Claude gán dựa trên đoạn lỗi LogChunks, kèm lý do ngắn trong `note`. **Chưa được người kiểm tra.**
- `human`: người gán, hoặc người đã duyệt nhãn nháp (`note` ghi `reviewed: kept draft` hoặc `reviewed: changed from ...`).
  Nếu nhãn nháp được kiểm tra bên ngoài công cụ, `label --accept-drafts <tên>` ghi nhận toàn bộ với
  `note` = `reviewed: bulk accepted by <tên>`, để vẫn phân biệt được với duyệt từng mẫu.

Báo cáo `evaluate` cảnh báo nếu tập test còn nhãn nháp. Nhãn nháp do một LLM viết, nên khi so sánh
với phương pháp LLM, kết quả có thể bị thiên vị: hãy duyệt hết nhãn của tập test trước khi báo cáo.

Tóm tắt pain point và câu hỏi cho mentor: [`docs/pain-points.html`](docs/pain-points.html).
Báo cáo duyệt nhãn và kiểm định thống kê: [`docs/reports/2026-09-15-label-review-and-statistics.md`](docs/reports/2026-09-15-label-review-and-statistics.md).
Báo cáo cải thiện bước cắt log: [`docs/reports/2026-09-15-excerpt-improvement.md`](docs/reports/2026-09-15-excerpt-improvement.md).
Báo cáo ngưỡng TF-IDF và bộ phân loại lai: [`docs/reports/2026-09-15-tfidf-threshold-and-hybrid.md`](docs/reports/2026-09-15-tfidf-threshold-and-hybrid.md).

## Kết quả hiện tại (15/09/2026)

Dữ liệu: 944 mẫu có nhãn (194 GitHub Actions, 750 LogChunks), toàn bộ đã được người duyệt (nhãn nháp do Claude gán,
HuyHoangTran kiểm tra và giữ nguyên). Chia theo (repo, workflow), phân tầng theo (nguồn, loại lỗi): 653 train / 291 test.
Báo cáo đầy đủ nằm trong `results/`.

**Tập test cố định (291 mẫu)**, khoảng tin cậy 95% bằng bootstrap theo nhóm workflow (`results/20260915-112959/`):

| Phương pháp | Accuracy [95% CI] | Macro F1 [95% CI] | Abstention (unknown) | Accuracy khi trả lời |
| --- | --- | --- | --- | --- |
| Luật từ khóa | 0.30 [0.19, 0.42] | 0.37 [0.19, 0.46] | 0.54 | 0.65 |
| TF-IDF + logistic regression (ngưỡng 0.2) | 0.57 [0.44, 0.69] | 0.29 [0.22, 0.44] | 0.00 | 0.57 |
| LLM `nvidia/nemotron-3-super-120b-a12b:free` (prompt v1) | 0.71 [0.59, 0.80] | **0.67** [0.50, 0.76] | 0.08 | 0.77 |
| Hybrid: LLM, TF-IDF khi LLM trả `unknown` | **0.74** [0.62, 0.83] | **0.67** [0.50, 0.76] | 0.00 | 0.74 |

**Kiểm định McNemar** (cùng 291 mẫu): LLM hơn TF-IDF (p ≈ 9e-5), TF-IDF hơn luật (p ≈ 2e-12),
hybrid hơn LLM (đúng thêm 9 mẫu, không sai thêm mẫu nào, p = 0.004).

**Cross-validation 5 lần theo nhóm** trên toàn bộ 944 mẫu (mean ± sd):

| Phương pháp | Accuracy | Macro F1 | Abstention |
| --- | --- | --- | --- |
| Luật từ khóa | 0.27 ± 0.04 | 0.33 ± 0.03 | 0.55 |
| TF-IDF | 0.62 ± 0.07 | 0.42 ± 0.11 | 0.00 |
| LLM (chỉ 293 mẫu đã có câu trả lời) | 0.72 ± 0.07 | 0.62 ± 0.07 | 0.08 |
| Hybrid (cùng 293 mẫu) | 0.75 ± 0.06 | 0.60 ± 0.06 | 0.00 |

Cách đọc:
- Khoảng tin cậy **rộng** (khoảng ±0.1) vì tập test chỉ có 43 nhóm workflow: cần thêm dữ liệu để kết luận chi tiết.
- **Ngưỡng TF-IDF đã đổi từ 0.4 sang 0.2** (chọn bằng `tune-tfidf`, chỉ nhìn train). Ngưỡng cũ khiến TF-IDF trả
  `unknown` cho 73% mẫu test, nên kết quả trước đây (0.23, "luật ≈ TF-IDF") là do ngưỡng chứ không phải do phương pháp.
  TF-IDF vẫn yếu ở các loại hiếm (macro F1 0.29) và trên log GitHub Actions (0.32).
- ⚠️ Ý tưởng hybrid được chọn sau khi thử trên tập test, nên con số test có thể hơi lạc quan. Chi tiết:
  [`docs/reports/2026-09-15-tfidf-threshold-and-hybrid.md`](docs/reports/2026-09-15-tfidf-threshold-and-hybrid.md).
- LLM: khoảng 1.5k token prompt + 300 token trả lời mỗi mẫu, độ trễ trung vị 4.5 giây, chi phí 0 USD. 8/291 câu trả
  lời không đọc được JSON. Loại yếu nhất là `infrastructure` (F1 0.39), hay nhầm với `test_assertion`.
- ⚠️ Nhãn ban đầu do một LLM (Claude) gán rồi người duyệt giữ nguyên. Duyệt khi đã thấy nhãn nháp dễ bị ảnh hưởng
  theo nhãn đó, nên điểm LLM vẫn có thể hơi cao. Nên nhờ một người thứ hai gán mù khoảng 50 mẫu để đo Cohen's kappa.

Mẫu `authentication` rất hiếm nên đã được bổ sung bằng tìm kiếm có mục tiêu:
`fetch --workflow-filter ... --require <regex lỗi xác thực> --tag targeted-auth`. Trong 38 log khớp từ khóa, chỉ 12 log
là lỗi xác thực thật. Các mẫu này mang `retrieval: targeted-auth` và được báo cáo tách riêng, vì được chọn bằng từ khóa
nên luật từ khóa đạt điểm cao bất thường trên chúng. Kết quả trên **không so được** với lần chấm trước vì tập test đã đổi.

Hướng cải thiện tiếp theo: gán nhãn mù lại một phần tập test để đo mức thiên vị của nhãn nháp, chạy LLM trên train
để có cross-validation độc lập với tập test, cắt log tốt hơn (so với lần chạy thành công gần nhất), và thêm luật cho
lint, link checker, docs build, lỗi mạng (chỉ nhìn tập train). Bộ lai "luật cho `authentication`/`compilation` → LLM"
đã thử và kém hơn LLM một chút (0.698 so với 0.708), nên không dùng.

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
  logchunks.py              nhập bộ LogChunks (tải từ Zenodo, kiểm tra checksum)
  excerpt.py                cắt log -> data/excerpts/*.txt (chiến lược marker / hints / baseline-diff)
  excerpt_eval.py           đo độ phủ đoạn lỗi LogChunks và lý do bỏ sót
  baselines.py              tải run thành công gần nhất -> data/baselines/, data/baselines.jsonl
  label.py                  công cụ gán nhãn -> data/labels.jsonl
  split.py                  chia train/test -> data/split.json
  rules.py                  baseline 1: luật regex
  tfidf.py                  baseline 2: TF-IDF + logistic regression
  llm.py                    phương pháp 3: LLM qua OpenRouter, lưu câu trả lời -> data/llm_predictions.jsonl
  tune_tfidf.py             chọn ngưỡng abstain của TF-IDF bằng cross-validation trên train
  methods.py                tạo bộ phân loại theo tên phương pháp; hybrid = LLM, TF-IDF khi LLM trả unknown
  classify.py               phân loại một log đã lưu + runbook
  triage.py                 đo thời gian triage của người -> data/triage_sessions.jsonl
  evaluate.py               metrics bằng pandas, báo cáo bằng Jinja2
  stats.py                  khoảng tin cậy bootstrap theo nhóm, kiểm định McNemar
  crossval.py               cross-validation theo nhóm, phân tầng theo (nguồn, loại lỗi)
  templates/report.md.j2    mẫu báo cáo
docs/labeling-guide.md      định nghĩa nhãn và quy tắc khi phân vân
docs/runbooks/              runbook mẫu cho từng loại lỗi
tests/                      pytest; regression_cases.jsonl = log thật phải phân loại đúng
```

`data/raw/` và `data/excerpts/` tái tạo được nên không cần lưu vào git. `labels.jsonl`, `split.json`,
`manifest.jsonl` và `triage_sessions.jsonl` là công sức của bạn, **phải giữ lại**.
