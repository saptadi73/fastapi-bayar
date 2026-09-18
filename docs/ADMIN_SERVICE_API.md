# Admin Service API

Aktif development setelah migration 0014. Satu client dapat memiliki banyak service.
Service adalah kategori layanan (misalnya EVENT/TICKET/SHOP), bukan identitas event
atau akun pembayar. Kontrak event/email tetap mengikuti PORTAL_IDENTITY.md.
Tidak ada perubahan protokol/routing merchant Midtrans/DOKU pada iterasi ini.

## Endpoint dan permission

Prefix default: /api/v1/admin/clients/{client_id}/services. client_id dan service_id
pada URL adalah UUID internal. Kode service digunakan sebagai service_code saat
backend Portal membuat payment. Service awal dari registrasi client tetap tersedia.

| Metode | Path relatif | Permission |
| --- | --- | --- |
| GET | koleksi | admin.services.read |
| GET | /{service_id} | admin.services.read |
| POST | koleksi | admin.services.manage |
| PATCH | /{service_id} | admin.services.manage |

SUPER_ADMIN dan INTEGRATION_ADMIN mendapat read/manage; AUDITOR hanya read;
FINANCE tidak mendapat permission service. Seluruh mutasi memakai sesi admin,
Origin dan X-CSRF-Token sesuai ADMIN_API.md. JWT client/checkout bukan sesi admin.
Admin saat ini operator global, belum ada penugasan admin hanya untuk client tertentu.
Query service selalu dibatasi client_id pada path; service milik client lain -> 404.

## Create

POST koleksi tanpa trailing slash:

```json
{
  "code": "TICKET",
  "name": "Penjualan Tiket",
  "active": true,
  "reason": "Menambah layanan tiket"
}
```

Semua field wajib. code alfanumerik/underscore/minus, maksimal 100 karakter,
case-sensitive dan unik per client. Kode yang sama boleh di client berbeda.
name maksimal 250 karakter, reason maksimal 500, keduanya dipangkas dan wajib nonblank.
active harus JSON boolean (bukan string/angka). Field tambahan ditolak.
Response 201 data: id, client_id, code, name, active, version=1.
Konfigurasi service boleh disiapkan ketika client inactive; ini tidak mengaktifkan client.

## List, detail dan update

GET koleksi memakai limit (1-100, default 50), offset (>=0); meta limit/offset.
Daftar mencakup service aktif/nonaktif, urut code. Detail mengembalikan field yang sama.
Tidak ada credential pada response. Client tidak ditemukan -> 404 CLIENT_NOT_FOUND;
service tidak ditemukan pada client -> 404 SERVICE_NOT_FOUND.

PATCH /{service_id}:

```json
{
  "name": "Penjualan Tiket",
  "active": false,
  "expected_version": 1,
  "reason": "Hentikan order baru sementara"
}
```

PATCH wajib seluruh field tersebut (bukan sparse patch). Kode dan pemilik client
tidak dapat diubah. Setiap update menaikkan version; versi salah/dua edit bersamaan
menghasilkan 409 SERVICE_VERSION_CONFLICT pada edit yang kalah. Muat ulang dan minta
konfirmasi operator, jangan auto-retry. Duplicate create -> 409 SERVICE_CODE_EXISTS.
Expected_version integer positif, bukan bool. Schema invalid -> 422.

Tidak ada delete service; penonaktifan mempertahankan referensi dan ledger.
Update service tidak menaikkan token_version client atau merotasi credential.

## Dampak pada transaksi

active=false menolak pembuatan payment BARU dengan SERVICE_NOT_FOUND (404).
Create/update service memakai client row lock yang sama dengan payment initiation,
sehingga perubahan status dan order baru diserialisasi. Order yang sudah diterima
sebelum penonaktifan tetap ada. Replay idempotent order lama tetap dapat berhasil.
Payment, callback, expiry, refund atau checkout existing tidak otomatis dibatalkan;
checkout lama masih dapat membuat attempt bila state payment mengizinkan.
Gunakan proses pembatalan payment terpisah bila diperlukan, bukan toggle service.

## Audit dan frontend

SERVICE_CREATED/SERVICE_UPDATED dicatat atomik dengan mutasi: actor, UUID service,
reason dan waktu. Jangan memasukkan secret/PII sensitif pada reason. Audit before/after
dan request_id masih TODO. Tidak ada idempotency key admin: timeout create harus
ditindaklanjuti lewat list/detail sebelum mencoba lagi (kode unik mencegah duplikasi).

Frontend: tab Services pada detail client, daftar aktif/nonaktif, form create,
edit nama/status, expected_version dari response terbaru, dan konfirmasi dampak saat
menonaktifkan. Permission mengatur menu/tombol; enforcement tetap di backend.
Tampilkan 403 sebagai forbidden dan 409 sebagai konflik yang perlu reload.
UI admin, role editor, MFA dan konfigurasi gateway/channel per-service belum tersedia.

Referensi provider diperiksa kembali sebagai batas integrasi:
[Midtrans notification](https://docs.midtrans.com/docs/https-notification-webhooks) dan
[DOKU notification best practice](https://developers.doku.com/get-started-with-doku-api/notification/best-practice).
Toggle service adalah aturan order internal, bukan request cancel ke gateway.
