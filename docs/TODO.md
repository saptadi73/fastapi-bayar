# TODO dan Roadmap Implementasi

## Admin reconciliation queue - migration 0016/0017

- [x] List/request case dengan permission read/request dan CSRF.
- [x] Hanya MIDTRANS INITIATED/UNKNOWN/PENDING; attempt lain ditolak.
- [x] Satu case per attempt; request berulang tidak menggandakan antrean.
- [x] Audit request dan field response tanpa payload/customer/credential.
- [x] Index/unique constraint dinormalisasi migration 0017; alembic check bersih.
- [x] Dokumentasi admin/frontend diperbarui.
- [x] 99 tes lulus: queue idempotency, worker claim/result, role request/read, unsupported state dan schema isolation.
- [x] Migration 0016/0017 tanpa schema drift; endpoint aktif di Swagger dan database connected.
- [x] Worker mengambil REQUESTED, inquiry Midtrans, lalu update RUNNING/COMPLETED/FAILED.
- [ ] Backoff/fairness multi-merchant, metrics backlog dan alert dead-letter.
- [x] DOKU Non-SNAP Check Status adapter dengan HMAC-SHA256 signature dan order mismatch guard.
- [x] DOKU Non-SNAP Indomaret payment-code adapter dengan signature dan response validation.
- [ ] DOKU product/channel lain, refund adapter, notification verifier, dan sandbox UAT.

Queue otomatis tersedia melalui payment_worker; script satu-attempt tetap tersedia.

## Pembacaan transaksi admin - migration 0015

- [x] List/detail payment, history dan attempt ringkas dengan admin.payments.read.
- [x] Akses Super Admin/Finance/Auditor; Admin Integrasi ditolak.
- [x] Filter client/service/event/status/reference/tanggal timezone-aware.
- [x] Pagination limit/offset/has_more tanpa menggandakan payment karena banyak attempt.
- [x] Allowlist field response tanpa customer PII, metadata, instruksi/token atau credential.
- [x] Indeks created/id, client/event/created dan history payment/time.
- [x] Panduan frontend ADMIN_PAYMENT_API serta dokumen admin diperbarui.
- [x] 97 tes lulus: filter/rentang tanggal, role, pagination, redaksi data dan banyak attempt.
- [x] Migration 0015 tanpa schema drift; endpoint aktif di Swagger dan database connected.
- [ ] Cursor/snapshot export, dashboard/report agregasi dan audit akses-baca.
- [ ] Permission PII terpisah, per-client admin assignment dan UI transaksi.
- [x] Rekonsiliasi admin dan refund maker-checker internal.
- [ ] Settlement reconciliation dan provider refund end-to-end.

Endpoint ini read-only dari ledger DB, bukan inquiry gateway real-time.

## Service multi-client - migration 0014

- [x] Admin API list/detail/create/update service per client dengan permission dan CSRF.
- [x] Code unik per-client, immutable code/owner, expected_version dan audit atomik.
- [x] Row lock client menyerialisasi konfigurasi service dengan payment initiation.
- [x] Penonaktifan hanya menolak order baru; tidak menghapus ledger/payment existing.
- [x] Dokumentasi ADMIN_SERVICE_API dan panduan frontend/Event/Admin diperbarui.
- [x] 96 tes lulus: schema, isolasi client/service, duplicate code, concurrent edit dan service inactive.
- [x] Migration 0014 tanpa schema drift; endpoint aktif di Swagger, database connected.
- [ ] UI tab service dan konfigurasi gateway/channel per-service.

Tetap development-only. Tidak ada service client nyata yang diubah saat pengujian.

## Pengelolaan user admin - migration 0013

- [x] Create operator, update nama/role/status dan revoke seluruh sesi via Admin API.
- [x] Permission admin.users.manage hanya Super Admin, Origin/CSRF tetap wajib.
- [x] Email unik ternormalisasi; password hash dan tidak ditampilkan/audit otomatis.
- [x] expected_version mencegah stale edit; setiap update/revoke menaikkan versi.
- [x] Update user mencabut sesi; admin aktif terakhir dilindungi lock lintas-worker.
- [x] Actor/session diperiksa ulang sesudah lock; audit dan mutation atomik.
- [x] Kontrak frontend ADMIN_USER_API.md dan dokumentasi terkait diperbarui.
- [x] 90 tes lulus; tes admin diperluas untuk session revoke, konflik versi dan race Super Admin terakhir.
- [x] Migration 0013 tanpa schema drift; endpoint aktif, database connected.
- [ ] MFA, invitation, forced password change, reset/recovery password.
- [ ] Role editor/custom permissions, per-client assignment dan UI admin.

Pengujian memakai akun/schema disposable; tidak mengubah akun admin aplikasi.

## Admin client management - migration 0012

- [x] List/detail/create/update/rotate client dengan permission backend dan CSRF.
- [x] Create service awal atomik bersama client; validasi scopes dan exact allowlist URL.
- [x] Response credential hanya pada create/rotate; GET tidak menampilkan secret/hash.
- [x] expected_version + row lock untuk stale/concurrent edits; update/rotate mencabut JWT lama.
- [x] Audit atomik actor/action/resource/reason tanpa payload credential otomatis.
- [x] Dokumentasi API client admin, frontend dan Event Client diperbarui.
- [x] 90 tes lulus (tes admin diperluas: credential redaction, revocation dan concurrent edit).
- [x] Migration 0012 tanpa schema drift; endpoint aktif di Swagger dan database connected.
- [ ] UI pengelolaan client/service dan role editor.
- [x] Service tambahan melalui create/read/update API (tanpa delete).
- [x] Create/update/revoke user admin via API (tanpa delete/reset password).
- [ ] Recovery/rotasi callback secret, enkripsi credential, audit before/after/request_id.

Tetap development-only; tidak ada client nyata yang dibuat/dirotasi dalam pengujian.

## Fondasi admin development - migration 0011

- [x] User admin terpisah dari Client/PortalUser; password hash PBKDF2 bersalt.
- [x] Sesi opaque cookie HttpOnly, hash di DB, expiry idle/absolut dan revoke logout.
- [x] Login/me/logout, exact Origin dan CSRF untuk mutasi.
- [x] Permission backend + read-only users/roles/audit, pemetaan role sementara di kode.
- [x] Atomic shared PostgreSQL fixed-window login throttle per peer IP + Retry-After.
- [x] Audit autentikasi minimal dan bootstrap Super Admin interaktif tanpa default account.
- [x] Sanitasi input sensitif dari response validation error.
- [x] ADMIN_ENABLED dan parameter sesi/throttle .env; production guard sampai MFA tersedia.
- [x] 90 tes lulus; migration 0011 tanpa schema drift, endpoint aktif di Swagger.
- [ ] MFA/enrollment/recovery, password reset, revoke semua sesi dan reauthentication.
- [ ] Role/permission tables dan audit perubahan before/after lengkap.
- [x] API create/update user serta revoke sessions.
- [ ] Per-client assignment, maker-checker refund dan role editor.
- [ ] Cleanup session/bucket, account-aware throttling/edge limits dan security review.

Kontrak aktif di ADMIN_API.md. Jangan menandai matrix target UI sebagai fitur yang sudah ada.

## Identitas Portal/Event/Pembayar - kontrak aktif

- [x] Event unik (client_id,event_id), pembayar unik (client_id,email ternormalisasi).
- [x] Create order wajib event_id/event_name dan customer.name/email.
- [x] Client/nama Portal dari JWT/registrasi, bukan input browser.
- [x] Snapshot nama/identitas pada order; multiple order per pembayar/event diperbolehkan.
- [x] Service identitas terpisah, unique constraints dan composite tenant FK.
- [x] Migration 0010 mempertahankan data lama nullable, tanpa synthetic backfill.
- [x] Response backend dan callback memuat identitas event; checkout tidak membocorkan PII.
- [x] Dokumentasi PORTAL_IDENTITY, Event Client, Frontend dan Admin diperbarui.
- [x] 87 tes lulus: identitas tenant, multi-order, snapshot, idempotency dan composite FK.
- [ ] Update payload Portal Event existing untuk kontrak mandatory event/email.
- [ ] Backfill historis hanya jika tersedia mapping event/email asli yang disetujui.
- [ ] Admin CRUD/listing event/pembayar, filter transaksi per event dan audit perubahan master.

Bagian ini menggantikan kontrak email opsional di catatan historis bawah.

## Rancangan user, role dan portal admin

- [x] Dokumentasi rekomendasi frontend: [ADMIN_FRONTEND_SPEC.md](ADMIN_FRONTEND_SPEC.md),
  termasuk permission matrix, alur sesi, API usulan dan acceptance checklist.
- [x] Model/migration user, sesi admin dan audit autentikasi minimal.
- [ ] Tabel role/permission configurable dan audit perubahan resource lengkap.
- [x] Bootstrap Super Admin oleh operator, tanpa self-registration publik/default password.
- [x] Login/logout/me, password hash, sesi revocable, CSRF dan throttle login per IP.
- [ ] MFA dan hardening produksi.
- [x] Admin authorization terpisah dari JWT client/checkout; permission endpoint read-only.
- [ ] Pembatasan resource/client untuk penugasan admin per-client.
- [ ] Finalisasi OpenAPI admin, error codes, pagination, concurrency dan contract tests.
- [x] Admin API client: allowlist, one-time secret, rotasi dan audit actor/resource/reason.
- [x] Service tambahan melalui Admin Service API.
- [ ] Audit before/after lengkap.
- [ ] Frontend login/MFA, user/role, client/service dan route/action guards.
- [ ] Modul transaksi, rekonsiliasi, refund maker-checker, audit dan settings sesuai permission.
- [ ] Tes revoke/expiry/disable, isolasi akses, CSRF, secret redaction dan larangan self-approval.

Sebagian target admin masih usulan; kontrak foundation aktif ada di ADMIN_API.md.
Registrasi client tersedia lewat CLI dan Admin Client API; belum ada UI admin.

## Pembaruan worker callback dan retention

- [x] Worker proses terpisah, mode berulang/sekali jalan dan pemilihan job.
- [x] Interval/batch lewat .env; loop callback dan cleanup independen.
- [x] Commit per callback di scheduler, row lock hanya delivery, multi-worker SKIP LOCKED.
- [x] Recovery error loop dan sinyal shutdown; log tidak memasukkan exception message sensitif.
- [x] Cleanup batch checkout expired tanpa menghapus ledger/idempotency/sesi aktif.
- [x] Migration 0009 indeks expiry, tanpa schema drift.
- [x] Tes PostgreSQL concurrent delivery, retry, inactive client, timeout, rollback dan cleanup.
- [x] Seluruh suite: 81 passed; satu deprecation warning dependency TestClient.
- [x] Panduan operasi: WORKER_OPERATIONS.md; kontrak Event/Frontend diperbarui.
- [ ] Instal/aktifkan service atau Task Scheduler di lingkungan deployment.
- [ ] Heartbeat worker terpusat, alert backlog/dead-letter dan audit replay operator.
- [ ] Scheduler inquiry batch multi-merchant dengan backoff dan fairness.

Pengiriman callback nyata dan cleanup data aplikasi tidak dijalankan saat implementasi.

## Kontrak aktif: OAuth JWT dan checkout terlindungi

Bagian ini menggantikan petunjuk HMAC client API di catatan historis bawah.
HMAC tetap dipakai callback; helper legacy tidak dipasang pada routes client.

- [x] CLI provisioning/rotasi client, secret OAuth hash scrypt.
- [x] OAuth client credentials JWT pendek dengan issuer/audience/expiry.
- [x] Scope read/write/refund, active client dan token_version diperiksa per request.
- [x] Client API selalu JWT, tanpa bypass AUTH_ENABLED=false.
- [x] Checkout token hash di DB, expiry dan ownership payment/attempt.
- [x] Exact return/callback URL allowlist, diperiksa ulang saat callback dikirim.
- [x] Checkout minimal dengan fragment, sessionStorage, CSP/no-store/no-referrer.
- [x] Migration 0008 diterapkan; alembic check tanpa schema drift.
- [x] Suite 71 tes lulus termasuk PostgreSQL, JWT dan isolasi checkout.
- [x] Panduan FRONTEND dan EVENT_CLIENT diperbarui.
- [ ] Provision/rotate client existing dengan URL sebenarnya sebelum integrasi baru.
- [ ] Rate limit terdistribusi dan audit autentikasi.
- [ ] Admin provisioning UI, enkripsi callback secret, rotasi JWT signing key.
- [x] Cleanup checkout expired (worker retention).
- [ ] Kebijakan revoke semua checkout per-client.
- [ ] Egress/DNS hardening callback dan tes browser end-to-end.
- [x] Implementasi scheduler callback; aktivasi service deployment masih diperlukan.
- [x] Scheduler reconciliation Midtrans tersedia di payment_worker.
- [ ] Sandbox merchant Midtrans/DOKU end-to-end dan DOKU inquiry adapter.

Provider di suite menggunakan mock; belum klaim siap produksi penuh.

## Pembaruan HMAC dan production guard

- [x] X-Key-ID dicocokkan dengan clients.key_id; migration 0007 diterapkan.
- [x] Timestamp invalid/naive/null ditolak tanpa exception.
- [x] Signature menggunakan raw path/query; header ASCII, panjang nonce/signature divalidasi.
- [x] Atomic PostgreSQL nonce INSERT ON CONFLICT; bukan menangkap seluruh IntegrityError sebagai replay.
- [x] Empat request nonce sama: satu diterima, tiga replay; body tamper dan key salah ditolak.
- [x] Production menolak auth-off, auto-DDL/debug/SQL echo aktif, public URL non-HTTPS.
- [x] NONCE_TTL_SECONDS minimal dua kali toleransi timestamp positif.
- [ ] Enkripsi credential database, tabel client_credentials dan rotasi dua key aktif.
- [ ] Cleanup nonce kedaluwarsa dan rate limiting; admin provisioning/audit.

Perubahan ini hanya autentikasi Portal Event -> Payment Portal. Kontrak signature
DOKU/Midtrans tidak diubah; referensi provider ada di PROVIDER_VERIFICATION.md.

## Pembaruan invariants ledger

- [x] Idempotency-Key mandatory dan dibatasi 150 karakter.
- [x] Serialisasi initiate per client; request paralel identik menghasilkan satu payment.
- [x] Unique (client_id, external_reference), CHECK amount > 0, unique (payment_id, attempt_no).
- [x] Migration 0006 preflight data existing; tidak menghapus/mengoreksi ledger otomatis.
- [x] Nominal strict integer positif, batas bigint; currency IDR; expiry timezone-aware.
- [x] History CREATED pada initiate.
- [x] 51 tests termasuk PostgreSQL concurrency identical requests, reference collision, key conflict.
- [ ] Load test throughput lock per client dan optimasi granular locking bila dibutuhkan.

Iterasi ini hanya mengubah kontrak internal dan PostgreSQL, tidak mengubah request
atau mapping provider. Referensi provider terakhir tercatat di PROVIDER_VERIFICATION.md.

## Email customer opsional

- [x] API schema nullable EmailStr; blank/whitespace menjadi null; invalid email ditolak.
- [x] Migration 0005: customer_email nullable tanpa mengubah nilai lama; diterapkan ke bayar.
- [x] Midtrans payload menghilangkan email yang tidak tersedia.
- [x] 42 tests lulus termasuk create/idempotency PostgreSQL tanpa email dan payload provider mock.
- [ ] Validasi persyaratan data customer per channel DOKU saat adapter produk diimplementasikan.
- [ ] Sandbox UAT pembayaran tanpa email pada channel merchant yang diaktifkan.

## Pembaruan inquiry Midtrans

- [x] GET Core status adapter, timeout khusus gateway, validasi order response.
- [x] Worker CLI inquiry satu attempt; processor ledger/history/callback yang sama dengan webhook.
- [x] HTTP/body 404 tetap UNRESOLVED dan tidak mengubah ledger.
- [x] Recovery UNKNOWN/INITIATED ke PENDING ketika inquiry terverifikasi PENDING.
- [x] Referensi resmi dan batas metode dicatat di PROVIDER_VERIFICATION.md.
- [x] 27 tests lulus (mock provider + PostgreSQL untuk concurrency attempt).
- [ ] Scheduler batch dengan interval/backoff, fair pagination, dan metric inquiry.
- [ ] Routing inquiry multi-merchant serta dukungan transaction_id untuk metode yang memerlukannya.
- [ ] Sandbox UAT inquiry nyata; recovery token Snap yang hilang.

## Pembaruan durable attempt

- [x] Pisahkan orchestration attempt ke `app/services/attempt_service.py`.
- [x] Lock payment, reserve INITIATED, commit sebelum network I/O.
- [x] Double-click saat INITIATED/UNKNOWN menghasilkan 409; PENDING channel sama memakai attempt existing.
- [x] Timeout/error provider atau response malformed menghasilkan UNKNOWN, tidak membuat order baru otomatis.
- [x] Refresh attempt setelah provider response agar webhook PAID lebih awal tidak tertimpa.
- [x] Tolak attempt jika payment sudah expired atau currency bukan IDR.
- [x] Validasi key/channel sebelum membuat reservation; UUID instruksi divalidasi FastAPI.
- [x] Cancel idempotent dan menolak attempt aktif sampai provider diperiksa/dibatalkan.
- [x] 19 tests lulus termasuk integration PostgreSQL dengan schema disposable dan adapter mock.
- [ ] Provider status inquiry/reconciliation untuk INITIATED yang tertinggal dan UNKNOWN.
- [ ] Constraint database untuk attempt_no dan single active attempt (di luar lock service).
- [ ] Sandbox UAT dengan merchant key nyata; integration test ini tidak memanggil Midtrans.

## Pembaruan webhook reliability

- [x] Verifikasi signature setiap delivery sebelum deduplikasi, termasuk request ulang yang ditolak.
- [x] Validasi Decimal amount/currency terhadap payment ledger.
- [x] Capture hanya dapat PAID ketika fraud_status=accept.
- [x] PostgreSQL advisory transaction lock per merchant/order dan row lock payment pada webhook/client inquiry.
- [x] Status identik dan notifikasi pending setelah PAID tidak membuat callback tambahan.
- [x] Audit Midtrans menyimpan field allowlist tanpa signature/customer/card data.
- [x] Body callback dikirim dengan bytes JSON yang sama dengan input signature.
- [x] 18 unit/service tests lulus; test service menggunakan session mock.
- [ ] PostgreSQL integration test concurrent notification/cancel dan crash recovery.
- [ ] Lengkapi merchant binding: merchant_code saat ini belum dihubungkan ke credential per merchant.
- [ ] Winning attempt eksplisit, rekonsiliasi late-paid dan duplicate-paid, serta nominal refund kumulatif.
- [x] Durable attempt sebelum outbound provider dan concurrent create-attempt protection; timeout inquiry masih TODO.
- [ ] Enkripsi secret at rest, nonce cleanup, mandatory HMAC, dan constraint duplicate reference.

Status belum siap produksi penuh. Channel Midtrans tersedia bila dikonfigurasi;
DOKU, scheduler reconciliation, merchant admin, report, settlement dan sandbox UAT
belum selesai. Scheduler callback sudah tersedia, belum otomatis diaktifkan sebagai service.

## Selesai pada foundation

- [x] FastAPI modular: routes, services, schemas, models, core.
- [x] `.env` untuk database, gateway, Redis, callback, dan runtime.
- [x] PostgreSQL async connection dan automatic development table creation.
- [x] `/health`, `/health/database`, `/health/ready`.
- [x] JSON response/error envelope dengan `request_id`.
- [x] Client initiate/get/cancel payment.
- [x] Idempotency dan duplicate reference protection.
- [x] HMAC canonical helper, timestamp validation, dan nonce replay record.
- [x] Public checkout summary, channel list, attempt boundary, dan status polling.
- [x] Gateway registry boundary DOKU/Midtrans.
- [x] Webhook ingestion, hash deduplication, dan quarantine record.
- [x] Alembic environment siap untuk migration.
- [x] Initial migration, refund status migration, dan callback outbox migration.
- [x] Callback delivery record saat payment dibatalkan.
- [x] Development seed script dan unit test signature dasar.
- [x] Callback signing, HTTPX delivery worker satu kali jalan, dan retry/dead-letter state.
- [x] Provider status mapper terisolasi.
- [x] Midtrans Snap adapter boundary, create transaction client, dan legacy notification verifier.
- [x] Midtrans webhook endpoint: signature check, deduplication, status mapping, ledger update, dan callback enqueue.

## Payment lifecycle

- [ ] Generate dan jalankan initial Alembic migration di environment target.
- [ ] Lengkapi state transition service dan immutable status history pada setiap perubahan.
- [ ] Tambahkan payment attempt locking untuk concurrent webhook/cancel.
- [ ] Tambahkan expiry worker dan status inquiry worker.
- [x] Refund maker-checker internal: request, list, approve/reject, version conflict, self-approval guard, dan audit trail.
- [x] Worker provider refund Midtrans dengan `refund_key` deterministik dan status `PROVIDER_ACCEPTED`.
- [x] Inquiry refund Midtrans mencocokkan `refund_key` dan nominal sebelum finalisasi ledger.
- [ ] Worker provider refund DOKU, webhook/inquiry refund, final ledger transition, dan settlement reconciliation.

## Gateway

- [ ] Implementasi DOKU Direct API adapter per product/channel sesuai kontrak merchant aktif.
- [ ] Implementasi DOKU signature/request mapper dan notification verifier.
- [ ] Implementasi Midtrans Snap create transaction dan frontend token contract.
- [ ] Implementasi Midtrans notification verification dan status mapper.
- [ ] Simpan credential merchant terenkripsi untuk multi-merchant production.
- [ ] Tambahkan sandbox contract test untuk setiap channel yang diaktifkan.

## Client callback dan operasi

- [x] Proses scheduler callback periodik; instalasi supervisor production tetap diperlukan.
- [ ] Organizer/service admin API dan tenant authorization.
- [ ] Merchant account, routing rules, channel eligibility, dan feature flag.
- [ ] Reports summary/drill-down/export tanpa double counting attempts.
- [ ] Reconciliation provider dan settlement workflow maker-checker.
- [ ] Structured logging, metrics, alert, Sentry/OpenTelemetry.

## Quality dan production

- [ ] Unit test signature, mapper, state machine, money, dan idempotency.
- [ ] Integration test PostgreSQL locking dan tenant isolation.
- [ ] Webhook duplicate/out-of-order/late event test.
- [ ] Load test, security review, secret scanning, backup/restore test.
- [ ] Matikan `AUTO_CREATE_TABLES` di production dan gunakan migration gate.
