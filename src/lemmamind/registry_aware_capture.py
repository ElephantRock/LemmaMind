"""Registry-aware extension of the deterministic GitHub capture path.

The M0 capture service intentionally rejects mutable repository metadata drift.
This adapter preserves that default. Once M2 locator history exists for a Source,
all registry-aware captures must match the latest validated RepositoryLocator;
older seed state cannot silently regain authority.
"""
from __future__ import annotations

from .contracts import (
    DiscoveryResolution,
    PipelineRun,
    RepositoryIdentity,
    RepositoryLocator,
    RunType,
    Source,
    SourceKind,
    SourceRole,
)
from .github import (
    GitHubCaptureService,
    RepositoryIdentityDrift,
    SourceMetadataDrift,
)


class RegistryAwareGitHubCaptureService(GitHubCaptureService):
    """Permit only current M2-authorized mutable repository state."""

    def _stable_source(
        self,
        source_id: str,
        canonical_locator: str,
        source_role: SourceRole,
        observed_at,
    ) -> Source:
        existing = self.store.get(Source, source_id)
        if existing is None:
            return super()._stable_source(
                source_id,
                canonical_locator,
                source_role,
                observed_at,
            )
        if existing.source_kind is not SourceKind.GITHUB_REPOSITORY:
            raise SourceMetadataDrift(f"{source_id} changed source kind")
        if existing.source_role != source_role:
            raise SourceMetadataDrift(
                f"{source_id} is already classified as {existing.source_role.value}; "
                f"requested {source_role.value}"
            )

        has_history = self._has_registry_history(source_id)
        if has_history:
            locator = self._latest_registry_locator(
                source_id,
                canonical_locator=canonical_locator,
            )
            if locator is None:
                raise SourceMetadataDrift(
                    f"{source_id} incoming locator does not match latest validated M2 history"
                )
            return existing

        if existing.canonical_locator == canonical_locator:
            return existing
        raise SourceMetadataDrift(
            f"{source_id} canonical locator changed without matching M2 registry history"
        )

    def _stable_repository(
        self,
        source_id: str,
        provider_id: str,
        owner: str,
        name: str,
        default_branch: str,
        archived: bool,
    ) -> RepositoryIdentity:
        existing = self.store.get(RepositoryIdentity, source_id)
        if existing is None:
            return super()._stable_repository(
                source_id,
                provider_id,
                owner,
                name,
                default_branch,
                archived,
            )
        if existing.provider_repository_id != provider_id:
            raise RepositoryIdentityDrift(
                f"{source_id} provider repository ID changed; identity cannot be migrated"
            )

        has_history = self._has_registry_history(source_id)
        if has_history:
            locator = self._latest_registry_locator(
                source_id,
                provider_id=provider_id,
                owner=owner,
                name=name,
                default_branch=default_branch,
                archived=archived,
            )
            if locator is None:
                raise RepositoryIdentityDrift(
                    f"{source_id} incoming repository state does not match latest validated M2 history"
                )
            return existing

        current = (existing.owner, existing.name, existing.default_branch, existing.archived)
        incoming = (owner, name, default_branch, archived)
        if current == incoming:
            return existing
        raise RepositoryIdentityDrift(
            f"{source_id} repository metadata changed without matching M2 registry history"
        )

    def _has_registry_history(self, source_id: str) -> bool:
        return any(
            locator.source_id == source_id
            for locator in self.store.list(RepositoryLocator)
        )

    def _latest_registry_locator(
        self,
        source_id: str,
        *,
        canonical_locator: str | None = None,
        provider_id: str | None = None,
        owner: str | None = None,
        name: str | None = None,
        default_branch: str | None = None,
        archived: bool | None = None,
    ) -> RepositoryLocator | None:
        locators = [
            locator
            for locator in self.store.list(RepositoryLocator)
            if locator.source_id == source_id
        ]
        if not locators:
            return None
        latest = max(
            locators,
            key=lambda locator: (locator.observed_at, locator.repository_locator_id),
        )
        expected = {
            "canonical_locator": canonical_locator,
            "provider_repository_id": provider_id,
            "owner": owner,
            "name": name,
            "default_branch": default_branch,
            "archived": archived,
        }
        for field, value in expected.items():
            if value is not None and getattr(latest, field) != value:
                return None

        pipeline = self.store.get(PipelineRun, latest.pipeline_run_id)
        if pipeline is None or pipeline.run_type is not RunType.REGISTRY:
            return None
        resolutions = [
            resolution
            for resolution in self.store.list(DiscoveryResolution)
            if resolution.repository_locator_id == latest.repository_locator_id
            and resolution.source_id == source_id
            and resolution.pipeline_run_id == latest.pipeline_run_id
        ]
        if len(resolutions) != 1:
            return None
        return latest
