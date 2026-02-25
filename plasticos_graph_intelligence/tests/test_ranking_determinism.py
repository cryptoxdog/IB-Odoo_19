def test_deterministic_ranking(match_service):
    intake_id = "INT-001"

    result1 = match_service.match(intake_id)
    result2 = match_service.match(intake_id)

    assert result1 == result2
