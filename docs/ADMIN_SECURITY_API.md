# Admin Security API

Login admin memakai counter PostgreSQL bersama dengan key gabungan IP dan identifier
account. Audit mencatat `LOGIN_FAILED`, `LOGIN_RATE_LIMITED`, `LOGIN_MFA_REQUIRED`,
`LOGIN_MFA_FAILED`, dan `LOGIN_SUCCEEDED` tanpa password, OTP, atau identifier mentah.

MFA TOTP tersedia melalui `POST /api/v1/admin/auth/mfa/enroll` dan
`POST /api/v1/admin/auth/mfa/confirm` dengan `{ "code": "123456" }`. Login berikutnya
mengirim field `otp`; recovery code hanya dapat digunakan sekali dan disimpan sebagai
digest. `POST /api/v1/admin/auth/reauthenticate` menandai session ter-auth ulang lima
menit. `CREDENTIAL_ENCRYPTION_KEY` wajib tersedia untuk enrollment.

Password reset admin memakai `POST /admin/users/{user_id}/password-reset` dan
`POST /admin/auth/password-reset/confirm`. Invitation memakai
`POST /admin/users/invite` lalu `POST /admin/auth/invitations/accept`; token hanya
ditampilkan sekali oleh API dan harus dikirim melalui saluran aman.
Forced password-change enforcement, role editor configurable, dan per-client admin
assignment sudah aktif; lihat [ADMIN_ROLE_ASSIGNMENT_API.md](ADMIN_ROLE_ASSIGNMENT_API.md).
