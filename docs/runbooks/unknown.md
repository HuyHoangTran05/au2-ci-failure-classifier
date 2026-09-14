# Runbook: unknown (bộ phân loại không chắc)

Bộ phân loại chủ động không đoán. Việc này có chủ đích: đoán sai còn tốn thời gian hơn.

1. Mở run trên CI và tìm bước **đầu tiên** bị fail.
2. Đọc khoảng 50 dòng trước dấu lỗi đầu tiên, rồi dùng bảng dấu hiệu trong `docs/labeling-guide.md`.
3. Khi đã biết nguyên nhân, làm theo runbook tương ứng.
4. **Giúp bộ phân loại tốt hơn:** thêm dòng lỗi quyết định vào `tests/regression_cases.jsonl` (đặt `known_gap: true` nếu luật chưa bắt được), để lần sau có thể sửa luật.
