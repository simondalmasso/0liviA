# Privacy model

0liviA is designed so that a public copy of the code does not create shared access to another user's data or infrastructure.

## Separate runtime state

Each installation has **separate runtime state**:
- owner account;
- chats and projects;
- library and memory;
- job history;
- provider credentials;
- trusted devices;
- SQLite database.

Forking the repository does not copy another deployment's runtime database, cookies, provider keys or cloud-account credentials.

## Data flow

The canonical Core keeps durable state server-side in SQLite.

Browser IndexedDB is only a disposable cache/migration layer.

External model/search providers receive request context only when the deployment owner has explicitly configured that provider. Provider credentials remain server-side.

The canonical Core does not include maintainer-operated analytics or a maintainer-owned data plane.

## Cloudflare

Cloudflare is optional. The repository does not require the maintainer's Cloudflare account.

The transitional Cloudflare inference/read bridge is disabled by default. A deployment that chooses Cloudflare must use its own account and credentials.

## Public repository

The public source tree is intentionally free of:
- personal runtime databases;
- personal email/password material;
- maintainer provider keys;
- maintainer Cloudflare account IDs/tokens;
- deployment cookies and device IDs.
