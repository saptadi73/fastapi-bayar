# Catatan pemeriksaan provider — 18 September 2026

## Email customer — pemeriksaan 18 September 2026

Referensi resmi:

- https://docs.midtrans.com/reference/request-body-json-parameter — customer_details opsional;
  contoh minimum hanya transaction_details.
- https://docs.midtrans.com/docs/snap-advanced-feature — collect_email dapat required/optional/none;
  aturan koleksi checkout berbeda dari kewajiban field pada request merchant.
- https://docs.doku.com/accept-payments/no-integration-products/payment-link/create-payment-link —
  koleksi email Payment Link dapat dinonaktifkan. Bukan bukti aturan email Direct API.

Keputusan: email customer opsional pada kontrak umum Payment Portal, divalidasi bila
diisi, tidak dikirim ke Midtrans bila kosong. DOKU tetap menunggu implementasi serta
verifikasi persyaratan per endpoint/channel. Tidak ada dummy email atau klaim bahwa
seluruh metode pembayaran selalu mendukung customer tanpa email.

42 tests lulus termasuk payload HTTPX mock dan PostgreSQL insert/idempotency tanpa
email. Migration nullable diterapkan ke database lokal. Sandbox provider belum diuji.

## Midtrans legacy Snap/Core inquiry

Referensi resmi yang diperiksa:

- https://docs.midtrans.com/reference/get-transaction-status
- https://docs.midtrans.com/docs/get-status-api-requests
- https://docs.midtrans.com/docs/transaction-status-cycle
- https://docs.midtrans.com/docs/https-notification-webhooks

Implementasi: GET Core API `/v2/{order_id}/status`, Basic Auth server key dengan
password kosong. Base URL Core terpisah dari Snap create. GET terautentikasi
masuk processor ledger internal dengan source RECONCILIATION; endpoint webhook
publik tetap wajib signature. Tidak membuat signature provider sintetis.

404 (HTTP atau status_code body) dianggap UNRESOLVED: Snap dapat belum mempunyai
status Core sebelum customer memilih metode. Tidak membuat ulang charge atau
menandai FAILED. Order response harus identik, nominal/currency diperiksa sebelum
update ledger. Capture fraud challenge, refund, late-paid yang tidak didukung
tetap membutuhkan review. Inquiry tidak memulihkan token Snap yang hilang.

Batas: konfigurasi satu merchant global; metode BI-SNAP/DANA yang mensyaratkan
transaction_id dan kontrak berbeda belum ditangani worker order_id ini.

## DOKU

Referensi Check Status Non-SNAP dan signature GET diperiksa:

- https://developers.doku.com/get-started-with-doku-api/check-status-api/non-snap
- https://developers.doku.com/get-started-with-doku-api/signature-component/non-snap/signature-from-api-get-method

Implementasi kini menyediakan inquiry `GET /orders/v1/status/{invoice}` dengan
`Client-Id`, `Request-Id`, `Request-Timestamp`, dan HMAC-SHA256 `Signature`.
Charge/refund tetap product/channel-specific dan belum diaktifkan secara generik.
Iterasi berikutnya mengaktifkan hanya `DOKU_INDOMARET` melalui endpoint
`/indomaret-online-to-offline/v2/payment-code`; channel DOKU lain tetap ditolak
oleh registry sampai kontraknya dipetakan.
Untuk channel non-card aktif, refund mengikuti prosedur manual DOKU; worker tidak
menebak atau memakai endpoint refund product lain. API refund hanya boleh ditambahkan
setelah product/channel merchant dikonfirmasi dan kontrak request/response diuji.
Notification DOKU kini diverifikasi pada `/api/v1/webhooks/doku/{merchant_code}`;
signature memakai digest body dan request target aktual, lalu event dideduplikasi
berdasarkan hash body serta diproses hanya jika invoice dan nominal cocok.
Verifier juga menolak timestamp stale/future di luar `DOKU_TIMESTAMP_TOLERANCE_SECONDS`
dan `Request-Id` di atas 128 karakter untuk mengurangi risiko replay.

## Bukti pengujian

27 tests lulus, termasuk PostgreSQL isolated schema untuk reservation/concurrency
attempt dan HTTPX mock untuk inquiry (URL, Basic Auth, 404, order mismatch, response
malformed, error provider). Belum melakukan sandbox UAT nyata atau inquiry nyata.
