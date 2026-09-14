# Runbook: authentication

**Dấu hiệu:** `401 Unauthorized`, `403`, `Bad credentials`, `AADSTS…`, `Resource not accessible by integration`.

1. Xác định bước nào cần xác thực: tải package, đăng nhập cloud, đẩy image, gọi API.
2. **PR từ fork?** Fork thường không được đọc secret, nên lỗi này có thể là hành vi đúng. Hãy ghi chú lại.
3. Kiểm tra secret, token hoặc service connection: còn hạn không, có bị đổi tên không, còn đủ quyền không.
4. Lỗi `AADSTS…`: tra mã lỗi và kiểm tra cấu hình federated credential (subject, audience, issuer).
5. **Không bao giờ** in secret ra log để debug.

**Chuyển cho người khác khi:** cần cấp mới hoặc xoay vòng (rotate) credential. Việc này thuộc người quản lý quyền.

> Runbook mẫu cho dữ liệu công khai. Khi có quyền, thay link trong `config.toml` bằng runbook thật trong DMS_DOCS.
