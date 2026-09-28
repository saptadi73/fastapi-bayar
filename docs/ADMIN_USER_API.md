# Pengelolaan user admin

Aktif development setelah migration 0013. Bukan user pembayar Portal Event.
Login/CSRF mengikuti [ADMIN_API.md](ADMIN_API.md); bootstrap akun pertama tetap CLI.
Role masih empat kode tetap, bukan role editor/custom permission.

## Endpoint

Prefix default /api/v1/admin/users. Mutasi hanya SUPER_ADMIN dengan
admin.users.manage, cookie sesi, exact Origin dan X-CSRF-Token. GET daftar memakai
admin.users.read dan pagination limit/offset. Tidak ada delete atau self-registration.

| Metode | Path relatif | Kegunaan |
| --- | --- | --- |
| GET | koleksi | Profil user dengan version |
| POST | koleksi | Buat operator baru |
| PATCH | /{user_id} | Ubah nama/role/status |
| POST | /{user_id}/revoke-sessions | Cabut semua sesi user |

POST koleksi (tanpa trailing slash):

```json
{
  "email": "operator@example.com",
  "display_name": "Operator Integrasi",
  "role": "INTEGRATION_ADMIN",
  "active": true,
  "password": "<password awal 15-128 karakter>",
  "reason": "Penugasan integrasi portal"
}
```

Role: SUPER_ADMIN, INTEGRATION_ADMIN, FINANCE, AUDITOR. FINANCE dapat membaca ledger
melalui ADMIN_PAYMENT_API.md. Email dinormalisasi lowercase dan unik untuk akun admin. Password di-hash,
tidak dikembalikan response/audit. Response 201 data: id, email, display_name, role,
active, version=1, dan force_password_change=true. Email undangan, reset password,
dan forced password change tersedia. Akun baru wajib mengganti password awal melalui
`POST /admin/users/password-change` sebelum mengakses modul lain. Serahkan password
awal melalui saluran aman; frontend jangan menyimpan/log/analytics input password dan
hapus state setelah submit. Admin tetap development-only sampai security review.

PATCH memakai seluruh field berikut (bukan sparse patch):

```json
{
  "display_name": "Operator Audit",
  "role": "AUDITOR",
  "active": true,
  "expected_version": 1,
  "reason": "Perubahan tanggung jawab"
}
```

Email/password tidak dapat diubah lewat PATCH. Unknown fields ditolak. Setiap update
menaikkan version dan mencabut SELURUH sesi target, termasuk perubahan nama saja.
Jika mengubah diri sendiri, request sukses tetapi request berikutnya wajib login ulang;
frontend perlu membersihkan state. Reaktivasi tidak memulihkan sesi yang dicabut.

Revoke: POST /{user_id}/revoke-sessions dengan body
{"expected_version":2,"reason":"Cabut akses perangkat"}. Response data berisi id,
version baru dan status sessions_revoked. User masih dapat login lagi bila aktif
dan password valid; untuk memblokir login berikutnya gunakan active=false.
Jangan auto-retry mutation saat timeout: ambil ulang versi dan konfirmasi operator.

## Pengaman dan error

- 409 LAST_SUPER_ADMIN: Super Admin aktif terakhir tidak boleh dinonaktifkan/diturunkan.
- 409 ADMIN_USER_VERSION_CONFLICT: stale expected_version; reload dan konfirmasi ulang.
- 409 ADMIN_EMAIL_EXISTS: email duplikat; jangan buat email alternatif otomatis.
- 404 ADMIN_USER_NOT_FOUND: UUID tidak ditemukan.
- 422: schema invalid; response tidak menyertakan raw input password.
- 401 sesi invalid; 403 permission/Origin/CSRF ditolak.

Semua mutation user diserialisasi advisory lock PostgreSQL bersama bootstrap; actor,
permission dan keberadaan sesi diperiksa ulang setelah lock. User target di-row-lock.
Invariant Super Admin terakhir hanya dijamin alur aplikasi; direct SQL dapat melanggarnya.
Login memakai row lock user, sehingga login/revoke bersamaan diserialisasi. Login
baru setelah revoke tetap diperbolehkan jika user aktif.

Audit ADMIN_USER_CREATED, ADMIN_USER_UPDATED, ADMIN_SESSIONS_REVOKED mencatat actor,
resource UUID, reason dan waktu, atomik dengan perubahan. Reason bebas teks: jangan
masukkan password/secret/PII sensitif. Before/after, request_id, redaksi otomatis reason
dan tamper-resistant audit masih TODO. Proxy juga tidak boleh merekam body password.

Test memakai schema PostgreSQL terisolasi; tidak membuat/mengubah akun admin nyata.
