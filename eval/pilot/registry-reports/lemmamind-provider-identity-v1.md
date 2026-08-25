# LemmaMind provider identity checkpoint

## Scope

This checkpoint validates the non-destructive live boundary for the first M2 repository-registry identity/evolution slice.

It does not mutate repository ownership, name, archive state, fork state, or default branch solely for validation.

## Current provider identity

Rechecked through the authorized GitHub connection on 2026-08-26:

| Field | Observed value |
| --- | --- |
| Repository | `ElephantRock/LemmaMind` |
| GitHub provider repository ID | `1345295505` |
| Owner | `ElephantRock` |
| Name | `LemmaMind` |
| Canonical locator | `https://github.com/ElephantRock/LemmaMind` |
| Default branch | `main` |
| Archived | `false` |
| Fork | `false` |
| Visibility | `public` |

The stable identity anchor used by M2 is the provider repository ID, not owner/name.

## Implemented lineage

```text
DiscoveryChannel
       ↓
DiscoveryRun
       ↓
DiscoveryHit
       ↓
DiscoveryResolution
       ↓
Source
       ↑
RepositoryLocator
```

A later locator observation with the same provider repository ID maps to the same Source. Historical hits and prior locators remain immutable.

## Evolution validation

Rename/transfer/default-branch/archive evolution is validated deterministically rather than by mutating a real repository for demonstration.

The regression matrix establishes:

- same provider ID + later discovery hit + changed owner/name → same Source, new `RepositoryLocator`;
- same provider ID + changed default branch/archive state → same Source, new locator generation;
- resolving the same hit with identical state is idempotent;
- resolving the same historical hit with different mutable state is rejected;
- different provider ID for a fork creates a distinct Source;
- parent provider ID is preserved as an explicit relation rather than collapsing fork identity;
- one provider ID cannot map to multiple Sources;
- incomplete M1 discovery lineage cannot enter M2;
- original M0 capture remains fail-closed on drift;
- registry-aware capture accepts changed state only when the latest M2 locator authorizes it;
- stale historical locator state cannot regain capture authority after a newer locator exists.

## Test checkpoint

Temporary branch workflow run `32909661970` on head `d48f9f046d16059117593b74ad0bb6beb78330c3` passed the full repository suite after the stale-state correction:

```text
131 passed in 1.94s
```

An immediately preceding run intentionally exposed the stale-state hole in the first registry-aware capture implementation: one test failed because old seed identity state could still authorize capture after a newer M2 locator existed. The implementation was corrected so latest validated locator history takes precedence once M2 history exists.

## Boundary

This checkpoint demonstrates the identity/evolution half of M2. It does not claim the full M2 roadmap milestone is closed, because tracking levels `0–5` and their policy effects remain unimplemented.

No upstream repository mutation was required to validate the identity model.
