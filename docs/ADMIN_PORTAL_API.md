# Admin Portal Administration API

Endpoint ini mengelola master pembayar (`PortalUser`) per client. Akses dibatasi
tenant melalui `client_id` dan permission `admin.portal_users.manage` (saat ini
role `SUPER_ADMIN`). Semua request mutasi admin memerlukan session admin dan CSRF.

## Create

`POST /api/v1/admin/clients/{client_id}/portal-users`

```json
{"email":"payer@example.com","name":"Peserta","reason":"Koreksi data registrasi"}
```

Email dinormalisasi lowercase dan immutable. Duplicate email pada client yang sama
menghasilkan `409 PORTAL_USER_EXISTS`.

## Update

`PATCH /api/v1/admin/clients/{client_id}/portal-users/{user_id}`

```json
{"name":"Peserta Baru","expected_version":1,"reason":"Perubahan nama"}
```

Email tidak disediakan sebagai field update. Version mismatch menghasilkan `409
PORTAL_USER_VERSION_CONFLICT`; gunakan response terbaru sebelum retry.

## Delete

`DELETE /api/v1/admin/clients/{client_id}/portal-users/{user_id}` dengan body:

```json
{"reason":"Penghapusan data duplikat"}
```

Penghapusan ditolak dengan `409 PORTAL_USER_DELETE_CONFLICT` jika user masih
direferensikan payment transaction. Ini menjaga integritas identity order historis.

## Audit dan frontend

Audit mutasi menyimpan actor, action, reason, versi before/after, hash email
terpotong, dan status nama. Email/nama mentah tidak disalin ke detail audit.
Frontend dapat memakai `version` untuk optimistic locking dan harus menampilkan
`request_id` ketika menerima error. Kontrak TypeScript tersedia pada
`vue-bayar/src/api/admin.ts` melalui `clientsApi.createPortalUser`,
`updatePortalUser`, dan `deletePortalUser`.
