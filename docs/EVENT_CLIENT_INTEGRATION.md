# Integrasi Portal Event Client

## Identitas client/event/pembayar (kontrak aktif)

Lihat [PORTAL_IDENTITY.md](PORTAL_IDENTITY.md). event_id, event_name dan customer.email
wajib pada create payment. Client ditentukan JWT; nama Portal dari registrasi operator.
Event unik per client, pembayar berdasarkan email per client. Satu pembayar dapat membuat
beberapa order per event dengan reference_id berbeda. service_code tetap untuk routing.

## Kontrak aktif

Client API wajib OAuth2 Client Credentials JWT. Panduan ini menggantikan HMAC untuk
request client API. Callback Payment ke Event tetap memakai HMAC.
Client ID, Origin/Referer, atau query string bukan bukti otorisasi.

Alur: backend Event meminta JWT -> membuat payment -> browser diarahkan ke
payment_url -> checkout menggunakan token terpisah yang terikat satu payment.
Harga, reference, service dan customer ditentukan backend, bukan query browser.

## Registrasi operator

Operator dapat menambah service_code lewat [Admin Service API](ADMIN_SERVICE_API.md).
Service nonaktif menolak order baru (404 SERVICE_NOT_FOUND); order existing tidak
otomatis dibatalkan. Event ID tetap terpisah dari service_code.

Selain CLI di bawah, operator dapat mendaftarkan client lewat
[Admin Client API](ADMIN_CLIENT_API.md) dengan sesi/permission admin.
Perubahan konfigurasi lewat API admin mencabut JWT lama; backend Event perlu meminta
JWT baru. Rotasi OAuth mengharuskan penggantian client_secret di backend Event.

Jalankan migration sebelum startup; AUTO_CREATE_TABLES=false.
JWT_SECRET acak minimal 48 karakter, JWT_ISSUER dan JWT_AUDIENCE berada di .env server.
Jangan membagikan JWT_SECRET ke client.

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe scripts\register_client.py --code EVENT-CLIENT --name "Portal Event" --service EVENT --return-url https://event.example.com/payment/result --callback-url https://event.example.com/api/payment/callback
```

Ganti domain contoh dengan URL sebenarnya. Client existing memerlukan --rotate:
mengganti OAuth secret, scopes dan allowlist, menaikkan token_version, sehingga JWT lama
ditolak. Simpan client_secret dan callback_secret dari output secara aman di backend
Event, bukan Git/log/frontend. client_id OAuth adalah code EVENT-CLIENT, bukan UUID.

Secret OAuth di-hash scrypt; callback secret masih plaintext (enkripsi TODO).
Registrasi hanya lewat CLI operator, belum ada admin UI. Client inactive tidak dapat
meminta token atau mengakses checkout. Allowlist URL harus cocok persis, termasuk
path/query. HTTPS wajib, kecuali HTTP loopback untuk development. Tidak ada wildcard.
DNS/egress filtering masih perlu hardening; jangan daftarkan URL internal sensitif.

## Token backend

POST /api/v1/oauth/token dengan Authorization: Basic base64(client_id:client_secret)
dan Content-Type: application/x-www-form-urlencoded.

Body: grant_type=client_credentials&scope=payments:read%20payments:write

```json
{"access_token":"<JWT>","token_type":"Bearer","expires_in":600,"scope":"payments:read payments:write"}
```

Respons OAuth tidak memakai envelope data; Cache-Control no-store.
Token hanya disimpan backend. Tidak ada refresh token. ACCESS_TOKEN_TTL_SECONDS
default 600, maksimum 900. HS256 dipatok, issuer/audience/expiry diperiksa, begitu juga
status client, token_version dan scopes terkini setiap request.
Scope default read/write. Refund memerlukan payments:refund: operator memberikan
--scope payments:refund, kemudian backend meminta scope itu saat issuance.
invalid_client -> 401; invalid_scope/unsupported_grant_type -> 400.
Parameter wajib hilang memakai validation error FastAPI 422.

## Membuat payment

POST /api/v1/client/payments
Authorization: Bearer <access_token>
Idempotency-Key: event-order-2026-0001
Content-Type: application/json

```json
{
  "service_code": "EVENT",
  "event_id": "EVT-2026-001",
  "event_name": "Konferensi Tahunan",
  "reference_id": "ORDER-2026-0001",
  "description": "Tiket event",
  "amount": 150000,
  "currency": "IDR",
  "customer": {"name": "Pembeli", "email": "pembeli@example.com"},
  "return_url": "https://event.example.com/payment/result",
  "metadata": {"event_id": "EVT-001"}
}
```

Email wajib valid dan dinormalisasi lowercase/trim sebagai identitas user per client.
Amount integer positif rupiah, bukan string,
bool atau pecahan. expires_at optional tetapi harus timezone-aware dan di masa depan.
return_url optional; jika diisi wajib allowlisted.

Respons 201: data berisi payment_id, payment_no, reference_id, amount, currency, status,
expires_at dan untuk payment aktif: payment_url, checkout_token, checkout_expires_at.
Tambahan identitas: client_id (UUID internal), client_name, event_id, event_name,
customer.name/email. Snapshot order lama dapat null; client_id OAuth tetap code client.
meta.idempotent_replay membedakan replay.
Contoh payment_url: https://payment.example.com/p/PAYMENT-NUMBER#token=<checkout_token>.
Frontend hanya redirect ke URL yang diberikan backend, tidak merangkai nominal query.

Idempotency-Key wajib 1-150 karakter nonblank. Payload identik dan key sama mengembalikan
payment sama, dengan checkout token baru jika payment aktif/belum expired.
Token tidak disimpan di response idempotency. Snapshot replay bukan status terkini.
Key sama/body berbeda: 409 IDEMPOTENCY_CONFLICT; reference duplikat: 409 DUPLICATE_REFERENCE.

## Operasi lainnya

- GET /api/v1/client/payments/{payment_id}: payments:read, payment milik client.
- POST /api/v1/client/payments/{payment_id}/checkout: payments:write, renewal checkout.
- POST /api/v1/client/payments/{payment_id}/cancel: payments:write.
- POST /api/v1/client/payments/{payment_id}/refunds: payments:refund,
  body {"amount":150000,"reason":"Permintaan pembeli"}. Baru mencatat request,
  bukan bukti refund gateway selesai.

Client API selalu JWT, termasuk development/AUTH_ENABLED=false.
Missing/invalid/expired/revoked token: 401; scope kurang: 403; payment client lain: 404;
URL tidak terdaftar: 422 URL_NOT_ALLOWED.
Checkout token bukan JWT client dan keduanya tidak dapat saling menggantikan.
Checkout default 1800 detik, dibatasi expiry payment. Renewal tidak membatalkan token
checkout lama. Rotasi OAuth mencabut JWT lama, bukan checkout lama; menonaktifkan
client menolak keduanya. Siapa pun yang memperoleh checkout token mempunyai akses
checkout payment tersebut selama token valid.

Attempt INITIATED/PENDING/UNKNOWN/PAID menghalangi cancel lokal
(409 PROVIDER_CANCEL_REQUIRED). Timeout UNKNOWN bukan izin membuat payment baru.
Cancel ulang CANCELLED idempotent. Query status untuk memastikan state sebelum melepas tiket.

## Callback Payment ke Event

Callback server-to-server dikirim ke callback_url terdaftar, bukan return_url.
Headers: X-Event-ID, X-Timestamp, X-Signature.
Verifikasi Base64(HMAC-SHA256(callback_secret, timestamp + "." + raw_body)).
Gunakan raw UTF-8 body sebelum parsing, perbandingan constant-time, timestamp
timezone-aware dengan toleransi, dan deduplikasi event_id.
Payload: event_id, event_type, occurred_at, data berisi payment_id/payment_no/
reference_id/amount/currency/status. Cocokkan nominal/order server-side.

Balas 2xx setelah tersimpan aman; duplikat yang sudah diproses juga 2xx tanpa
menerbitkan tiket lagi. Callback worker: python scripts/callback_worker_once.py.
Scheduler tersedia: `python scripts/payment_worker.py --jobs callbacks`; aktivasi service
deployment mengikuti WORKER_OPERATIONS.md. Delivery at-least-once: crash setelah Event
menerima callback tetapi sebelum commit dapat menyebabkan pengiriman ulang event_id yang sama.
URL allowlist/client active diperiksa ulang sebelum kirim.
Return browser atau query status dari pengguna tidak menjadi bukti lunas.
Gunakan callback terverifikasi atau GET status backend sebagai sumber status.

## Batas implementasi dan referensi

Lihat FRONTEND_INTEGRATION.md, TODO.md dan PROVIDER_VERIFICATION.md.
Protokol Midtrans/DOKU terpisah dari JWT client portal. Suite provider menggunakan mock;
belum transaksi sandbox merchant end-to-end. DOKU/refund gateway, admin provisioning,
rate limit terdistribusi, enkripsi callback secret dan scheduler inquiry masih TODO.
Cleanup checkout expired tersedia lewat worker, tanpa menghapus ledger pembayaran.

[RFC 6749 client credentials](https://www.rfc-editor.org/rfc/rfc6749#section-4.4)
dan [RFC 6750 bearer token](https://www.rfc-editor.org/rfc/rfc6750).
