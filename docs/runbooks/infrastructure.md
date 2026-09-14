# Runbook: infrastructure

**Dấu hiệu:** `No space left on device`, runner mất kết nối hoặc bị tắt, job bị huỷ do hết giờ, `ECONNRESET`, 502/503.

1. Cùng thời điểm, các job hoặc repo khác có fail giống vậy không? Nếu có thì gần như chắc chắn là hạ tầng.
2. Kiểm tra trang trạng thái của nhà cung cấp CI (GitHub Status, Azure DevOps Status).
3. Hết dung lượng hoặc bộ nhớ: xem bước nào tạo nhiều dữ liệu, dọn cache, hoặc dùng runner lớn hơn.
4. Chạy lại **một lần**. Ghi lại cả lần fail đầu tiên, đừng để lần chạy lại thành công xoá mất bằng chứng.
5. Nếu chạy lại vẫn fail cùng lỗi, xem lại phân loại: có thể là lỗi code (ví dụ test treo).

**Chuyển cho người khác khi:** runner tự quản lý (self-hosted) bị lỗi, hoặc sự cố kéo dài trên toàn hệ thống.

> Runbook mẫu cho dữ liệu công khai. Khi có quyền, thay link trong `config.toml` bằng runbook thật trong DMS_DOCS.
