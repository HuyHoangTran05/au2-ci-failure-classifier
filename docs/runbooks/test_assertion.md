# Runbook: test_assertion

**Dấu hiệu:** `Assert.Equal() Failure`, `AssertionError`, `N failing`, `--- FAIL:`, snapshot không khớp.

1. Ghi lại **tên test** và giá trị **expected / actual**.
2. Test này fail ở nhánh chính gần đây chưa? Nếu fail lúc có lúc không, nghi **flaky test**: ghi chú lại, đừng chạy lại cho đến khi xanh rồi coi như xong.
3. Chạy riêng test đó trên máy với cùng commit.
4. Quyết định: **code sai** (sửa code) hay **kỳ vọng của test đã lỗi thời** (sửa test, giải thích lý do trong PR).
5. Với snapshot test: chỉ cập nhật snapshot khi đã chắc thay đổi là cố ý.

**Chuyển cho người khác khi:** test phụ thuộc dịch vụ ngoài hoặc dữ liệu dùng chung (có thể là `infrastructure`).

> Runbook mẫu cho dữ liệu công khai. Khi có quyền, thay link trong `config.toml` bằng runbook thật trong DMS_DOCS.
