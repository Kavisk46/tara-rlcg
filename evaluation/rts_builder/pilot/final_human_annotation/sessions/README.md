# Annotator Session Directories

Two independent working copies of `annotation_queue.jsonl`, one per
annotator, seeded identically from the workspace's top-level
`annotation_queue.jsonl` (439 records, every `grade` still
`"TO_BE_ASSIGNED"`). Each annotator grades **their own copy**
independently — neither should read the other's copy before both are
complete and submitted, per `RELEVANCE_ANNOTATION_HANDBOOK.md` §6's
double-annotation requirement.

## Per-session directory contents

```
sessions/annotator_A/
  annotation_queue.jsonl   -- annotator A's working copy; edited in place as grading proceeds
  session_log.jsonl        -- one line per work session (see schema below); empty until sessions begin
sessions/annotator_B/
  annotation_queue.jsonl   -- annotator B's working copy
  session_log.jsonl
```

**Neither `session_log.jsonl` file has been populated** — no
annotation session has occurred yet. They are present as empty files
so the expected location is unambiguous, not as placeholders
containing fabricated session data.

## `session_log.jsonl` schema

One JSON object per line, one line per work session (target session
length: approximately 2 hours, per `annotation_checklist.md`):

```json
{
  "session_id": "",
  "annotator_id": "",
  "start_time": "",
  "end_time": "",
  "queries_completed": 0,
  "judgments_completed": 0
}
```

`start_time`/`end_time` should be ISO 8601 UTC timestamps
(`YYYY-MM-DDTHH:MM:SSZ`), matching the `timestamp` field convention
used in `annotation_queue.jsonl` records.
