# Nhật ký chạy

Mọi lần chạy đều trên máy local Apple M1 (CPU), Python 3.12.0, ngày 2026-11-14.

## Môi trường và sự cố

- **pgvector không chạy được.** Lệnh `docker compose -p day6_student_starter up -d --wait` (image `pgvector/pgvector:0.8.7-pg16`) **thất bại**, đã thử lại 2 lần, với lỗi:
`Get "https://registry-1.docker.io/v2/": net/http: request canceled while waiting for connection (Client.Timeout exceeded while awaiting headers)`
Bản thân máy vẫn kết nối được registry (curl trả HTTP 401). Phần bị timeout là proxy của Docker Desktop (`http.docker.internal:3128`). Máy cũng không có sẵn image pgvector.
- **Phương án dự phòng:** **Chroma 1.5.9 PersistentClient**, được GUIDE/CHECKPOINTS cho phép.
  - Dữ liệu lưu trên đĩa tại `vectordb/chroma/`.
  - Metric cosine, chỉ mục HNSW với ef_construction=200, ef_search=200, M=32.
  - Đây là approximate search. Mỗi collection có tối đa 451 vector và ef_search=200, nên kết quả có lẽ gần với exact search, nhưng chưa đo riêng.

- Model embedding được nạp offline (`HF_HUB_OFFLINE=1`) từ snapshot đã cache, revision cố định.

## Thay đổi trước khi chấm điểm (chưa xem điểm truy xuất nào)

Lần ingest đầu tiên cho thấy B có chunk chỉ dài 20 ký tự: heading trơ ở cuối đơn vị và các mảnh đuôi. Hai sửa đổi:

1. Đơn vị không còn kết thúc bằng một heading trơ.
2. B gộp mảnh dưới 200 ký tự vào chunk trước cùng section (`min_size=200`).

Số đơn vị giảm từ 107 xuống 105. Mọi trang gold giữ nguyên (đã kiểm chứng lại bằng `verify-benchmark`).

## Các lệnh đã chạy (theo thứ tự)

```
python -m src.run manifest
python -m src.run verify-benchmark
python -m src.run ingest
python -m src.run reload-check
python -m src.run evaluate --split dev
# -> ghi lựa chọn bên dưới, sau đó mới chạy:
python -m src.run evaluate --split test
python -m src.run samples
```

## Kết quả dev và lựa chọn (ghi TRƯỚC khi chạy test)

| Chiến lược | Hit@1 dev | Evidence Hit@3 dev |
|---|---|---|
| A | 13/19 | 15/19 |
| B | 10/19 | 15/19 |
| C | 10/19 | 15/19 |

Theo quy tắc trong `benchmark/README.md`: ba chiến lược hòa ở Hit@3 dev, nên xét tiếp Hit@1 dev, và **A thắng (13/19)**.

**Chiến lược được chọn: A** (cố định 500 ký tự, overlap 50). Không tham số nào bị thay đổi sau khi xem dev.

## Kết quả test (chạy sau khi đã chọn)

| Chiến lược | Hit@1 test | Evidence Hit@3 test | Tuân thủ filter (test) |
|---|---|---|---|
| A | 2/6 | 6/6 | 1/2 |
| B | 4/6 | 6/6 | 1/2 |
| C | 4/6 | 6/6 | 2/2 |

Chiến lược được chọn trên dev (A) có Hit@1 test thấp nhất. Không có gì được chỉnh lại sau khi xem test.

## File chấm thủ công

- `manual_coherence.csv`: 10 vị trí × 3 chiến lược. Các vị trí được cố định trong `run.py:COHERENCE_POSITIONS` trước khi chấm.
- `manual_metadata.csv`: 6 câu test × top-3 × 3 chiến lược.
  - Các trường bắt buộc được script đối chiếu với đơn vị nguồn: text nằm đúng tại offset của trang, cùng với `document_id`, `page`, URL `source` và `doc_type`.
  - Nhãn `section` được đọc kiểm tra thêm bằng tay.
- `manual_grounding.csv`: 6 câu test × 3 chiến lược, đọc toàn văn top-3.
- **Người chấm:** tác giả, soạn với hỗ trợ của Claude Code từ toàn văn trace. Nguy cơ thiên lệch: người chấm cũng là người xây pipeline và đã thấy chỉ số.

Về cột `ms_per_query`: trong mỗi lần evaluate, chiến lược A chạy đầu tiên nên thời gian của A bao gồm cả warm-up. Các giá trị này không dùng để so sánh độ trễ được.
