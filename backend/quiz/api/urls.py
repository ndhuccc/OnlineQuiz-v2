from django.urls import path

from . import session_views, views

urlpatterns = [
    path("health/", views.health, name="health"),
    path(
        "question-banks/",
        views.question_bank_list,
        name="question-bank-list",
    ),
    path(
        "question-banks/<int:bank_id>/",
        views.question_bank_detail,
        name="question-bank-detail",
    ),
    path("sessions/", session_views.session_create, name="session-create"),
    path("sessions/join/", session_views.session_join, name="session-join"),
    path("sessions/<int:session_id>/", session_views.session_detail, name="session-detail"),
    path("sessions/<int:session_id>/state/", session_views.session_state, name="session-state"),
    path("sessions/<int:session_id>/start/", session_views.session_start, name="session-start"),
    path("sessions/<int:session_id>/phase/", session_views.session_phase, name="session-phase"),
    path("sessions/<int:session_id>/timer/", session_views.session_timer, name="session-timer"),
    path("sessions/<int:session_id>/next/", session_views.session_next, name="session-next"),
    path(
        "sessions/<int:session_id>/stats/current/",
        session_views.session_stats_current,
        name="session-stats-current",
    ),
    path(
        "sessions/<int:session_id>/stats/summary/",
        session_views.session_stats_summary,
        name="session-stats-summary",
    ),
    path(
        "sessions/<int:session_id>/stats/question/<int:question_id>/",
        session_views.session_stats_question,
        name="session-stats-question",
    ),
    path(
        "sessions/<int:session_id>/open-review/",
        session_views.session_open_review,
        name="session-open-review",
    ),
    path("participants/me/", session_views.participant_me_state, name="participant-me"),
    path("participants/me/review/", session_views.participant_me_review, name="participant-review"),
    path("participants/me/options/", session_views.participant_me_options, name="participant-options"),
    path("participants/me/answers/", session_views.participant_me_submit, name="participant-submit"),
]
