# NGUYÊN TẮC BẮT BUỘC KHI SỬ DỤNG AI PHÁT TRIỂN CODE (AI CODING RULES)
## DỰ ÁN: DataShield - Django Privacy & Compliance Platform

> **LƯU Ý TỐI THƯỢNG CHO TẤT CẢ CÁC MÔ HÌNH AI (Antigravity, Cursor, Copilot, ChatGPT, Claude...):**  
> Dự án này là hệ thống bảo mật cấp doanh nghiệp (*Enterprise Security & Privacy Engineering*), đồng thời là đồ án môn học Django Cơ Bản (UIT). Mọi dòng code sinh ra bắt buộc phải:
> 1. Đọc lại và ghi nhớ toàn bộ mã nguồn cũ trước khi tạo code mới.
> 2. Tuân thủ tuyệt đối phân công nhiệm vụ và ranh giới tệp tin trong `TASKS.md`.
> 3. Tuân thủ 100% chuẩn cấu trúc giảng dạy trong 3 slide bài giảng (Buổi 1, Buổi 2, Buổi 3).

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

### NGUYÊN TẮC 1: TUÂN THỦ CHUẨN CẤU TRÚC GIẢNG DẠY (UIT DJANGO SLIDES B1, B2, B3)

#### 1.1. Cấu trúc thư mục Static chuẩn (Slide 29-31 Buổi 2)
Mọi static files phải được bố trí theo cấu trúc chuẩn:
```
DataShield/
├── static/                     <- Thư mục static dùng chung toàn project
│   ├── css/
│   │   └── style.css           <- CSS toàn cục
│   ├── js/
│   │   └── main.js             <- JS toàn cục
│   └── images/                 <- Hình ảnh, logo, avatar
├── privacy/
│   └── static/privacy/         <- Static riêng của app (nếu có)
│       └── app.css
```
- Cấu hình trong `config/settings.py`:
  ```python
  STATIC_URL = "static/"
  STATICFILES_DIRS = [
      BASE_DIR / "static",       # Thư mục static dùng chung toàn project
  ]
  STATIC_ROOT = BASE_DIR / "staticfiles"
  ```
- Sử dụng trong template: Bắt buộc dùng `{% load static %}` và `{% static 'css/style.css' %}`. Tuyệt đối không hard-code đường dẫn static `/static/...`.

#### 1.2. Cấu trúc thư mục & cấu hình Templates (Slide 18, 23-27 Buổi 2)
- **App Templates:** Bắt buộc tuân thủ quy tắc Namespacing theo app:
  `privacy/templates/privacy/<tên_trang>.html`
  *(Tránh xung đột tên template khi `APP_DIRS: True`).*
- **Root Templates:** `templates/` ở thư mục gốc project chứa `404.html`, `500.html` và các template dùng chung qua `{% include %}`.
- Cấu hình trong `config/settings.py`:
  ```python
  TEMPLATES = [
      {
          "BACKEND": "django.template.backends.django.DjangoTemplates",
          "DIRS": [BASE_DIR / "templates"],
          "APP_DIRS": True,
          ...
      }
  ]
  ```
- **Kế thừa Template (Template Inheritance):** Trang con bắt buộc dùng `{% extends "privacy/base.html" %}` và ghi đè qua `{% block content %}...{% endblock %}`.

#### 1.3. Chuẩn URL Dispatcher & Reverse Resolution (Slide 8-9, 14-15, 37 Buổi 2)
- Mọi app phải có `app_name = 'privacy'` trong `urls.py`.
- Mọi path phải đặt `name='...'`.
- Trong template: BẮT BUỘC dùng `{% url 'privacy:tên_route' %}` (hoặc truyền tham số `{% url 'privacy:dsar_detail' reference=case.reference %}`).
- Trong Python view: BẮT BUỘC dùng `redirect('privacy:tên_route')` hoặc `reverse('privacy:tên_route')`. Tuyệt đối không hard-code URL string.

#### 1.4. Chuẩn Model, ORM & Admin (Slide 10-18, 30, 33, 40 Buổi 3)
- Mọi Model phải có phương thức `__str__(self)` trả về định danh rõ ràng.
- Khóa ngoại `ForeignKey` bắt buộc khai báo `on_delete` và `related_name`.
- Mọi Model phải được đăng ký trong `admin.py` bằng `@admin.register(ModelName)` kèm `list_display`, `list_filter`, `search_fields`.
- Mọi thay đổi Model phải sinh file migration bằng `python manage.py makemigrations` và chạy `python manage.py migrate`.

---

### NGUYÊN TẮC 2: ĐỌC LẠI VÀ GHI NHỚ TOÀN BỘ SOURCE CODE CŨ TRƯỚC KHI VIẾT MỚI
1. **Không suy đoán / Không hallucinate:** Trước khi tạo file mới hoặc chỉnh sửa bất kỳ module nào, AI **PHẢI** đọc lại toàn bộ mã nguồn của các file liên quan (đặc biệt là `privacy/models.py`, `privacy/services.py`, `privacy/tenant_context.py`, `config/settings.py`).
2. **Nắm chắc Dependency Graph:** Phải hiểu rõ luồng dữ liệu giữa Models -> Services -> Views -> Forms -> Celery Tasks trước khi can thiệp.
3. **Tuyệt đối không viết đè phá vỡ logic cũ:** Mọi tính năng mới phải kế thừa và mở rộng trên nền tảng kiến trúc sẵn có, không được xóa bỏ hoặc thay thế các hàm cốt lõi nếu không có yêu cầu rõ ràng từ nhóm trưởng.

---

### NGUYÊN TẮC 3: BẢO TOÀN CÁC CƠ CHẾ BẢO MẬT CỐT LÕI (ZERO TOLERANCE)
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

### NGUYÊN TẮC 4: QUY CHUẨN KỸ THUẬT & KIỂM THỬ (TEST-DRIVEN & CLEAN CODE)
1. **Type Annotations & Docstrings:** Tất cả các hàm và method mới phải có đầy đủ gợi ý kiểu dữ liệu (Python Type Hints: `from __future__ import annotations`) và docstring giải thích rõ ràng mục đích, tham số, ngoại lệ.
2. **Transaction-safe:** Các thao tác ghi nhiều bảng (đặc biệt là DSAR, Consent, AuditEvent) phải nằm trong khối `transaction.atomic()`.
3. **Chạy kiểm thử trước khi báo cáo:** Trước khi thông báo hoàn thành task, AI phải đảm bảo bộ test `pytest` vượt qua 100% không có lỗi hồi quy (*regression*).
