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

## Client credential encryption backfill

Set `CREDENTIAL_ENCRYPTION_KEY` pada secret manager terlebih dahulu. Generate Fernet key
di environment deployment, bukan di repository. Audit jumlah legacy row tanpa perubahan:

Rotasi key: isi key baru pada `CREDENTIAL_ENCRYPTION_KEY` dan pindahkan key lama ke
`CREDENTIAL_ENCRYPTION_KEY_PREVIOUS`. Restart deployment secara rolling, jalankan backfill,
lalu hapus `CREDENTIAL_ENCRYPTION_KEY_PREVIOUS` setelah seluruh ciphertext selesai ditulis
dengan key baru. Selama masa transisi backend dapat mendekripsi kedua key, tetapi selalu
mengenkripsi credential baru dengan key aktif.

```powershell
.\venv\Scripts\python.exe scripts\encrypt_callback_secrets.py --dry-run
```

Setelah backup dan approval operator, jalankan tanpa `--dry-run`. Script mengenkripsi
plaintext legacy dan me-re-encrypt ciphertext yang masih hanya dapat dibuka dengan key
sebelumnya. Pastikan output `credentials_to_rewrite` sesuai ekspektasi sebelum commit.
Jangan mencetak key, secret, atau payload ke log.
