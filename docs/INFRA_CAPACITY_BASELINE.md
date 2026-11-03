# OCI capacity baseline

Snapshot: 2026-11-02, region `sa-saopaulo-1`, AD `fDpo:SA-SAOPAULO-1-AD-1`. Read-only inventory via OCI CLI on the connected Windows host. Refresh before provisioning.

## Compute quotas

The shape pools are separate and not interchangeable.

| Shape | Quota | Used | Remaining |
|---|---:|---:|---:|
| `VM.Standard.A1.Flex` | 2 OCPU + 12 GB RAM | 0 OCPU + 0 GB | 2 OCPU + 12 GB |
| `VM.Standard.E2.1.Micro` | 2 OCPU | 2 OCPU | 0 OCPU |

A1 quota exists in the quota ledger, but physical capacity is NOT certified; available quota does not guarantee launch capacity.

## Running instances

| Instance | State | Shape | OCPU | RAM | Boot |
|---|---|---|---:|---:|---:|
| `olivia-live-free` | RUNNING | E2.1.Micro | 1 | 1 GB | 50 GB |
| `olivia-text-free` | RUNNING | E2.1.Micro | 1 | 1 GB | 50 GB |
| **Total** | **2 RUNNING** | | **2** | **2 GB** | **100 GB attached** |

## Storage

- Boot volumes: 2 x 50 GB = 100 GB; both attached; no unattached boot volumes.
- Additional block volumes: 0.
- Boot-volume backups found: 0.
- Block-storage quota values: `backup-count=5`, `free-backup-count=5`, `volume-count=10000` (count, not GB).
- **Total GB storage allowance is unverified.** Do not infer a 200 GB account allowance or claim 100 GB remains. No total-GB limit was returned by the queried limits API.

## Billing / free tier

Instances have tag `orcl-cloud: free-tier-retained=true`; this is not billing evidence. Subscription, billing entitlement and potential charges were not verified. Preserve the zero-cost guard: do not provision, resize, reserve or enable paid resources without explicit approval and a verified cost boundary.

## Refresh checklist

1. Re-query A1/E2 limits and resource availability.
2. Inventory all instances and shape configuration.
3. Inventory boot/block volumes, attachments, backups and snapshots.
4. Verify Billing & Cost Management subscription/entitlement.
5. Check physical capacity for target shape/AD.

Always distinguish quota remaining from physical capacity. Never treat a freeform tag as proof of free billing.