# BỘ QUY TẮC PHỐI HỢP NHÓM HIỆU QUẢ CAO (TEAM_RULES.md)
## DỰ ÁN: DataShield - Django Privacy & Compliance Platform
**Áp dụng cho:** Lê Duy Khánh (Nhóm trưởng) & Nguyễn Văn Hiếu (Thành viên)  
**Mục tiêu tối thượng:** Đạt điểm tối đa Seminar (20%) & Vấn đáp Đồ án cuối kỳ (60%)

---

## 💎 BỘ QUY TẮC 1: "DEFINITION OF DONE" (ĐỊNH NGHĨA HOÀN THÀNH CHUẨN MỰC)
Trong kỹ nghệ phần mềm, không bao giờ được coi một task là "xong" nếu nó chỉ mới chạy được trên máy người viết. Một task chỉ được chấp nhận là **ĐÃ HOÀN THÀNH** khi thỏa mãn đủ **5 tiêu chí vàng (5 Checks)**:

1. ✅ **Chạy sạch trên môi trường chuẩn:** Không báo bất kỳ lỗi nào khi chạy `python manage.py runserver` và `python manage.py check`.
2. ✅ **100% Pass Automated Tests:** Chạy `pytest` vượt qua toàn bộ các bài kiểm thử mà không làm hỏng các test có sẵn.
3. ✅ **Đúng chuẩn Slide bài giảng UIT:** Đúng cấu trúc thư mục Static (`static/css/`, `static/js/`), Templates namespacing (`privacy/templates/privacy/`), URL reverse và Model `__str__`.
4. ✅ **Tự tin trả lời vấn đáp:** Thành viên viết task phải tự trả lời được câu hỏi: *"Tại sao viết đoạn code này? Cơ chế hoạt động đằng sau là gì nếu Giảng viên hỏi vặn?"*.
5. ✅ **Cập nhật trạng thái:** Đã cập nhật đánh dấu `[x]` vào tệp `TASKS.md`.

---

## 🧠 BỘ QUY TẮC 2: "HIỂU BẢN CHẤT - CHỐNG LẠM DỤNG AI" (CHIẾN LƯỢC VẤN ĐÁP 60%)
- **Bối cảnh:** Điểm đồ án cuối kỳ thi dưới hình thức **Vấn đáp trực tiếp** với Giảng viên (NCS.ThS. Trần Phương Duy). Thầy sẽ hỏi sâu vào kiến trúc và logic code chứ không chỉ nhìn giao diện bề nổi.
- **Quy tắc bắt buộc:**
  1. **Tuyệt đối không "Copy - Paste" mù quáng:** Khi sử dụng AI hỗ trợ viết code, thành viên phụ trách **BẮT BUỘC phải đọc hiểu từng dòng code** được sinh ra.
  2. **Quyền "Vấn đáp thử" của Nhóm trưởng:** Nhóm trưởng có quyền đặt câu hỏi kiểm tra ngẫu nhiên về cơ chế của code trước khi duyệt Merge PR. Nếu thành viên không giải thích được luồng dữ liệu, PR sẽ được yêu cầu làm rõ lại.
  3. **Ghi chú logic bằng Tiếng Việt:** Với những đoạn code phức tạp (như băm SHA-256, PostgreSQL RLS, Celery worker), bắt buộc phải có comment tiếng Việt ngắn gọn giải thích lý do thiết kế.

---

## ⏱️ BỘ QUY TẮC 3: "GIAO TIẾP NHANH & NGUYÊN TẮC CỨU VIỆN 30 PHÚT"
- **Báo cáo Daily Standup ngắn (Mỗi ngày 3 dòng tin nhắn):**
  1. Hôm qua đã làm được gì?
  2. Hôm nay sẽ làm task nào trong `TASKS.md`?
  3. Đang vướng mắc gì không?
- **Nguyên tắc "Cứu viện 30 phút" (30-Minute Block Rule):**
  - Khi gặp một con bug hoặc vấn đề kỹ thuật hóc búa, tự mày mò và hỏi AI trong **tối đa 30 phút**.
  - Nếu sau 30 phút vẫn bế tắc, **BẮT BUỘC PHẢI BÁO NGAY CHO NHÓM TRƯỞNG** để cùng debug. Tuyệt đối không im lặng ôm bug làm trễ tiến độ của cả nhóm.

---

## 🛡️ BỘ QUY TẮC 4: "CODE REVIEW KHÔNG NỂ NANG & QUY TẮC PULL REQUEST"
1. **Nhóm trưởng là Người gác cổng (Gatekeeper):** Nhánh `main` là nhánh thi cử và nộp bài. Quyết định duyệt hay từ chối PR dựa hoàn toàn trên chất lượng kỹ thuật, không duyệt theo cảm tính nể nang.
2. **Quy cách gửi Pull Request của Thành viên 2:**
   - Mỗi PR chỉ giải quyết **1 task nhỏ duy nhất**.
   - Tiêu đề PR rõ ràng theo chuẩn: `feat(consent): bo sung giao dien rut lai su dong y`.
   - Trong phần mô tả PR: Ghi rõ các file đã sửa, kết quả chạy `pytest` và đính kèm ảnh chụp màn hình tính năng.

---

## 🎬 BỘ QUY TẮC 5: "ZERO-FAIL DEMO" (QUẢN TRỊ RỦI RO BUỔI THI VẤN ĐÁP & SEMINAR)
- 80% sự cố thi cử của sinh viên đến từ việc: mất mạng tại phòng máy, lỗi port, thiếu thư viện hoặc CSDL trống trơn.
- Nhóm áp dụng quy tắc phòng ngừa rủi ro 3 lớp:
  1. **Lớp 1 - Lệnh Seed dữ liệu thần tốc:** Dự án luôn có sẵn lệnh `python manage.py seed_demo`. Khi mở máy ở bất kỳ phòng thi nào, chỉ cần gõ 1 lệnh là có đầy đủ tài khoản, consent, case DSAR mẫu đẹp mắt.
  2. **Lớp 2 - Chạy kép Local & Docker:** Đảm bảo hệ thống có thể chạy được cả trên SQLite cục bộ (khi không bật được Docker) và PostgreSQL RLS (khi môi trường có Docker).
  3. **Lớp 3 - Video Demo dự phòng:** Luôn quay trước một Video Demo chất lượng cao (1080p, có phụ đề/thuyết minh rõ ràng). Nếu máy chiếu hoặc laptop gặp sự cố kỹ thuật ngoài ý muốn, lập tức phát video demo thuyết trình chay để cứu điểm số tuyệt đối.
