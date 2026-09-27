# Admin Merchant, Routing, Channel, dan Feature Flag API

Konfigurasi ini tenant-scoped berdasarkan `client_id` dan tidak menerima secret
gateway mentah. `credential_ref` hanya referensi ke secret manager/deployment secret.
Permission baca adalah `admin.routing.read`, sedangkan mutasi memakai
`admin.routing.manage` (SUPER_ADMIN dan INTEGRATION_ADMIN).

Endpoint aktif:

- `GET/POST /admin/clients/{client_id}/organizers`
- `PATCH /admin/clients/{client_id}/organizers/{organizer_id}`
- `GET/POST /admin/clients/{client_id}/merchant-accounts`
- `PATCH /admin/clients/{client_id}/merchant-accounts/{account_id}`
- `GET/POST /admin/clients/{client_id}/payment-channels`
- `PATCH /admin/clients/{client_id}/payment-channels/{channel_id}`
- `GET/POST /admin/clients/{client_id}/routing-rules`
- `PATCH /admin/clients/{client_id}/routing-rules/{rule_id}`
- `GET /admin/clients/{client_id}/feature-flags`
- `PUT /admin/clients/{client_id}/feature-flags`

Semua mutasi membutuhkan `reason`, audit operator, dan optimistic `expected_version`
untuk update. Channel memiliki `active`, currency, serta batas nominal; rule memiliki
scope optional service/event, priority, channel, dan merchant account.

Runtime checkout sekarang memakai konfigurasi aktif bila client memiliki channel:
merchant harus aktif, channel harus aktif, currency dan batas nominal harus cocok,
serta routing rule yang matching harus tersedia bila rule aktif dikonfigurasi.
Attempt dengan channel di luar hasil eligibility ditolak `422 UNSUPPORTED_CHANNEL`.
Client tanpa channel terkonfigurasi masih memakai fallback legacy Midtrans.
Validasi merchant binding, credential secret manager, kontrak DOKU/Midtrans, dan UAT
tetap wajib sebelum channel diaktifkan untuk traffic produksi.
