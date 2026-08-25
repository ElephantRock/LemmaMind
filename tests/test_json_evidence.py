from lemmamind.contracts import Artifact
from lemmamind.extraction import ExtractionError
from lemmamind.json_evidence import JsonPointerExtractor

DIGEST = "sha256:" + "a" * 64


def artifact(path: str = "policy.json") -> Artifact:
    return Artifact(
        artifact_id="artifact:json",
        capture_id="capture:json",
        source_locator=path,
        content_hash=DIGEST,
        media_type="application/json",
    )


def test_json_pointer_extractor_emits_sorted_scalar_leaves() -> None:
    extractor = JsonPointerExtractor()
    facts = extractor.extract(
        artifact(),
        b'{"z":2,"a":{"flag":false,"items":["x",3]},"slash/key":"v","tilde~key":null}',
    )

    assert [(fact.locator, fact.normalized_value) for fact in facts] == [
        ("policy.json#/a/flag", False),
        ("policy.json#/a/items/0", "x"),
        ("policy.json#/a/items/1", 3),
        ("policy.json#/slash~1key", "v"),
        ("policy.json#/tilde~0key", None),
        ("policy.json#/z", 2),
    ]
    assert all(fact.extractor_name == "json-pointer" for fact in facts)
    assert all(fact.extractor_version == "1" for fact in facts)


def test_json_pointer_extractor_is_opt_in_by_json_suffix() -> None:
    extractor = JsonPointerExtractor()
    assert extractor.supports(artifact("governance.json")) is True
    assert extractor.supports(artifact("README.md")) is False


def test_json_pointer_extractor_rejects_nonfinite_numbers() -> None:
    extractor = JsonPointerExtractor()
    try:
        extractor.extract(artifact(), b'{"value": NaN}')
    except ExtractionError as exc:
        assert "invalid JSON" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("non-finite JSON must fail closed")
