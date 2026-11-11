# Complete-text AI review workspace

This is preparation, not a completed review. Six33-record partitions contain66 batches of at most three full records. Read the baseline first. If a tool truncates a file, reduce the reading span and mark needs_reread until all fields are inspected. Templates contain null annotation slots and are intentionally not valid review rows.

Use assemble with an explicit reviewer ID and reader-written annotation JSON. It fills only identity, model=not_exposed, and mechanically checked quote offsets. Keep one primary JSONL per partition; preserve corrected versions and needs_reread history separately. Validation reports primary coverage, not comprehension, faithfulness or human accuracy. Second-pass plans are pending tasks, never completed checks.
