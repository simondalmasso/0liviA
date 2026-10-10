# Repository metadata and discoverability

## GitHub About (requires repository administration)

Suggested description (<=160 characters):

`Personal AI workspace with a Python/SQLite Core, lightweight web UI, agents, memory, replaceable LLMs and a strict zero-cost-first policy.`

Suggested topics:
`personal-ai`, `agentic-ai`, `python`, `sqlite`, `llm`, `self-hosted`, `cloudflare-workers`, `ai-agents`, `model-routing`, `voice-ai`

The website field is configured in GitHub About; use the verified canonical deployment origin. Do not hardcode an owner's private runtime host into reusable source files. The GitHub Admin description/topics are **not changed** by merging a content PR.

Do **not** add an `open-source` topic until the owner has chosen and published a license after copyright and dependency review. A public repository is not automatically licensed for reuse.

## Public-shell SEO scope

- Existing product title and description are preserved because they are part of the browser UI/test contract.
- The static entry page adds crawler/locale/brand metadata and a portable root-relative canonical link.
- `robots.txt` allows the public homepage and excludes private API paths.
- No static `sitemap.xml` is committed: sitemap URLs must be absolute and deployment-specific, so generate one separately only after the canonical domain is owned and verified.
- No personal deployment host, credentials or private Core endpoint is embedded in HTML/docs.
- The actual production Worker currently runs **static-only, no inference**; the Python Core is a separate service and is not certified deployed.
- These files do not create Firebase DNS, redirects, accounts or deployments. Publish via a separate exact-SHA release after security review.
