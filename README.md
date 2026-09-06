# DataShield: Django Privacy & Compliance Platform

> **Đề tài:** Xu hướng bảo vệ dữ liệu cá nhân & tuân thủ GDPR / Nghị định 13 trong Django  
> **Chủ đề:** BẢO MẬT & CHUẨN MỰC MỚI  
> **Môn học:** Django Cơ Bản (4 tín chỉ) - Trường Đại học Công nghệ Thông tin (UIT)  
> **Giảng viên hướng dẫn:** NCS.ThS. Trần Phương Duy  
> **Repository:** [https://github.com/leduykhanhdevs/Django_Serminar](https://github.com/leduykhanhdevs/Django_Serminar)

---

## 👥 THÀNH VIÊN NHÓM & PHÂN CÔNG NHIỆM VỤ

| STT | Họ và Tên | Vai trò | Nhánh Git | Nhiệm vụ chính |
| :--- | :--- | :--- | :--- | :--- |
| 1 | **Lê Duy Khánh** | **Nhóm trưởng** (Tech Lead & Security Architect) | `main` | Quản trị repo & merge code; Kiến trúc CSDL Multi-tenancy & PostgreSQL RLS; Mã hóa cấp trường AES-256; Sổ cái Audit Log bất biến Merkle/SHA-256; Khuyết danh hóa dữ liệu (Anonymizer); Docker & CI/CD. |
| 2 | **Nguyễn Văn Hiếu** | **Thành viên** (Core Developer & Compliance Specialist) | `nguyen-van-hieu` | Nghiên cứu pháp lý NĐ 13/GDPR/Luật 91; Consent Management Center; DSAR Workflow Pipeline (SLA 72h); Tự động hóa Hồ sơ DPIA Mẫu 04 & Chuyển DL quốc tế Mẫu 06; Quy trình Sự cố 72h; UI DPO Dashboard & TOTP 2FA. |

---

## 🔒 NGUYÊN TẮC QUẢN TRỊ MÃ NGUỒN (GIT WORKFLOW)

1. **Nhánh `main` được bảo vệ tuyệt đối:** Thành viên 2 (`Nguyễn Văn Hiếu`) không push trực tiếp vào `main`.
2. **Nhánh phát triển cá nhân:** Thành viên 2 làm việc trên nhánh `nguyen-van-hieu` và đẩy code lên nhánh này.
3. **Quyền Gộp Code (Merge):** **CHỈ CÓ NHÓM TRƯỞNG (Lê Duy Khánh) MỚI CÓ QUYỀN REVIEW VÀ MERGE VÀO `main`.**
4. Chi tiết xem tại [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 🤖 NGUYÊN TẮC LẬP TRÌNH BẰNG AI (AI CODING RULES)

Khi sử dụng bất kỳ công cụ AI nào (Antigravity, Cursor, Copilot, ChatGPT, Claude...):
- **BẮT BUỘC AI PHẢI ĐỌC VÀ GHI NHỚ TOÀN BỘ SOURCE CODE CŨ TRƯỚC KHI VIẾT MỚI.**
- Tuyệt đối không xóa bỏ hoặc phá vỡ các cơ chế: PostgreSQL RLS, TenantScopedModel, Chuỗi băm SHA-256 AuditEvent.
- Chi tiết xem tại [AI_RULES.md](AI_RULES.md) và [.cursorrules](.cursorrules).

---


## 📐 CHUẨN MỰC KIẾN TRÚC THEO BÀI GIẢNG (UIT SLIDES B1, B2, B3)

Dự án tuân thủ nghiêm ngặt các quy chuẩn kỹ thuật do Giảng viên (NCS.ThS. Trần Phương Duy) hướng dẫn:
1. **Cấu trúc Static Files chuẩn (Slide 29-31 Buổi 2):**
   - Thư mục tĩnh dùng chung toàn project: `static/` gồm `css/style.css`, `js/main.js`, `images/`.
   - Cấu hình trong `config/settings.py`:
     ```python
     STATIC_URL = "static/"
     STATICFILES_DIRS = [BASE_DIR / "static"]
     STATIC_ROOT = BASE_DIR / "staticfiles"
     ```
   - Sử dụng trong template: `{% load static %}` và `{% static 'css/style.css' %}`.
2. **Cấu trúc thư mục & cấu hình Templates (Slide 18, 23-27 Buổi 2):**
   - Namespacing cấp app: `privacy/templates/privacy/*.html` (ngăn xung đột khi `APP_DIRS: True`).
   - Thư mục template dùng chung cấp project: `templates/` (chứa `404.html`, `500.html`).
   - Cấu hình trong `config/settings.py`: `TEMPLATES[0]['DIRS'] = [BASE_DIR / "templates"]`, `APP_DIRS = True`.
   - Kế thừa giao diện chuẩn mực: `{% extends "privacy/base.html" %}` và `{% block content %}`.
3. **Cấu trúc URL Routing & Reverse Resolution (Slide 8-9, 14-15 Buổi 2):**
   - Khai báo `app_name = 'privacy'` trong `privacy/urls.py`.
   - Định tuyến chuẩn: Dùng thẻ `{% url 'privacy:route_name' %}` trong template và `redirect('privacy:route_name')` trong view, tuyệt đối không hard-code URL string.
4. **Cấu trúc Model, ORM, Admin & Migration (Slide 10-18, 30, 33, 40 Buổi 3):**
   - Mọi Model đều có phương thức `__str__(self)` trả về chuỗi đại diện rõ ràng.
   - Khóa ngoại `ForeignKey` bắt buộc có `on_delete` và `related_name`.
   - Đăng ký toàn bộ Model vào Admin bằng `@admin.register` kèm cấu hình `list_display`, `list_filter`, `search_fields`.
   - Quy trình đồng bộ CSDL chuẩn mực qua `makemigrations` và `migrate`.

## 🚀 HƯỚNG DẪN CHẠY DỰ ÁN

### 1. Chạy cục bộ (Local)
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py runserver
```
Mở trình duyệt: `http://127.0.0.1:8000/`. Lệnh `seed_demo` hiển thị tài khoản demo và mật khẩu.

### 2. Chạy với Docker Compose (Production-ready với PostgreSQL RLS & Celery)
```powershell
Copy-Item .env.example .env
docker compose up --build
docker compose exec web python manage.py seed_demo
```
- Web Application: `http://localhost:8000/`
- Mailpit (Kiểm tra Email kích hoạt & DSAR): `http://localhost:8025/`

---

## 🧪 CHẠY KIỂM THỬ (AUTOMATED TESTING)

```powershell
# Chạy bộ test pytest toàn diện
.\.venv\Scripts\python.exe -m pytest

# Kiểm tra an toàn bảo mật dependencies
.\.venv\Scripts\python.exe -m pip_audit -r requirements.txt

# Kiểm tra chính sách PostgreSQL Row-Level Security trong Docker
docker compose run --rm migrate python manage.py test privacy.tests.test_postgresql_rls -v 2
```

---

## ⚖️ CƠ SỞ PHÁP LÝ ÁP DỤNG
- **Nghị định 13/2023/NĐ-CP** của Chính phủ Việt Nam về Bảo vệ dữ liệu cá nhân.
- **Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15** (Quốc hội thông qua, hiệu lực 01/01/2026).
- **GDPR (General Data Protection Regulation - EU 2016/679)** của Liên minh Châu Âu.
