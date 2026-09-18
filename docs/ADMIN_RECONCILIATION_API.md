# Admin Reconciliation API

Aktif development setelah migration 0016/0017. Modul ini membuat antrean inquiry yang
aman; belum menjalankan request gateway dari HTTP admin.

## Endpoint dan permission

Prefix default `/api/v1/admin/reconciliation`.

| Metode | Path | Permission |
| --- | --- | --- |
| GET | `/` | `admin.reconciliation.read` |
| POST | `/{attempt_id}/request` | `admin.reconciliation.request` |

SUPER_ADMIN dan FINANCE mendapat read/request. AUDITOR hanya read. INTEGRATION_ADMIN
tidak mendapat akses. POST membutuhkan cookie admin, exact Origin dan X-CSRF-Token.

## Request

```json
{"reason":"Status gateway belum pasti setelah timeout"}
```

Hanya attempt MIDTRANS dengan status INITIATED, UNKNOWN atau PENDING yang dapat diminta.
Satu attempt memiliki satu case; request berulang saat REQUESTED/RUNNING mengembalikan
case yang sama. Case COMPLETED tidak dibuat ulang; FAILED dapat diminta kembali dengan
alasan baru. Unique index PostgreSQL menjadi idempotency boundary.

Response `202` berisi case id, attempt_id, requested_by, status, reason, timestamps,
result_status/error_code dan ringkasan gateway/channel/order/status. Jangan mengirim
gateway order ID ke analytics. 409 berarti tidak membutuhkan inquiry, 422 berarti
gateway belum didukung, 404 berarti attempt tidak ditemukan.

GET memakai limit 1-100, offset >=0 dan has_more. Data customer, metadata, payload
gateway, token dan secret tidak ditampilkan.

## Lifecycle

Target status: REQUESTED -> RUNNING -> COMPLETED/FAILED. Worker otomatis mengambil queue;
operator juga dapat menjalankan satu attempt secara manual:

```powershell
.\venv\Scripts\python.exe scripts\reconcile_attempt.py <attempt_uuid>
```

Script dan worker memakai Midtrans Core status dan processor ledger/webhook yang sama.
Jangan membuat reference/order baru karena UNKNOWN. Backoff/fairness lanjutan,
multi-merchant routing, DOKU inquiry dan sandbox UAT tetap TODO.

Frontend harus menampilkan status antrean, disable double-submit, dan tidak menganggap
202 sebagai PAID. Jika timeout, cek daftar/detail dahulu; jangan auto-retry.
Audit `RECONCILIATION_REQUESTED` menyimpan actor/payment UUID/reason/waktu; jangan isi
reason dengan credential/PII. Audit access-read dan alert backlog masih TODO.

Referensi: [Midtrans notification](https://docs.midtrans.com/docs/https-notification-webhooks)
dan [DOKU best practice](https://developers.doku.com/get-started-with-doku-api/notification/best-practice).
