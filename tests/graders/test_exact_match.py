from agent_eval_lab.graders.exact_match import grade_exact_match


def test_exact_match_passes_identical_values() -> None:
    result = grade_exact_match(expected="get_weather", actual="get_weather")

    assert result.passed is True
    assert result.score == 1.0
    assert result.feedback == "Values match exactly."


def test_exact_match_fails_different_values() -> None:
    result = grade_exact_match(expected="get_weather", actual="search_docs")

    assert result.passed is False
    assert result.score == 0.0
    assert result.feedback == "Expected 'get_weather', received 'search_docs'."
