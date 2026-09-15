# CLAUDE.md

Hướng dẫn cho Claude Code (và người mới) khi làm việc trong repo này.

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
.\.venv\Scripts\python.exe -m ci_classifier llm-run --limit 40
.\.venv\Scripts\python.exe -m ci_classifier evaluate --cv 5   # báo cáo -> results/<thời gian>/
.\.venv\Scripts\python.exe -m ci_classifier classify job.log --method rules|tfidf|llm
```

## Cấu trúc

| Đường dẫn | Vai trò |
| --- | --- |
| `ci_classifier/__main__.py` | CLI; lệnh mới phải thêm vào `COMMANDS` (và `MODULES` nếu tên module khác tên lệnh) |
| `fetch.py`, `logchunks.py` | thu thập log -> `data/raw/*.log.gz`, `data/manifest.jsonl` |
| `excerpt.py` | cắt log thành đoạn quan trọng; **cả 3 phương pháp chỉ nhìn thấy đoạn cắt** |
| `label.py`, `split.py` | nhãn (`data/labels.jsonl`), chia train/test theo nhóm (repo, workflow) |
| `rules.py`, `tfidf.py`, `llm.py`, `methods.py` | 3 bộ phân loại; `build_predictor` là điểm vào chung |
| `evaluate.py`, `stats.py`, `crossval.py` | metrics (pandas), bootstrap CI theo nhóm, McNemar, CV; báo cáo Jinja2 `templates/report.md.j2` |
| `config.toml` | loại lỗi, runbook, thông số cắt log, split, TF-IDF, LLM, evaluation |
| `docs/` | hướng dẫn gán nhãn, runbook mẫu, báo cáo, trang pain points |
| `tests/` | pytest; `regression_cases.jsonl` = log thật luật regex phải phân loại đúng |

## Quy ước dữ liệu (quan trọng)

- File `.jsonl` trong `data/` là **append-only**: bản ghi sau cùng của cùng `sample_id` thắng. Không sửa/xoá dòng cũ
  (trừ `llm-run --reparse`, chỉ đọc lại câu trả lời đã lưu).
- `labels.jsonl` có `labeler` (`human` / `claude-draft`); giữ nguyên nguồn gốc nhãn khi báo cáo.
- `data/raw/`, `data/excerpts/`, `data/external/` tái tạo được và bị gitignore. `manifest`, `labels`, `split`,
  `llm_predictions` là công sức thật, phải commit.
- Profile cắt log: `CI_EXCERPT_PROFILE=<tên>` áp `[excerpt.profiles.<tên>]` và đọc/ghi `data/excerpts-<tên>/`;
  `evaluate` gắn tên profile (và `--source`) vào thư mục kết quả. Nhớ xoá biến môi trường sau khi dùng.
- LLM: câu trả lời lưu theo (model, `PROMPT_VERSION`, mã băm đoạn cắt). Đổi prompt thì tăng `PROMPT_VERSION`;
  đổi cách cắt log thì câu trả lời cũ không còn khớp và phải chạy lại `llm-run`.

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
