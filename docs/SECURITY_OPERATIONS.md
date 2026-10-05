# Security operations

This file is operational policy for the canonical 0liviA Core. It is not a substitute for provider/account controls.

## Secrets

- Never commit API keys, cloud credentials, passwords, private keys or backup passphrases.
- Runtime/provider secrets belong in root-owned server environment files or GitHub encrypted secrets.
- Browser UI never asks for provider/admin API keys.
- The coding agent execution job has repository read permission only; optional publication is a separate write-capable job after deterministic verification.
- Current repository audits have not established a specific live leaked key. Do not invent a rotation event. Any real secret-scanning/provider alert is treated as compromised immediately.

## Rotation procedure

If a credential is exposed or suspected:
1. Revoke/rotate it at the provider first.
2. Replace the encrypted GitHub secret or root-owned host environment value.
3. Restart only the affected service/job path.
4. Confirm the old credential fails.
5. Search current code and Git history for the leaked value/pattern.
6. Record a sanitized security event/incident note; never paste the credential into logs, issues or chat.

Provider-side rotation cannot be performed safely from the public repository itself.

## Owner authentication

- One owner per installation.
- First-owner registration is protected by a root-only one-time setup token.
- Passwords use scrypt verifiers; plaintext passwords are never stored.
- Login is rate-limited.
- There is intentionally no public password-reset/email-recovery endpoint yet, avoiding account enumeration and weak recovery links.
- Session cookies are Secure + HttpOnly + SameSite=Strict and expire.
- Remembered sessions are bound to random server-side trusted-device IDs and can be revoked.
- Every private resource route re-checks authorization server-side.

A future public reset flow must have the same anti-enumeration response for known/unknown emails, rate limiting, single-use expiring tokens, and a verified delivery channel before it is exposed.

## Web boundary

- API cross-origin requests fail closed.
- No credentialed wildcard CORS.
- Security headers are emitted by the Core and again at Caddy.
- User/model text is rendered with text nodes, not injected as trusted HTML.
- URL/research content is untrusted, bounded and ephemeral.

## Logs and incident response

The Core records sanitized `security.*` events for registration, login failures/rate limits, successful login and device revocation. The owner-only Session UI can inspect recent events.

Never log:
- passwords;
- bearer/API tokens;
- backup passphrases;
- payment-card data;
- raw provider authorization headers.

When something happens:
1. preserve sanitized logs/event timestamps;
2. revoke active credentials/devices if relevant;
3. isolate the affected provider/worker;
4. reproduce from a clean checkout;
5. patch + test;
6. restore from an encrypted verified backup if state integrity is uncertain;
7. only re-enable the route after smoke verification.

## Backups

- Use `deploy/backup.sh`: SQLite online backup → integrity check → encrypted file.
- Keep `OLIVIA_BACKUP_PASSPHRASE` outside Git.
- `deploy/restore.sh` verifies checksum/decryption/SQLite integrity before replacing state.
- CI performs a real encrypted backup/restore round-trip and wrong-passphrase failure test.
- Production restores must be periodically rehearsed on a disposable target.

## Dependency maintenance

Dependabot is enabled for Python and GitHub Actions. Dependency PRs still require CI before merge; automatic update is not automatic trust.

## Account controls required before production claim

Enable MFA/2FA on every control-plane account that can change production or secrets, at minimum:
- GitHub;
- Oracle Cloud;
- Cloudflare, if retained for any deployment/DNS role;
- model/provider accounts holding production-capable credentials.

This repository cannot prove or enable account-level 2FA by itself. Production security status remains incomplete until those account controls are verified out-of-band.
