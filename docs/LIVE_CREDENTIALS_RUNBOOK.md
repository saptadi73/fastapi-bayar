# Live Credential Runbook

Credential live tidak disimpan di repository, `.env.example`, log, test, atau frontend.
Credential yang pernah dibagikan di chat/tiket dianggap compromised dan wajib di-rotate di
dashboard Midtrans/DOKU sebelum dipakai.

Konfigurasi production memakai secret manager atau `.env` lokal dengan permission terbatas.
`MIDTRANS_SERVER_KEY` hanya boleh berada di backend. Frontend tidak boleh menerima Server Key
atau DOKU Secret Key.

Checklist aktivasi:

1. Revoke/rotate Midtrans Server Key, Client Key, dan DOKU Secret Key yang pernah terekspos.
2. Simpan file DOKU SNAP private/public key di `.secrets/`, bukan Git.
3. Set `ENVIRONMENT=production`, `PUBLIC_BASE_URL=https://api.iwbif.id`, dan gunakan migration gate.
4. Set `MIDTRANS_ENVIRONMENT=PRODUCTION` hanya setelah UAT disetujui.
5. Verifikasi notification URL DOKU persis dengan path endpoint, signature, timestamp, dan merchant binding.
6. Uji transaksi nominal kecil, webhook, inquiry, callback, refund, dan rekonsiliasi.
7. Audit agar secret tidak masuk response, browser, telemetry, atau commit.
