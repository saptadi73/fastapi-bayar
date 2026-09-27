# Rancangan Frontend Admin Payment Portal

Status: rancangan target UI. Fondasi backend login/me/logout dan read-only user/role/audit
sudah tersedia khusus development; kontrak AKTIF ada di [ADMIN_API.md](ADMIN_API.md).
Bagian API/matrix di bawah tetap target rancangan; jangan menganggap semua endpoint
atau permission sudah tersedia. Client create/read/update/rotate tersedia di
[ADMIN_CLIENT_API.md](ADMIN_CLIENT_API.md); create/update/revoke user tersedia di
[ADMIN_USER_API.md](ADMIN_USER_API.md). MFA, role editor dan UI masih belum tersedia.
Tab service per client sudah memiliki API list/detail/create/update:
[ADMIN_SERVICE_API.md](ADMIN_SERVICE_API.md). Bagian kontrak aktif tersebut mengungguli
path/field usulan pada tabel rancangan di bawah.
Pembacaan transaksi (list/detail/history/attempts) sudah tersedia:
[ADMIN_PAYMENT_API.md](ADMIN_PAYMENT_API.md). Customer PII tidak disertakan pada tahap ini.
Antrean rekonsiliasi tersedia di [ADMIN_RECONCILIATION_API.md](ADMIN_RECONCILIATION_API.md);
response 202 bukan bukti payment PAID.
Katalog error frontend ada di [API_ERROR_CODES.md](API_ERROR_CODES.md). Event Portal,
listing PortalUser PII, revoke checkout, export, summary, dan retry reconciliation
memiliki kontrak aktif di dokumen API masing-masing; tabel rancangan di bawah hanya
menjadi target UI untuk fitur yang memang belum aktif.

## 1. Pisahkan tiga jenis akses

| Aktor | Identitas/credential | Tujuan |
| --- | --- | --- |
| Pengelola Payment | User manusia + sesi admin + role/permission | Portal admin |
| Backend Event | Client ID + secret -> JWT client | Client payment API |
| Pembeli | Checkout token satu payment | Checkout |

Login admin tidak menggunakan /api/v1/oauth/token. JWT client dan checkout token
tidak boleh diterima sebagai sesi admin; sesi admin tidak boleh dipakai untuk client
API/checkout. Jika backend admin kelak memakai JWT, bedakan audience, jenis token
dan validasinya dari JWT client. User admin bukan record Client.

Registrasi client tersedia lewat scripts/register_client.py dan Admin Client API.
Login, tabel user/sesi dan audit autentikasi minimal sudah ada. Role sementara satu
kode per user dengan permission mapping di kode; role editor/tabel RBAC masih TODO.

Identitas transaksi aktif dijelaskan di [PORTAL_IDENTITY.md](PORTAL_IDENTITY.md):
nama client adalah nama Portal, satu client memiliki banyak event, pembayar dikenali
melalui email per client. PortalUser bukan user admin. Master event/pembayar dibuat
dari create payment backend client; belum tersedia CRUD admin untuk kedua master ini.
Desain daftar/detail transaksi perlu menampilkan client, event dan pembayar sesuai
permission, serta menangani null pada order historis. Form client tidak meminta
password pembayar atau kredensial user Portal Event.

## 2. Role dan permission usulan

Role bawaan: SUPER_ADMIN, INTEGRATION_ADMIN, FINANCE, AUDITOR.
Frontend membaca daftar permissions efektif dari backend; jangan menyimpulkan akses
hanya dari nama role. Permission berikut khusus admin, bukan scope payments:read/write
pada JWT backend Event. Default akses ditolak jika permission tidak dikenal/tidak ada.

| Permission | Super Admin | Admin Integrasi | Finance | Auditor |
| --- | --- | --- | --- | --- |
| admin.users.read / admin.users.manage | Ya | Tidak | Tidak | Tidak |
| admin.roles.read / admin.roles.manage | Ya | Tidak | Tidak | Tidak |
| admin.clients.read / admin.services.read | Ya | Ya | Tidak | Ya |
| admin.clients.manage / admin.services.manage | Ya | Ya | Tidak | Tidak |
| admin.clients.rotate_secret | Ya | Ya | Tidak | Tidak |
| admin.payments.read | Ya | Tidak | Ya | Ya |
| admin.reconciliation.read / admin.reconciliation.request | Ya | Tidak | Ya | Baca saja |
| admin.refunds.read / admin.refunds.request | Ya | Tidak | Ya | Baca/request |
| admin.refunds.approve | Penugasan eksplisit | Tidak | Penugasan eksplisit | Tidak |
| admin.audit.read | Ya | Tidak | Tidak | Ya |
| admin.settings.manage | Ya | Tidak | Tidak | Tidak |

Pengaju tidak boleh menyetujui refund sendiri, termasuk Super Admin. Permission
approve terpisah dari role default; UI dan backend harus menerapkan maker-checker.
Approval internal tidak berarti refund provider sudah berhasil.
Auditor hanya melihat metadata integrasi/transaksi/audit yang disanitasi, bukan secret.
Backend wajib memeriksa permission setiap request serta batas resource/client bila
user dibatasi ke client tertentu. Jangan menganggap role otomatis memberi akses global.

## 3. Halaman dan perilaku frontend

| Route UI usulan | Isi | Pengaman |
| --- | --- | --- |
| /admin/login | Identitas, password, error login generik | Tidak ada self-registration publik |
| /admin/mfa | Verifikasi MFA bila diminta | Belum dianggap login penuh sebelum selesai |
| /admin | Ringkasan modul yang boleh diakses | Jangan tampilkan metrik transaksi tanpa izin |
| /admin/users | Daftar, undang/buat, nonaktifkan, reset akses | admin.users.read/manage |
| /admin/roles | Role dan permission | admin.roles.read/manage |
| /admin/clients | Daftar dan form integrasi | admin.clients.read/manage |
| /admin/clients/:id | Service, allowlist, status, rotasi secret | Permission per aksi |
| /admin/payments | Filter, pagination, detail/history | admin.payments.read |
| /admin/reconciliation | Daftar kasus dan permintaan inquiry | Permission read/request terpisah |
| /admin/refunds | Permintaan, approval, status provider | Read/request/approve + bukan pengaju |
| /admin/audit | Filter actor/action/resource/time/result | admin.audit.read |
| /admin/settings | Konfigurasi yang diizinkan backend | admin.settings.manage; secret write-only |

Sediakan loading, empty, error, forbidden, session-expired dan submitting state.
Route guard berlaku pada direct URL, bukan hanya menu. Tombol mutasi dinonaktifkan
saat submit; aksi sensitif memakai konfirmasi dampak dan alasan perubahan.
Modul yang backend-nya belum tersedia diberi label belum tersedia, tidak menampilkan
mock sebagai data produksi. Frontend boleh membangun mock adapter terpisah sejak sekarang.

## 4. Sesi admin dan keamanan UI (rancangan)

Baseline deployment usulan: admin UI dan API same-origin, sesi opaque server-side
dengan cookie HttpOnly, Secure pada production dan SameSite sesuai deployment
(default usulan Lax). Jangan menyimpan password/token sesi admin dalam localStorage
atau sessionStorage. Checkout sessionStorage yang sudah ada bukan pola login admin.
Request mutasi menggunakan proteksi CSRF backend; same-site cookie bukan penggantinya.
Jika UI/API berbeda origin, kontrak CORS/cookie/CSRF perlu disepakati dahulu.

Alur: login -> challenge MFA bila diperlukan -> backend menerbitkan sesi -> GET me
-> render permission -> logout mencabut sesi di server dan membersihkan state/cache UI.
Reload halaman memanggil me; jangan menganggap cache profil sebagai bukti autentikasi.
Perubahan role, nonaktif user, reset password dan pencabutan sesi harus berlaku di server.
MFA, rate limit login, password hash, sesi idle/absolute expiry, reset password dan
reauthentication aksi sensitif adalah requirement backend sebelum produksi.
TTL sesi, mekanisme enrollment/recovery MFA dan email undangan belum difinalisasi.

Jangan kirim credential admin/client ke analytics, log browser, URL, atau error tracker.
Tidak ada akun/password default di frontend. Bootstrap Super Admin pertama melalui
proses operator yang diaudit; cegah hilangnya seluruh Super Admin aktif.

## 5. API admin usulan: semua BELUM TERSEDIA

Prefix usulan /api/v1/admin. Nama path/field berikut untuk mock dan pembahasan backend.

| Metode/path | Kebutuhan frontend |
| --- | --- |
| POST /auth/login | Input identifier/password; hasil authenticated atau mfa_required |
| POST /auth/mfa/verify | Input challenge_id/code; menerbitkan sesi setelah valid |
| GET /auth/me | Profil, roles, permissions, batas client, expiry sesi dan CSRF token |
| POST /auth/logout | Revoke sesi; frontend hapus state |
| GET /users; POST /users; PATCH /users/{id} | Listing dan pengelolaan user |
| GET /roles; PATCH /roles/{id} | Listing dan pengelolaan role/permission |
| GET /clients; POST /clients; PATCH /clients/{id} | Listing, pendaftaran, perubahan client |
| POST /clients/{id}/rotate-secret | Rotasi dengan konfirmasi dan audit |
| GET /clients/{id}/services; POST /clients/{id}/services | Service milik client |
| PATCH /clients/{id}/services/{service_id} | Ubah/nonaktifkan service |

API admin payments/reconciliation/refunds/audit/settings belum dirinci; jangan memakai
endpoint client API sebagai pengganti otorisasi admin. Pagination/filter dan concurrency
version untuk edit harus disepakati sebelum integrasi live.

Contoh response me untuk mock, bukan response backend saat ini:

```json
{
  "data": {
    "user": {"id": "user-demo", "display_name": "Admin Integrasi", "active": true},
    "roles": ["INTEGRATION_ADMIN"],
    "permissions": ["admin.clients.read", "admin.clients.manage", "admin.clients.rotate_secret"],
    "access_scope": {"all_clients": false, "client_ids": ["client-demo"]},
    "session_expires_at": "2026-09-18T12:00:00Z",
    "csrf_token": "<mock-only>"
  }
}
```

Gunakan envelope data untuk sukses, error.code/message/request_id/details untuk gagal.
Usulan perilaku: 401 -> hapus state dan login ulang; 403 -> halaman/tombol forbidden
tanpa logout paksa; 409 -> konflik/refresh resource; 422 -> validasi field; 429 ->
tunggu Retry-After; 5xx -> tampilkan request_id, jangan tampilkan exception/secret.
Kode simbolik admin, schema MFA dan endpoint CSRF bootstrap masih perlu finalisasi.
Jangan auto-retry rotasi secret atau mutasi lain tanpa kontrak idempotency backend.

## 6. Form pendaftaran client

Field rancangan: code/client_id unik, name, active, scopes yang diizinkan,
allowed_return_urls (list), callback_url, allowed_callback_urls (list), dan service
(code/name). Scope dipilih dari pilihan server, bukan bebas memasukkan nilai sendiri.
Kode client bukan secret. Perbedaan UUID internal dan code perlu label yang jelas.

URL cocok persis, tanpa wildcard; HTTPS production. HTTP loopback hanya development.
Form harus menjelaskan bahwa URL callback bukan URL redirect browser. Backend tetap
melakukan seluruh validasi; UI tidak boleh menerima URL arbitrary lewat query.

Create/rotate menghasilkan secret yang hanya ditampilkan sekali pada respons khusus,
bukan GET detail/list. Ini pengecualian tampilan sementara untuk operator berwenang,
bukan penyimpanan credential integrasi di frontend. Gunakan modal tanpa analytics,
copy eksplisit pengguna, instruksi simpan ke secret store backend Event, dan hapus
nilai dari state ketika modal ditutup/berpindah route. Tidak ada tombol reveal secret lama.
Kebijakan endpoint one-time tersebut BELUM ada; CLI saat ini mencetak credential.

Konfirmasi rotasi menjelaskan bahwa JWT client lama ditolak dan Event harus mengganti
client_secret. Rotasi OAuth saat ini tidak mencabut checkout token lama; menonaktifkan
client menolak JWT/checkout. Rotasi callback secret merupakan aksi terpisah yang perlu
kontrak transisi agar callback tertunda tetap dapat diverifikasi.

## 7. Audit dan acceptance checklist

Audit backend: actor, action, resource ID, waktu UTC, request_id, hasil, alasan,
serta before/after tersanitasi. Jangan merekam password/token/secret. Frontend hanya
menampilkan audit read-only; perubahan audit lewat UI tidak disediakan.

- [ ] Menu, tombol dan direct URL mengikuti permissions efektif.
- [ ] API menolak mutasi tanpa permission meskipun request dibuat di luar UI.
- [ ] Token client/checkout tidak bisa login admin dan sebaliknya.
- [ ] Login gagal generik, MFA challenge tidak memberikan sesi penuh.
- [ ] Logout/revoke/expiry/disable menghilangkan akses di server dan UI.
- [ ] Sesi/credential tidak masuk storage persisten, URL atau telemetry browser.
- [ ] CSRF, rate limit dan reauthentication aksi sensitif teruji.
- [ ] Create/rotate secret one-time; stale edits dan double-submit ditangani.
- [ ] Filter client/resource enforcement diuji, bukan hanya filter frontend.
- [ ] Pengaju refund tidak dapat approve sendiri, termasuk Super Admin.
- [ ] Aksi sensitif tercatat pada audit dengan redaksi credential.
- [ ] Mock diganti API nyata hanya setelah OpenAPI/contract test tersedia.

## Referensi

Pemeriksaan izin per request dan default-deny mengacu pada
[OWASP Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html).
Rancangan cookie dan lifecycle sesi mengacu pada
[OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
Keputusan role, nama permission dan path admin di dokumen ini adalah usulan proyek,
bukan ketentuan Midtrans/DOKU; protokol gateway tidak diubah.
