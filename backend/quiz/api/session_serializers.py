from rest_framework import serializers

from quiz.models import Answer, Participant, QuizSession


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participant
        fields = ["id", "student_no", "display_name", "joined_at", "start_question_index"]


class SessionCreateSerializer(serializers.Serializer):
    bank_id = serializers.IntegerField()


class SessionJoinSerializer(serializers.Serializer):
    join_code = serializers.CharField(max_length=6)
    student_no = serializers.CharField(max_length=64)
    display_name = serializers.CharField(max_length=128, required=False, allow_blank=True, default="")
    tab_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")


class PhaseSerializer(serializers.Serializer):
    phase = serializers.ChoiceField(choices=QuizSession.Phase.values)
    timer_seconds = serializers.IntegerField(required=False, min_value=5, max_value=3600)


class TimerAdjustSerializer(serializers.Serializer):
    timer_seconds = serializers.IntegerField(min_value=-3600, max_value=3600)

    def validate_timer_seconds(self, value):
        if value == 0:
            raise serializers.ValidationError("秒數不可為 0")
        return value


class SubmitAnswerSerializer(serializers.Serializer):
    option_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True,
    )


class AnswerResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ["id", "score", "is_full_score", "submit_source", "submitted_at"]
