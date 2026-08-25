# CSD-Foundry issue #37 event-history checkpoint

## Result

The first live `github_process_event_history` probe succeeded against `ElephantRock/CSD-Foundry` issue #37.

- LemmaMind workflow run: `32869669389`
- branch head: `445642b07bca6032b83ef446e4ea05c434aac93e`
- offline regression suite: **97 passed**
- live event-history step: **success**
- source analysis anchor: `aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7`
- recovered issue events: **9**
- deterministic event facts: **54**

## Observed state transition

GitHub's issue-event endpoint directly records:

| Event | Provider event ID | Timestamp | Actor |
| --- | --- | --- | --- |
| `closed` | `29940854834` | `2026-08-24T21:31:54Z` | `Alajmah` |
| `reopened` | `29941032785` | `2026-08-24T21:36:12Z` | `Alajmah` |

Therefore the historical proposition **“issue #37 was closed and later reopened”** is now direct provider evidence. It is no longer an inference from comments or current state.

## Evidence boundary

The durable artifact is captured separately from the current issue snapshot at:

```text
$github/issue/37/events
```

The event artifact carries provider event IDs, event kinds, actors, UTC timestamps, and optional commit references. It is content-addressed and attached to the same `SourceRevision` analysis generation as other CSD evidence, while the provider event timestamps remain the event-history time authority.

The reader paginates with `per_page=100` and fails closed if the configured page ceiling would truncate history.

## What this does not conclude

Event history does **not** itself establish:

```text
implementation complete
!=
evidentiary closure complete
```

That is a derived temporal/frontier reconciliation over multiple evidence classes. The close→reopen sequence is now an observed input to that later reasoning layer, not the conclusion itself.

## Readiness effect

`github_process_event_history` moves from `missing` to `implemented`.

`csd-foundry-frontier` remains `blocked`, but its only remaining blocker is now:

```text
temporal_change_reconciliation
```

Historical evidence remains append-only; the later reconciliation must supersede an earlier stronger conclusion rather than rewrite or erase it.
