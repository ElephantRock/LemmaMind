from lemmamind.contracts import Artifact
from lemmamind.extraction import MarkdownListAssertionExtractor


def artifact(path: str = "README.md") -> Artifact:
    return Artifact(
        artifact_id="artifact:list-test",
        capture_id="capture:list-test",
        source_locator=path,
        content_hash="sha256:" + "0" * 64,
        media_type="text/markdown",
    )


def extracted(data: bytes):
    return MarkdownListAssertionExtractor().extract(artifact(), data)


def test_extracts_unordered_ordered_nested_and_continued_items() -> None:
    data = b"""- parent item\n  continued parent text\n  - nested child\n1. ordered item\n   continued ordered text\n"""

    result = extracted(data)

    assert [(item.locator, item.statement) for item in result] == [
        ("README.md:L1-L2", "parent item continued parent text"),
        ("README.md:L3-L3", "nested child"),
        ("README.md:L4-L5", "ordered item continued ordered text"),
    ]
    assert all(item.extractor_name == "markdown-list" for item in result)
    assert all(item.extractor_version == "1" for item in result)


def test_fenced_code_is_never_promoted_to_list_assertions() -> None:
    data = b"""- visible item\n\n```text\n- hidden code item\n```\n\n- visible after fence\n"""

    result = extracted(data)

    assert [(item.locator, item.statement) for item in result] == [
        ("README.md:L1-L1", "visible item"),
        ("README.md:L7-L7", "visible after fence"),
    ]


def test_table_and_block_quote_lines_do_not_extend_list_items() -> None:
    data = b"""- item before table\n  | a | b |\n\n- item before quote\n  > quoted material\n"""

    result = extracted(data)

    assert [(item.locator, item.statement) for item in result] == [
        ("README.md:L1-L1", "item before table"),
        ("README.md:L4-L4", "item before quote"),
    ]


def test_non_markdown_artifacts_are_not_supported() -> None:
    extractor = MarkdownListAssertionExtractor()
    assert extractor.supports(artifact("README.md")) is True
    assert extractor.supports(artifact("notes.markdown")) is True
    assert extractor.supports(artifact("config.yaml")) is False
