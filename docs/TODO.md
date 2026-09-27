# TODO dan Roadmap Implementasi

> Review terakhir: 27 September 2026. Checklist ini dicocokkan dengan route,
> service, gateway, migration, dokumentasi, dan test repository.
> Status checklist: 34 selesai, 24 terbuka. `alembic check` bersih dan head
> berada di `20260918_0022`. Validasi test terbaru: `100 passed, 14 skipped`.

## Hasil audit 27 September 2026

- **Selesai dan terverifikasi:** struktur modular FastAPI, database/migration,
  health/readiness, OAuth client credentials, checkout token, identity client/event/user,
  payment ledger/idempotency, webhook/outbox, admin API, reconciliation retry/backoff,
  refund maker-checker, winning attempt, late/duplicate-paid quarantine, DOKU Indomaret,
  Midtrans boundary, error catalog, dan kontrak route/error OpenAPI.
- **Selesai sebagian:** admin frontend sudah memiliki login, client, user, service,
  payment, refund, reconciliation, audit, event, dan portal-user read-only. Role editor,
  MFA, export UI, dan konfigurasi gateway/channel belum tersedia.
- **Belum terverifikasi:** sandbox UAT/provider live, merchant binding, credential
  encryption/rotation, secret manager, scheduler deployment, observability terpusat,
  load test PostgreSQL, backup/restore, browser E2E, dan approval live launch.
- **Catatan test:** assertion refund Midtrans sekarang mem-parse JSON request body,
  sehingga tidak bergantung pada whitespace serialisasi JSON. Contract test OpenAPI
  juga memverifikasi parameter `search` pada daftar dan export payment.

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
- [x] Winning attempt eksplisit dan late-paid/duplicate-paid webhook quarantine untuk review reconciliation.
- [x] Cumulative refund validation dengan locking payment dan pengecualian refund REJECTED/FAILED.
- [x] Constraint database single active attempt (`INITIATED`/`PENDING`/`UNKNOWN`) per payment.
- [ ] Aturan `attempt_no` tambahan bila diperlukan setelah load test.
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
- [x] Server-side payment search dan `total_count` agar pagination tidak terbatas pada halaman aktif.
- [ ] Update payload portal existing untuk kontrak mandatory event/email.
- [ ] Backfill data historis hanya setelah mapping event/email asli disetujui.
- [ ] Organizer/service admin API, merchant account, routing rules, channel eligibility, dan feature flags.

### Worker dan observability

- [ ] Install/aktifkan worker sebagai service atau Windows Task Scheduler di environment deployment.
- [ ] Worker heartbeat terpusat, alert backlog/dead-letter, dan audit replay operator.
- [ ] Metrics aplikasi/provider, Sentry/OpenTelemetry, dashboard latency/error, dan alerting.
- [ ] Load test throughput lock per client serta PostgreSQL concurrent webhook/cancel/crash recovery.

### Release gate

- [x] Error-code catalog frontend dan kontrak endpoint aktif diperbarui.
- [x] Contract test path aktif OpenAPI dan error envelope.
- [x] OpenAPI payment response schema, pagination consistency, dan concurrency contract tests.
- [ ] Finalisasi seluruh OpenAPI admin dan generated client.
- [ ] Unit test tambahan untuk seluruh state transition, money, idempotency, dan provider channel.
- [x] Migration gate production: `AUTO_CREATE_TABLES=false`, migration head diverifikasi sebelum startup.
- [ ] Checklist deployment, secret rotation, backup/restore, sandbox UAT, dan approval live launch.

## Catatan status

- Admin masih dibatasi production guard sampai MFA dan security review selesai.
- Provider test saat ini memakai mock atau test lokal; tidak ada klaim live production readiness.
- Credential live yang pernah ditempel di percakapan harus dianggap compromised dan dirotasi; jangan dimasukkan ke repository atau `.env` lokal.
- Adapter/mock test tidak boleh dianggap sebagai bukti merchant binding, settlement, credential encryption, UAT, atau production readiness.
