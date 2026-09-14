# Runbook: dependency

**Dấu hiệu:** `npm ERR!`, `ERESOLVE`, `NU1101 Unable to find package`, `No matching distribution found`, `ModuleNotFoundError`.

1. Xác định **gói nào** và **phiên bản nào** không cài được.
2. Commit này có sửa file khai báo thư viện không (`package.json`, lock file, `*.csproj`, `requirements.txt`)?
3. Kiểm tra gói hoặc phiên bản đó còn tồn tại trên registry (npm, NuGet, PyPI) không, và có bị gỡ không.
4. Nếu registry là nguồn nội bộ: kiểm tra CI có quyền truy cập nguồn đó không. Nếu lỗi là 401/403 thì chuyển sang runbook `authentication`.
5. Cập nhật lock file hoặc ghim phiên bản, rồi chạy lại.

**Chuyển cho người khác khi:** registry nội bộ bị lỗi, hoặc cần nâng phiên bản ảnh hưởng nhiều dự án.

> Runbook mẫu cho dữ liệu công khai. Khi có quyền, thay link trong `config.toml` bằng runbook thật trong DMS_DOCS.
