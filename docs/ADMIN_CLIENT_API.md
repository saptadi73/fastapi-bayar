# Admin Client API

Aktif khusus development, mengikuti ADMIN_ENABLED dan production guard admin.
Migration 0012 menambah resource_id/reason pada audit. Login dan CSRF mengikuti
[ADMIN_API.md](ADMIN_API.md). UI admin belum tersedia; frontend dapat memakai API ini.

## Permission dan endpoint

Prefix /api/v1/admin/clients (sesuai API_PREFIX). Identitas path adalah UUID internal;
code adalah client_id OAuth. Admin saat ini operator global, belum penugasan per-client.

| Metode | Path relatif | Permission |
| --- | --- | --- |
| GET | / | admin.clients.read |
| GET | /{client_id} | admin.clients.read |
| POST | / | admin.clients.manage |
| PATCH | /{client_id} | admin.clients.manage |
| POST | /{client_id}/rotate-secret | admin.clients.rotate_secret |
| POST | /{client_id}/revoke-checkouts | admin.clients.manage |

Gunakan path koleksi tanpa slash akhir: /api/v1/admin/clients.
SUPER_ADMIN dan INTEGRATION_ADMIN mendapat ketiga permission. AUDITOR hanya read;
FINANCE tidak mendapat akses client. Semua mutasi memerlukan cookie sesi, exact Origin
dan X-CSRF-Token. JWT client tidak diterima sebagai otorisasi admin.

## Registrasi

POST koleksi:

```json
{
  "code": "EVENT-CLIENT",
  "name": "Portal Event",
  "service_code": "EVENT",
  "active": true,
  "scopes": ["payments:read", "payments:write"],
  "allowed_return_urls": ["https://event.example.com/payment/result"],
  "allowed_callback_urls": ["https://event.example.com/api/payment/callback"],
  "callback_url": "https://event.example.com/api/payment/callback",
  "reason": "Pendaftaran portal event"
}
```

Semua field di atas wajib. callback_url boleh null; daftar URL boleh kosong jika tidak
dipakai. code/service_code hanya alfanumerik, underscore dan tanda minus. Code unik
case-sensitive. Scope yang didukung: payments:read, payments:write, payments:refund.
URL harus valid HTTPS (loopback HTTP development), maksimal 500 karakter, 20 entri/list;
callback_url harus cocok persis dengan salah satu allowed_callback_urls.

201 data memuat id, code, name, active, version=1, scopes, URL, service_code,
client_secret dan callback_secret. Service awal dibuat atomik bersama client dan audit.
Secret OAuth disimpan hash, callback secret masih plaintext di DB (enkripsi TODO).
Tidak ada email/user pembayar yang dibuat saat registrasi client.

Frontend menampilkan credential sekali dari response create dalam modal tanpa logging/
analytics/persistent storage. Tutup modal -> hapus secret dari state. Serahkan secret
ke operator backend Event lewat saluran aman. Jangan memakai credential di frontend Event.
GET list/detail tidak pernah mengembalikan secret atau hash. Tidak ada reveal endpoint.

## Ubah konfigurasi dan rotasi

GET list memakai limit (1-100, default 50), offset (>=0), meta limit/offset.
Response detail memuat konfigurasi dan version, tanpa credential.

PATCH menggunakan SEMUA field konfigurasi create kecuali code/service_code, ditambah
expected_version dari GET terakhir. Ini full configuration update meskipun metode PATCH:
field yang dihilangkan ditolak 422, tidak diam-diam dikosongkan. Code/service awal tidak
dapat diubah endpoint ini. Unknown fields ditolak. reason wajib nonblank.

Update menaikkan version/token_version dan mencabut JWT client lama, termasuk perubahan
nama. Event perlu memperoleh JWT baru dengan secret yang sama. active=false juga
menolak checkout client. Mengaktifkan kembali dapat membuat checkout lama yang belum
expired dapat diakses lagi; gunakan endpoint revoke-checkouts untuk mencabut seluruh
checkout session aktif milik client bila diperlukan.

POST /{client_id}/rotate-secret body:

```json
{"expected_version": 2, "reason": "Rotasi credential berkala"}
```

Response memuat konfigurasi/version baru dan client_secret baru sekali saja.
OAuth secret/JWT lama ditolak. Callback secret TIDAK berubah dan tidak ditampilkan;
checkout token lama tidak dicabut oleh rotasi OAuth.

POST `/{client_id}/revoke-checkouts` memakai body `{ "reason": "..." }` dan
menghapus seluruh checkout session aktif milik client tersebut. Payment ledger,
attempt, dan history tidak dihapus. Operasi dikunci pada client dan dicatat sebagai
`CLIENT_CHECKOUTS_REVOKED`.
Concurrent update/rotation diserialisasi row lock: hanya expected_version terkini
yang diterima. CLI register_client --rotate juga menaikkan version yang sama.

## Error, retry, audit dan batas

- 401: sesi admin tidak valid; 403: Origin/CSRF/permission tidak memenuhi.
- 404 CLIENT_NOT_FOUND: UUID tidak ditemukan.
- 409 CLIENT_CODE_EXISTS: kode sudah ada; jangan otomatis membuat kode alternatif.
- 409 CLIENT_VERSION_CONFLICT: muat ulang detail dan konfirmasi ulang, bukan auto-retry.
- 422: payload/URL/scope invalid.

Belum ada idempotency key admin mutation. Response create hilang: cari client lewat
list/detail; credential tidak dapat dibaca ulang lewat API. OAuth dapat dirotasi
secara eksplisit, sedangkan recovery/rotasi callback secret masih memerlukan prosedur
operator (CLI existing) dan koordinasi backend Event. Jangan rotasi otomatis saat timeout.

Audit CLIENT_CREATED/CLIENT_UPDATED/CLIENT_SECRET_ROTATED menyimpan actor, UUID resource,
reason, waktu. Commit audit dan perubahan client atomik; tidak menyimpan secret/hash
atau payload konfigurasi. Reason bebas teks: operator dilarang memasukkan secret/PII
sensitif. Belum ada redaksi otomatis reason, before/after atau request_id audit.
Response no-store; proxy/observability juga tidak boleh merekam response credential.

Service tambahan dapat dikelola melalui [ADMIN_SERVICE_API.md](ADMIN_SERVICE_API.md).
Belum ada delete client (ledger dipertahankan), enkripsi callback
secret, role editor, MFA maupun UI admin. Pengelolaan user sekarang tersedia di
[ADMIN_USER_API.md](ADMIN_USER_API.md). Tidak ada perubahan protokol Midtrans/DOKU.
