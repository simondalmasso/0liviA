# Self-hosting 0liviA

0liviA is designed so each installation owns its identity, data and providers.

## 1. Clone or fork

Clone the repository into infrastructure you control.

Do not reuse another person's environment file, runtime database, Cloudflare account or provider credentials.

## 2. Configure your own provider routes

Start from `.env.example`.

Every external model/search route must use **your own provider** account and credentials.

Provider secrets stay server-side. `OLIVIA_PROVIDERS_JSON` references environment-variable names; it does not contain the secret itself.

## 3. First-run registration

Production bootstrap creates:
- a unique internal gateway token;
- a one-time registration setup token.

Open the root-only `SETUP_URL`, choose **Registrate**, create the owner email/password, and optionally enable **Recordarme**.

After the first owner is created, registration closes automatically.

## 4. Zero-cost-first mode

Keep:

```env
OLIVIA_HARD_ZERO_COST=1
```

Allowed route classes:
- `local`;
- `free_hard_cap` only when that deployment has verified the upstream cannot bill beyond its free boundary.

Blocked route classes:
- `free_unverified`;
- `paid`.

If all eligible routes are exhausted or unavailable, 0liviA degrades/fails rather than silently paying.

This is not a guarantee that third-party services remain free forever.

## 5. Optional Cloudflare

The canonical Python Core does not require Cloudflare.

If you choose Cloudflare features, connect your own account. The transitional inference/read Worker in this repository is disabled by default.

## 6. Optional coding worker

Configure your own repository:

```env
OLIVIA_CODING_WORKER_ENABLED=1
OLIVIA_CODING_REPO=owner/your-repo
OLIVIA_CODING_BASE_REF=main
```

Configure that repository's Actions with operator-owned values:

- secret `OLIVIA_CODING_API_KEY`;
- variable `OLIVIA_CODING_API_BASE` (optional; defaults to the NVIDIA NIM OpenAI-compatible endpoint);
- variable `OLIVIA_CODING_MODEL` (optional; defaults to DeepSeek V4.1 Flash);
- variable `OLIVIA_CODING_ZERO_COST_VERIFIED=true` only after the operator verifies that exact route/account cannot create spend.

The workflow fails closed if the zero-cost verification flag is absent/false or if the API key is absent.

For backward compatibility, an existing `NVIDIA_API_KEY` secret may still be used as a fallback key name. Public forks inherit no secret values from this repository.

## 7. Runtime data

Durable state belongs outside the Git checkout under `OLIVIA_DATA_DIR`.

Back up the SQLite database using an online-safe method or a clean service stop.

## 8. Public deployment rule

Do not expose a new installation before:
- HTTPS is active;
- first-owner registration is protected by the setup token;
- port 8080 remains private;
- only deployment-owned provider accounts are configured.
