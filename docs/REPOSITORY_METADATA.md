# Repository metadata and discoverability

## GitHub About (requires repository administration)

Suggested description (<=160 characters):

`Personal AI workspace with a Python/SQLite Core, lightweight web UI, agents, memory, replaceable LLMs and a strict zero-cost-first policy.`

Suggested topics:
`personal-ai`, `agentic-ai`, `python`, `sqlite`, `llm`, `self-hosted`, `cloudflare-workers`, `ai-agents`, `model-routing`, `voice-ai`

The website field is configured in GitHub About; use the verified canonical deployment origin. Do not hardcode an owner's private runtime host into reusable source files. The GitHub Admin description/topics are **not changed** by merging a content PR.

Do **not** add an `open-source` topic until the owner has chosen and published a license after copyright and dependency review. A public repository is not automatically licensed for reuse.


## Release names, tags and QA truth

GitHub issue labels (such as `P0`, `auth0` and `release-blocker`) classify work; **Git version tags** identify immutable commits. They are not interchangeable.

Do not create a `v1.0`, `production-ready` or `owner-chat-pass` Git tag merely because CI is green or a static Worker deploy succeeds. Name a functional release only after the independent **real-owner acceptance** described in the root README and [release issue #115](https://github.com/simondalmasso/0liviA/issues/115). Publish the precise source commit, deployed commit, verified account-tier/no-overage evidence and authorization outcome (sanitized) in the release notes.

Until then, report the distinction explicitly: `OFFLINE_TESTS=PASS` may coexist with `OWNER_CHAT_LIVE=FAIL`. Do not tag or mark the Python Core operational because a Cloudflare demonstration responds.


## Public-shell SEO scope

- Existing product title and description are preserved because they are part of the browser UI/test contract.
- The static entry page adds crawler/locale/brand metadata and a portable root-relative canonical link.
- `robots.txt` allows the public homepage and excludes private API paths.
- No static `sitemap.xml` is committed: sitemap URLs must be absolute and deployment-specific, so generate one separately only after the canonical domain is owned and verified.
- No personal deployment host, credentials or private Core endpoint is embedded in HTML/docs.
- The actual production Worker currently runs **static-only, no inference**; the Python Core is a separate service and is not certified deployed.
- These files do not create Firebase DNS, redirects, accounts or deployments. Publish via a separate exact-SHA release after security review.
