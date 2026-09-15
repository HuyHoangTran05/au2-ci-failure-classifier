# Session handoff - 15/09/2026

Tài liệu bàn giao để một phiên làm việc mới (người hoặc Claude Code) tiếp tục dự án mà không cần đọc lại lịch sử chat.
Đọc kèm `CLAUDE.md` (quy ước) và `README.md` (cách dùng).

## 1. Bối cảnh

- **Người thực hiện:** Trần Huy Hoàng (thực tập AI, VSF). Đề bài gốc: `D:\VSF_TT\ASSIGNMENT.md`.
- **Dự án chính được giao:** #3 *Application Insights incident triage agent* - **chưa bắt đầu**, vì chưa có máy công ty
  và quyền truy cập dữ liệu nội bộ DMS.
- **Đang làm:** side project **AU2 - CI failure classifier** (mentor đã đồng ý), chỉ dùng log công khai.
  Kỹ năng dùng lại được cho dự án #3: gom/cắt log, phân loại bằng LLM, đánh giá precision/recall.
- **Repo:** https://github.com/HuyHoangTran05/au2-ci-failure-classifier (private), nhánh `main`.
- **Thư mục:** `D:\VSF_TT\au2-ci-failure-classifier`.
- **Commit cuối lúc bàn giao:** `88ef9a8` (máy và GitHub khớp, working tree sạch, pytest 63 pass + 1 xfail cố ý).

## 2. Trạng thái so với đề bài AU2

| Yêu cầu AU2 | Trạng thái |
| --- | --- |
| MVP: phân loại log job fail đã lưu và chỉ tới runbook (`classify`) | ✅ Xong |
| So sánh luật từ khóa, TF-IDF, LLM | ✅ Xong |
| Precision/recall theo loại, tỷ lệ abstain | ✅ Xong |
| Đo triage time | ❌ **Chưa** - công cụ `triage` có sẵn, cần người thật chạy |
| Runbook | ⚠️ Bản mẫu trong `docs/runbooks/`, chưa phải runbook DMS |
| Adapter `httpx` tải artifact CI | ⏸ Chưa làm (đề bài bảo làm sau khi bộ phân loại offline ổn) |

## 3. Số liệu chính (để khỏi phải chạy lại)

> **Cập nhật sau bàn giao (15/09/2026, chiều) - số liệu bên dưới đã cũ, dùng số trong khung này:**
> - Ngưỡng TF-IDF đổi từ 0.4 sang 0.2 (`tune-tfidf`, chỉ nhìn train); thêm phương pháp `hybrid` (LLM, TF-IDF khi LLM trả unknown).
> - Luật từ khóa được sửa trên train (npm, auth, lint, network). CI GitHub Actions chạy pytest.
> - LLM đã trả lời thêm 40 mẫu GitHub Actions trong train (tổng 444 câu trả lời).
> - Test 291 mẫu (`results/20260915-115444/`): luật 0.34, TF-IDF 0.57, LLM 0.71, hybrid 0.74.
> - Gán mù lượt 1 (`HuyHoangTran`): 80 mẫu trong 8.8 phút, kappa 0.25 → ghi nhận là gán quá nhanh, không dùng.
> - Hội đồng 3 LLM (`panel-run`, `panel-report`, `results/20260915-145737-panel/`): kappa với nhãn nháp 0.82–0.88,
>   Fleiss 0.87; 72 confirmed / 6 contested / 2 split. **8 mẫu chờ người dùng `label --adjudicate --panel`.**
>   Không cho người dùng xem `votes.csv` (có nhãn nháp) trước khi phân xử.
> - Báo cáo: `docs/reports/2026-09-15-tfidf-threshold-and-hybrid.md`, `docs/reports/2026-09-15-rules-ci-and-llm-train.md`.
> - **Việc tiếp theo, theo thứ tự:** (1) người dùng phân xử 8 mẫu hội đồng tranh cãi → `evaluate --cv 5`;
>   (2) `llm-run --split train --limit 40` mỗi ngày; (3) chỉ sau khi nhãn đã chốt mới làm prompt v2 hoặc thêm dữ liệu.
>   Đừng tinh chỉnh thêm trên tập test trước bước (1).

**Dữ liệu:** 944 mẫu có nhãn, **tất cả `labeler: human`** (926 nhãn nháp do Claude gán được người duyệt giữ nguyên
bằng `label --accept-drafts HuyHoangTran`, 18 nhãn duyệt từng mẫu). Nguồn: 194 GitHub Actions (164 lấy ngẫu nhiên,
30 lấy có mục tiêu `retrieval: targeted-auth`), 750 LogChunks (Travis CI). Chia 653 train / 291 test theo nhóm
(repo, workflow), phân tầng theo (nguồn, loại lỗi). Phân bố nhãn: other 328, test_assertion 325, dependency 114,
compilation 85, infrastructure 61, authentication 31.

**Tập test 291 mẫu** (`results/20260915-094355/`):

| Phương pháp | Accuracy [95% CI] | Macro F1 | Abstain |
| --- | --- | --- | --- |
| Luật từ khóa | 0.30 [0.19, 0.42] | 0.37 | 54% |
| TF-IDF + logistic regression | 0.23 [0.11, 0.34] | 0.16 | 73% |
| LLM `nvidia/nemotron-3-super-120b-a12b:free`, prompt `v1` | **0.71 [0.59, 0.80]** | **0.67** | 8% |

- McNemar: LLM > luật (p ≈ 2e-24), LLM > TF-IDF (p ≈ 3e-28), luật vs TF-IDF không khác biệt (p = 0.067).
- CV 5 lần: luật 0.27 ± 0.04, TF-IDF 0.21 ± 0.07, LLM 0.72 ± 0.07 (LLM chỉ 293 mẫu có câu trả lời).
- LLM yếu nhất ở `infrastructure` (F1 0.39, hay nhầm với `test_assertion`).

**Bước cắt log** (`docs/reports/2026-09-15-excerpt-improvement.md`):
- Đoạn cắt mặc định giữ trọn 446/797 (56%) đoạn lỗi LogChunks (con số 41% cũ là do lỗi so khớp, đã sửa).
- Profile thử nghiệm trên 62 mẫu GitHub Actions test, accuracy LLM: `default` 0.69, `wide80` 0.73, `diff` 0.74
  (McNemar p = 0.73 và 0.58 → chưa có ý nghĩa). `hints` kém hơn mặc định (kết quả âm tính).
- **Quyết định: giữ cách cắt mặc định.**

## 4. Tài liệu đã có

| File | Nội dung |
| --- | --- |
| `CLAUDE.md` | Quy ước dự án, lệnh, cách commit |
| `README.md` | Hướng dẫn cài đặt, quy trình, kết quả hiện tại |
| `docs/labeling-guide.md` | Định nghĩa 6 loại lỗi, quy tắc khi phân vân |
| `docs/reports/2026-09-15-label-review-and-statistics.md` | Bước 1-2: duyệt nhãn, CI, McNemar, CV |
| `docs/reports/2026-09-15-excerpt-improvement.md` | Bước 4: đo và thử các cách cắt log |
| `docs/pain-points.html` | Pain points + câu hỏi cho mentor. Bản xuất bản: https://claude.ai/code/artifact/9eb4923e-2ac8-4332-b4cf-e3fbe113d976 (riêng tư, chia sẻ qua menu Share) |

## 5. Môi trường và các lưu ý đã gặp

- **Python:** `.\.venv\Scripts\python.exe -m ci_classifier <lệnh>` (không cần activate). `gh` đã đăng nhập tài khoản `HuyHoangTran05`.
- **API key OpenRouter** ở `.env` (gitignore). ⚠️ Key này **đã bị dán vào chat** → nên thu hồi trên OpenRouter,
  tạo key mới và cập nhật `.env`. Không bao giờ in hay commit key.
- **Model miễn phí:** giới hạn lượt/phút và /ngày, đôi khi lỗi 429 upstream hoặc 502 quá tải; `llm-run` tự thử lại và
  chạy tiếp được. `google/gemma-4-31b-it:free` bị chặn upstream khi thử.
- **Máy ít RAM** (có lúc còn khoảng 350 MB): tiến trình nền dài từng bị hệ thống dừng. Chạy `llm-run --limit 40` theo đợt.
- **PowerShell 5.1** làm vỡ dấu nháy kép trong `git commit -m`: ghi message ra file UTF-8 không BOM rồi `git commit -F`.
- **Log GitHub Actions hết hạn nhanh:** nhiều run cũ trả "log not found" / HTTP 410.
- **Biến `CI_EXCERPT_PROFILE`** đổi thư mục đoạn cắt cho mọi lệnh; nhớ xoá sau khi dùng (`Remove-Item Env:\CI_EXCERPT_PROFILE`).
- **Dữ liệu tái tạo được, không có trong git:** `data/raw/`, `data/excerpts*/`, `data/baselines/`, `data/external/`.
  Máy khác cần chạy lại `fetch`, `import-logchunks`, `excerpt`, `fetch-baselines --labelled-only`
  (một số log cũ có thể đã hết hạn trên GitHub).
- **Người dùng muốn:** commit nhỏ, tách từng phần (code / dữ liệu / kết quả / docs), push sau mỗi commit;
  giải thích bằng tiếng Việt, rõ ràng; báo trung thực cả kết quả âm tính.

## 6. Việc cần làm tiếp (theo thứ tự ưu tiên)

### A. Để đóng AU2
1. **Đo triage time** - cần 1-2 người không tham gia gán nhãn:
   `python -m ci_classifier triage --participant <tên> --count 20 --method llm`, rồi `evaluate` (có mục Triage time).
2. **Báo cáo tổng kết cho mentor** gộp MVP, bảng so sánh có CI, triage time, pain points, hướng tiếp theo.

### B. Làm kết quả đáng tin hơn
3. Người thứ hai **gán mù** khoảng 50 mẫu test (không xem nhãn cũ) → Cohen's kappa. Chưa có công cụ; cần thêm chế độ gán mù và tính kappa.
4. **Thêm log GitHub Actions** (tập test mới có 62 mẫu) để thu hẹp CI và kiểm chứng profile `diff`.
5. `llm-run --split train` dần theo giới hạn ngày để CV của LLM phủ đủ mẫu.

### C. Engineering depth
6. **CI cho repo** (GitHub Actions chạy pytest) - nhanh, nên làm sớm.
7. **Bộ phân loại lai** luật (precision cao) → LLM, đường risk-coverage, kiểm tra độ tin cậy LLM tự khai (ECE).
8. **Prompt v2** few-shot với ví dụ lấy từ train (tăng `PROMPT_VERSION`), so sánh thêm 1-2 model miễn phí.
9. Cắt log: `diff` + cửa sổ rộng hơn; xử lý 64 job không có dấu lỗi.

### D. Khi có quyền DMS
10. Adapter log Azure DevOps / GitLab; che thông tin nhạy cảm trước khi gửi LLM; runbook thật; tự động hoá khi CI fail.

## 7. Câu hỏi đang chờ mentor

1. Log nội bộ DMS có được gửi lên LLM bên ngoài (OpenRouter) không?
2. CI của DMS chạy trên Azure DevOps hay GitLab; lấy log fail lịch sử ở đâu, lưu bao lâu?
3. Giữ 6 loại lỗi hay tách thêm (lint, docs build, cấu hình workflow)?
4. Tiêu chí "đạt": precision/recall tối thiểu, tỷ lệ `unknown` tối đa?
5. Runbook thật của DMS nằm ở đâu?

## 8. Kiểm tra nhanh khi bắt đầu phiên mới

```powershell
cd D:\VSF_TT\au2-ci-failure-classifier
git pull
git log --oneline -5
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ci_classifier            # danh sách lệnh
Get-ChildItem Env:\CI_EXCERPT_PROFILE -ErrorAction SilentlyContinue   # phải trống
```

Kỳ vọng: pytest 63 passed, 1 xfailed; `data/labels.jsonl` có 944 mẫu `human`; `data/llm_predictions.jsonl` có 404 câu trả lời.
