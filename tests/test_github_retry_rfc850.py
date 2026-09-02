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


def test_rfc850_date_near_future_can_advance_into_next_century() -> None:
    reader = GitHubRESTReader(wall_clock=lambda: 4102444799.0)

    assert reader._parse_retry_after(
        "Friday, 01-Jan-00 00:00:00 GMT"
    ) == 1.0


def test_rfc850_date_exactly_fifty_years_in_past_keeps_candidate_century() -> None:
    reader = GitHubRESTReader(wall_clock=lambda: 2524608000.0)

    assert reader._parse_retry_after(
        "Saturday, 01-Jan-00 00:00:00 GMT"
    ) == 0.0
