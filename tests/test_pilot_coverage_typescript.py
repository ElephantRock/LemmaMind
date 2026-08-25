from types import SimpleNamespace

from lemmamind.pilot_coverage_v3 import _assess_typescript_bundle


def extracted_fixture():
    return SimpleNamespace(
        assertions=[
            SimpleNamespace(
                extractor_name="typescript-comment",
                locator="server/src/tenant-package.ts:L10-L14",
                statement=(
                    "A skill is an instruction and confers nothing. "
                    "The run-time offer is always the intersection of the two."
                ),
            ),
            SimpleNamespace(
                extractor_name="typescript-comment",
                locator="server/src/tenant-package.ts:L20-L24",
                statement=(
                    "Refs are deliberately NOT checked against the tools this deployment has seen. "
                    "An unknown ref stays inert because the run-time intersection drops it."
                ),
            ),
        ],
        facts=[
            SimpleNamespace(
                extractor_name="typescript-ast",
                locator="server/src/tenant-package.ts:L30:C2-L30:C48#typescript/call",
                normalized_value={
                    "kind": "call",
                    "text": "transaction.insert(skillTools).values(rows)",
                },
            ),
            SimpleNamespace(
                extractor_name="typescript-ast",
                locator="server/src/tenant-package.ts:L31:C2-L31:C52#typescript/call",
                normalized_value={
                    "kind": "call",
                    "text": "transaction.insert(pluginGrants).values(grants)",
                },
            ),
            SimpleNamespace(
                extractor_name="typescript-ast",
                locator="server/src/tenant-package.ts:L40:C2-L42:C3#typescript/if",
                normalized_value={
                    "kind": "if",
                    "condition": "(!skillSlugs.has(slug))",
                    "text": "if (!skillSlugs.has(slug)) { throw new Error('missing'); }",
                },
            ),
        ],
    )


def test_bundle_requires_comments_and_structural_facts() -> None:
    requirement = {
        "evidence_id": "openbot-authority-2",
        "evidence_type": "ObservedFact",
        "check": {
            "kind": "typescript_evidence_bundle",
            "artifact": "server/src/tenant-package.ts",
            "comment_fragments": [
                "instruction and confers nothing",
                "run-time offer is always the intersection",
            ],
            "fact_selectors": [
                {"kind": "call", "field": "text", "contains": "insert(skillTools)"},
                {"kind": "call", "field": "text", "contains": "insert(pluginGrants)"},
            ],
        },
        "needed_capability_if_missing": "typescript-comments-and-structural-facts",
    }

    result = _assess_typescript_bundle(requirement, extracted_fixture())
    assert result.status == "recovered"
    assert result.check_kind == "typescript_evidence_bundle"
    assert len(result.matched_locators) == 4


def test_bundle_reports_missing_fact_without_promoting_comment() -> None:
    requirement = {
        "evidence_id": "openbot-authority-3",
        "evidence_type": "ObservedFact",
        "check": {
            "kind": "typescript_evidence_bundle",
            "artifact": "server/src/tenant-package.ts",
            "comment_fragments": ["run-time intersection drops it"],
            "fact_selectors": [
                {"kind": "throw", "field": "text", "contains": "does not ship"},
            ],
        },
        "needed_capability_if_missing": "typescript-comments-and-structural-facts",
    }

    result = _assess_typescript_bundle(requirement, extracted_fixture())
    assert result.status == "gap"
    assert result.needed_capability == "typescript-comments-and-structural-facts"
    assert any(item.startswith("fact:throw:text") for item in result.missing_fragments)
