# CI Failure Classifier

[![tests](https://github.com/HuyHoangTran05/au2-ci-failure-classifier/actions/workflows/tests.yml/badge.svg)](https://github.com/HuyHoangTran05/au2-ci-failure-classifier/actions/workflows/tests.yml)

Đọc log của một job CI bị fail, cho biết **vì sao nó fail**, **dòng log nào là bằng chứng** và **nên mở runbook nào**.

```text
$ python -m ci_classifier classify job.log
Category: dependency
Evidence: npm ERR! code ERESOLVE
Runbook:  docs/runbooks/dependency.md
```

Có 6 loại lỗi: `compilation`, `test_assertion`, `dependency`, `authentication`, `infrastructure`, `other`.
Khi không đủ chắc chắn, bộ phân loại trả về `unknown` (abstain) thay vì đoán bừa.

Dự án so sánh ba cách tiếp cận trên cùng một tập test cố định, có khoảng tin cậy và kiểm định thống kê:

1. **Luật từ khóa** (regex)
2. **TF-IDF + logistic regression** (scikit-learn)
3. **LLM** qua [OpenRouter](https://openrouter.ai) (chỉ dùng model miễn phí), cùng một bản **hybrid**: dùng LLM trước,
   TF-IDF trả lời thay khi LLM không chắc.

Toàn bộ dữ liệu là log **công khai**: GitHub Actions của các repo mã nguồn mở và bộ dữ liệu [LogChunks](https://doi.org/10.5281/zenodo.3632351) (Travis CI).

## Kết quả

Tập test gồm 291 mẫu (chia theo repo/workflow, không mẫu nào trùng nhóm với train). Khoảng tin cậy 95% tính bằng
bootstrap theo nhóm workflow. Báo cáo đầy đủ: [`results/20260916-091707/report.md`](results/20260916-091707/report.md).

| Phương pháp | Accuracy [95% CI] | Macro F1 [95% CI] | Tỉ lệ `unknown` | Accuracy khi có trả lời |
| --- | --- | --- | --- | --- |
| Luật từ khóa | 0.34 [0.23, 0.46] | 0.46 [0.27, 0.54] | 0.57 | 0.79 |
| TF-IDF + logistic regression | 0.56 [0.43, 0.69] | 0.30 [0.23, 0.44] | 0.00 | 0.56 |
| LLM (`nvidia/nemotron-3-super-120b-a12b:free`) | 0.74 [0.63, 0.84] | **0.74** [0.63, 0.83] | 0.08 | 0.80 |
| Hybrid (LLM, TF-IDF khi LLM trả `unknown`) | **0.77** [0.66, 0.86] | 0.73 [0.62, 0.83] | 0.00 | 0.77 |

- **Kiểm định McNemar** trên cùng 291 mẫu cho thấy LLM hơn TF-IDF (p ≈ 5e-5), TF-IDF hơn luật (p ≈ 2e-10), và hybrid hơn
  LLM (p = 0.004): hybrid đúng thêm 9 mẫu mà không sai thêm mẫu nào.
- **Cross-validation 5 lần theo nhóm** trên toàn bộ 944 mẫu cho kết quả cùng thứ tự. Accuracy lần lượt là: luật 0.42 ± 0.10,
  TF-IDF 0.61 ± 0.06, LLM 0.71 ± 0.07 và hybrid 0.76 ± 0.08. Riêng LLM và hybrid chỉ được chấm trên 333 mẫu đã có câu trả lời.
- **Luật từ khóa** thường đúng khi đã chịu trả lời (0.79), nhưng bỏ qua hơn nửa số mẫu.
- **Chi phí LLM:** mỗi mẫu tốn khoảng 1.5k token prompt và 300 token trả lời, độ trễ trung vị 4.5 giây, chi phí 0 USD
  vì dùng model miễn phí. Có 8/291 câu trả lời không đọc được thành JSON.

### Nên đọc các con số này thế nào

- **Khoảng tin cậy rộng** (khoảng ±0.1) vì tập test chỉ có 43 nhóm workflow.
- **Nhãn ban đầu do một LLM (Claude) gán nháp**, sau đó được một người duyệt. Một hội đồng gồm 3 LLM khác soát lại
  toàn bộ tập test (Fleiss' kappa 0.89), và người phân xử 37 mẫu bị tranh cãi. Người duyệt đã nhìn thấy nhãn nháp nên
  có thể bị ảnh hưởng theo nhãn đó, vì vậy điểm của LLM có thể hơi cao. Con số thận trọng hơn là
  **LLM đúng 0.80 trên 171 mẫu mà cả hội đồng đồng ý**.
- **Ý tưởng hybrid được chọn sau khi đã thấy kết quả trên tập test**, nên điểm test của hybrid có thể hơi lạc quan.
- Phần lớn dữ liệu là log Travis CI từ khoảng năm 2019. Tập test chỉ có 62 mẫu GitHub Actions, và trên các mẫu này điểm
  của TF-IDF thấp hơn hẳn.
- Loại lỗi khó nhất là `infrastructure`: LLM chỉ đạt F1 0.39 và hay nhầm loại này với `test_assertion`.

Chi tiết nằm trong [`docs/reports/`](docs/reports/), gồm cả các hướng **đã thử nhưng không cải thiện**, như prompt v2
và bộ lai "luật + LLM".

## Cài đặt

Cần Python 3.11 trở lên. Nếu muốn tự tải log từ GitHub Actions, cần thêm [GitHub CLI](https://cli.github.com/) đã đăng nhập bằng `gh auth login`.

```bash
git clone https://github.com/HuyHoangTran05/au2-ci-failure-classifier.git
cd au2-ci-failure-classifier
python -m venv .venv
source .venv/bin/activate            # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest                               # test không gọi mạng, không cần API key
```

### API key cho LLM (không bắt buộc)

Phương pháp `llm` và `hybrid` cần một key [OpenRouter](https://openrouter.ai/keys). Hãy tạo file `.env` ở thư mục gốc.
File này đã có trong `.gitignore`, **đừng commit nó**:

```
OPENROUTER_API_KEY=sk-or-v1-...
```

Phương pháp `rules` và `tfidf` chạy hoàn toàn offline, không cần key.

Cần biết về model miễn phí: chúng bị giới hạn số lượt gọi mỗi phút và mỗi ngày, đôi khi còn bị nhà cung cấp chặn tạm thời.
Vì vậy mọi câu trả lời đều được lưu vào `data/llm_predictions.jsonl`, theo model, phiên bản prompt và mã băm của đoạn log.
Lần sau, `llm-run` bỏ qua những mẫu đã có câu trả lời. Còn `evaluate` chỉ đọc file này, không gọi API.

> ⚠️ Log CI có thể chứa đường dẫn nội bộ, tên máy hoặc token bị lộ. Đừng gửi log không công khai lên LLM bên ngoài nếu chưa
> được phép và chưa che thông tin nhạy cảm.

## Sử dụng

### Phân loại một log

```bash
gh run view <run-id> -R owner/repo --log-failed > job.log

python -m ci_classifier classify job.log                   # mặc định: luật từ khóa
python -m ci_classifier classify job.log --method tfidf    # rules | tfidf | llm | hybrid
python -m ci_classifier classify job.log --json            # xuất JSON cho công cụ khác
```

Phương pháp `tfidf` và `hybrid` học từ dữ liệu đã gán nhãn trong `data/`. Repo đã có sẵn nhãn, nhưng đoạn log cắt sẵn
thì không, nên cần chạy bước `excerpt` trong phần [Tái tạo kết quả](#tái-tạo-kết-quả) trước.

### Demo trên trình duyệt

Dán log vào trang, chọn phương pháp và xem kết quả của các phương pháp cạnh nhau:

```bash
python -m ci_classifier demo                       # mở http://127.0.0.1:8000
python -m ci_classifier demo --port 8123 --no-browser
```

Gõ `python -m ci_classifier` để xem toàn bộ lệnh, và `python -m ci_classifier <lệnh> -h` để xem tuỳ chọn của từng lệnh.

## Cách hoạt động

```
log CI (vài MB)  ──excerpt──▶  đoạn cắt (≤ 300 dòng)  ──▶  rules / tfidf / llm / hybrid  ──▶  loại lỗi + bằng chứng + runbook
```

1. **Cắt log** (`excerpt.py`). Log của một job có thể dài hàng chục MB. Bước này giữ lại cửa sổ dòng ngay trước các dấu
   `##[error]` và một số dòng "đáng chú ý" trong toàn bộ job. **Cả ba phương pháp đều chỉ nhìn thấy đoạn cắt này.**
   Trên LogChunks, 56% đoạn cắt chứa trọn đoạn lỗi do con người đánh dấu, và độ phủ dòng trung bình là 68%. Có thể thử
   cách cắt khác bằng biến môi trường `CI_EXCERPT_PROFILE`: `wide80` lấy cửa sổ rộng hơn, `diff` bỏ các dòng cũng xuất
   hiện trong lần chạy thành công gần nhất.
2. **Phân loại**:
   - `rules.py`: regex theo từng loại lỗi, trả `unknown` khi không khớp luật nào.
   - `tfidf.py`: TF-IDF + logistic regression, trả `unknown` khi xác suất cao nhất dưới ngưỡng. Ngưỡng này được chọn
     bằng cross-validation, chỉ dùng tập train (`tune-tfidf`).
   - `llm.py`: gửi prompt yêu cầu model trả JSON gồm loại lỗi, độ tự tin và dòng bằng chứng.
3. **Runbook**: `config.toml [runbooks]` ánh xạ từng loại lỗi tới một file trong `docs/runbooks/`. Các runbook hiện có
   chỉ là bản mẫu; hãy thay bằng runbook thật của nhóm bạn.

## Tái tạo kết quả

Log thô không được lưu trong repo vì quá nặng, nhưng có thể tải lại. Nhãn, cách chia train/test và câu trả lời của LLM
thì đã được commit sẵn.

```bash
# 1. Tải log các run bị fail (danh sách repo trong config.toml). Bị ngắt giữa chừng thì chạy lại để làm tiếp.
python -m ci_classifier fetch
python -m ci_classifier import-logchunks        # 797 log Travis CI từ Zenodo, có kiểm tra checksum

# 2. Cắt log -> data/excerpts/
python -m ci_classifier excerpt
python -m ci_classifier excerpt-eval            # độ phủ đoạn lỗi LogChunks

# 3. Chấm điểm trên tập test -> results/<thời gian>/report.md, metrics.json, predictions.csv
python -m ci_classifier evaluate
python -m ci_classifier evaluate --cv 5         # thêm cross-validation 5 lần theo nhóm
```

Log GitHub Actions chỉ được giữ trong một thời gian giới hạn, nên một số run cũ có thể không còn tải được.
Khi đó `evaluate` sẽ chấm trên ít mẫu hơn con số trong bảng.

<details>
<summary>Quy trình đầy đủ: gán nhãn, kiểm tra nhãn, chia dữ liệu, tinh chỉnh</summary>

```bash
# Gán nhãn bằng tay (đọc docs/labeling-guide.md trước)
python -m ci_classifier label --source logchunks       # nhanh: đã có đoạn lỗi do người đánh dấu làm gợi ý
python -m ci_classifier label --source github-actions
python -m ci_classifier label --review                 # duyệt nhãn nháp

# Kiểm tra độ tin cậy của nhãn: tự gán mù lại một phần tập test, đo Cohen's kappa, phân xử chỗ bất đồng
python -m ci_classifier label --blind --labeler <tên> --count 80
python -m ci_classifier agreement --labeler <tên>
python -m ci_classifier label --adjudicate --labeler <tên>

# Hoặc để hội đồng 3 LLM gán lại, người chỉ phân xử các mẫu bị tranh cãi
python -m ci_classifier panel-run
python -m ci_classifier panel-report
python -m ci_classifier label --adjudicate --panel --labeler <tên>

# Chia train/test MỘT LẦN, sau khi gán nhãn xong
python -m ci_classifier split

# Tinh chỉnh, CHỈ nhìn tập train
python -m ci_classifier rules --split train            # thêm mỗi lỗi đã sửa vào tests/regression_cases.jsonl
python -m ci_classifier tune-tfidf                      # chép ngưỡng tìm được vào config.toml [tfidf]
python -m ci_classifier fetch-baselines --labelled-only --workers 4   # cần cho profile cắt log "diff"

# Hỏi LLM (chạy lại để làm tiếp khi hết lượt trong ngày)
python -m ci_classifier llm-run --limit 40

# Đo thời gian triage của người khi có và không có gợi ý (nên nhờ người KHÔNG tham gia gán nhãn)
python -m ci_classifier triage --participant <tên> --count 20
```

Mẫu `authentication` rất hiếm, nên đã được bổ sung bằng tìm kiếm có mục tiêu
(`fetch --workflow-filter ... --require <regex> --tag targeted-auth`). Các mẫu này mang trường
`retrieval: targeted-auth` và được báo cáo riêng, vì chúng được chọn bằng từ khóa nên luật từ khóa được lợi.

</details>

## Dữ liệu

| Nguồn | Số mẫu có nhãn | Ghi chú |
| --- | --- | --- |
| GitHub Actions (`fetch`) | 194 | Log gần đây từ `dotnet/aspire`, `microsoft/vscode`, `python/cpython`, `grafana/grafana`, ... |
| [LogChunks](https://doi.org/10.5281/zenodo.3632351) (`import-logchunks`) | 750 | Travis CI khoảng năm 2019, 80 repo, 29 ngôn ngữ |

Có 653 mẫu train và 291 mẫu test. Dữ liệu được chia theo nhóm (repo, workflow) và phân tầng theo (nguồn, loại lỗi).

| File trong `data/` | Nội dung |
| --- | --- |
| `manifest.jsonl` | danh sách mẫu và nguồn gốc |
| `labels.jsonl` | nhãn; trường `labeler` cho biết nhãn do người gán hay là nhãn nháp |
| `split.json` | cách chia train/test cố định |
| `llm_predictions.jsonl` | câu trả lời của LLM đã lưu lại |
| `panel_labels.jsonl` | câu trả lời của hội đồng LLM |
| `blind_labels.jsonl` | nhãn gán mù |

Các file `.jsonl` chỉ được ghi thêm (append-only): nếu một `sample_id` xuất hiện nhiều lần, bản ghi sau cùng được dùng.
Định nghĩa các loại lỗi và quy tắc khi phân vân nằm trong [`docs/labeling-guide.md`](docs/labeling-guide.md).

**LogChunks:** Brandt, Panichella, Zaidman, Beller. *"LogChunks: A Data Set for Build Log Analysis"*, MSR 2020.
Bộ dữ liệu dùng giấy phép [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Bộ phân loại **không bao giờ
thấy** đoạn lỗi do người đánh dấu; đoạn đó chỉ được dùng làm gợi ý khi gán nhãn và để đo chất lượng bước cắt log.

Các bộ dữ liệu đã xem xét nhưng không dùng:
- [Zheng et al., TOSEM 2025](https://github.com/zhengly1/workflow_failure): không kèm log, và log gốc đã bị xoá.
- [GHALogs](https://doi.org/10.5281/zenodo.10154920): 142 GB, không có nhãn.
- Java Travis MSR'17: nhãn được sinh tự động bằng regex, nên không dùng làm đáp án được.

## Nguyên tắc đánh giá

- **Không chỉnh luật, ngưỡng hay prompt khi đang nhìn tập test.** Mọi tinh chỉnh chỉ dựa trên tập train.
- **Chia train/test theo (repo, workflow).** Các run của cùng một workflow có log gần giống nhau, nên nếu chúng nằm ở
  cả hai phía thì điểm của TF-IDF sẽ cao ảo.
- **`unknown` được tính là sai** khi tính accuracy, nhưng tỉ lệ abstain được báo cáo riêng.
- **Mỗi báo cáo ghi lại** cấu hình, số mẫu và mã băm của `labels.jsonl` đã dùng.
- **Kết quả không cải thiện cũng được ghi lại** trong `docs/reports/`.

## Cấu trúc

```
config.toml                 loại lỗi, runbook, repo cần tải, thông số cắt log, split, TF-IDF, LLM
ci_classifier/
  __main__.py               CLI: python -m ci_classifier <lệnh>
  fetch.py, logchunks.py    thu thập log -> data/raw/, data/manifest.jsonl
  baselines.py              tải lần chạy thành công gần nhất (cho profile "diff")
  excerpt.py, excerpt_eval.py  cắt log và đo chất lượng đoạn cắt
  label.py, split.py        gán nhãn, chia train/test theo nhóm
  agreement.py, panel.py    kiểm tra nhãn: Cohen's kappa, hội đồng LLM, Fleiss' kappa
  rules.py                  phương pháp 1: luật regex
  tfidf.py, tune_tfidf.py   phương pháp 2: TF-IDF + logistic regression và chọn ngưỡng
  llm.py                    phương pháp 3: LLM qua OpenRouter, có lưu câu trả lời
  methods.py                tạo bộ phân loại theo tên, gồm cả hybrid
  classify.py, demo.py      phân loại một log (CLI) và bản demo trên trình duyệt
  evaluate.py, stats.py, crossval.py  metrics, bootstrap CI, McNemar, cross-validation
  triage.py                 đo thời gian triage của người
  templates/                mẫu báo cáo Jinja2
docs/
  labeling-guide.md         định nghĩa nhãn
  runbooks/                 runbook mẫu cho từng loại lỗi
  reports/                  báo cáo các thí nghiệm
results/                    báo cáo sinh ra bởi evaluate
tests/                      pytest; regression_cases.jsonl là các log thật phải được phân loại đúng
```

## Hạn chế và hướng tiếp theo

- Mới hỗ trợ định dạng log của GitHub Actions và Travis CI; chưa có adapter cho GitLab CI hay Azure DevOps.
- Chưa có bước che thông tin nhạy cảm trước khi gửi log lên LLM.
- Chỉ có một người gán nhãn; cần thêm người thứ hai gán mù để kiểm tra độ tin cậy của nhãn.
- Cần thêm mẫu GitHub Actions, đặc biệt cho loại `infrastructure` và `authentication`.

## Giấy phép

Mã nguồn phát hành theo giấy phép [MIT](LICENSE). Bộ dữ liệu LogChunks thuộc giấy phép CC BY 4.0 của các tác giả gốc. Log GitHub Actions thuộc về các repo tương ứng.
