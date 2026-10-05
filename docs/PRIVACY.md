# Privacy model

0liviA is self-hosted software. By default there is no central 0liviA service collecting the content of public installations.

## Separate runtime state

Every installation has **separate runtime state** and a separate owner account.

The canonical Core stores its operational data in that installation's SQLite database, including:

- chats;
- projects;
- library items;
- promoted memory;
- jobs/checkpoints;
- remembered-device records.

The public GitHub repository is source code and engineering documentation. It is not a shared user-data store.

## Browser storage

IndexedDB is a disposable cache/migration layer when the canonical Core is active. It is not the durable source of truth.

Clearing browser storage should not erase canonical server-side projects/chats/memory after they have synchronized.

## Provider disclosure

When an operator configures a remote model provider, that provider may receive the prompt/context needed for inference.

The operator chooses those providers and is responsible for reviewing their privacy terms.

0liviA does not send prompts to a hidden maintainer-controlled model account.

## Web research

Fetched web-page/search content is treated as untrusted data.

Page/search content used by `/read`, `/search` or `/research` is injected as ephemeral context and is not promoted into durable memory merely because the page contains instructions.

## Credentials

Provider credentials, GitHub tokens, Cloudflare credentials and setup/gateway tokens are server-side configuration.

They are not requested through the normal browser UI and should never be committed to Git.

## Remembered devices

A remembered device is represented by:

- a random server-side device ID;
- a user-visible browser/platform label;
- timestamps/expiry.

0liviA does not require hardware fingerprinting for remembered-device support.

Revoking the device record invalidates the persistent owner session associated with it.

## Cloudflare

The transitional Cloudflare Worker is disabled by default for inference/read routes and is not a shared public backend.

A public clone cannot use the maintainer's Cloudflare account or data unless the maintainer separately grants credentials, which the repository does not contain.

## Deletion semantics

Explicit durable-memory deletion physically removes the selected memory key from the memory table. Chat-history retention is a separate concern and should not be represented as memory deletion.
