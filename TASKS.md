# BẢNG PHÂN CÔNG NHIỆM VỤ & THEO DÕI TIẾN ĐỘ (TASKS.md)
## DỰ ÁN: DataShield - Django Privacy & Compliance Platform
**Môn học:** Django Cơ Bản (4 tín chỉ) - UIT  
**Giảng viên:** NCS.ThS. Trần Phương Duy  
**Repository:** [https://github.com/leduykhanhdevs/Django_Serminar](https://github.com/leduykhanhdevs/Django_Serminar)

---

> [!CAUTION]
> ### 🤖 YÊU CẦU BẮT BUỘC DÀNH CHO TẤT CẢ CÁC MÔ HÌNH AI (AI MUST READ THIS FIRST)
> 1. **Trước khi thực hiện bất kỳ yêu cầu code nào**, AI **PHẢI ĐỌC KỸ FILE NÀY** để xác định chính xác:
>    - Người yêu cầu đang đóng vai trò Thành viên nào (Khánh hay Hiếu)?
>    - Task đang làm thuộc phạm vi của ai và nằm ở nhánh Git nào (`main` hay `nguyen-van-hieu`)?
> 2. **Tuân thủ ranh giới tệp tin (File Boundaries):** Tuyệt đối không can thiệp vào các tệp thuộc quyền quản lý của thành viên khác nếu không được nhóm trưởng cho phép, nhằm triệt tiêu nguy cơ xung đột mã nguồn (*Git merge conflict*).
> 3. **Cập nhật tiến độ:** Sau khi hoàn thành một task, AI phải hỗ trợ đánh dấu `[x]` vào checklist tương ứng.

---


> [!IMPORTANT]
> ### 📐 NGUYÊN TẮC BẮT BUỘC VỀ CẤU TRÚC THEO 3 SLIDE BÀI GIẢNG (UIT)
> Mọi thành viên và AI khi code phải tuân thủ nghiêm ngặt:
> 1. **Static Files:** File tĩnh chung đặt tại `static/css/style.css`, `static/js/main.js`, `static/images/`. Cấu hình `STATICFILES_DIRS = [BASE_DIR / 'static']`.
> 2. **Templates:** Template của app bắt buộc đặt trong `privacy/templates/privacy/*.html`. Template chung tại `templates/` (404, 500). Dùng `{% extends "privacy/base.html" %}`.
> 3. **URL Reverse:** Dùng `{% url 'privacy:route' %}` và `redirect('privacy:route')`, không hard-code URL.
> 4. **Model & Admin:** Mọi Model có `__str__`, `related_name` cho ForeignKey, và đăng ký `@admin.register` trong `admin.py`.



> [!CAUTION]
> ### 🔄 BƯỚC 0 BẮT BUỘC TRƯỚC KHI CODE (PRE-EXECUTION GIT PULL)
> Mỗi khi AI bắt đầu làm việc, **BẮT BUỘC PHẢI CHẠY `git pull`** để lấy bản code mới nhất từ GitHub về, đọc kỹ các thay đổi của thành viên và dựa trên nền tảng đó mới được code tiếp.

> [!IMPORTANT]
> ### ⚡ QUY TẮC THỰC HIỆN TASK BẮT BUỘC DÀNH CHO AI
> 1. **CHỈ LÀM TỪNG TASK NHỎ MỘT:** Tuyệt đối không làm gộp, không làm một lèo nhiều task. Xong dứt điểm task này mới được chuyển sang task khác.
> 2. **TỰ KIỂM TRA LẠI 1 LẦN TRƯỚC KHI BÁO CÁO:** Sau khi code xong, AI bắt buộc phải tự chạy `python manage.py check` và `pytest` để kiểm chứng.
> 3. **ĐÁNH DẤU HOÀN THÀNH:** Sau khi kiểm tra đạt 100%, AI tự động cập nhật đổi `[ ]` thành `[x]` trong file `TASKS.md` này rồi mới báo cáo cho người dùng.

## 🗺️ RANH GIỚI PHẠM VI TRÁCH NHIỆM & TỆP TIN (FILE BOUNDARIES)

Để tránh xung đột code giữa 2 thành viên, ranh giới file được phân chia rõ ràng như sau:

| Thành viên | Nhánh Git | Phạm vi Tệp tin Phụ trách chính |
| :--- | :---: | :--- |
| **Lê Duy Khánh**<br>*(Nhóm trưởng - Tech Lead)* | `main` | - `privacy/models.py` (Core Schema, RLS, AuditEvent)<br>- `privacy/services.py` (Security services, Encryption, Anonymizer, Hash Chain)<br>- `privacy/tenant_context.py` & `privacy/middleware.py`<br>- `postgres/`, `docker/`, `Dockerfile`, `docker-compose.yml`<br>- `privacy/migrations/`<br>- `privacy/tests/test_domain_services.py`, `test_postgresql_rls.py`<br>- `config/settings.py` (Security settings) |
| **Nguyễn Văn Hiếu**<br>*(Thành viên - Core Dev)* | `nguyen-van-hieu` | - `privacy/views.py` (DSAR, Consent, Legal Crosswalk, Compliance UI logic)<br>- `privacy/forms.py` (Form nhập liệu, validation giao diện)<br>- `privacy/templates/privacy/` (Toàn bộ giao diện HTML, CSS, Dashboard)<br>- `privacy/exports.py` (Báo cáo PDF ReportLab, Watermark, JSON export)<br>- `privacy/tasks.py` (Celery background tasks, Email notifications)<br>- `privacy/tests/test_workflows.py` |

---

## 📋 CHI TIẾT NHIỆM VỤ THEO GIAI ĐOẠN (ROADMAP & CHECKLIST)

### GIAI ĐOẠN 1: BÁO CÁO SEMINAR (Trọng số 20%)
*Mục tiêu: Hoàn thiện bài thuyết trình, kịch bản demo và bản prototype chạy mượt mà.*

#### 🛡️ Nhóm trưởng: Lê Duy Khánh (Nhánh `main`)
- [x] **Task K1.1:** Khởi tạo cấu trúc dự án, thiết lập Git repository và cấu hình phân nhánh `main` & `nguyen-van-hieu`.
- [x] **Task K1.2:** Soạn thảo bộ quy chuẩn làm việc (`CONTRIBUTING.md`, `AI_RULES.md`, `.cursorrules`, `TASKS.md`).
- [ ] **Task K1.3:** Kiểm tra và hoàn thiện môi trường chạy cục bộ và Docker Compose (PostgreSQL RLS, Redis, Celery, Mailpit).
- [ ] **Task K1.4:** Tối ưu hóa hàm kiểm toán chuỗi băm `verify_audit_chain()` phục vụ kịch bản live demo trước lớp.
- [ ] **Task K1.5:** Hỗ trợ Thành viên 2 chuẩn bị dữ liệu mẫu (`seed_demo`) phục vụ thuyết trình Seminar.
- [ ] **Task K1.6:** Cùng Thành viên 2 hoàn thiện Slide thuyết trình Seminar (Phần Kiến trúc kỹ thuật & Security).

#### 🛡️ Thành viên: Nguyễn Văn Hiếu (Nhánh `nguyen-van-hieu`)
- [ ] **Task H1.1:** Nghiên cứu đối chiếu chi tiết Nghị định 13/2023/NĐ-CP, Luật Bảo vệ DLCN 91/2025 và GDPR để chuẩn bị nội dung lý thuyết cho Slide Seminar.
- [ ] **Task H1.2:** Hoàn thiện giao diện Consent Center (`consent_center.html`) hiển thị rõ ràng việc bật/tắt từng mục đích xử lý dữ liệu cá nhân.
- [ ] **Task H1.3:** Hoàn thiện giao diện DSAR List & Detail (`dsar_list.html`, `dsar_detail.html`) có hiển thị nhãn trạng thái SLA 72h trực quan.
- [ ] **Task H1.4:** Kiểm tra tính năng xuất file PDF ReportLab có đóng dấu Watermark và link tải bảo mật.
- [ ] **Task H1.5:** Xây dựng kịch bản thuyết trình và phân cảnh Live Demo 5 phút cho buổi Seminar.
- [ ] **Task H1.6:** Tạo Pull Request đầu tiên từ `nguyen-van-hieu` vào `main` để Nhóm trưởng review và gộp code.

---

### GIAI ĐOẠN 2: HOÀN THIỆN ĐỒ ÁN TOÀN DIỆN (Trọng số 60%)
*Mục tiêu: Nâng cấp toàn diện các tính năng chiều sâu, viết báo cáo kỹ thuật và quay video demo.*

#### 🛡️ Nhóm trưởng: Lê Duy Khánh (Nhánh `main`)
- [ ] **Task K2.1:** Cài đặt Module mã hóa cấp trường (Field-Level Encryption) cho các trường dữ liệu cá nhân nhạy cảm bằng AES-256-GCM.
- [ ] **Task K2.2:** Nâng cấp thuật toán Khuyết danh hóa thông minh (`Intelligent Anonymization Engine`): thay thế PII bằng dữ liệu ngẫu nhiên của Faker khi người dùng yêu cầu xóa tài khoản (Right to be Forgotten) mà vẫn giữ nguyên báo cáo tài chính/hóa đơn.
- [ ] **Task K2.3:** Hoàn thiện chính sách PostgreSQL Row-Level Security (RLS) ngăn chặn triệt để nguy cơ rò rỉ dữ liệu giữa các tổ chức/doanh nghiệp.
- [ ] **Task K2.4:** Viết bộ kiểm thử hồi quy tự động (Automated Regression Tests) với `pytest`, kiểm tra độ bao phủ mã nguồn (> 85% coverage).
- [ ] **Task K2.5:** Quản trị Code Review, kiểm tra xung đột và thực hiện merge định kỳ các Pull Request từ Thành viên 2.
- [ ] **Task K2.6:** Chủ trì viết Báo cáo kỹ thuật Đồ án (Chương Kiến trúc Hệ thống, An toàn Bảo mật & CSDL).

#### 🛡️ Thành viên: Nguyễn Văn Hiếu (Nhánh `nguyen-van-hieu`)
- [ ] **Task H2.1:** Xây dựng Module tự động sinh Hồ sơ Đánh giá tác động xử lý dữ liệu (DPIA Mẫu số 04 theo Phụ lục Nghị định 13/2023) xuất file Word/PDF.
- [ ] **Task H2.2:** Xây dựng Module Hồ sơ Đánh giá chuyển dữ liệu cá nhân ra nước ngoài (Mẫu số 06 gửi Cục An ninh mạng A05).
- [ ] **Task H2.3:** Hoàn thiện quy trình điều phối sự cố rò rỉ dữ liệu (Incident Escalation 72h) với mẫu thông báo sự cố gửi Bộ Công an.
- [ ] **Task H2.4:** Xây dựng Celery Cron Task tự động quét các yêu cầu DSAR sắp chạm ngưỡng 72h để gửi email cảnh báo cho DPO qua Mailpit.
- [ ] **Task H2.5:** Thiết kế giao diện Dashboard DPO chuyên nghiệp (thống kê tổng số consent, DSAR quá hạn, nhật ký audit, trạng thái vendor).
- [ ] **Task H2.6:** Đồng chủ trì viết Báo cáo kỹ thuật Đồ án (Chương Nghiệp vụ Pháp lý, Quy trình Tuân thủ & Hướng dẫn Người dùng) và quay Video Demo cuối kỳ.

---

## 🔄 QUY TRÌNH PHỐI HỢP GIT HÀNG NGÀY GIỮA 2 THÀNH VIÊN

```
             [ Nhóm trưởng: Lê Duy Khánh ]
                         │
        (1) Quản trị & phát triển trên branch 'main'
                         │
        (4) Review & Merge PR ◄────────────────┐
                         │                     │
                         ▼                     │ (3) Tạo Pull Request
             [ Remote Repo: GitHub ]           │
                         │                     │
        (2) Đồng bộ code mới về                │
                         │                     │
                         ▼                     │
             [ Thành viên: Nguyễn Văn Hiếu ]   │
                         │                     │
        Phát triển tính năng trên branch 'nguyen-van-hieu' ──┘
```

1. **Trước khi bắt đầu code mỗi ngày:**
   - Thành viên Hiếu chạy `git checkout main && git pull origin main` để nhận code mới nhất từ Khánh.
   - Chạy `git checkout nguyen-van-hieu && git merge main` để đồng bộ vào nhánh của mình.
2. **Sau khi hoàn thành tính năng:**
   - Chạy `pytest` đảm bảo không có lỗi.
   - Đẩy lên nhánh: `git push origin nguyen-van-hieu`.
   - Lên GitHub tạo Pull Request gửi Nhóm trưởng Lê Duy Khánh kiểm duyệt.
3. **Tuyệt đối không:** Push thẳng vào `main` hoặc sửa file thuộc phân vùng của thành viên khác khi chưa trao đổi.
