from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("quiz.api.urls")),
    # Vue SPA (teacher / student routes)
    re_path(
        r"^(?!api/|admin/|static/|ws/).*",
        TemplateView.as_view(template_name="index.html"),
        name="spa",
    ),
]
