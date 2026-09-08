from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "m5-frozen-semantic-replay.yml"
)


def _validate_section() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    return text.split("\n  validate:\n", 1)[1].split("\n  aggregate:\n", 1)[0]


def test_validation_state_retrieval_has_exactly_one_bounded_retry() -> None:
    section = _validate_section()

    assert section.count("name: state-${{ matrix.repo_key }}") == 2
    assert "id: download_state" in section
    assert section.count("continue-on-error: true") == 1
    assert "id: state_shape" in section
    assert section.count("if: steps.state_shape.outputs.complete != 'true'") == 2
    assert "name: Retry authenticated state download once" in section


def test_validation_retry_discards_partial_state_and_never_synthesizes_files() -> None:
    section = _validate_section()
    cleanup_index = section.index("name: Discard incomplete authenticated state before retry")
    retry_index = section.index("name: Retry authenticated state download once")

    assert cleanup_index < retry_index
    assert "rm -rf state" in section
    assert "mkdir -p state" in section
    assert "touch state/" not in section
    assert "cp inference/" not in section
    assert "artifact-sha256.txt" in section
    assert "lemmamind.db" in section
    assert "packets.json" in section
    assert "build_meta.json" in section


def test_validation_integrity_remains_mandatory_after_retry() -> None:
    section = _validate_section()

    retry_index = section.index("name: Retry authenticated state download once")
    verify_index = section.index("name: Verify cross-stage artifact integrity")
    validate_index = section.index("name: Validate semantic proposals and group review surface")

    assert retry_index < verify_index < validate_index
    assert "for required in lemmamind.db packets.json build_meta.json artifact-sha256.txt" in section
    assert "[[ -f \"state/${required}\" ]] ||" in section
    assert "sha256sum --check --strict artifact-sha256.txt" in section
    assert "cmp --silent state/artifact-sha256.txt inference/input-artifact-sha256.txt" in section
