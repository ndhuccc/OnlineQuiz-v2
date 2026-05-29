from django.contrib import admin

from .models import Answer, Option, Participant, Question, QuestionBank, QuizSession


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
