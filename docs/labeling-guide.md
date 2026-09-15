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

## Gán nhãn mù (kiểm tra độ tin cậy của nhãn)

Nhãn hiện tại do Claude gán nháp rồi được duyệt khi đã thấy nhãn nháp. Gán mù đo xem nhãn đó có đứng vững không,
khi không có người thứ hai.

```powershell
python -m ci_classifier label --blind --labeler <tên> --count 80   # dừng bằng q, chạy lại để làm tiếp
python -m ci_classifier agreement --labeler <tên>                  # kappa, ma trận nhầm, độ thiên vị của từng phương pháp
python -m ci_classifier label --adjudicate --labeler <tên>         # chốt nhãn cuối cho các mẫu bất đồng
```

Quy tắc:

1. **Không mở `data/labels.jsonl`, báo cáo `results/` hay `predictions.csv`** trong lúc gán mù.
   Nên để ít nhất vài ngày sau lần duyệt nhãn trước, để không nhớ đáp án.
2. Công cụ chọn cố định 80 mẫu test theo thứ tự ngẫu nhiên. Mỗi đoạn lỗi LogChunks giống hệt nhau chỉ lấy 1 mẫu.
   Không chọn mẫu theo cảm tính, nếu không kappa sẽ bị lệch.
3. Dùng đúng các quy tắc ở trên. Không chắc thì bấm `s`: mẫu được ghi là "không rõ" và không tính vào kappa.
4. Nhãn mù ghi vào `data/blind_labels.jsonl`, **không đổi nhãn đang dùng để chấm điểm**.
   Chỉ bước `--adjudicate` mới ghi nhãn cuối vào `labels.jsonl`, với ghi chú `adjudicated by <tên>: draft=..., blind=...`.
5. Khi phân xử, hai nhãn được hiện theo thứ tự ngẫu nhiên, không cho biết nhãn nào của Claude. Có thể chọn một nhãn thứ ba.

Cách đọc Cohen's kappa: dưới 0.6 là yếu, 0.6–0.8 là khá, trên 0.8 là tốt. Nếu phương pháp LLM khớp với nhãn nháp nhiều
hơn hẳn so với nhãn mù (p nhỏ trong bảng của `agreement`), điểm LLM trước đây đã được nhãn nháp nâng lên.

**Tốc độ:** một log CI không thể đọc trong vài giây. Nên dành 20–60 giây mỗi mẫu (log GitHub Actions lâu hơn).
`agreement` cảnh báo nếu trung vị dưới 15 giây. Khi đó kết quả đo độ vội nhiều hơn chất lượng nhãn.

**Làm lại một vòng:** dùng tên mới, ví dụ `--labeler HuyHoangTran-r2`. Công cụ đưa ra cùng 80 mẫu, và vòng cũ vẫn được
giữ để báo cáo. Trước vòng mới, **không mở** `results/*-agreement/disagreements.csv`, vì file đó chứa nhãn nháp.

Vòng 1 (15/09/2026, `HuyHoangTran`): 80 mẫu trong 8.8 phút, trung vị 6 giây mỗi mẫu, kappa 0.25. Trong 41 mẫu bất đồng,
18 mẫu có dòng log ghi rõ loại của nhãn nháp (ví dụ `AssertionError`, `1 failing`) nhưng không có dấu hiệu nào của nhãn
mù; chỉ 2 mẫu ngược lại. Vì vậy vòng này được ghi nhận là **gán quá nhanh**, không dùng để kết luận về chất lượng nhãn nháp.

Hạn chế: người gán mù cũng là người đã duyệt nhãn nháp, nên vẫn có thể nhớ một phần. Kết quả này là cận trên của mức
đồng thuận thật; ghi rõ điều đó khi báo cáo.

Nếu thấy quy tắc nào nên sửa, hãy sửa file này **trước**, rồi dùng `--relabel` cho các mẫu bị ảnh hưởng,
và ghi lại thay đổi trong báo cáo cuối.
