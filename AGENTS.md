# Project agreements

- Scope: reusable Douyin commerce review Skill and offline evidence checks. No automatic advertising changes, messaging, login extraction or production deployment.
- Public source: `skills/`, `tests/`, `examples/`, `tools/`, `docs/`, root documentation. Only fully synthetic fixtures belong in Git.
- Private input, extracts, reports and run manifests live in ignored `private/`. Never publish customer/store identifiers, dashboard URLs, actual metrics, original books, local user paths or screenshots.
- Records: `CURRENT_STATE.md`, `ROADMAP.md`, `docs/history/`; reusable operation instructions are in `docs/runbooks/local-review.md`.
- All new source is independently written. Referenced projects/books inform methods; do not copy their code or substantial text without a separate license review and attribution.
- Use Python standard library for the offline pipeline. HTML is data, never executed. Missing values differ from zero. Evidence locations and input hashes must survive export.
- Platform definitions depend on product version and scope. Book advice is a hypothesis source, not a current platform rule. Do not invent missing attribution, margins or causal effects.
- Run `python -m unittest discover -s tests -v`, skill quick validation, and `python tools/check_public_payload.py --git-index` before publishing. Inspect `git diff --cached` and ignored status.
- The input pipeline supports the supplied WorkBuddy HTML schema and explicit canonical JSON; arbitrary platform exports, CSV/XLSX mapping and automatic browser collection are roadmap items.
- New decision reports use schema v2; preserve schema v1 rendering/replay compatibility. Business context, numeric highlights, task acceptance, effect criteria and feedback must stay distinct. The existing evidence engine version is independent of the decision schema.
