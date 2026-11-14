# Day 06 · Data Ingestion Engineering

> ## Bài làm: Nguyễn Đức Hải (2A202603899)
>
> **Corpus:** Python 3.15 docs, gồm 7 chương Tutorial và 2 HOWTO (PSF License), 105 đơn vị ≥1.500 ký tự. **Model:** `paraphrase-multilingual-MiniLM-L12-v2`, chạy local, 384 chiều. **Store:** Chroma 1.5.9 persistent, cosine. pgvector không pull được image do lỗi proxy Docker, xem `results/run_log.md`.
> Báo cáo nằm ở [report/individual/2A202603899_NguyenDucHai.md](report/individual/2A202603899_NguyenDucHai.md).
>
> ```bash
> cd starter
> python3.12 -m venv .venv && source .venv/bin/activate
> pip install -r requirements.txt   # sentence-transformers, chromadb, ...
> python -m src.run manifest            # đọc + chuẩn hóa -> data/manifest.json, results/ingest_errors.log
> python -m src.run verify-benchmark    # kiểm chứng evidence -> results/benchmark_verification.csv
> python -m src.run ingest              # A, B, C -> vectordb/chroma, results/ingest_stats.json, chunks_*.jsonl
> python -m src.run reload-check        # nạp lại không trùng + giả lập tài liệu đổi -> results/reload_check.log
> python -m src.run evaluate --split dev
> python -m src.run evaluate --split test   # -> results/traces_*.jsonl, metrics_*.csv
> python -m src.run samples             # mẫu coherence (nhãn thủ công ở results/manual_*.csv)
> ```
>
> Lần đầu cần mạng để tải model. Code đặt `HF_HUB_OFFLINE=1` để dùng snapshot đã cache; nếu máy chưa có model, chạy với `HF_HUB_OFFLINE=0`.
>
> | Thư mục | Nội dung |
> |---|---|
> | `data/raw/python-docs-3.15/` | Corpus gốc và giấy phép |
> | `data/manifest.json` | Nguồn, quyền, ranh giới đơn vị |
> | `benchmark/` | 25 câu hỏi (19 dev / 6 test) và README về split, filter, tiêu chí chọn |
> | `starter/src/` | Pipeline |
> | `results/` | Trace, chỉ số, nhãn thủ công, log |
> | `artifacts/experiment_log.csv` | Nhật ký thí nghiệm A/B/C |
>
> Đề bài gốc giữ nguyên bên dưới.

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

Dùng [starter PostgreSQL + pgvector](starter/README.md) để dựng database và hoàn thiện các hàm TODO, hoặc tự chọn vector store tương đương. Starter chỉ là khung: **bạn tự hiện thực pipeline và benchmark**.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Phần xử lý và benchmark do bạn tự hiện thực; không bắt buộc xây chatbot.
