# Admin API - foundation development

Status aktif setelah migration 0029: login, me, logout, rate limit account-aware,
MFA TOTP/reauthentication, read-only user/role/audit,
bootstrap Super Admin pertama. Client create/read/update/rotate kini tersedia lewat
[ADMIN_CLIENT_API.md](ADMIN_CLIENT_API.md). Create/update/revoke user tersedia di
[ADMIN_USER_API.md](ADMIN_USER_API.md). Belum ada UI admin,
Reset password, invitation, forced password change, dan role editor masih terbuka.

Service per-client: [ADMIN_SERVICE_API.md](ADMIN_SERVICE_API.md), list/detail/create/update.
SUPER_ADMIN/INTEGRATION_ADMIN mendapat admin.services.read/manage; AUDITOR hanya read.

Portal event read-only tersedia pada `GET /admin/clients/{client_id}/events` dan
`GET /admin/clients/{client_id}/events/{event_id}` dengan `admin.payments.read`.
Response hanya memuat identitas event non-PII. Listing payer tersedia pada
`GET /admin/clients/{client_id}/portal-users` dan hanya SUPER_ADMIN dengan
`admin.portal_users.read`; response mengandung PII dan setiap akses diaudit.
Path aktif diproteksi oleh contract test OpenAPI; generated client dan contract
pagination/concurrency masih menjadi pekerjaan release berikutnya.

## Aktivasi

ADMIN_ENABLED default false di .env.example; .env lokal development diset true.
Mode production menolak ADMIN_ENABLED=true sampai MFA/security review selesai.
Tidak ada password bawaan atau akun yang dibuat oleh migration.

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe scripts\bootstrap_admin.py --email admin@example.com --name "Super Admin"
```

Ganti email dengan milik operator. Password diminta interaktif dua kali (15-128
karakter), tidak melalui argument CLI/.env/log. Hash PBKDF2-HMAC-SHA256 600000 iterasi
dengan salt acak. Bootstrap menolak jika sudah ada satu admin; tidak mengganti password
atau mengaktifkan user existing. Bootstrap serentak diserialisasi advisory lock DB.
Jangan menghapus akun untuk mereset password; recovery admin masih TODO.

## Konfigurasi

| Setting | Default | Fungsi |
| --- | --- | --- |
| ADMIN_ENABLED | false | Aktifkan hanya development |
| ADMIN_SESSION_TTL_SECONDS | 28800 | Expiry absolut sesi |
| ADMIN_IDLE_TTL_SECONDS | 1800 | Expiry tidak aktif |
| ADMIN_LOGIN_LIMIT | 10 | Maksimum percobaan per peer IP/window |
| ADMIN_LOGIN_WINDOW_SECONDS | 300 | Fixed-window PostgreSQL |
| PUBLIC_BASE_URL | http://localhost:8000 | Sumber exact allowed Origin |

Frontend admin same-origin dengan API. localhost dan 127.0.0.1 adalah origin berbeda.
Login dan seluruh mutasi admin wajib header Origin persis scheme://host:port dari
PUBLIC_BASE_URL. Tidak ada fallback Origin hilang. Di browser Origin dikirim browser;
pada pengujian HTTP manual sertakan header. API tidak mengaktifkan CORS lintas-origin.

## Endpoint aktif (prefix default /api/v1/admin)

| Metode/path | Input / akses | Hasil data |
| --- | --- | --- |
| POST /auth/login | JSON identifier (email), password; Origin wajib | status, user, csrf_token, session_expires_at |
| GET /auth/me | Cookie sesi | user, roles, permissions, access_scope, expiry, csrf_token |
| POST /auth/logout | Cookie + Origin + X-CSRF-Token | status logged_out |
| GET /users | admin.users.read | List profil tanpa password_hash |
| GET /roles | admin.roles.read | List code dan permissions yang aktif |
| GET /audit | admin.audit.read | List id, actor_id, action, occurred_at |

List users/audit memakai limit (1-100, default 50) dan offset (>=0), meta memuat
keduanya, belum total count/filter. Timestamp ISO8601. Semua memakai envelope data/error.
identifier dinormalisasi lowercase. User tidak aktif/login salah memberi pesan generik.

Contoh request login:

```json
{"identifier":"admin@example.com","password":"<password operator>"}
```

Login mengatur cookie payment_admin_session, HttpOnly, SameSite=Lax, path
/api/v1/admin (mengikuti API_PREFIX), tanpa Domain. Secure bila PUBLIC_BASE_URL HTTPS;
HTTP hanya untuk development. Cookie adalah token opaque acak, bukan JWT; DB menyimpan
hash token. Raw token tidak dikembalikan di JSON. Login ulang mengganti sesi browser
yang sama, bukan mencabut semua sesi perangkat lain.

Semua endpoint listing admin mengembalikan `meta.limit`, `meta.offset`, dan `meta.has_more`.
Frontend memanggil me saat reload; simpan csrf_token dalam memory dan kirim pada
mutasi. Jangan simpan password/session token di localStorage/sessionStorage. Cookie
tidak dibaca JavaScript. Logout menghapus sesi di DB dan cookie; 401 berikutnya berarti
sesi tidak tersedia. Expiry idle/absolut dan status aktif diperiksa setiap request.
Sesi admin, JWT client dan checkout token tidak dapat saling menggantikan.

## Permission aktif

Role disimpan satu kode per user, pemetaan permission sementara di kode, bukan tabel
RBAC configurable. SUPER_ADMIN: admin.users.read/manage, admin.roles.read, admin.audit.read.
AUDITOR: admin.audit.read. Tambahan modul client: SUPER_ADMIN/INTEGRATION_ADMIN mendapat
admin.clients.read/manage/rotate_secret; AUDITOR mendapat admin.clients.read.
SUPER_ADMIN/FINANCE/AUDITOR mendapat admin.payments.read untuk list/detail/history/attempts;
lihat [ADMIN_PAYMENT_API.md](ADMIN_PAYMENT_API.md). INTEGRATION_ADMIN tidak mendapat akses transaksi.
Jangan menggunakan matrix target rancangan sebagai hak akses nyata; gunakan me/roles.
Permission tidak dikenal ditolak; backend memeriksa permission pada route terlindungi.
Perubahan role/active di DB berlaku pada request berikutnya. Belum ada API untuk
mengedit role definition; pengubahan role/status user mengikuti ADMIN_USER_API.md.
User admin saat ini operator global (access_scope.all_clients=true);
penugasan per-client dan mutasi payment admin belum tersedia; pembacaan ledger dan
antrean rekonsiliasi tersedia, sedangkan worker gateway masih manual.

## Error, rate limit, audit

401 ADMIN_LOGIN_FAILED / ADMIN_SESSION_REQUIRED / ADMIN_SESSION_INVALID: login ulang.
403 ADMIN_ORIGIN_DENIED / ADMIN_CSRF_INVALID / ADMIN_FORBIDDEN: tolak aksi, jangan
otomatis logout karena permission kurang. 422 VALIDATION_ERROR: field invalid;
detail tidak menyertakan input mentah (termasuk password). 503 ADMIN_DISABLED: fitur mati.
429 ADMIN_LOGIN_RATE_LIMIT: tunggu Retry-After (detik).

Throttle shared PostgreSQL menghitung login dengan schema/Origin valid sebelum hash
password, termasuk login sukses; fixed window per peer IP, bukan per-account.
Bukan perlindungan menyeluruh dari distributed attack/body flood. Reverse proxy harus
mengatur trusted forwarded IP dengan benar; jangan percaya X-Forwarded-For sembarang.
Cleanup bucket login dan session expired tersedia melalui worker cleanup; aktivasi worker
sebagai service deployment tetap menjadi tanggung jawab environment.

Audit minimal: BOOTSTRAP, LOGIN_SUCCEEDED, LOGIN_FAILED, LOGOUT; actor login gagal null,
tanpa identitas yang dicoba, password, token atau payload. Belum audit denied/rate-limit,
request_id, resource, before/after atau tamper-resistant log. Hindari log body di proxy.
Frontend tidak boleh menganggap fondasi ini siap produksi/MFA-ready.

## Referensi

Work factor password: [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
Origin dan CSRF: [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
Tidak ada perubahan protokol Midtrans/DOKU pada iterasi admin ini.
