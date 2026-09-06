# NGUYÊN TẮC BẮT BUỘC KHI SỬ DỤNG AI PHÁT TRIỂN CODE (AI CODING RULES)
## DỰ ÁN: DataShield - Django Privacy & Compliance Platform

> **LƯU Ý TỐI THƯỢNG CHO TẤT CẢ CÁC MÔ HÌNH AI (Antigravity, Cursor, Copilot, ChatGPT, Claude...):**  
> Dự án này là hệ thống bảo mật cấp doanh nghiệp (*Enterprise Security & Privacy Engineering*). Mọi dòng code sai sót đều có thể dẫn đến rò rỉ dữ liệu hoặc phá vỡ các ràng buộc pháp lý. AI bắt buộc phải tuân thủ nghiêm ngặt các nguyên tắc dưới đây.

---

### NGUYÊN TẮC 0: ĐỌC KỸ FILE TASKS.MD VÀ XÁC ĐỊNH RANH GIỚI TRÁCH NHIỆM
1. **BẮT BUỘC ĐỌC `TASKS.md`:** Trước khi thực hiện bất kỳ chỉ thị code nào, AI **PHẢI ĐỌC KỸ FILE `TASKS.md`** để biết rõ:
   - Ai là người đang yêu cầu (Lê Duy Khánh hay Nguyễn Văn Hiếu)?
   - Task đó thuộc trách nhiệm của ai và tác động đến những tệp tin nào?
2. **Tuân thủ Ranh giới Tệp tin (File Boundaries):**
   - **Nhánh `main` (Lê Duy Khánh):** `privacy/models.py`, `privacy/services.py`, `privacy/tenant_context.py`, `privacy/middleware.py`, `postgres/`, `docker/`, `config/settings.py`.
   - **Nhánh `nguyen-van-hieu` (Nguyễn Văn Hiếu):** `privacy/views.py`, `privacy/forms.py`, `privacy/templates/`, `privacy/exports.py`, `privacy/tasks.py`.
   - **KHÔNG SỬA LẪN LỘN:** Tránh tuyệt đối việc sửa chéo file gây ra xung đột Git (Merge Conflicts) giữa hai thành viên.

---

### NGUYÊN TẮC 1: ĐỌC LẠI VÀ GHI NHỚ TOÀN BỘ SOURCE CODE CŨ TRƯỚC KHI VIẾT MỚI
1. **Không suy đoán / Không hallucinate:** Trước khi tạo file mới hoặc chỉnh sửa bất kỳ module nào, AI **PHẢI** đọc lại toàn bộ mã nguồn của các file liên quan (đặc biệt là `privacy/models.py`, `privacy/services.py`, `privacy/tenant_context.py`, `config/settings.py`).
2. **Nắm chắc Dependency Graph:** Phải hiểu rõ luồng dữ liệu giữa Models -> Services -> Views -> Forms -> Celery Tasks trước khi can thiệp.
3. **Tuyệt đối không viết đè phá vỡ logic cũ:** Mọi tính năng mới phải kế thừa và mở rộng trên nền tảng kiến trúc sẵn có, không được xóa bỏ hoặc thay thế các hàm cốt lõi nếu không có yêu cầu rõ ràng từ nhóm trưởng.

---

### NGUYÊN TẮC 2: BẢO TOÀN CÁC CƠ CHẾ BẢO MẬT CỐT LÕI (ZERO TOLERANCE)
1. **Multi-tenancy & PostgreSQL RLS:**
   - Mọi model chứa dữ liệu nghiệp vụ bắt buộc phải kế thừa `TenantScopedModel`.
   - Không được phép bypass biến session `app.current_organization_id`. Mọi truy vấn phải chạy qua `organization_scope` hoặc `TenantScopedManager`.
2. **Tính bất biến của Audit Ledger (`AuditEvent`):**
   - Không bao giờ được phép chỉnh sửa hoặc xóa bản ghi `AuditEvent`.
   - Mọi sự kiện audit phải được tính toán `event_hash` nối chuỗi băm SHA-256 từ `previous_hash`.
   - Bất kỳ can thiệp nào làm đứt chuỗi băm đều bị coi là lỗi nghiêm trọng.
3. **Mã hóa & Dữ liệu nhạy cảm:**
   - Dữ liệu PII nhạy cảm (Điều 28 Nghị định 13) không bao giờ được lưu plain text hay in vào log/traceback.
   - Bắt buộc lọc sạch mật khẩu, token, thông tin thẻ/CCCD khỏi các thông điệp exception hoặc logging.

---

### NGUYÊN TẮC 3: QUY CHUẨN KỸ THUẬT & KIỂM THỬ (TEST-DRIVEN & CLEAN CODE)
1. **Type Annotations & Docstrings:** Tất cả các hàm và method mới phải có đầy đủ gợi ý kiểu dữ liệu (Python Type Hints: `from __future__ import annotations`) và docstring giải thích rõ ràng mục đích, tham số, ngoại lệ.
2. **Transaction-safe:** Các thao tác ghi nhiều bảng (đặc biệt là DSAR, Consent, AuditEvent) phải nằm trong khối `transaction.atomic()`.
3. **Chạy kiểm thử trước khi báo cáo:** Trước khi thông báo hoàn thành task, AI phải đảm bảo bộ test `pytest` vượt qua 100% không có lỗi hồi quy (*regression*).
