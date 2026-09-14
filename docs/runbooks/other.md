# Runbook: other

**Dấu hiệu:** lint/format, kiểm tra nhãn PR, build tài liệu, kiểm tra chính sách.

1. Đọc tên job hoặc bước bị fail. Nhóm này thường tự giải thích.
2. Lint/format: chạy công cụ đó trên máy (thường có lệnh tự sửa), rồi commit lại.
3. Kiểm tra nhãn hoặc chính sách PR: làm theo thông báo trong log (thêm nhãn, ký CLA...).
4. Build tài liệu: tìm dòng lỗi của công cụ build tài liệu (Sphinx, DocFX...) và xem file tài liệu vừa sửa.
5. Nếu cùng một kiểu lỗi "other" lặp lại nhiều lần, hãy đề xuất tạo **loại lỗi mới** trong `docs/labeling-guide.md`.

> Runbook mẫu cho dữ liệu công khai. Khi có quyền, thay link trong `config.toml` bằng runbook thật trong DMS_DOCS.
