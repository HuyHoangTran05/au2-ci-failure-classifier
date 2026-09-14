# Hướng dẫn gán nhãn

Mục tiêu: với mỗi lần chạy CI bị fail, trả lời câu hỏi **"vì sao nó fail?"** bằng đúng một nhãn.
Nhãn phải nhất quán, vì đây là đáp án dùng để chấm điểm các bộ phân loại.

## Các nhãn

| Nhãn | Khi nào dùng | Dấu hiệu thường gặp |
| --- | --- | --- |
| `compilation` | Code không biên dịch hoặc không type-check được | `error CS1002`, `error TS2345`, `file.c:10: error:`, `SyntaxError`, `undefined reference` |
| `test_assertion` | Code build được nhưng test cho kết quả sai | `Assert.Equal() Failure`, `AssertionError`, `3 failing`, `--- FAIL:`, snapshot không khớp |
| `dependency` | Không cài, tải hoặc giải quyết được thư viện/gói | `npm ERR! ERESOLVE`, `NU1101 Unable to find package`, `No matching distribution`, `ModuleNotFoundError` |
| `authentication` | Thiếu hoặc sai quyền, token, secret | `401 Unauthorized`, `403`, `Bad credentials`, `AADSTS...`, `Resource not accessible by integration` |
| `infrastructure` | Máy chạy CI hoặc mạng có vấn đề, không phải lỗi code | `No space left on device`, runner mất kết nối, bị huỷ do quá thời gian, `ECONNRESET`, 502/503 |
| `other` | Nguyên nhân rõ ràng nhưng không thuộc các nhóm trên | lint/format, kiểm tra nhãn PR, lỗi build tài liệu, kiểm tra chính sách |

## Quy tắc khi phân vân

1. **Chọn nguyên nhân gốc, không chọn hậu quả.** Thiếu package làm build hỏng và test không chạy được
   thì nhãn là `dependency`, không phải `compilation`.
2. **Bỏ qua job tổng hợp.** Các job như "All required checks pass", "Final Results" chỉ báo rằng job khác
   đã fail. Hãy nhìn vào job fail thật sự.
3. **Nhiều job fail vì nhiều lý do khác nhau:** chọn nguyên nhân của job fail quan trọng nhất (thường là
   build hoặc test chính), và ghi `mixed` vào ghi chú.
4. **Test fail vì gọi mạng hoặc dịch vụ ngoài bị lỗi** (ví dụ `ECONNREFUSED` khi test kết nối trình duyệt):
   nếu lỗi nằm ở môi trường, không phải logic đang được test, thì dùng `infrastructure`, ghi chú `flaky?`.
   Nếu không chắc, dùng `test_assertion` và ghi chú lý do.
5. **Test bị timeout:** một test cụ thể chạy quá lâu thì là `test_assertion`; cả job bị huỷ vì hết giờ thì là `infrastructure`.
6. **Đoạn log cắt ra không đủ để quyết định:** bấm `o` để mở run trên GitHub. Vẫn không rõ thì bấm `s`
   để bỏ qua. Không đoán bừa.
7. **Không nhìn kết quả của bộ phân loại khi gán nhãn.** Công cụ gán nhãn cố tình không hiện dự đoán.

## Mẫu LogChunks (Travis CI)

- Công cụ hiện **đoạn log mà tác giả LogChunks đã đánh dấu là nguyên nhân**. Thường chỉ cần đọc đoạn này.
  Nếu chưa đủ để quyết định, bấm `e` để xem đoạn log đầy đủ.
- Đoạn đánh dấu cho biết *chỗ nào* lỗi, không cho biết *loại lỗi*. Vẫn áp dụng các quy tắc ở trên.
- Khi bạn gán nhãn một mẫu, các mẫu chưa gán có **đoạn lỗi giống hệt** sẽ được gán cùng nhãn, với ghi chú
  `auto: same chunk as ...`. Không muốn vậy thì chạy với `--no-propagate`.
- Lỗi kiểu `Line longer than 80 characters`, kiểm tra kích thước package... thuộc `other`.

Nếu thấy quy tắc nào nên sửa, hãy sửa file này **trước**, rồi dùng `--relabel` cho các mẫu bị ảnh hưởng,
và ghi lại thay đổi trong báo cáo cuối.
