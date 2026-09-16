# CLAUDE.md

Hướng dẫn cho Claude Code (và người mới) khi làm việc trong repo này.

**Bắt đầu phiên mới:** đọc `README.md` (kết quả hiện tại) và báo cáo mới nhất trong `docs/reports/`.

## Dự án

AU2 - phân loại lỗi CI (intern project VSF, mentor: xem `../ASSIGNMENT.md`). Đọc log của một job CI bị fail,
trả về loại lỗi (`compilation`, `test_assertion`, `dependency`, `authentication`, `infrastructure`, `other`,
hoặc `unknown`), dòng bằng chứng và runbook. So sánh 3 phương pháp: luật regex, TF-IDF + logistic regression, LLM.

Dữ liệu chỉ là log **công khai** (GitHub Actions + bộ LogChunks của Travis CI). Không đưa dữ liệu nội bộ DMS vào repo
và không gửi log nội bộ lên LLM bên ngoài khi chưa có mentor đồng ý.

## Môi trường

- Windows, PowerShell. Python trong `.venv`: gọi `.\.venv\Scripts\python.exe -m ...` (không cần activate).
- `gh` CLI đã đăng nhập (dùng cho `fetch`).
- API key OpenRouter nằm trong `.env` (`OPENROUTER_API_KEY`), đã gitignore. **Không bao giờ in, ghi vào file khác hay commit key.**
- Máy ít RAM: tránh chạy nền việc dài; chạy `llm-run --limit 40` theo từng đợt.

## Lệnh thường dùng

```powershell
.\.venv\Scripts\python.exe -m pytest -q                       # toàn bộ test, phải xanh trước khi commit
.\.venv\Scripts\python.exe -m ci_classifier                   # danh sách lệnh
.\.venv\Scripts\python.exe -m ci_classifier fetch             # tải log run fail (gh)
.\.venv\Scripts\python.exe -m ci_classifier excerpt [--force] # cắt log -> data/excerpts/
.\.venv\Scripts\python.exe -m ci_classifier excerpt-eval      # độ phủ đoạn lỗi LogChunks (--set key=value để thử)
.\.venv\Scripts\python.exe -m ci_classifier fetch-baselines --labelled-only --workers 4
.\.venv\Scripts\python.exe -m ci_classifier label --review    # duyệt nhãn nháp
.\.venv\Scripts\python.exe -m ci_classifier label --blind --labeler <tên>   # người gán mù; Claude không tự gán
.\.venv\Scripts\python.exe -m ci_classifier agreement          # kappa nhãn mù vs nháp, thiên vị theo phương pháp
.\.venv\Scripts\python.exe -m ci_classifier label --adjudicate --labeler <tên>
.\.venv\Scripts\python.exe -m ci_classifier panel-run          # hội đồng 3 LLM (config [panel]) gán lại 80 mẫu lượt mù
.\.venv\Scripts\python.exe -m ci_classifier panel-report       # đồng thuận + danh sách cho label --adjudicate --panel
.\.venv\Scripts\python.exe -m ci_classifier llm-run --limit 40
.\.venv\Scripts\python.exe -m ci_classifier evaluate --cv 5   # báo cáo -> results/<thời gian>/
.\.venv\Scripts\python.exe -m ci_classifier tune-tfidf         # chọn [tfidf] abstain_below bằng CV trên train
.\.venv\Scripts\python.exe -m ci_classifier classify job.log --method rules|tfidf|llm|hybrid
```

## Cấu trúc

| Đường dẫn | Vai trò |
| --- | --- |
| `ci_classifier/__main__.py` | CLI; lệnh mới phải thêm vào `COMMANDS` (và `MODULES` nếu tên module khác tên lệnh) |
| `fetch.py`, `logchunks.py` | thu thập log -> `data/raw/*.log.gz`, `data/manifest.jsonl` |
| `excerpt.py` | cắt log thành đoạn quan trọng; **cả 3 phương pháp chỉ nhìn thấy đoạn cắt** |
| `label.py`, `split.py` | nhãn (`data/labels.jsonl`), chia train/test theo nhóm (repo, workflow) |
| `agreement.py` | nhãn mù so với nhãn nháp: kappa (bootstrap theo nhóm), độ thiên vị theo phương pháp, hàng đợi phân xử |
| `rules.py`, `tfidf.py`, `llm.py`, `methods.py` | 3 bộ phân loại + `hybrid` (LLM, TF-IDF khi LLM trả unknown); `build_predictor` là điểm vào chung |
| `tune_tfidf.py` | chọn ngưỡng abstain TF-IDF bằng CV trên train (không đọc test) |
| `evaluate.py`, `stats.py`, `crossval.py` | metrics (pandas), bootstrap CI theo nhóm, McNemar, CV; báo cáo Jinja2 `templates/report.md.j2` |
| `config.toml` | loại lỗi, runbook, thông số cắt log, split, TF-IDF, LLM, evaluation |
| `docs/` | hướng dẫn gán nhãn, runbook mẫu, báo cáo, trang pain points |
| `tests/` | pytest; `regression_cases.jsonl` = log thật luật regex phải phân loại đúng |

## Quy ước dữ liệu (quan trọng)

- File `.jsonl` trong `data/` là **append-only**: bản ghi sau cùng của cùng `sample_id` thắng. Không sửa/xoá dòng cũ
  (trừ `llm-run --reparse`, chỉ đọc lại câu trả lời đã lưu).
- `labels.jsonl` có `labeler` (`human` / `claude-draft`); giữ nguyên nguồn gốc nhãn khi báo cáo.
- `blind_labels.jsonl`: nhãn gán mù (label `null` = không rõ), không bao giờ ghi đè `labels.jsonl`. Chỉ `label --adjudicate`
  ghi nhãn cuối (note `adjudicated by ...`). Claude không được tạo nhãn mù thay người, và không hiện nhãn hay dự đoán
  cho người đang gán mù.
- `panel_labels.jsonl`: câu trả lời của hội đồng LLM, khoá (model, `PANEL_PROMPT_VERSION`, mã băm đầu vào). Hội đồng không
  được thấy nhãn; `panel-run` không in so sánh với nhãn. Không dùng model của bộ phân loại (Nemotron) hay Claude trong hội đồng.
  Nhãn `confirmed` của hội đồng không phải nhãn người kiểm tra; báo cáo phải ghi rõ.
- `data/raw/`, `data/excerpts/`, `data/external/` tái tạo được và bị gitignore. `manifest`, `labels`, `split`,
  `llm_predictions` là công sức thật, phải commit.
- Profile cắt log: `CI_EXCERPT_PROFILE=<tên>` áp `[excerpt.profiles.<tên>]` và đọc/ghi `data/excerpts-<tên>/`;
  `evaluate` gắn tên profile (và `--source`) vào thư mục kết quả. Nhớ xoá biến môi trường sau khi dùng.
- LLM: câu trả lời lưu theo (model, phiên bản prompt, mã băm đoạn cắt). Phiên bản đang chấm điểm nằm ở `[llm] prompt_version`
  (v1 hoặc v2; `llm-run --prompt-version` để thử phiên bản khác). Đổi cách cắt log thì câu trả lời cũ không còn khớp
  và phải chạy lại `llm-run`. Prompt mới **chỉ được so sánh trên train**; v2 đã thử và không tốt hơn (xem báo cáo).

## Quy tắc đánh giá

- Không chỉnh luật, ngưỡng hay prompt khi đang nhìn tập test; chỉ nhìn train.
- Không chia lại `split.json` (`--force`) sau khi đã tinh chỉnh theo train, trừ khi ghi rõ lý do.
- Mẫu lấy có mục tiêu (`retrieval: targeted-*`) được báo cáo tách riêng.
- Báo cáo con số kèm khoảng tin cậy; ghi rõ khi LLM chỉ được chấm trên một phần mẫu.

## Code

- Code, comment, docstring, thông điệp CLI kỹ thuật: tiếng Anh. README, docs, hướng dẫn cho người dùng: tiếng Việt.
- Theo phong cách hiện có: hàm nhỏ, `from __future__ import annotations`, mỗi module có `main(argv)` và docstring usage.
- Mỗi tính năng mới có test trong `tests/`; không gọi mạng thật trong test (dùng fake opener/monkeypatch).

## Git

- Commit **nhỏ, tách theo từng phần** (code / dữ liệu / kết quả + docs) để dễ tìm lại; push sau mỗi commit.
- Nội dung commit tiếng Anh, dòng đầu ngắn gọn, kết thúc bằng dòng `Co-Authored-By`.
- PowerShell 5.1 làm vỡ dấu nháy kép trong `git commit -m`: ghi message ra file UTF-8 (không BOM) rồi `git commit -F <file>`.
