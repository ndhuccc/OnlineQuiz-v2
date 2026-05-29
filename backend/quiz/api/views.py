import json
from pathlib import Path

from django.db import transaction
from django.shortcuts import get_object_or_404
from pydantic import ValidationError as PydanticValidationError
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from quiz.models import QuestionBank
from quiz.services.import_json import import_from_json_text, load_import_payload

from .serializers import QuestionBankDetailSerializer, QuestionBankListSerializer


@api_view(["GET"])
def health(request):
    return Response({"status": "ok", "backend": "django"})


@api_view(["GET", "POST"])
def question_bank_list(request):
    if request.method == "GET":
        banks = QuestionBank.objects.all()
        serializer = QuestionBankListSerializer(banks, many=True)
        return Response(serializer.data)

    return _handle_import(request)


@api_view(["GET", "DELETE"])
def question_bank_detail(request, bank_id: int):
    bank = get_object_or_404(QuestionBank, pk=bank_id)
    if request.method == "DELETE":
        with transaction.atomic():
            bank.sessions.all().delete()
            bank.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = QuestionBankDetailSerializer(bank)
    return Response(serializer.data)


def _handle_import(request):
    try:
        if request.FILES.get("file"):
            uploaded = request.FILES["file"]
            raw_text = uploaded.read().decode("utf-8-sig")
            if not raw_text.strip():
                raise ValueError(
                    "Uploaded JSON file is empty. Please choose a file with at least one question."
                )
            name = (
                request.data.get("name")
                or request.POST.get("name")
                or Path(uploaded.name).stem
            )
            default_points = float(
                request.data.get("default_points") or request.POST.get("default_points") or 1
            )
            default_timer_seconds = int(
                request.data.get("default_timer_seconds")
                or request.POST.get("default_timer_seconds")
                or 90
            )
            result = import_from_json_text(
                raw_text,
                bank_name=name,
                default_points=default_points,
                default_timer_seconds=default_timer_seconds,
            )
        else:
            body = request.data
            if isinstance(body, bytes):
                body = json.loads(body.decode())
            if "questions" in body:
                payload = load_import_payload(body)
            else:
                return Response(
                    {"detail": "請提供 JSON body（含 name、questions）或上傳 file"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            from quiz.services.import_json import import_question_bank

            result = import_question_bank(payload)
    except json.JSONDecodeError:
        return Response({"detail": "無效的 JSON"}, status=status.HTTP_400_BAD_REQUEST)
    except PydanticValidationError as exc:
        return Response({"detail": exc.errors()}, status=status.HTTP_400_BAD_REQUEST)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    if not result.success:
        return Response(
            {
                "detail": "匯入失敗，沒有任何題目寫入",
                "errors": [{"index": e.index, "message": e.message} for e in result.errors],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    bank = QuestionBank.objects.get(pk=result.bank_id)
    response_data = QuestionBankDetailSerializer(bank).data
    response_data["import_report"] = {
        "imported_count": result.imported_count,
        "error_count": len(result.errors),
        "errors": [{"index": e.index, "message": e.message} for e in result.errors],
    }
    return Response(response_data, status=status.HTTP_201_CREATED)
