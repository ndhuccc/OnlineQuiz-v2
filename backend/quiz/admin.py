from django import forms
from django.contrib import admin, messages
from django.http import HttpRequest
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path

from .models import Answer, Option, Participant, Question, QuestionBank, QuizSession, UserProfile
from .services.user_import import import_users_from_csv_bytes


class UserProfileImportForm(forms.Form):
    csv_file = forms.FileField(label="CSV 檔案")


class OptionInline(admin.TabularInline):
    model = Option
    extra = 0
    fields = ["letter", "label_text", "is_correct", "sort_order"]


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 0
    show_change_link = True


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = ["name", "question_count", "default_points", "imported_at"]
    search_fields = ["name"]
    inlines = [QuestionInline]

    @admin.display(description="題數")
    def question_count(self, obj: QuestionBank) -> int:
        return obj.question_count


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["bank", "order_index", "type", "category"]
    list_filter = ["type", "bank"]
    inlines = [OptionInline]


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0


@admin.register(QuizSession)
class QuizSessionAdmin(admin.ModelAdmin):
    list_display = ["join_code", "bank", "status", "current_question_index", "current_phase"]
    list_filter = ["status"]
    inlines = [ParticipantInline]


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ["session", "participant", "question", "score", "is_full_score", "submit_source"]
    list_filter = ["submit_source", "is_full_score"]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["student_no", "name", "email", "created_at", "updated_at"]
    search_fields = ["student_no", "name", "email"]
    ordering = ["student_no"]
    change_list_template = "admin/quiz/userprofile/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import/",
                self.admin_site.admin_view(self.import_users_view),
                name="quiz_userprofile_import",
            ),
        ]
        return custom_urls + urls

    def import_users_view(self, request: HttpRequest):
        if request.method == "POST":
            form = UserProfileImportForm(request.POST, request.FILES)
            if form.is_valid():
                uploaded = form.cleaned_data["csv_file"]
                try:
                    result = import_users_from_csv_bytes(uploaded.read())
                except ValueError as exc:
                    messages.error(request, str(exc))
                    return redirect("admin:quiz_userprofile_changelist")
                else:
                    if result.created_count or result.updated_count:
                        messages.success(
                            request,
                            (
                                f"CSV 匯入完成：新增 {result.created_count} 筆，"
                                f"更新 {result.updated_count} 筆。"
                            ),
                        )
                    if result.errors:
                        for err in result.errors[:10]:
                            messages.warning(request, f"第 {err.index + 1} 列：{err.message}")
                        if len(result.errors) > 10:
                            messages.warning(request, f"另有 {len(result.errors) - 10} 筆錯誤未顯示")
                    if not (result.created_count or result.updated_count):
                        messages.error(request, "沒有成功匯入任何使用者資料")
                    return redirect("admin:quiz_userprofile_changelist")
        else:
            form = UserProfileImportForm()

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "CSV 匯入使用者",
            "form": form,
        }
        return TemplateResponse(request, "admin/quiz/userprofile/import.html", context)
