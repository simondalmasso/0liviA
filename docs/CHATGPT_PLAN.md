# ChatGPT plan provider — one-time setup

Status: **transport implemented / OAuth onboarding implemented / production connection not yet verified**

0liviA can use OpenAI's official **Sign in with ChatGPT** plan-usage flow for an eligible ChatGPT Plus/Pro owner. This is not an API-key workaround and does not use ChatGPT private `backend-api` surfaces.

Official references:
- https://developers.openai.com/siwc/token-sharing-open-source
- https://developers.openai.com/siwc/token-sharing-open-source/sign-in
- https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference
- https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms
- https://help.openai.com/en/articles/20001542-using-your-chatgpt-plan-in-other-apps-and-sites

## Cost gate first

Before enabling this provider, open **ChatGPT → Settings → Usage** and verify the app cannot consume paid credits.

OpenAI documents that:
- app credit use is opt-in and off by default;
- a per-app usage limit below 100% prevents credit use for that app;
- if plan/allowed credits cannot be used, the app does not silently switch to another paid option.

0liviA still fails closed locally: `cost_mode=plan_included` is rejected while hard-zero-cost is enabled unless `no_credit_overage_verified=true`.

## 1. Connect once on the machine with your browser

A remote VM cannot receive a `127.0.0.1` OAuth callback from your browser. Complete OAuth locally, then transfer the protected profile to the Core.

```bash
python -m venv .venv-chatgpt
. .venv-chatgpt/bin/activate
pip install -e '.[chatgpt]'
python scripts/connect_chatgpt_plan.py
```

On Windows PowerShell, activate with:

```powershell
.\.venv-chatgpt\Scripts\Activate.ps1
python -m pip install -e ".[chatgpt]"
python scripts\connect_chatgpt_plan.py
```

The helper:
- creates/reuses a stable opaque host ID;
- uses fresh state, nonce and PKCE;
- uses OpenAI dynamic registration for the first account connection;
- validates the ID-token signature against OpenAI JWKS, plus issuer, audience and nonce;
- requires the `chatgpt.tokens.use.direct` grant;
- lists the signed-in account's visible model catalog;
- writes `~/.config/0livia/chatgpt-plan.json` atomically with owner-only permissions;
- never prints access or refresh tokens.

The local OAuth helper is one-time setup. Normal 0liviA runtime remains cloud-first.

## 2. Transfer the profile to the Core

Transfer over SSH/SCP. Never paste the profile into chat, Library, Memory, a browser form or Git.

Example:

```bash
scp ~/.config/0livia/chatgpt-plan.json USER@HOST:/tmp/chatgpt-plan.json
```

Then on the 0liviA host:

```bash
sudo env OLIVIA_CHATGPT_NO_CREDIT_OVERAGE_VERIFIED=1 \
  bash /opt/0livia/current/scripts/install_chatgpt_plan_profile.sh \
  /tmp/chatgpt-plan.json
rm -f /tmp/chatgpt-plan.json
```

The installer copies the profile to:

```text
/var/lib/0livia/private/chatgpt-plan.json
```

with mode `0600`, selects the OAuth account's recommended/available model, prepends the provider to the existing catalog and restarts only the Python Core.

## 3. Runtime contract

The provider:
- calls only `https://api.openai.com/v1/responses`;
- sets `store:false` and `stream:true`;
- keeps conversation state in 0liviA, not OpenAI Responses storage;
- refreshes OAuth tokens server-side, respects OpenAI's `earliest_refresh_at`, serializes rotation and writes the replacement refresh token atomically;
- treats plan/app-limit exhaustion as quota failure;
- may fail over only before visible output to another eligible provider;
- never accepts an OpenAI API key.

The configured model slug must exist in the connected account's model catalog. `gpt-6-astra` is preferred only when the account actually exposes it.

## Disconnect / recovery

To end the renewable ChatGPT session from the machine that holds the profile:

```bash
python scripts/connect_chatgpt_plan.py --disconnect
```

The helper:
- discovers OpenAI's current `revocation_endpoint`;
- posts the saved refresh token with `token_type_hint=refresh_token` and the issued client ID;
- retries only bounded network/5xx failures;
- removes the local credential profile whether or not remote revocation can be confirmed;
- never prints the refresh/access token.

If remote revocation cannot be confirmed, the CLI says so explicitly. Check **ChatGPT Settings** and disconnect 0liviA there if it still appears.

If refresh becomes terminally invalid:
- stop using the route;
- reconnect with the local helper using the retained host ID and the issued client mapping where available;
- never loop OAuth or requests to bypass a plan/app limit.

For a compromised profile, disconnect the app in ChatGPT settings, remove any copied VM profile, and reconnect.

## Not yet claimed

Until a real owner connection is completed and smoked:
- 0liviA does **not** claim GPT-6 Astra is live;
- no ChatGPT-plan production availability or latency claim is made;
- no claim of unlimited usage is made.
