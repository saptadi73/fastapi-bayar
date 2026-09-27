# Operasional worker Payment

## Cakupan

Worker terpisah dari proses FastAPI: pengiriman callback Payment ke Portal Event,
cleanup checkout session expired, dan rekonsiliasi case admin yang sudah diminta.
Worker tidak membuat charge, tidak menjalankan inquiry provider, tidak mengubah payment menjadi EXPIRED, dan tidak menghapus ledger,
idempotency record, callback atau audit webhook. DOKU inquiry kini tersedia melalui
adapter Check Status dan antrean rekonsiliasi.

## Menjalankan

Dari C:\projek\fastapi-bayar, setelah migration `python -m alembic upgrade head`:

```powershell
.\venv\Scripts\python.exe scripts\payment_worker.py --jobs all
```

Pilihan `--jobs callbacks`, `--jobs cleanup`, atau `--jobs reconciliation` menjalankan hanya job tersebut.
Tambahkan `--once` untuk satu batch per job; cocok dijalankan Task Scheduler/cron.
Exit code nonzero menandakan job sekali jalan gagal. Pada mode berulang, error dicatat
tanpa exception message sensitif dan dicoba kembali setelah interval.

Mode callbacks/all melakukan HTTP POST ke URL client terdaftar. Periksa konfigurasi
dan allowlist sebelum mengaktifkan. Implementasi diuji dengan HTTP mock; proses
pengiriman ke client sebenarnya tidak otomatis dinyalakan saat deployment kode ini.

## Konfigurasi .env

| Setting | Default | Makna |
| --- | --- | --- |
| WORKER_CALLBACK_INTERVAL_SECONDS | 5 | Jeda setelah batch callback selesai |
| WORKER_CLEANUP_INTERVAL_SECONDS | 300 | Jeda setelah batch cleanup selesai |
| WORKER_CALLBACK_BATCH_SIZE | 20 | Maksimum event per callback tick |
| WORKER_CLEANUP_BATCH_SIZE | 500 | Maksimum sesi expired dihapus per tick |
| WORKER_RECONCILIATION_INTERVAL_SECONDS | 60 | Jeda antar batch inquiry |
| WORKER_RECONCILIATION_BATCH_SIZE | 10 | Maksimum case inquiry per tick |
| CALLBACK_TIMEOUT_SECONDS | 10 | Timeout HTTPX per fase network |
| CALLBACK_MAX_ATTEMPTS | 7 | Maksimum percobaan tercatat sebelum dead-letter |

Interval bukan jaminan waktu kirim: durasi HTTP, antrean dan gangguan database
mempengaruhi latensi. Callback, cleanup dan reconciliation memiliki loop independen. Tidak ada
overlap tick job yang sama dalam satu proses. Batch dibatasi agar backlog tidak
menjadi transaksi cleanup tak terbatas. Indeks expiry tersedia via migration 0009.

Checkout attempt memiliki unique partial index `uq_attempt_one_active_per_payment`.
Database hanya mengizinkan satu attempt berstatus `INITIATED`, `PENDING`, atau `UNKNOWN`
untuk satu payment. Lock payment di service tetap dipakai untuk menentukan `attempt_no`
dan menjaga urutan, sedangkan index menjadi pagar terakhir terhadap concurrent insert.

## Konsistensi dan retry

PostgreSQL FOR UPDATE OF callback_deliveries SKIP LOCKED membagi pekerjaan antar
worker. Row client/payment tidak ikut dikunci oleh query pengambilan batch.
Worker baru commit per event, sehingga error event berikutnya tidak membatalkan
event sebelumnya. Transaksi tetap terbuka selama satu HTTP delivery; connection
pool dan timeout perlu disesuaikan sebelum scaling.

Network timeout/error dan HTTP non-2xx dijadwalkan ulang dengan jeda internal
60, 300, 900, 3600, 21600, 86400 detik, sampai batas percobaan. Redirect tidak
diikuti. Client nonaktif atau URL di luar allowlist menjadi DEAD_LETTER tanpa HTTP.
Jeda ini kebijakan Payment -> Event, BUKAN jadwal retry Midtrans/DOKU -> Payment.

Semantik at-least-once: bila Event menerima callback lalu worker mati sebelum commit,
callback dapat dikirim lagi. Event wajib deduplikasi event_id dan verifikasi HMAC.
Crash sebelum commit me-rollback state SENDING sehingga record dapat dicoba ulang.
Attempt count hanya mencerminkan percobaan yang berhasil di-commit; bukan pembatas
mutlak network sends ketika ada crash. Tidak ada klaim exactly-once.

Reconciliation mengambil case REQUESTED memakai `FOR UPDATE SKIP LOCKED`, menandainya
RUNNING dan commit sebelum network provider. Setelah inquiry case menjadi COMPLETED
dengan result status, atau FAILED dengan error code terkontrol. UNRESOLVED berarti
inquiry selesai tetapi provider belum menemukan transaksi; bukan PAID atau FAILED.
Midtrans Core memakai adapter dan processor ledger yang sama dengan jalur webhook.
DOKU inquiry diproses oleh worker rekonsiliasi dengan adapter Check Status Non-SNAP;
charge DOKU Indomaret tersedia, sementara channel tambahan dan refund API DOKU tetap
menunggu kontrak product/channel.

Reconciliation provider error bersifat retryable sampai `WORKER_RECONCILIATION_MAX_ATTEMPTS`;
retry memakai exponential backoff berbasis `WORKER_RECONCILIATION_BACKOFF_SECONDS` dan
status `RETRY_WAIT`. Setelah batas tercapai, case menjadi `FAILED`.

Refund `--jobs refunds` mengambil refund `APPROVED` memakai `FOR UPDATE SKIP LOCKED`,
mengubahnya ke `PROCESSING`, lalu mengirim Midtrans Core Refund memakai `refund_no`
sebagai `refund_key`. Respons `refund`/`partial_refund` dicatat sebagai
`PROVIDER_ACCEPTED`, bukan langsung `REFUNDED`. Batch berikutnya melakukan inquiry
Midtrans, mencocokkan `refund_key` dan nominal di riwayat refund, lalu baru menulis
`SUCCEEDED` serta `PARTIALLY_REFUNDED`/`REFUNDED`. Untuk channel aktif DOKU non-card,
worker menandai refund sebagai `MANUAL_REQUIRED` dengan kode
`DOKU_MANUAL_REFUND_REQUIRED`; worker tidak mengirimnya ke adapter Midtrans.
Operator harus mengikuti prosedur DOKU support dan memverifikasi bukti sebelum
finalisasi ledger.

Cleanup menghapus permanen CheckoutSession dengan expires_at <= waktu saat job mulai,
serta AdminSession yang expired/idle dan login-throttle bucket yang sudah melewati
dua window retensi. Sesi aktif tidak dihapus; tidak menonaktifkan payment. Token expired tidak
perlu dipulihkan: minta checkout baru via backend bila payment masih memenuhi syarat.
Job cleanup belum dijalankan terhadap data aplikasi saat implementasi ini.

## Supervisi

Jalankan sebagai proses/service terpisah dengan working directory proyek supaya .env
terbaca. Windows Task Scheduler dapat menjalankan `--once` berulang (pilih tidak
memulai instance baru ketika instance sebelumnya masih berjalan); alternatifnya
supervisor service menjalankan mode berulang dengan restart-on-failure.
Jangan menambahkan worker ke lifespan tiap proses uvicorn.

SIGINT/SIGTERM meminta shutdown setelah batch berjalan selesai, lalu koneksi ditutup.
Penghentian paksa memerlukan retry at-least-once. Latensi shutdown dipengaruhi ukuran
batch dan timeout; HTTPX timeout per fase bukan hard wall-clock deadline.
Belum ada instalasi service OS otomatis, heartbeat terpusat atau alert dead-letter.

Pantau log job/outcome/counts/error_type serta jumlah PENDING/RETRY/DEAD_LETTER di DB.
Health API hanya memeriksa API/database, tidak membuktikan worker aktif.
Jangan log payload, Authorization, secret atau callback URL sensitif.

## Referensi provider yang diperiksa

Pemisahan callback keluar dari request webhook dan deduplikasi sejalan dengan panduan
[Midtrans notification](https://docs.midtrans.com/docs/https-notification-webhooks)
dan [DOKU best practice](https://developers.doku.com/get-started-with-doku-api/notification/best-practice).
Protokol provider tidak diubah pada iterasi ini. Pengujian sandbox merchant dan
implementasi DOKU tetap terpisah dari worker internal ini.
