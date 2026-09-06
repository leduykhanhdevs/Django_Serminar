"""Forms for the Vietnamese-first privacy portal.

The forms deliberately avoid model-bound defaults for consent.  A subject must
affirmatively select each processing purpose and acknowledge the notice that
was presented with that choice.
"""

from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm


DSAR_REQUEST_TYPES = (
    ("access", "Xem dữ liệu cá nhân"),
    ("rectification", "Sửa dữ liệu cá nhân"),
    ("portability", "Cung cấp dữ liệu"),
    ("erasure", "Xóa dữ liệu"),
    ("restriction", "Hạn chế xử lý"),
    ("objection", "Phản đối xử lý"),
    ("withdrawal", "Rút lại sự đồng ý"),
    ("protection", "Yêu cầu biện pháp bảo vệ"),
)


class VietnameseAuthenticationForm(AuthenticationForm):
    """Django's authentication form with clear Vietnamese labels."""

    username = forms.CharField(label="Tên đăng nhập hoặc email", max_length=254)
    password = forms.CharField(label="Mật khẩu", strip=False, widget=forms.PasswordInput)


class ConsentSelectionForm(forms.Form):
    """Build one opt-in control for every active processing purpose."""

    notice_acknowledged = forms.BooleanField(
        label="Tôi đã đọc thông báo xử lý dữ liệu này.",
        required=True,
    )

    def __init__(self, *args, purposes=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.purposes = list(purposes)
        for purpose in self.purposes:
            field_name = self.field_name_for(purpose.pk)
            self.fields[field_name] = forms.BooleanField(
                label=getattr(purpose, "name", str(purpose)),
                required=False,
                initial=False,
                help_text="Để trống nếu bạn không đồng ý cho mục đích này.",
            )

    @staticmethod
    def field_name_for(purpose_id):
        return f"purpose_{purpose_id}"

    def selected_purposes(self):
        """Return only purposes explicitly checked in this submission."""
        return [
            purpose
            for purpose in self.purposes
            if self.cleaned_data.get(self.field_name_for(purpose.pk), False)
        ]

    def clean(self):
        cleaned_data = super().clean()
        if self.purposes and not any(
            cleaned_data.get(self.field_name_for(purpose.pk), False) for purpose in self.purposes
        ):
            raise forms.ValidationError("Hãy chọn ít nhất một mục đích nếu bạn muốn ghi nhận sự đồng ý.")
        return cleaned_data


class DSARCreateForm(forms.Form):
    """A data-subject request with an explicit identity confirmation."""

    subject_email = forms.EmailField(label="Email của chủ thể dữ liệu")
    request_type = forms.ChoiceField(label="Quyền bạn muốn thực hiện", choices=DSAR_REQUEST_TYPES)
    details = forms.CharField(
        label="Nội dung yêu cầu",
        required=False,
        max_length=4000,
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="Không gửi CCCD, dữ liệu sức khỏe, tài chính hoặc thông tin nhạy cảm qua biểu mẫu demo.",
    )
    identity_confirmed = forms.BooleanField(
        label="Tôi xác nhận mình là chủ thể dữ liệu hoặc có quyền đại diện hợp lệ.",
        required=True,
    )

    def __init__(self, *args, request_type_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        if request_type_choices:
            self.fields["request_type"].choices = request_type_choices


class OfficerApprovalForm(forms.Form):
    """Require an affirmative confirmation before an officer approval action."""

    confirmed = forms.BooleanField(
        label="Tôi đã rà soát hồ sơ và chịu trách nhiệm về quyết định phê duyệt.",
        required=True,
    )


class TOTPTokenForm(forms.Form):
    """A short, manually entered TOTP code for privileged local accounts."""

    token = forms.CharField(
        label="Mã xác thực 6 chữ số",
        min_length=6,
        max_length=12,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code"}),
        help_text="Mã được tạo trong ứng dụng xác thực của bạn; không gửi mã qua email.",
    )

    def clean_token(self):
        token = "".join(self.cleaned_data["token"].split())
        if not token.isdigit():
            raise forms.ValidationError("Mã xác thực chỉ gồm chữ số.")
        return token
