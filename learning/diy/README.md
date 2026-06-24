# DIY build practice

Where you reproduce the build artifacts yourself (the real models/specs are the answer key).

- `TICKET_<name>.md` — @cikgu writes the spec (WHAT not HOW). Read it, then build.
- `<name>_diy.sql` / `<name>_diy.py` — your attempt. Use `cheatsheets/` at the elbow
  (pattern-level help, never the answer).
- When you say "done", @cikgu opens the real model and you diff line-by-line, WHY on every gap.

Suggested first DIY (after Module 6): rebuild the Gold `fact_chunk` T-SQL view from the
Silver notebook's cleaned-chunk shape (`warehouse/core/fact_chunk.sql`, F2). Then the harder
one: `int_metric_chunk_alignment` (the time-range join — Module 8), also a Gold view.

Nothing here is graded for correctness on first try. It's graded on whether you can explain the
gap between your version and the reference.
