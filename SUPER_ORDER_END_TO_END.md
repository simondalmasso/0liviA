# 0liviA product engineering mandate 🎲

## Mission

Build 0liviA as a **public, self-hosted agentic AI workspace**: a persistent browser/mobile intelligence layer that can chat, code, research the web, use tools, keep durable project context and support low-latency live voice.

The product is not a shared hosted account and not a wrapper around one provider. Every installation owns its own identity, data, model/provider configuration and optional integrations.

## Product principles

- self-hosted by default;
- privacy-first;
- mobile-ready;
- replaceable models/providers;
- durable server-side workspace state;
- agentic coding isolated from the internet-facing core;
- safe web research with untrusted-content boundaries;
- zero-cost-first routing without hidden spend;
- no user-entered API keys in the normal browser UI;
- no dependency on a maintainer's Cloudflare, GitHub or model-provider account;
- optional ChatGPT-plan inference only through the official Sign in with ChatGPT / Responses flow, with OAuth credentials server-side and no hidden credit overage.

## Cost policy

Target recurring cost can be USD 0 when the deployment uses:
- local inference; or
- provider routes with a verified hard-free boundary.

"$0" is an engineering target, not a vendor guarantee. Paid or unverified routes must remain blocked while `OLIVIA_HARD_ZERO_COST=1`.

## Reference resource envelope

A useful low-cost benchmark profile is:
- Linux;
- ARM64 or x86_64;
- ~2 CPU cores;
- ~12 GB RAM;
- SSD-backed SQLite state.

Oracle A1 is one reference profile, not a mandatory provider.

## Required capabilities

- fast streamed chat;
- Projects / Chats / Library / Memory / Config / Session;
- first-run registration and revocable remembered devices;
- durable memory and resumable jobs;
- multi-provider routing and failover before visible output;
- isolated coding jobs with verification;
- live web read/search/research behind safe boundaries;
- mobile-first UI;
- live voice with barge-in/cancellation;
- restart/resume without losing canonical state.

## Security boundaries

- no secrets in Git, prompts or durable memory;
- no maintainer account credentials in public configuration;
- no reverse-engineered consumer-session APIs;
- browser is a thin client;
- runtime state is per installation;
- provider/API credentials stay server-side;
- optional cloud adapters fail closed when identity/cost is uncertain.

## Engineering standard

Before promoting a component:
- inspect source and license;
- verify architecture/OS support;
- benchmark on the intended target;
- define fallback/failure behavior;
- define security/privacy boundaries;
- add tests;
- keep changes reversible.

For coding work:
- inspect before edit;
- protect unrelated work;
- use small commits;
- run repo gates;
- do not claim PASS from stale evidence;
- leave a current checkpoint.

## Voice requirement

The browser experience should support:
- quick microphone start;
- streaming input;
- VAD/end-of-turn;
- partial transcript;
- streaming response audio;
- barge-in/cancel;
- shared text/voice session context;
- fallback to text without losing state.

Transport/speech components remain benchmark-gated and replaceable.

## Public-product rule

A public user installing 0liviA must never connect to a maintainer-owned backend by default.

The operator must provide their own:
- host/runtime;
- owner registration;
- model/provider route;
- optional GitHub coding integration;
- optional search/cloud integrations.

## Stop condition

A change is complete only when the repository is more usable, safer or more verifiable than before.

Do not deploy paid infrastructure.
Do not create hidden costs.
Do not expose secrets.
Do not fake completion.
