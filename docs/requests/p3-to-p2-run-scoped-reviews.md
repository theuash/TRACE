# To Person 2: reviews and runs need a run scope

**From:** Person 3 (verification, API, reviewer experience)
**What I need:** one extra piece of information on `EscalationItem`, or one extra method on
`WorkflowService`.

## The problem

`EscalationItem.review_id == ExtractedMetric.id == "<TICKER>:<metric>:<fiscal_year>"`. That id has
no run in it, so two runs of the same company produce the *same* review ids. Today the API cannot
tell "the review of run A" from "the review of run B".

Consequences I had to work around in `api/main.py`:

- A finished run still shows the open reviews of an older run of the same company in its queue.
- The API keeps the newest reviews and truncates the list to `RunSummary.pending_reviews`, which is
  correct only for the newest run of a company.
- The reviewer can only ever see one queue per company, and only if it is the newest run.

## What would fix it

Either of these, smallest first:

1. **A `run_id` field on `EscalationItem`** (and on the review rows in the audit log). The workflow
   knows the run id when it creates the escalation, so this is a one-line change plus a schema
   change in `shared/schemas.py` (frozen - needs a `contract/` branch).
2. **A `list_reviews(run_id: str | None = None)`** on the `WorkflowService` protocol, so the API can
   ask for the reviews of one run. Also a contract change, but no schema change.

With either one, the API can do exactly what it should:

- the queue of a run shows that run's reviews, nothing else;
- a finished run shows its own decided items and no pending ones;
- two runs of the same company can both be open in the dashboard, side by side.

## What I did meanwhile (no action needed, but good to know)

`api/main.py` sorts the company's reviews by `created_at`, keeps the newest `pending_reviews` of them
for the run that is actually waiting, and de-duplicates by `review_id`. It is correct for the newest
run of each company, which is what the dashboard shows. If two runs of one company are open at the
same time, the dashboard shows the newest one and the older one is reachable through the audit log.

`docs/requests/p3-to-p1-local-filing-source.md` and `p3-to-p1-broken-extraction-tests.md` are related
but separate.
