# Benchmark: truy xuất tài liệu Python

File `questions.json` chứa 25 câu hỏi, viết tay từ corpus đã chuẩn hóa **trước khi chạy truy xuất lần nào**.

| Split | Số câu | Có metadata filter |
|---|---:|---:|
| dev | 19 (q01–q19) | 3 (q17, q18, q19) |
| test | 6 (q20–q25) | 2 (q21, q22) |

Mỗi câu có các trường sau:

| Trường | Ý nghĩa |
|---|---|
| `id` | Mã câu hỏi |
| `split` | `dev` hoặc `test` |
| `type` | Loại câu: trực tiếp / diễn đạt lại / điều kiện / filter |
| `question` | Câu hỏi |
| `expected_answer` | Đáp án mong đợi |
| `gold_source_id` | Tài liệu chứa đáp án |
| `gold_page` | Số thứ tự đơn vị, xem `data/manifest.json` |
| `evidence_quote` | Câu trích nguyên văn làm bằng chứng |
| `filter` | Filter metadata, nếu có |
| `alternatives` | Các vị trí khác cũng chứa bằng chứng hợp lệ |

Câu hỏi viết bằng tiếng Anh vì corpus là tiếng Anh và evidence phải trích nguyên văn từ nguồn.

## Cách kiểm chứng evidence

Lệnh `python -m src.run verify-benchmark` chuẩn hóa từng quote và từng đơn vị nguồn: NFKC, chữ thường, gộp khoảng trắng, nối lại từ bị ngắt gạch nối cuối dòng. Sau đó lệnh này:

1. Yêu cầu quote phải xuất hiện trong tài liệu gold.
2. Điền `gold_page` bằng đơn vị chứa quote.
3. Ghi mọi đơn vị khác cũng chứa quote vào `alternatives`. Kết quả: không có đơn vị nào khác.
4. Kiểm tra đơn vị gold thỏa filter của câu hỏi.

Kết quả lưu ở `results/benchmark_verification.csv`. Tác giả cũng đọc lại từng đơn vị gold để chắc quote đủ hỗ trợ đáp án, kể cả điều kiện. Ví dụ: q03 về tuple làm key, q10 về `return` trong `finally`.

## Filter

Trường filter duy nhất là `doc_type`, nhận giá trị `tutorial` hoặc `howto`. Giá trị lấy từ đường dẫn URL docs.python.org (`/tutorial/…` hoặc `/howto/…`), nên là metadata đáng tin chứ không phải suy đoán.

Câu có filter bắt đầu bằng tiền tố ngữ cảnh, ví dụ `[Context: user is reading the HOWTO guides]`. Filter được coi là **input người dùng cung cấp trước khi truy xuất** (trang họ đang đọc), không suy ra từ đáp án gold.

Mỗi câu filter được chọn vì cùng chủ đề xuất hiện ở cả hai phạm vi, nên filter thực sự có tác dụng:
- Sorting có trong Tutorial §5 và trong Sorting HOWTO.
- Logging có trong Tutorial §11.5 và trong Logging HOWTO.

Giá trị `howto` bao 2 tài liệu, `tutorial` bao 7 tài liệu, nên filter không bao giờ chỉ thẳng ra tài liệu gold.

## Cách chia split và nguy cơ rò rỉ

Split chia theo **chủ đề** bên trong tài liệu, không theo tài liệu. Lý do: corpus chỉ có 9 tài liệu, và test cần có câu ở cả hai phạm vi.

Câu test dùng lại một số tài liệu đã có ở dev (howto-sorting, howto-logging, tut-datastructures, tut-stdlib2), nhưng hỏi về đơn vị và nội dung khác. Nguy cơ: chiến lược được chỉnh trên dev vẫn có thể hưởng lợi trên test nhờ tương đồng ở mức tài liệu. Trong bài này không tham số nào được chỉnh theo dev hay test. A, B và C được cố định trong `starter/src/config.py` trước lần chạy đầu tiên.

## Quy tắc chọn chiến lược (chốt trước khi chạy truy xuất)

1. Chọn chiến lược có **Evidence Hit@3 trên dev** cao nhất.
2. Nếu hòa, chọn chiến lược có Hit@1 trên dev cao hơn.
3. Nếu vẫn hòa, chọn chiến lược tốn ít tài nguyên hơn (ít chunk hơn, ingest nhanh hơn). Điểm grounding thủ công trên test chỉ được báo cáo, không dùng để chọn.

Chỉ số test chỉ được tính sau khi lựa chọn trên dev đã ghi vào `results/run_log.md`.
