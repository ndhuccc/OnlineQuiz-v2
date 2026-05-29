import pytest

from quiz.services.grading import grade_answer


@pytest.mark.parametrize(
    "correct,selected,n,points,expected_score,is_full",
    [
        ({"A", "B", "C"}, {"A", "B", "C"}, 4, 2.0, 2.0, True),
        ({"A", "B", "C"}, {"A", "B"}, 4, 2.0, 1.0, False),
        ({"A", "B", "C"}, {"A"}, 4, 2.0, 0.0, False),
        ({"B"}, {"B"}, 4, 2.0, 2.0, True),
        ({"B"}, {"A"}, 4, 2.0, 0.0, False),
    ],
)
def test_grade_answer(correct, selected, n, points, expected_score, is_full):
    score, full = grade_answer(
        n_options=n,
        correct_letters=correct,
        selected_letters=selected,
        points=points,
    )
    assert score == pytest.approx(expected_score)
    assert full is is_full
