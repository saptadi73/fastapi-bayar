# Admin Payment API - read-only

Aktif development setelah migration 0015 (indeks daftar transaksi/history).
Permission admin.payments.read diberikan kepada SUPER_ADMIN, FINANCE dan AUDITOR.
INTEGRATION_ADMIN tidak mendapat akses. Gunakan cookie sesi admin sesuai ADMIN_API.md;
JWT Portal Event/checkout token tidak memberikan akses endpoint admin.
Admin masih operator global: filter client adalah pencarian, bukan batas otorisasi tenant.
Penugasan admin per-client masih TODO. Production guard admin tetap berlaku.

## Endpoint

Prefix default /api/v1/admin/payments (koleksi tanpa trailing slash).

| Metode | Path relatif | Data |
| --- | --- | --- |
| GET | koleksi | Daftar payment |
| GET | /summary | Agregasi count/nominal per status dan client |
| GET | /export | Export JSON bounded ledger payment |
| GET | /{payment_id} | Detail ringkas ledger |
| GET | /{payment_id}/history | Riwayat perubahan status |
| GET | /{payment_id}/attempts | Ringkasan attempt |

payment_id adalah UUID internal. Tidak ada mutasi, inquiry gateway, cancel, refund,
settlement atau pengiriman callback melalui endpoint ini.
GET ini tidak membutuhkan CSRF; otorisasi/session tetap diperiksa backend.

## Filter daftar

| Query | Semantik |
| --- | --- |
| client_id | UUID client, exact match |
| service_id | UUID service, exact match |
| event_id | ID event eksternal; wajib disertai client_id |
| status | Enum status payment, misalnya CREATED/PENDING/PAID |
| reference_id | Reference order client, exact match |
| created_from | Timestamp timezone-aware, inklusif |
| created_to | Timestamp timezone-aware, eksklusif |
| limit | 1-100, default 50 |
| offset | >=0, default 0 |

Filter digabung AND. created_from harus lebih kecil dari created_to bila keduanya
diisi. Gunakan waktu ISO8601 ber-offset/Z; timezone lokal frontend dikonversi terlebih
dahulu. event_id tanpa client -> 422 CLIENT_FILTER_REQUIRED; rentang terbalik ->
422 INVALID_DATE_RANGE. Enum/UUID/tanggal naive/pagination invalid -> 422 VALIDATION_ERROR.
Kombinasi client/service yang tidak cocok mengembalikan daftar kosong, bukan data tenant lain.
Reference yang sama dapat ada di beberapa client, jadi tambahkan client_id bila perlu.

Daftar diurutkan created_at DESC, id DESC. Tidak join attempts saat pagination sehingga
satu payment tetap satu baris meskipun punya beberapa attempt.
Envelope {data:[...],meta:{limit,offset,has_more}}. Tidak ada total_count/agregasi nominal.
Offset pagination bukan snapshot: insert/status berubah di antara request bisa menggeser
halaman; refresh dari offset=0 saat filter berubah. Export cursor/snapshot tersedia pada
endpoint `/export`.

## Field response

Payment list/detail: id, payment_no, client_id, client_name, service_id, event_id,
event_name, reference_id, amount, currency, status, created_at, expires_at.
client_name/event_name adalah snapshot order, dapat null pada data historis.
Nominal integer rupiah IDR sesuai ledger; status bukan status attempt.

History: id, from_status, to_status, source, occurred_at; urut waktu lalu id ASC.
Attempts: id, attempt_no, gateway, gateway_order_id, channel_code, status;
urut attempt_no ASC. History/attempts menggunakan limit/offset/has_more yang sama.
Payment tidak ditemukan pada detail maupun subresource -> 404 PAYMENT_NOT_FOUND.
Tidak ada history sintetis: data legacy tanpa riwayat ditampilkan sebagai daftar kosong.

Tidak diekspos: nama/email/telepon customer, metadata, description/free-text reason,
return_url, payload webhook, instructions, checkout URL/token, secret maupun hash.
Karena izin baca customer belum dipisah, frontend tidak menambahkan data customer
dari endpoint client API. Modul PII terotorisasi terpisah masih TODO.
Nomor reference/nama event tetap bisa berisi informasi bisnis; jangan kirim ke analytics.

## Frontend dan batas operasional

Bangun tabel dengan filter client/event/service/status/rentang tanggal, tombol next
mengikuti has_more, detail dengan tab history/attempts, serta empty/loading/error states.
403 -> forbidden tanpa memaksa logout; 401 -> login ulang; 404 -> resource tidak tersedia.
Tampilkan history dan state ledger apa adanya. Jangan mengubah status/tiket dari UI.
Data read-only adalah kondisi DB saat dibaca, bukan inquiry real-time provider.
Setiap endpoint bisa membaca snapshot waktu berbeda; refresh untuk status terbaru.

Antrean rekonsiliasi dan worker inquiry tersedia di [ADMIN_RECONCILIATION_API.md](ADMIN_RECONCILIATION_API.md).
Export, PII permission, dan dashboard agregasi tersedia; settlement dan multi-merchant
routing masih TODO. Refund maker-checker internal tersedia di `ADMIN_REFUND_API.md`.
Tidak ada transaksi gateway nyata yang dibuat oleh tes admin ledger.

`GET /export` memakai filter daftar yang sama, limit 1-5000, dan mengembalikan
snapshot JSON bounded dengan `snapshot_at`, `has_more`, serta `next_cursor`.
Request berikutnya mengirim `cursor` dan `snapshot_at` dari response pertama;
server memakai urutan `(created_at DESC, id DESC)` sehingga insert baru tidak
menjadi field ledger yang sudah disanitasi. Setiap akses summary/export dicatat
sebagai `PAYMENT_SUMMARY_VIEWED` atau `PAYMENT_EXPORT_VIEWED`; audit hanya
menyimpan actor dan ringkasan filter.

`GET /summary` read-only mengembalikan `by_status` dan `by_client` dengan
`payment_count` serta `amount` IDR. Filter yang tersedia `client_id`, `status`,
`created_from`, dan `created_to`. Agregasi langsung dari `payment_transactions`
sehingga attempt tidak menggandakan jumlah. Endpoint tidak mengembalikan PII,
metadata, atau data provider.

Referensi resmi diperiksa kembali:
[Midtrans notifications](https://docs.midtrans.com/docs/https-notification-webhooks) dan
[DOKU notification handling](https://developers.doku.com/get-started-with-doku-api/notification/best-practice).
Endpoint admin ini hanya membaca ledger; tidak mengubah kontrak notifikasi provider.
