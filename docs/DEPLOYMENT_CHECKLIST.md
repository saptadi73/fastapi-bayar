# Deployment Checklist

Gunakan checklist ini sebelum Payment Portal menerima traffic nyata.

## 1. Configuration

- Salin `.env.example` ke secret storage deployment; jangan commit `.env`.
- Set `ENVIRONMENT=production`, `APP_DEBUG=false`, `DB_ECHO=false`, dan `AUTO_CREATE_TABLES=false`.
- Set `MIGRATION_GATE_ENABLED=true` dan pastikan `MIGRATION_HEAD` sesuai release.
- Gunakan `PUBLIC_BASE_URL` HTTPS.
- Isi `JWT_SECRET` acak minimal 48 karakter dan `CLIENT_API_SECRET` baru.
- Simpan DOKU private/public key di secret volume dengan permission terbatas.
- Pastikan credential Midtrans/DOKU sudah dirotasi jika pernah terekspos.

## 2. Database gate

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\alembic.exe check
.\venv\Scripts\python.exe -c "from app.core.config import get_settings; get_settings().validate_production(); print('config-ok')"
```

Aplikasi production menolak startup bila `alembic_version` tidak sama dengan
`MIGRATION_HEAD`.

## 3. API dan worker

Jalankan API sebagai service terpisah dari worker:

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
.\venv\Scripts\python.exe scripts/payment_worker.py --jobs all
```

Untuk Task Scheduler, gunakan `--once` pada jadwal berkala dan arahkan stdout/stderr
ke log yang tidak merekam body request, token, password, atau credential provider.
Jangan menjalankan scheduler di setiap worker process Uvicorn.

## 4. Smoke test

- `GET /health` mengembalikan status `ok`.
- `GET /health/database` mengembalikan database `connected`.
- `GET /health/ready` mengembalikan status `ready`.
- Cek response header `X-Request-ID` dan structured log JSON.
- Jalankan satu payment sandbox, webhook, callback, inquiry, dan refund sesuai provider.

## 5. Go-live approval

- Sandbox UAT Midtrans/DOKU disetujui untuk channel yang aktif.
- Notification URL, return URL, callback URL, merchant binding, dan firewall/egress diverifikasi.
- Backup/restore PostgreSQL diuji.
- Alert dead-letter, worker berhenti, database unavailable, dan provider timeout diuji.
- Live credential disetujui operator dan tidak pernah dicetak ke log/frontend.
