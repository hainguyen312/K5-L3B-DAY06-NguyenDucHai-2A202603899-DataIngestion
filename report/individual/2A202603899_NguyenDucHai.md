# Báo cáo cá nhân — Day 6

**Nguyễn Đức Hải — 2A202603899 — L3B.** Mọi số liệu dưới đây lấy từ lần chạy ngày 2026-11-14, file nguồn nằm trong `results/`.

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang.** Corpus là Python 3.15 documentation, bản plain-text (`python-3.15-docs-text.tar.bz2`, sha256 `5b2d847a…`, truy cập 2026-11-14). Chọn 9 tài liệu: 7 chương Tutorial (datastructures, modules, inputoutput, errors, venv, stdlib, stdlib2) và 2 HOWTO (sorting, logging). Giấy phép là **PSF License v2**; code mẫu dual-license PSF/0BSD. Bản sao giấy phép ở `data/raw/python-docs-3.15/LICENSE-python-docs.txt`. Corpus không có trang vật lý, nên theo GUIDE §1 mỗi tài liệu được chuẩn hóa rồi chia **theo thứ tự, tại ranh giới đoạn**, thành các đơn vị **≥1.500 ký tự**. Phần dư ngắn được gộp vào đơn vị trước, và không đơn vị nào kết thúc bằng một heading trơ. Kết quả: **105 đơn vị** (yêu cầu ≥30), 183.282 ký tự đã chuẩn hóa. `page` là số thứ tự đơn vị và `page_id = <source_id>#pNN`. Ranh giới, số ký tự và hash từng đơn vị có trong `data/manifest.json`.
- **Chuẩn hóa, lỗi và giới hạn.** Các bước chuẩn hóa: NFKC, CRLF→LF, tab→4 space, bỏ ký tự điều khiển, đổi heading kiểu RST (dòng gạch `===`/`---`/`***`) thành `# Tiêu đề`, gộp dòng trống. Thụt đầu dòng được giữ vì code mẫu cần nó. Log `results/ingest_errors.log` ghi 0 lỗi decode, 0 đơn vị rỗng, 0 đơn vị dưới 1.500 ký tự. Giới hạn: bảng ASCII lớn (ví dụ bảng logging level) không được xử lý riêng nên bị cắt theo dòng. Corpus là bản 3.15 nên một số chi tiết có thể khác bản 3.12/3.13.
- **Embedding, vector store, lệnh chạy và chi phí.** Model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` chạy local, revision `e8f8c211`, **384 chiều**, vector chuẩn hóa L2. Model đối xứng nên query và document không có prefix. `max_seq_length` nâng từ 128 lên **256** cho cả ba cấu hình: A không chunk nào bị cắt, B/C có 15/325 chunk vượt 256 token. Phiên bản thư viện: sentence-transformers 6.3.0, torch 2.15.0, CPU Apple M1. Vector store là **Chroma 1.5.9 PersistentClient** (`vectordb/chroma/`), mỗi chiến lược một collection, metric cosine, HNSW (ef_construction=200, ef_search=200, M=32). Đây là **approximate search**. pgvector là lựa chọn đầu tiên nhưng **không pull được image** (Docker Desktop proxy timeout tới registry-1.docker.io, chi tiết trong `results/run_log.md`), nên chuyển sang Chroma local theo phương án dự phòng trong GUIDE. Lệnh chạy xem `README.md`. Chi phí **0 USD** (không dùng API). Thời gian embed: A 8,5 s, B 6,4 s, C 6,4 s; nạp model khoảng 2–3 s.
- **Metadata và trường lọc.** Mỗi chunk có `document_id`, `source` (URL docs.python.org), `page`, `page_id`, `char_start`/`char_end` (vị trí trong đơn vị), `section` (heading đang hiệu lực ở đầu chunk), `title`, `version`, `content_hash`. Trường lọc là **`doc_type` ∈ {tutorial, howto}**. Giá trị lấy từ đường dẫn URL gốc (`/tutorial/` hoặc `/howto/`), nên là metadata đáng tin chứ không phải suy đoán. Trường này hữu ích vì hai phạm vi có chủ đề trùng nhau (sorting, logging), và người dùng thường biết mình đang đọc Tutorial hay HOWTO.

## Cấu hình và benchmark

- **A / B / C.** Tham số đặt trong `starter/src/config.py`:
  - **A:** cửa sổ ký tự cố định 500, overlap 50, cắt trong phạm vi từng đơn vị, không lọc.
  - **B:** gom nguyên đoạn đến tối đa 800 ký tự. Heading luôn mở chunk mới, đoạn quá dài được tách theo dòng hoặc câu, mảnh <200 ký tự được gộp vào chunk trước cùng section. Không lọc.
  - **C:** chunk **giống hệt B** (đã kiểm chứng text từng chunk bằng script), chỉ thêm `where doc_type = …` cho các câu có filter.

  B–C chỉ khác nhau ở filter. A–B khác nhau ở chunking.
- **Benchmark.** 25 câu (`benchmark/questions.json`), chia **19 dev / 6 test** trước khi chạy. Có 5 câu có filter: 3 câu dev (q17, q18, q19) và 2 câu test (q21, q22). Loại câu gồm trực tiếp, diễn đạt lại, điều kiện/ngoại lệ, và filter. Evidence được kiểm chứng tự động bằng `verify-benchmark`: mỗi quote nằm trong đúng 1 đơn vị của tài liệu gold, không có nguồn thay thế, và đơn vị gold thỏa filter (`results/benchmark_verification.csv`). Tác giả cũng đọc lại đơn vị gold. Filter được coi là ngữ cảnh người dùng cung cấp trước khi truy xuất (`[Context: user is reading …]`) và không chứa tên tài liệu gold.
- **Tiêu chí chọn, chốt trước khi xem test** (`benchmark/README.md`): (1) dev Evidence Hit@3 cao nhất; (2) nếu hòa thì dev Hit@1; (3) nếu vẫn hòa thì dùng ít tài nguyên hơn.

## Kết quả

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian ingest (chunk+embed+store) | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 13/19 | 15/19 | 451 | 8,8 s | 0 |
| B | dev | 10/19 | 15/19 | 325 | 6,6 s | 0 |
| C | dev | 10/19 | 15/19 | 325 | 6,7 s | 0 |
| A | test | 2/6 | 6/6 | 451 | — | 0 |
| B | test | 4/6 | 6/6 | 325 | — | 0 |
| C | test | 4/6 | 6/6 | 325 | — | 0 |

Chỉ số chẩn đoán phụ, page-only@3 (đúng trang nhưng chưa chắc đủ evidence) trên dev: A 17/19, B 15/19, C 15/19. Tổng ký tự được index: A 201.001 (có phần overlap), B/C 183.282.

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 0,9 (n=10; 0:1, 1:9, 2:0) | 18/18 | test 1/2 · dev 2/3 | 0/0/6 → 2,0 |
| B | 1,5 (n=10; 0:0, 1:5, 2:5) | 18/18 | test 1/2 · dev 2/3 | 0/0/6 → 2,0 |
| C | 1,5 (n=10; chunk giống B) | 18/18 | test 2/2 · dev 3/3 | 0/0/6 → 2,0 |

**Đường dẫn và cách chọn mẫu:**
- Trace đầy đủ (câu hỏi, chunk ID, text, score, metadata, nhãn evidence): `results/traces_dev.jsonl`, `results/traces_test.jsonl`. Chỉ số: `results/metrics_*.csv`.
- **Coherence:** `results/manual_coherence.csv`. 10 vị trí được cố định trong code trước khi chấm, gồm điểm giữa đơn vị `p02` của cả 9 tài liệu và điểm giữa `howto-logging#p10`. Mỗi vị trí chấm chunk chứa nó.
- **Metadata:** `results/manual_metadata.csv`, gồm 6 câu test × top-3 × 3 chiến lược. Các trường bắt buộc (`document_id`, `page`, `source`, `doc_type`) được đối chiếu với nguồn: text của chunk phải nằm đúng tại `char_start`/`char_end` của đơn vị.
- **Grounding:** `results/manual_grounding.csv`, đọc toàn văn top-3 của 6 câu test.
- **Nạp lại:** `results/reload_check.log`. Nạp lại 2 lần giữ nguyên số chunk (A 451, B 325). Khi giả lập tài liệu `tut-venv` mất đơn vị p04, upsert xóa đúng các chunk cũ (A 6, B 4) rồi khôi phục được.

## Phân tích và kết luận

- **A–B (thay chunking).** Trên dev, Evidence Hit@3 bằng nhau (15/19). A cao hơn ở Hit@1 (13 so với 10) và page-only@3 (17 so với 15): chunk 500 ký tự hẹp nên điểm cosine tập trung hơn. Trên test, xu hướng **đảo ngược**: B 4/6, A 2/6 ở Hit@1. Với N=6 và N=19, chênh lệch 2–3 câu nằm trong sai số mẫu, nên không kết luận được A hay B truy xuất tốt hơn. Khác biệt rõ là **coherence**: B 1,5/2 so với A 0,9/2. 9/10 chunk của A bắt đầu hoặc kết thúc giữa từ, và một chunk là mảnh bảng không có header. B cũng tốn ít tài nguyên hơn (325 so với 451 chunk, embed nhanh hơn khoảng 25%), đổi lại 15 chunk bị cắt ở 256 token.
- **B–C (thay filter).** Filter không đổi Hit@1/Hit@3 trên benchmark này, nhưng nâng tuân thủ phạm vi từ 2/3 lên 3/3 (dev) và từ 1/2 lên 2/2 (test). Ví dụ q22 (người dùng đang đọc Tutorial): B xếp hạng 1 là `howto-sorting#p01`, nằm ngoài phạm vi. C thay bằng chunk Tutorial và đưa evidence lên hạng 2. Metadata đúng 18/18 ở cả ba chiến lược. Hạn chế: `section` chỉ ghi heading ở **đầu** chunk. Với A, 4/18 bản ghi chứa thêm heading khác bên trong. Ví dụ `A:tut-stdlib2#p08:c01` mang nhãn "11.7. Tools for working with lists" nhưng evidence lại thuộc 11.8 Decimal. B tránh được lỗi này vì heading luôn mở chunk mới.
- **Ví dụ lỗi 1 — q14** (dev, `tut-stdlib#p01`, "Why should I write import os instead of from os import *?"). A tìm đúng trang ở hạng 2 (`A:tut-stdlib#p01:c00`), nhưng chunk dừng ở "…instead of "from os import *". This wi". Câu evidence "This will keep os.open() from shadowing the built-in open()…" bị cắt ngang ranh giới, nên tính là trượt Evidence Hit. B/C không đưa trang này vào top-3; hạng 1 là `tut-modules#p13` (mục "Importing * From a Package", cùng từ khóa `import *` nhưng khác ý). Đây là lỗi ranh giới của fixed-size cộng với nhiễu từ khóa trùng lặp.
- **Ví dụ lỗi 2 — q18** (dev, `tut-stdlib2#p05`, filter `tutorial`, "What does the logging module show by default…?"). A và B trả về chunk của Logging HOWTO, vi phạm phạm vi (B chỉ đúng ở hạng 1). C lọc đúng và hạng 1 thuộc đúng section "11.5. Logging", nhưng là nửa sau của section (`tut-stdlib2#p06`, phần cấu hình), trong khi câu "informational and debugging messages are suppressed…" nằm ở `#p05`. Filter loại được nhiễu ngoài phạm vi nhưng không sửa được việc section bị chia qua hai đơn vị.
- **Ví dụ lỗi 3 — q02** ("Can I use {}?"). A trúng ở hạng 1, còn B/C không đưa chunk về sets vào top-3. Model paraphrase-MiniLM biểu diễn ký hiệu như `{}` kém; chunk B dài hơn nên câu "empty set" bị pha loãng giữa các nội dung khác.
- **Chiến lược chọn, đánh đổi, điều kiện áp dụng.** Theo quy tắc đã chốt, **A được chọn** (hòa dev Hit@3, thắng dev Hit@1). Nhưng kết quả test và các audit thủ công không ủng hộ A một cách thuyết phục: test Hit@1 thấp nhất và coherence thấp nhất. Nếu tiêu chí chọn có tính coherence/filter, **C** (B + filter) hợp lý hơn cho corpus tài liệu kỹ thuật có heading rõ và có ngữ cảnh phạm vi từ người dùng. Ghi lại trung thực: quy tắc chọn dựa vào Hit@1 trên 19 câu là quá mong manh. Kết luận chỉ áp dụng cho corpus này, model này và benchmark nhỏ này.
- **Hạn chế.**
  - Test chỉ 6 câu, và cả ba chiến lược đều đạt Hit@3 6/6, grounding 2/2. Test quá dễ, không phân biệt được chiến lược.
  - Split theo chủ đề trong cùng tài liệu nên có nguy cơ rò rỉ mức tài liệu.
  - Evidence Hit yêu cầu khớp nguyên quote, nên có thể chấm trượt câu có bằng chứng tương đương ở đơn vị khác. Không có trường hợp nào như vậy được ghi nhận, nhưng chưa rà hết.
  - Nhãn thủ công do một người chấm là tác giả (soạn với hỗ trợ của Claude Code), không có người chấm thứ hai. Người chấm đồng thời xây pipeline và đã thấy chỉ số nên có nguy cơ thiên lệch.
  - Thời gian đo trên một lần chạy CPU. `ms_per_query` của A bao gồm warm-up nên không so sánh độ trễ được.
  - HNSW là approximate search, chưa đối chiếu với exact search.
  - Dùng Chroma thay pgvector do sự cố mạng Docker.
- **Nếu làm lại hoặc mở rộng.**
  - Tăng test lên ≥15 câu khó hơn (nhiều câu filter, câu có evidence dài hoặc ở bảng).
  - Chốt tiêu chí chọn kết hợp Hit@3, coherence và grounding.
  - Chia đơn vị theo section thay vì theo ngưỡng ký tự, để tránh trường hợp như q18.
  - Thêm tiêu đề section vào text khi embed (contextual header) cho B.
  - Thử model có ngữ cảnh dài hơn (ví dụ e5/bge, 512 token) để B không bị cắt.
  - Thử hybrid BM25 cho câu chứa ký hiệu như `{}` hay `import *`.
  - Chạy lại trên pgvector khi Docker hoạt động để so exact và approximate search.
