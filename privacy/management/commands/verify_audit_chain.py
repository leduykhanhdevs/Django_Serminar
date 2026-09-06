"""Management command to verify the cryptographic integrity of the audit hash-chain.

Designed for live-demos during seminars and classroom presentations.
"""

from __future__ import annotations

import json
from django.core.management.base import BaseCommand, CommandError

from privacy import services
from privacy.models import AuditEvent, Organization


class Command(BaseCommand):
    help = "Kiểm toán chuỗi băm mật mã học (SHA-256 Hash Chain) phục vụ thuyết trình và kiểm định an toàn dữ liệu."

    def add_arguments(self, parser):
        parser.add_argument(
            "--organization",
            dest="organization",
            default="an-phuc-demo",
            help="Slug hoặc ID của tổ chức cần kiểm toán (mặc định: an-phuc-demo).",
        )
        parser.add_argument(
            "--tamper",
            type=int,
            dest="tamper_sequence",
            help="[DEMO] Giả lập can thiệp sửa đổi trái phép một block tại sequence chỉ định để minh họa trước lớp.",
        )
        parser.add_argument(
            "--restore",
            type=int,
            dest="restore_sequence",
            help="[DEMO] Khôi phục lại trạng thái băm toàn vẹn cho block sau khi demo.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Xuất kết quả dưới định dạng JSON có cấu trúc.",
        )

    def handle(self, *args, **options):
        org_identifier = options["organization"]
        organization = (
            Organization.objects.filter(slug=org_identifier).first()
            or Organization.objects.filter(pk=org_identifier).first()
            or Organization.objects.first()
        )

        if not organization:
            raise CommandError(f"Không tìm thấy tổ chức với định danh '{org_identifier}'. Hãy chạy seed_demo trước.")

        # Handle Tamper Simulation
        if options.get("tamper_sequence") is not None:
            seq = options["tamper_sequence"]
            try:
                backup = services.simulate_audit_tampering(
                    organization=organization,
                    sequence=seq,
                    tampered_metadata={"_demo_tampered": True, "actor_compromised": "attacker_demo"},
                )
                self.stdout.write(self.style.WARNING(f"\n[DEMO CAN THIỆP] Đã giả lập sửa đổi trái phép metadata tại Block #{seq}!"))
                self.stdout.write(f"  - Event ID: {backup['event_id']}")
                self.stdout.write(f"  - Original Hash: {backup['original_hash']}")
                self.stdout.write(self.style.NOTICE("-> Chạy lại lệnh kiểm toán để quan sát hệ thống phát hiện gian lận:\n   python manage.py verify_audit_chain --organization " + organization.slug + "\n"))
                return
            except Exception as exc:
                raise CommandError(f"Lỗi khi giả lập can thiệp: {exc}")

        # Handle Restore Simulation
        if options.get("restore_sequence") is not None:
            seq = options["restore_sequence"]
            try:
                services.restore_audit_event(organization=organization, sequence=seq)
                self.stdout.write(self.style.SUCCESS(f"\n[DEMO KHÔI PHỤC] Đã khôi phục tính toàn vẹn mật mã học cho Block #{seq}!"))
                self.stdout.write(self.style.NOTICE("-> Chạy lại lệnh kiểm toán để xác nhận chuỗi băm đã xanh sạch:\n   python manage.py verify_audit_chain --organization " + organization.slug + "\n"))
                return
            except Exception as exc:
                raise CommandError(f"Lỗi khi khôi phục: {exc}")

        # Run Verification
        report = services.verify_audit_chain(organization=organization, return_report=True)

        if options.get("as_json"):
            self.stdout.write(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
            return

        # Visual Terminal Presentation
        self.stdout.write("=" * 72)
        self.stdout.write(self.style.HTTP_INFO("  DATASHIELD — BÁO CÁO KIỂM TOÁN CHUỖI BĂM MẬT MÃ HỌC (AUDIT HASH-CHAIN)"))
        self.stdout.write("=" * 72)
        self.stdout.write(f"  Tổ chức (Tenant):    {organization.name} ({organization.slug})")
        self.stdout.write(f"  Thuật toán băm:      SHA-256 (Merkle / Linked Cryptographic Ledger)")
        self.stdout.write(f"  Tổng số block audit: {report.total_events} bản ghi")
        self.stdout.write(f"  Thời gian thực thi:  {report.duration_ms:.3f} ms")
        self.stdout.write("-" * 72)

        if report.is_valid:
            self.stdout.write(self.style.SUCCESS("  [KẾT QUẢ]: ĐẠT TOÀN VẸN 100% (INTEGRITY VERIFIED)"))
            self.stdout.write("  -> Không có bản ghi nào bị can thiệp, xóa bỏ hoặc đứt đoạn chuỗi băm.")
        else:
            self.stdout.write(self.style.ERROR("  [KẾT QUẢ]: CẢNH BÁO ĐỎ — PHÁT HIỆN CAN THIỆP DỮ LIỆU TRÁI PHÉP!"))
            self.stdout.write(self.style.ERROR(f"  -> Điểm phát hiện đầu tiên: Block sequence #{report.tampered_sequence}"))
            if report.first_tampered_details:
                details = report.first_tampered_details
                self.stdout.write(f"     + Event ID:         {details.get('event_id')}")
                self.stdout.write(f"     + Loại sự kiện:     {details.get('event_type')}")
                self.stdout.write(f"     + Hash ghi nhận:    {details.get('recorded_hash')}")
                self.stdout.write(f"     + Hash tính lại:    {details.get('calculated_hash')}")
            self.stdout.write("\n  Danh sách vi phạm phát hiện:")
            for idx, err in enumerate(report.errors, 1):
                self.stdout.write(self.style.ERROR(f"    {idx}. {err}"))

        # Render recent blocks diagram
        recent_events = list(AuditEvent.all_objects.filter(organization=organization).order_by("-sequence")[:5])
        if recent_events:
            self.stdout.write("-" * 72)
            self.stdout.write("  5 Block Audit Gần Nhất:")
            for ev in reversed(recent_events):
                status_symbol = "✓" if (report.is_valid or ev.sequence != report.tampered_sequence) else "✗ [BỊ SỬA]"
                self.stdout.write(
                    f"  [{status_symbol}] #{ev.sequence} | {ev.event_type:<18} | Hash: {ev.event_hash[:12]}... | Prev: {ev.previous_hash[:8] or 'GENESIS':<8}"
                )
        self.stdout.write("=" * 72 + "\n")
