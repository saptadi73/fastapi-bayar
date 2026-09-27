# Integrasi Frontend Payment

## Portal admin: rancangan frontend

Panduan login pengelola, role/permission, halaman, form registrasi client, sesi,
kontrak API usulan dan acceptance checklist ada di [ADMIN_FRONTEND_SPEC.md](ADMIN_FRONTEND_SPEC.md).
Kontrak admin yang sudah aktif khusus development ada di [ADMIN_API.md](ADMIN_API.md).
Login/me/logout dan read-only user/role/audit tersedia. Pendaftaran/update/rotasi client
mengikuti [ADMIN_CLIENT_API.md](ADMIN_CLIENT_API.md). Pengelolaan user mengikuti
[ADMIN_USER_API.md](ADMIN_USER_API.md): create/update/revoke sesi, expected_version,
dan penanganan LAST_SUPER_ADMIN. MFA dan role editor masih mock.
Tab service client: [ADMIN_SERVICE_API.md](ADMIN_SERVICE_API.md), termasuk permission,
versi edit dan dampak penonaktifan (menolak order baru, tidak membatalkan order lama).
Modul daftar/detail transaksi admin: [ADMIN_PAYMENT_API.md](ADMIN_PAYMENT_API.md),
dengan filter, pagination dan tab history/attempts. API ini tidak mengirim customer PII.
Antrean inquiry admin dijelaskan di [ADMIN_RECONCILIATION_API.md](ADMIN_RECONCILIATION_API.md);
REQUESTED hanya berarti antrean tercatat.
Dokumen di bawah menjelaskan checkout yang sudah diimplementasikan. Login admin,
JWT backend Event dan checkout token adalah tiga domain akses terpisah.

## Batas akses

Kontrak identitas terbaru: [PORTAL_IDENTITY.md](PORTAL_IDENTITY.md).
Backend Event wajib mengirim event_id/event_name serta customer.name/email untuk
order baru; nama Portal berasal dari client terdaftar. Email tidak lagi opsional.
Frontend Event boleh menampilkan ringkasan dari backendnya, tetapi nominal dan
keanggotaan user harus diverifikasi backend. Checkout tidak membuat order dari query.
Email/nama pembayar tetap tidak ditampilkan API checkout publik; data lama bisa null.

Jangan menyimpan client_secret, JWT backend, JWT_SECRET maupun key gateway di browser.
Backend Event membuat payment menggunakan JWT dan memberikan payment_url untuk redirect.
Query amount/reference tidak digunakan untuk membuat transaksi.
Panduan backend: EVENT_CLIENT_INTEGRATION.md.

URL checkout: /p/{payment_no}#token=<checkout_token>.
HTML dapat dibuka siapa pun, tetapi data dan aksi payment wajib token valid.
Nomor payment saja tidak memberikan akses.

## Halaman bawaan

Halaman minimal /p/{payment_no} menggunakan /assets/checkout.js.
Script membaca token fragment, menyimpan sessionStorage per payment, lalu menghapus
fragment dari address bar dengan history.replaceState. Fragment tidak menjadi bagian
HTTP request. Jangan mencatat token/Authorization/URL lengkap atau memasang analytics
dan script pihak ketiga di checkout. sessionStorage tetap sensitif terhadap XSS.
Respons no-store/no-referrer; halaman menggunakan CSP terbatas.

API prefix dibaca dari /checkout-config. Ringkasan ditampilkan menggunakan textContent,
bukan query input. Tombol refresh mengambil status.
Channel Midtrans Snap tersedia bila enabled dan server key terisi.
Redirect provider hanya HTTPS host app.midtrans.com atau app.sandbox.midtrans.com.
UI belum menyediakan pengembalian otomatis ke return_url.

## API checkout

Semua endpoint wajib Authorization: Bearer <checkout_token>:

| Metode | Endpoint (prefix default /api/v1) | Fungsi |
| --- | --- | --- |
| GET | /public/payments/{payment_no} | Ringkasan |
| GET | /public/payments/{payment_no}/channels | Channel |
| POST | /public/payments/{payment_no}/attempts | Body {"channel_code":"MIDTRANS_SNAP"} |
| GET | /public/payments/{payment_no}/status | Status |
| GET | /public/attempts/{attempt_id}/instructions | Instruksi milik payment token |

Envelope sukses: data. Ringkasan hanya payment_no, amount, currency, status;
tidak mengekspos customer. JWT client ditolak di checkout, begitu pula sebaliknya.
Token checkout default 30 menit, dibatasi expiry payment; DB hanya menyimpan hash.
Token terikat satu payment, bisa digunakan ulang selama valid; jangan bagikan link.
Worker dapat menghapus sesi token yang sudah expired tanpa menghapus payment.
Respons 401 tetap ditangani dengan meminta link checkout baru lewat backend Event.
Renewal melalui backend Event: POST /api/v1/client/payments/{payment_id}/checkout.

## Error dan state

Error API: error.code, error.message, error.request_id, error.details.
Simpan request_id untuk tracing, bukan credential.
Katalog error lengkap ada di [API_ERROR_CODES.md](API_ERROR_CODES.md).

- 401: token hilang/invalid/expired atau client inactive; minta link baru lewat backend Event.
- 404: payment/attempt bukan milik token atau tidak ditemukan.
- 409: konflik state; ambil status terbaru.
- 422: input invalid.
- Gangguan provider: tampilkan pesan; jangan otomatis membuat order/payment baru.

CREATED/PENDING bukan pembayaran terkonfirmasi. Frontend tidak menandai order PAID
dari query string, redirect sukses, atau klik pengguna. Portal Event menerbitkan tiket
hanya dari callback terverifikasi atau pemeriksaan server-to-server.
Integrasi browser/provider sandbox tetap perlu pengujian end-to-end.

## Konfigurasi

Payment backend: PUBLIC_BASE_URL, API_PREFIX, CHECKOUT_TTL_SECONDS.
Event backend: client_id, client_secret, callback_secret dan base URL Payment.
Semua credential tetap di server; gunakan HTTPS production.

## Admin API terbaru

Frontend admin dapat memakai endpoint aktif berikut sesuai permission:

- Event: `GET /admin/clients/{client_id}/events` dan detail event.
- PortalUser PII: `GET /admin/clients/{client_id}/portal-users`, hanya
  `admin.portal_users.read` dan setiap akses diaudit.
- Revoke checkout: `POST /admin/clients/{client_id}/revoke-checkouts` dengan
  `{ "reason": "..." }`, membutuhkan `admin.clients.manage` dan CSRF.
- Export/summary payment: lihat [ADMIN_PAYMENT_API.md](ADMIN_PAYMENT_API.md).
- Search payment dilakukan server-side melalui parameter `search`; gunakan `total_count`
  dan `has_more` dari meta untuk pagination.
- Retry reconciliation: `RETRY_WAIT` berarti worker akan mencoba lagi sesuai
  exponential backoff; `FAILED` berarti batas retry tercapai.
