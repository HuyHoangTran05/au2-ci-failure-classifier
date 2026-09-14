# Runbook: compilation

**Dấu hiệu:** `error CS####`, `error TS####`, `file.c:10: error:`, `SyntaxError`, `Build FAILED`.

1. Tìm **dòng lỗi đầu tiên** (không phải dòng cuối). Các lỗi sau thường là hệ quả của lỗi đầu.
2. Mở commit hoặc PR gây fail. File và dòng trong thông báo lỗi có nằm trong phần vừa sửa không?
3. Build lại trên máy với **đúng phiên bản SDK/compiler** mà CI dùng (xem bước setup trong log).
4. Nếu trên máy build được mà CI không được: so sánh phiên bản SDK, cờ build (`-Werror`, `TreatWarningsAsErrors`) và file bị sinh tự động.
5. Sửa, đẩy commit, xác nhận CI xanh.

**Chuyển cho người khác khi:** lỗi nằm trong code sinh tự động hoặc SDK của bên thứ ba.

> Runbook mẫu cho dữ liệu công khai. Khi có quyền, thay link trong `config.toml` bằng runbook thật trong DMS_DOCS.
