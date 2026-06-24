# ADR-007 — Landing TTL (hard-delete aged non-golden videos at 30 days)

- **Status:** Accepted (owner decision, ratified-with-conditions by @data-architect 2026-06-22) ·
  **AMENDED 2026-06-24 by [ADR-008]** on the *enforcement-mechanism* axis only — the guarded
  delete now targets OneLake Lakehouse `Files/` (no S3 lifecycle rule to lean on either; a
  Fabric notebook/pipeline does the same conditional-Bronze-check job `scripts/
  enforce_landing_ttl.py` did). The **policy** (30-day hard-delete, golden exemption, frozen-
  asset log) is UNCHANGED — see Binding Conditions below, still binding.
- **Date:** 2026-06-22
- **Deciders:** owner (chose hard-delete, accepting the named consequence),
  @data-architect (ultimate veto — conditional approve, the three binding conditions below),
  @finops-agent (routed the storage-vs-Glacier economics; non-blocking sanity check outstanding),
  @senior-data-engineer (guard-script buildability)
- **Amends:** `DATA_MODEL.md` §3 (landing TTL exception + frozen-consequence note).
- **Does NOT touch:** Bronze immutability (ADR-003), the §9 cost firewall, the data model.

## Context

Landing (`landing/<client_id>/video/<asset_id>.<ext>`) holds the **only** full video binary
in the system. It is write-once but, until now, retained forever. The owner wants aged source
video purged to cap landing storage and limit how long raw client footage is held.

Per-client retention is parameterized by `dim_client.landing_ttl_days` (ADR-006); the default
and the decision below is **30 days**.

**What is and isn't threatened (framing correction — binding for the record).** The §9 cost
firewall is *"re-parse, never re-pay"*: Bronze JSON is kept forever, so re-parsing an
extraction into a new model shape is always free. **The TTL does not threaten the firewall.**
Bronze is never touched. What a landing delete surrenders is a *different, separate* ability:
to **re-EXTRACT** — to deliberately re-pay Gemini on a *new prompt or model version* — because
re-extraction needs the original bytes, and the bytes are what's deleted. The firewall is
intact; the casualty is **re-extract optionality**, and it is consciously surrendered
everywhere except the golden set.

## Decision

**Aged non-golden landing videos are HARD-DELETED at `landing_ttl_days` (default 30).** The
owner explicitly accepts the consequence below. Three conditions are **binding** — the TTL
process is not compliant without all three.

### Condition 1 — GOLDEN-DATASET EXEMPTION (permanent)

Golden-dataset videos are **permanently exempt** from TTL and are never deleted.

- **Mechanism:** golden videos land under a **separate non-expiring prefix**,
  `landing/_golden/<asset_id>.<ext>`, which the guarded-delete process **never scans**. (A
  `no-expire` object tag is the secondary marker, but the prefix is the primary, structural
  guarantee — a tag can be dropped by a careless re-upload; a prefix the deleter doesn't list
  cannot be.)
- **Why binding:** the deploy gate (`DATA_MODEL.md` §7 gate-3 — golden re-run on every
  prompt/model change) requires the original golden bytes to re-extract against the new
  prompt/model. If golden footage aged out, that gate would become **un-rerunnable** and the
  pipeline would lose its only deploy-blocking quality check. Non-negotiable.

### Condition 2 — PRE-DELETE BRONZE GUARD (no Bronze = no delete)

Nothing in landing is deleted unless its Bronze JSON
(`bronze/<client_id>/asset_raw/<asset_id>.parquet`) is **confirmed present** first.

- **Why an S3-native lifecycle rule is INSUFFICIENT:** S3 lifecycle expiration is an
  unconditional age rule — it cannot check "does a corresponding Bronze object exist?" and it
  cannot exclude the golden set by anything richer than a prefix/tag it's configured with
  before the fact. Relying on lifecycle alone risks deleting bytes whose extraction never
  completed → an asset that is **neither re-extractable nor re-parseable** (data loss).
- **Mandated mechanism:** a **scheduled guarded-delete script** (Airflow task), NOT a bare S3
  lifecycle rule. For each landing object older than the client's `landing_ttl_days`, the
  script: (1) skips anything under `landing/_golden/`; (2) confirms the matching
  `bronze/<client_id>/asset_raw/<asset_id>.parquet` exists; (3) only then deletes the landing
  object. No Bronze, or golden prefix → **skip, do not delete.** (An S3 lifecycle rule MAY be
  used as a coarse backstop only on a prefix proven to be fully extracted, but it never
  substitutes for the guard.)

### Condition 3 — NAMED CONSEQUENCE (frozen assets)

Recorded here and in `DATA_MODEL.md` §3: once an asset's landing bytes are deleted, that asset
is **FROZEN at its last extraction.** Re-extraction (re-pay on a new prompt/model) is
permanently impossible for it; only **re-parse from the immutable Bronze JSON** survives. This
is the accepted trade — the surrendered capability is re-extract optionality, not the §9
firewall (see Context).

## Rationale

- Source video is large relative to its analytical value once extracted; Bronze JSON is the
  durable asset. Capping landing retention is a reasonable storage/holding-period control.
- The three conditions ensure the cap never costs the project something irreplaceable: the
  deploy gate (golden exemption), pipeline integrity (Bronze guard), and an honest, recorded
  trade (named consequence) rather than a silent capability loss.

## Rejected alternatives

1. **Bare S3 lifecycle expiration rule, no script.** Rejected — cannot honour Condition 2
   (no conditional Bronze check) and is brittle on Condition 1.
2. **Delete Bronze too.** 🛑 VETOED — violates ADR-003 immutability and the §9 firewall; would
   destroy re-parse, the one capability the firewall guarantees. Bronze is forever, full stop.
3. **No TTL (retain landing forever).** Valid, but the owner chose the cap; recorded as the
   rejected status-quo.
4. **Glacier/cold-tier instead of delete.** Routed to @finops; owner chose hard-delete anyway.
   See Consequences for the outstanding non-blocking check.

## Consequences

- **Positive:** bounded landing storage and a bounded client-footage holding period; the
  durable asset (Bronze) and the deploy gate (golden) are fully protected.
- **Negative / accepted (owner-accepted):** aged non-golden assets are **frozen** —
  re-extraction on a future prompt/model is impossible for them; only re-parse remains.
- **FinOps follow-up (non-blocking):** @finops should sanity-check whether hard-deleting
  KB–MB videos is worth the lost re-extract optionality, given §9 already calls storage
  "noise by comparison" to Gemini token spend. This does **not** block ADR-007 — the owner has
  decided — but the check is recorded so the economics are revisited if landing volume grows.
