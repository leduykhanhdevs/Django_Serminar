# QUY CHẾ LÀM VIỆC NHÓM & QUY TRÌNH PHÁT TRIỂN (CONTRIBUTING GUIDE)
## DỰ ÁN: DataShield - Django Privacy & Compliance Platform
**Môn học:** Django Cơ Bản (4 tín chỉ) - Trường ĐH Công nghệ Thông tin (UIT)  
**Chủ đề:** BẢO MẬT & CHUẨN MỰC MỚI  
**Repository:** [leduykhanhdevs/Django_Serminar](https://github.com/leduykhanhdevs/Django_Serminar)

---

## 1. THÀNH VIÊN & PHÂN CÔNG NHIỆM VỤ (WBS)

### Thành viên 1: Lê Duy Khánh (Nhóm trưởng / Tech Lead & Security Architect)
- **Vai trò:** Quản trị toàn diện dự án, phân tích kiến trúc bảo mật tầng sâu, điều phối mã nguồn và quyết định kỹ thuật.
- **Nhiệm vụ trọng tâm:**
  1. **Quản trị Repository & Release:** Kiểm duyệt Code Review, thiết lập nhánh, bảo vệ nhánh `main`, trực tiếp gộp (Merge) code từ nhánh thành viên vào `main`.
  2. **Kiến trúc Dữ liệu & Multi-tenancy:** Thiết lập cơ chế cô lập dữ liệu tổ chức đa tầng bằng **PostgreSQL Row-Level Security (RLS)** và `TenantScopedModel`.
  3. **Mã hóa Cấp trường (Field-Level Encryption):** Xây dựng engine mã hóa AES-256 cho dữ liệu cá nhân nhạy cảm (CCCD, tài khoản ngân hàng, thông tin tài chính).
  4. **Sổ cái Nhật ký Bất biến (Tamper-evident Audit Ledger):** Cài đặt thuật toán chuỗi băm Merkle/SHA-256 (`AuditEvent`), cơ chế chống sửa/xóa log và hàm xác thực toàn vẹn `verify_audit_chain()`.
  5. **Thuật toán Khuyết danh hóa (Intelligent Anonymization):** Xây dựng cơ chế khuyết danh hóa dữ liệu PII khi thực thi quyền xóa tài khoản (Right to be Forgotten) mà không phá vỡ quan hệ CSDL và báo cáo tài chính.
  6. **Môi trường & Kiểm thử:** Cấu hình Docker Compose (Web, PostgreSQL, Celery, Redis, Mailpit), viết bộ test runner (`pytest`, kiểm tra RLS).

---

### Thành viên 2: Nguyễn Văn Hiếu (Core Developer & Compliance Specialist)
- **Vai trò:** Lập trình viên tính năng cốt lõi, chuyên trách quy trình nghiệp vụ tuân thủ pháp luật và trải nghiệm người dùng.
- **Nhiệm vụ trọng tâm:**
  1. **Nghiên cứu Pháp lý & Ma trận Đối chiếu:** Phân tích chi tiết Nghị định 13/2023/NĐ-CP, Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 và GDPR; xây dựng ma trận đối chiếu pháp lý (*Legal Crosswalk Matrix*).
  2. **Cổng Quản trị Sự đồng ý (Consent Management Center):** Xây dựng giao diện và logic cho phép chủ thể dữ liệu đồng ý hoặc rút lại sự đồng ý theo từng mục đích xử lý riêng biệt.
  3. **Quy trình Quyền Dữ liệu Chủ thể (DSAR Pipeline):** Hiện thực hóa quy trình tiếp nhận, phê duyệt và thực thi yêu cầu dữ liệu (Truy cập, Sửa đổi, Xuất dữ liệu) với đồng hồ đếm ngược SLA **72 giờ**.
  4. **Tự động hóa Hồ sơ Pháp lý:** Module kết xuất Hồ sơ Đánh giá tác động xử lý dữ liệu (DPIA Mẫu số 04) và Chuyển dữ liệu cá nhân ra nước ngoài (Mẫu số 06) gửi Cục An ninh mạng (A05).
  5. **Quy trình Điều phối Sự cố Rò rỉ (Incident Escalation 72h):** Xây dựng quy trình xử lý sự cố lộ lọt thông tin cá nhân và mẫu báo cáo gửi cơ quan chức năng trong hạn 72h.
  6. **UI/UX & Bảo mật Tài khoản:** Thiết kế Dashboard dành cho Cán bộ DPO, tích hợp xác thực hai yếu tố (TOTP 2FA Authenticator).

---

## 2. QUY TẮC PHÂN NHÁNH VÀ QUYỀN GỘP CODE (GIT WORKFLOW)

Để đảm bảo mã nguồn luôn ổn định, không bị xung đột (*conflict*) hoặc mất mát code, nhóm tuân thủ nghiêm ngặt mô hình phân nhánh sau:

```
[ Nhánh main ]  ◄────────────────────────────────── (Chỉ Nhóm trưởng được Merge)
      ▲
      │ Pull Request (Code Review kỹ lưỡng)
      │
[ Nhánh nguyen-van-hieu ] (Thành viên 2 commit & push vào đây)
```

### 🔒 Quy tắc Bắt buộc:
1. **Bảo vệ nhánh `main`:**
   - Nhánh `main` là nhánh chính thức của dự án.
   - **Thành viên 2 (Nguyễn Văn Hiếu) TUYỆT ĐỐI KHÔNG ĐƯỢC push trực tiếp lên nhánh `main`.**
   - Mọi đóng góp code của thành viên 2 bắt buộc phải commit và push lên nhánh riêng: `nguyen-van-hieu`.
2. **Quyền Duyệt và Gộp Code:**
   - **CHỈ CÓ NHÓM TRƯỞNG (Lê Duy Khánh) MỚI CÓ QUYỀN DUYỆT (REVIEW) VÀ MERGE PULL REQUEST VÀO `main`.**
   - Trước khi merge, nhóm trưởng phải chạy kiểm thử `pytest` và đảm bảo code không làm vỡ các tính năng hiện hữu.
3. **Quy trình làm việc chuẩn của Thành viên 2 (Nguyễn Văn Hiếu):**
   ```bash
   # Bước 1: Trước khi bắt đầu làm việc, cập nhật code mới nhất từ main
   git checkout main
   git pull origin main

   # Bước 2: Chuyển sang nhánh cá nhân và gộp code mới nhất vào
   git checkout nguyen-van-hieu
   git merge main

   # Bước 3: Viết code, chạy test cục bộ
   pytest

   # Bước 4: Thêm file và commit
   git add .
   git commit -m "feat: mo ta tinh nang da hoan thanh"

   # Bước 5: Đẩy lên nhánh cá nhân trên GitHub
   git push origin nguyen-van-hieu

   # Bước 6: Mở giao diện GitHub tạo Pull Request (PR) gửi Nhóm trưởng duyệt
   ```

---

## 3. TIÊU CHUẨN COMMIT & CODE QUALITY
- Thông điệp Commit tuân thủ chuẩn Conventional Commits:
  - `feat(...)`: Thêm tính năng mới
  - `fix(...)`: Sửa lỗi
  - `docs(...)`: Cập nhật tài liệu
  - `test(...)`: Thêm hoặc chỉnh sửa test
  - `refactor(...)`: Tối ưu hóa code mà không thay đổi logic
- Không bao giờ commit các file rác, file môi trường: `.env`, `db.sqlite3`, `__pycache__`, `.venv`.

---

## 4. QUY TẮC THỰC HIỆN TASK VÀ SỬ DỤNG AI (ATOMIC & VERIFY)

0. **Luôn chạy `git pull` đầu tiên:** Mỗi khi mở máy hoặc bắt đầu một phiên làm việc với AI, bắt buộc chạy `git pull` để nhận toàn bộ code mới nhất của đồng đội, đọc kỹ mã nguồn mới trước khi viết code tiếp theo.

1. **Chỉ làm từng task nhỏ một:** Tuyệt đối không làm gộp nhiều task cùng lúc ("không làm một lèo"). Mỗi commit hoặc pull request chỉ giải quyết một đơn vị công việc độc lập.
2. **Tự kiểm tra lại 1 lần trước khi thông báo hoàn thành:**
   - Chạy `python manage.py check` kiểm tra hệ thống.
   - Chạy `pytest` kiểm tra tính năng và đảm bảo không làm vỡ các bài test cũ.
3. **Cập nhật tiến độ trong `TASKS.md`:** Đánh dấu `[x]` vào checklist của task tương ứng khi đã tự kiểm tra thành công 100%.
