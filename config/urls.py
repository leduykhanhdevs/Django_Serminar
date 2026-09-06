from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from django.http import HttpResponse

urlpatterns = [
    path("favicon.ico", lambda request: HttpResponse(b"", content_type="image/x-icon", status=204)),
    path("admin/", admin.site.urls),
    path("", include("privacy.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

