from rest_framework import serializers

from quiz.models import Option, Question, QuestionBank


class OptionPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ["id", "letter", "label_text", "sort_order"]


class QuestionPublicSerializer(serializers.ModelSerializer):
    options = OptionPublicSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "order_index",
            "stem_text",
            "type",
            "category",
            "question_type_tag",
            "points",
            "timer_seconds",
            "options",
        ]


class QuestionDetailSerializer(QuestionPublicSerializer):
    """含解析，仍不洩漏 is_correct。"""

    class Meta(QuestionPublicSerializer.Meta):
        fields = QuestionPublicSerializer.Meta.fields + ["explanation_text"]


class QuestionBankListSerializer(serializers.ModelSerializer):
    question_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = QuestionBank
        fields = [
            "id",
            "name",
            "description",
            "default_points",
            "default_timer_seconds",
            "question_count",
            "imported_at",
            "updated_at",
        ]


class QuestionBankDetailSerializer(QuestionBankListSerializer):
    questions = QuestionDetailSerializer(many=True, read_only=True)

    class Meta(QuestionBankListSerializer.Meta):
        fields = QuestionBankListSerializer.Meta.fields + ["questions"]
