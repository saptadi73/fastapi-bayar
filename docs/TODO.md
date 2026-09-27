# TODO dan Roadmap Implementasi

> Review terakhir: 18 September 2026. Checklist ini dicocokkan dengan route,
> service, gateway, migration, dokumentasi, dan test repository.
> `94 passed, 14 skipped`; provider live/UAT belum dijalankan.

## Sudah selesai

- [x] FastAPI modular: routes, schemas, services, models, gateways, worker, dan core.
- [x] `.env.example`, production guard, PostgreSQL async, health/database/readiness.
- [x] JSON response/error envelope dan correlation `request_id`.
- [x] Structured JSON HTTP logging tanpa body, query string, token, PII, atau secret.
- [x] OAuth2 client credentials JWT dengan scope, issuer/audience, expiry, dan revoke token version.
- [x] Checkout token hash, expiry, ownership, return URL allowlist, CSP, dan no-store.
- [x] Portal/Event/User identity dengan composite tenant ownership dan snapshot order.
- [x] Idempotency, duplicate reference protection, locking, nominal/currency invariant.
- [x] Payment state transition dan immutable status history.
- [x] Durable payment attempt sebelum outbound provider dan concurrent protection.
- [x] Callback outbox, HMAC callback signing, retry/dead-letter, dan callback worker.
- [x] Cleanup checkout, admin session, login bucket, dan nonce expired dengan bounded `SKIP LOCKED`.
- [x] Admin auth, client, service, user, payment ledger, summary, export, audit, reconciliation, dan refund maker-checker API.
- [x] Midtrans adapter boundary, Snap create boundary, notification verifier/status mapper, inquiry, dan refund worker.
- [x] DOKU Non-SNAP signature verifier, timestamp freshness, deduplication, amount/order validation, status mapper.
- [x] DOKU Check Status, Indomaret payment-code adapter, webhook, dan reconciliation worker integration.
- [x] Webhook duplicate, out-of-order, late-event, quarantine, dan secret-redaction tests.
- [x] Alembic migration chain sampai `20260918_0020`; `alembic check` bersih.
- [x] Dokumentasi Frontend, Portal Event Client, Admin API, provider verification, worker operations, dan live credential runbook.
- [x] `.gitignore` untuk `.env`, `.secrets`, virtual environment, `__pycache__`, dan `.pyc`; virtual environment tidak lagi tracked.

## Prioritas berikutnya

### Provider dan payment operation

- [ ] DOKU adapter product/channel tambahan sesuai kontrak merchant aktif.
- [x] DOKU refund gate untuk channel non-card aktif: tidak memanggil endpoint provider yang salah dan menandai `MANUAL_REQUIRED`.
- [ ] DOKU refund API per product/channel yang mendukung API, webhook/inquiry refund, final ledger transition, dan settlement reconciliation.
- [x] Scheduler reconciliation bounded retry/backoff dan retry-due index.
- [ ] Scheduler inquiry multi-merchant dengan fairness, metric backlog, dan routing credential merchant.
- [ ] Winning attempt eksplisit, late-paid/duplicate-paid reconciliation, dan cumulative refund validation.
- [ ] Constraint database single active attempt dan aturan `attempt_no` bila diperlukan setelah load test.
- [ ] Sandbox UAT Midtrans/DOKU untuk channel yang diaktifkan, termasuk pembayaran tanpa email.
- [ ] Production credential rotation, secret-manager deployment, merchant binding, dan live UAT terkontrol.

### Security dan admin

- [ ] Credential merchant terenkripsi at rest, tabel credential multi-key, dan rotasi dua key aktif.
- [ ] Rate limiting terdistribusi dan audit autentikasi yang account-aware.
- [ ] MFA enrollment/recovery, password reset, forced password change, invitation, dan reauthentication.
- [ ] Role/permission configurable, per-client admin assignment, role editor, dan audit before/after lengkap.
- [x] Kebijakan revoke seluruh checkout session per client dengan audit operator.
- [ ] Recovery/rotasi callback secret dengan audit request ID dan redaksi field sensitif.
- [ ] Admin provisioning UI, UI transaksi, UI service/channel, dan UI role/MFA.
- [ ] Egress/DNS hardening, browser end-to-end test, security review, secret scanning, backup/restore test.

### Data dan portal administration

- [x] Admin read-only listing/detail PortalEvent per client dengan tenant filter dan permission.
- [x] Admin read-only listing PortalUser dengan permission PII terpisah, tenant filter, dan audit akses.
- [ ] PortalUser CRUD, perubahan master-data, dan audit before/after.
- [x] Filter transaksi per event dengan `client_id` wajib, permission ledger, dan response tanpa PII.
- [ ] Update payload portal existing untuk kontrak mandatory event/email.
- [ ] Backfill data historis hanya setelah mapping event/email asli disetujui.
- [ ] Organizer/service admin API, merchant account, routing rules, channel eligibility, dan feature flags.

### Worker dan observability

- [ ] Install/aktifkan worker sebagai service atau Windows Task Scheduler di environment deployment.
- [ ] Worker heartbeat terpusat, alert backlog/dead-letter, dan audit replay operator.
- [ ] Metrics aplikasi/provider, Sentry/OpenTelemetry, dashboard latency/error, dan alerting.
- [ ] Load test throughput lock per client serta PostgreSQL concurrent webhook/cancel/crash recovery.

### Release gate

- [ ] Finalisasi OpenAPI admin, error-code catalog, pagination, concurrency, dan contract tests.
- [ ] Unit test tambahan untuk seluruh state transition, money, idempotency, dan provider channel.
- [x] Migration gate production: `AUTO_CREATE_TABLES=false`, migration head diverifikasi sebelum startup.
- [ ] Checklist deployment, secret rotation, backup/restore, sandbox UAT, dan approval live launch.

## Catatan status

- Admin masih dibatasi production guard sampai MFA dan security review selesai.
- Provider test saat ini memakai mock atau test lokal; tidak ada klaim live production readiness.
- Credential live yang pernah ditempel di percakapan harus dianggap compromised dan dirotasi; jangan dimasukkan ke repository atau `.env` lokal.
- Adapter/mock test tidak boleh dianggap sebagai bukti merchant binding, settlement, credential encryption, UAT, atau production readiness.
