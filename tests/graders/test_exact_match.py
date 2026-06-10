from agent_eval_lab.graders.exact_match import grade_exact_match


def test_exact_match_passes_identical_values():
    result = grade_exact_match(expected="get_weather", actual="get_weather")
    assert result.grader_id == "output_match"
    assert result.passed is True
    assert result.score == 1.0
    assert result.failure_reason is None
    assert result.evidence["message"] == "Values match exactly."


def test_exact_match_fails_different_values():
    result = grade_exact_match(expected="get_weather", actual="search_docs")
    assert result.passed is False
    assert result.score == 0.0
    assert result.failure_reason == "wrong_tool"
    assert (
        result.evidence["message"] == "Expected 'get_weather', received 'search_docs'."
    )
