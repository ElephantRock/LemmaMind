from lemmamind.github import GitHubRESTReader


def test_rfc850_date_exactly_fifty_years_in_future_keeps_candidate_century() -> None:
    reader = GitHubRESTReader(wall_clock=lambda: 1767225600.0)

    assert reader._parse_retry_after(
        "Wednesday, 01-Jan-76 00:00:00 GMT"
    ) == 1577836800.0


def test_rfc850_date_more_than_fifty_years_in_future_rolls_back_century() -> None:
    reader = GitHubRESTReader(wall_clock=lambda: 1767225600.0)

    assert reader._parse_retry_after(
        "Wednesday, 01-Jan-76 00:00:01 GMT"
    ) == 0.0
