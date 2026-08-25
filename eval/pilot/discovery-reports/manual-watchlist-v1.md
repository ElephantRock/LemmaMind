# Manual watchlist discovery checkpoint

## Channel

```text
discovery_channel_id: discovery-channel:manual-watchlist:pilot
channel_type: manual_watchlist
canonical_locator: pilot/watchlist.yaml
```

## Frozen input

The M−1 watchlist remains the first curated M1 channel. It contains **13 ordered repository locators**: 9 ElephantRock repositories and 4 external read-only repositories.

The M1 adapter hashes the exact YAML bytes and records that digest in the `PipelineRun` input material. A later edit to the watchlist therefore produces a new discovery-run input hash without rewriting earlier discovery history.

## Lineage demonstrated

```text
DiscoveryChannel
       ↓
DiscoveryRun
       ↓
13 DiscoveryHits
```

The regression suite verifies that hit ordering matches the watchlist exactly:

1. `ElephantRock/ExpertOS`
2. `ElephantRock/ExpertForge`
3. `ElephantRock/CSD-Foundry`
4. `ElephantRock/ERLab`
5. `ElephantRock/Resonance-Field`
6. `ElephantRock/Resonance-World`
7. `ElephantRock/Resonance-ContextGraph`
8. `ElephantRock/ASRI`
9. `ElephantRock/Resonance-ASRI`
10. `chrisliu298/awesome-on-policy-distillation`
11. `CopilotKit/OpenBot`
12. `openclaw/openclaw`
13. `NousResearch/hermes-agent`

## Identity boundary

The final M1 design permits all 13 hits to be recorded before M2 identity resolution:

```text
DiscoveryHit.source_id = null
```

When a stable `Source` is already known, the same adapter may link that hit immediately. Any supplied link must resolve to an existing `Source`; M1 never invents placeholder identities.

This corrects an earlier branch-local design that required Source resolution before discovery and would have made M1 circular with M2.

## Validation

Temporary branch run `32877853029` passed the complete repository suite after the boundary correction:

```text
121 passed
```

The checkpoint proves the manual-watchlist discovery lineage and its M1/M2 separation. It does not claim that GitHub stars, saved searches, registry evolution, or automatic discovery are implemented.
