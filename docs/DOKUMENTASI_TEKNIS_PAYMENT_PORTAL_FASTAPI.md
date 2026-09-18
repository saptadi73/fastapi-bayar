# Dokumentasi Teknis Backend Payment Portal

## FastAPI + PostgreSQL — DOKU Direct API dan Midtrans Snap

**Versi dokumen:** 1.0  
**Tanggal:** 18 September 2026  
**Target pembaca:** Backend developer, frontend developer, DevOps, QA, system analyst, dan auditor operasional  
**Status:** Acuan implementasi awal

---

## 1. Tujuan Sistem

Payment Portal adalah layanan pembayaran terpusat yang dapat digunakan oleh banyak Portal Layanan, client, organizer, event, dan jenis layanan.

Contoh Portal Layanan:

- Portal IWBIF/IWAPI;
- portal membership;
- portal donasi, infaq, dan zakat;
- ERP Nilam;
- ERP MBG;
- portal invoice;
- portal ticketing atau e-commerce lain.

Payment Portal tidak menghitung harga bisnis. Portal Layanan tetap menjadi sumber kebenaran untuk harga tiket, donasi, tagihan, diskon, pajak, dan total akhir. Payment Portal menerima nilai final yang sudah ditandatangani, mengelola proses pembayaran, menerima webhook, mencatat ledger, melakukan callback, rekonsiliasi, dan menyediakan laporan.

Integrasi awal:

1. **DOKU Direct API** — Payment Portal menampilkan pilihan metode pembayaran sendiri, misalnya BSI VA, BJB VA, BTN VA, Alfamart, dan Indomaret.
2. **Midtrans Snap** — Payment Portal meminta Snap token dan membuka checkout Midtrans.

> Aktivasi dan ketersediaan setiap payment method tetap mengikuti kontrak dan konfigurasi merchant pada DOKU/Midtrans. Jangan menganggap sebuah channel aktif hanya karena tersedia dalam dokumentasi provider.

---

## 2. Prinsip dan Batas Tanggung Jawab

### 2.1 Portal Layanan

Portal Layanan bertanggung jawab atas:

- business order, registrasi, invoice, atau donasi;
- `reference_id` yang unik dalam ruang lingkup client;
- nominal final `amount`;
- deskripsi transaksi;
- identitas customer;
- perubahan status bisnis setelah callback terverifikasi;
- pembatalan bisnis dan kebijakan refund.

### 2.2 Payment Portal

Payment Portal bertanggung jawab atas:

- autentikasi Portal Layanan;
- verifikasi HMAC dan pencegahan replay;
- idempotency;
- pembuatan `payment_id`;
- pemilihan merchant account dan gateway;
- pembuatan `gateway_order_id` untuk setiap attempt;
- integrasi DOKU Direct API dan Midtrans Snap;
- normalisasi status provider;
- penyimpanan payment ledger;
- verifikasi serta pemrosesan webhook;
- callback bertanda tangan ke Portal Layanan;
- retry callback;
- reconciliation dan settlement tracking;
- report lintas client, event/service, gateway, dan payment method.

### 2.3 Payment Gateway

Provider bertanggung jawab memproses pembayaran, menyediakan instruksi/token, mengirim notifikasi perubahan status, dan menyediakan data settlement sesuai produk merchant.

### 2.4 Identitas Transaksi

| Identitas | Pembuat | Contoh | Fungsi |
|---|---|---|---|
| `reference_id` | Portal Layanan | `REG-2026-00123` | Identitas order/registrasi/invoice bisnis |
| `payment_id` | Payment Portal | UUID + `PAY-20260918-000001` | Identitas pembayaran internal |
| `attempt_id` | Payment Portal | UUID | Identitas satu percobaan pembayaran |
| `gateway_order_id` | Payment Portal | `PAY-20260918-000001-MT-01` | Order unik yang dikirim ke gateway |
| `gateway_reference` | Gateway | token/reference provider | Referensi yang dikembalikan provider |

Satu `payment_id` dapat memiliki beberapa `payment_attempts`, tetapi hanya satu attempt yang boleh menjadi pembayaran sukses yang diakui.

---

## 3. Arsitektur Tingkat Tinggi

```mermaid
flowchart TB
    A[Portal Layanan] -->|Signed REST API| B[Payment Portal FastAPI]
    B --> C[PostgreSQL Ledger]
    B --> D[Redis: nonce, lock, queue]
    B --> E[DOKU Direct API]
    B --> F[Midtrans Snap]
    E -->|Webhook| B
    F -->|Webhook| B
    B -->|Signed callback| A
```

Komponen yang disarankan:

- FastAPI sebagai API dan orchestration layer;
- PostgreSQL sebagai system of record;
- SQLAlchemy 2 async + Alembic;
- Redis untuk distributed lock, nonce/replay protection, rate limit, dan queue;
- Celery, Dramatiq, ARQ, atau worker berbasis queue untuk callback/reconciliation;
- HTTPX async untuk koneksi provider dan callback;
- Nginx sebagai reverse proxy dan TLS termination;
- object storage opsional untuk export report;
- Sentry/OpenTelemetry/Prometheus untuk observability.

### 3.1 Aliran Data Normal

```mermaid
sequenceDiagram
    participant L as Portal Layanan
    participant P as Payment Portal
    participant G as DOKU/Midtrans
    participant C as Customer

    L->>P: initiate(reference, amount, signature)
    P->>P: verify + idempotency + create payment
    P-->>L: payment_id + payment_url
    C->>P: buka halaman pembayaran
    C->>P: pilih DOKU method / Midtrans
    P->>G: create gateway transaction
    G-->>P: VA/code atau Snap token
    P-->>C: instruksi pembayaran/checkout
    G->>P: signed webhook
    P->>P: lock, verify, update ledger
    P-->>G: HTTP 2xx
    P->>L: signed callback
    L-->>P: HTTP 2xx
```

---

## 4. Stack dan Dependensi

Contoh `requirements.txt` atau padanannya:

```text
fastapi
uvicorn[standard]
gunicorn
sqlalchemy[asyncio]
asyncpg
alembic
pydantic
pydantic-settings
httpx
cryptography
python-jose[cryptography]
redis
arq
orjson
structlog
prometheus-client
sentry-sdk[fastapi]
tenacity
pytest
pytest-asyncio
pytest-cov
respx
freezegun
```

Gunakan versi yang dipin dan diuji pada lock file. Jangan menyimpan credential dalam repository.

---

## 5. Struktur Project FastAPI

```text
payment-portal/
├── alembic/
│   └── versions/
├── app/
│   ├── api/
│   │   ├── dependencies.py
│   │   └── v1/
│   │       ├── client_payments.py
│   │       ├── public_checkout.py
│   │       ├── webhooks_doku.py
│   │       ├── webhooks_midtrans.py
│   │       ├── admin_clients.py
│   │       ├── admin_merchants.py
│   │       ├── admin_reports.py
│   │       └── admin_settlements.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── redis.py
│   │   ├── security.py
│   │   ├── logging.py
│   │   └── exceptions.py
│   ├── models/
│   ├── schemas/
│   ├── repositories/
│   ├── services/
│   │   ├── payment_service.py
│   │   ├── attempt_service.py
│   │   ├── webhook_service.py
│   │   ├── callback_service.py
│   │   ├── reconciliation_service.py
│   │   ├── settlement_service.py
│   │   └── report_service.py
│   ├── gateways/
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── doku/
│   │   │   ├── client.py
│   │   │   ├── signer.py
│   │   │   ├── mapper.py
│   │   │   └── schemas.py
│   │   └── midtrans/
│   │       ├── client.py
│   │       ├── verifier.py
│   │       ├── mapper.py
│   │       └── schemas.py
│   ├── workers/
│   │   ├── callback_tasks.py
│   │   ├── reconciliation_tasks.py
│   │   └── expiry_tasks.py
│   ├── main.py
│   └── lifespan.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── fixtures/
├── scripts/
├── .env.example
├── alembic.ini
├── pyproject.toml
└── README.md
```

Jangan menaruh logika provider langsung di router. Router hanya memvalidasi input dan memanggil service. Adapter gateway mengisolasi perbedaan DOKU dan Midtrans.

---

## 6. Model Data PostgreSQL

Gunakan UUID sebagai primary key internal dan kode manusia sebagai alternate key. Semua timestamp disimpan sebagai `timestamptz` dalam UTC. Semua nominal IDR disimpan sebagai `bigint`; untuk multi-currency gunakan `numeric(20,4)` dan aturan minor unit per currency.

### 6.1 Hierarki Bisnis

```mermaid
erDiagram
    CLIENTS ||--o{ ORGANIZERS : owns
    CLIENTS ||--o{ SERVICES : owns
    ORGANIZERS ||--o{ SERVICES : organizes
    SERVICES ||--o{ PAYMENT_TRANSACTIONS : classifies
    PAYMENT_TRANSACTIONS ||--o{ PAYMENT_ATTEMPTS : has
    PAYMENT_ATTEMPTS ||--o{ PAYMENT_WEBHOOKS : receives
    PAYMENT_TRANSACTIONS ||--o{ CALLBACK_DELIVERIES : notifies
    PAYMENT_TRANSACTIONS ||--o| SETTLEMENT_DETAILS : included
    SETTLEMENTS ||--o{ SETTLEMENT_DETAILS : contains
```

### 6.2 Tabel Inti

#### `clients`

- `id uuid PK`
- `code varchar(50) UNIQUE NOT NULL`
- `name varchar(200) NOT NULL`
- `status enum(active,inactive,suspended)`
- `default_callback_url text`
- `timezone varchar(50) default 'Asia/Jakarta'`
- `created_at`, `updated_at`

#### `client_credentials`

- `id uuid PK`
- `client_id uuid FK`
- `key_id varchar(100) UNIQUE`
- `api_key_hash text`
- `secret_ciphertext text`
- `secret_version integer`
- `valid_from`, `valid_until`
- `status`
- `last_used_at`

Secret harus terenkripsi at rest atau berasal dari secret manager. API key disimpan dalam bentuk hash bila lookup strategy memungkinkan. Dukung dua credential aktif selama rotasi.

#### `organizers`

- `id uuid PK`
- `client_id uuid FK`
- `code varchar(50)`
- `name varchar(200)`
- `status`
- unique `(client_id, code)`

#### `services`

- `id uuid PK`
- `client_id uuid FK`
- `organizer_id uuid FK nullable`
- `service_type varchar(50)` — `EVENT`, `MEMBERSHIP`, `DONATION`, `ZAKAT`, `INFAQ`, `INVOICE`, `PRODUCT`, `OTHER`
- `code varchar(100)` — contoh `IWBIF2026`
- `name varchar(250)`
- `status`
- `metadata jsonb`
- unique `(client_id, code)`

#### `merchant_accounts`

- `id uuid PK`
- `client_id uuid FK nullable` — null jika account platform bersama diperbolehkan kontrak
- `gateway enum(DOKU,MIDTRANS)`
- `code varchar(100) UNIQUE`
- `environment enum(SANDBOX,PRODUCTION)`
- `display_name varchar(200)`
- `credential_ciphertext jsonb`
- `config jsonb`
- `status`
- `created_at`, `updated_at`

`config` dapat menyimpan non-secret seperti base URL, expiry default, Snap mode, atau notification URL. Jangan menyimpan raw secret di log atau response admin.

#### `merchant_routing_rules`

- `id uuid PK`
- `client_id`, `organizer_id`, `service_id` nullable
- `gateway`
- `merchant_account_id`
- `priority integer`
- `conditions jsonb`
- `valid_from`, `valid_until`
- `status`

Resolusi rule paling spesifik: service → organizer → client → platform default.

#### `payment_channels`

- `id uuid PK`
- `merchant_account_id uuid FK`
- `gateway`
- `channel_code` — `DOKU_BSI_VA`, `DOKU_BJB_VA`, `DOKU_BTN_VA`, `DOKU_ALFAMART`, `DOKU_INDOMARET`, `MIDTRANS_SNAP`
- `provider_code`
- `display_name`
- `category` — `VIRTUAL_ACCOUNT`, `CONVENIENCE_STORE`, `HOSTED_CHECKOUT`
- `min_amount`, `max_amount`
- `display_order`
- `logo_url`
- `config jsonb`
- `enabled boolean`
- unique `(merchant_account_id, channel_code)`

Limit dari master tetap harus divalidasi terhadap respons/aturan provider. Admin harus dapat menonaktifkan channel tanpa deployment.

#### `payment_transactions`

- `id uuid PK`
- `payment_no varchar(40) UNIQUE NOT NULL`
- `client_id uuid FK NOT NULL`
- `organizer_id uuid FK nullable`
- `service_id uuid FK NOT NULL`
- `external_reference varchar(150) NOT NULL`
- `description varchar(500)`
- `amount bigint NOT NULL CHECK (amount > 0)`
- `currency char(3) default 'IDR'`
- `status enum(CREATED,PENDING,PAID,EXPIRED,CANCELLED,FAILED,REFUND_PENDING,PARTIALLY_REFUNDED,REFUNDED)`
- `customer_name`, `customer_email`, `customer_phone`
- `return_url text`
- `callback_url_snapshot text`
- `expires_at timestamptz`
- `paid_at`, `cancelled_at`, `refunded_at`
- `winning_attempt_id uuid nullable`
- `metadata jsonb`
- `version integer default 1`
- `created_at`, `updated_at`
- unique `(client_id, external_reference)`

Jika Portal Layanan membutuhkan beberapa pembayaran sah untuk satu order, tambahkan `reference_sequence` atau ubah unique key secara eksplisit. Jangan menghapus constraint tanpa model bisnis yang jelas.

#### `payment_attempts`

- `id uuid PK`
- `payment_id uuid FK NOT NULL`
- `attempt_no integer NOT NULL`
- `gateway`
- `merchant_account_id uuid FK`
- `payment_channel_id uuid FK nullable`
- `gateway_order_id varchar(100) UNIQUE NOT NULL`
- `gateway_reference varchar(255)`
- `status enum(INITIATED,PENDING,PAID,DENIED,CANCELLED,EXPIRED,FAILED,REFUND_PENDING,PARTIALLY_REFUNDED,REFUNDED)`
- `amount bigint NOT NULL`
- `currency`
- `payment_url text nullable`
- `va_number text nullable`
- `payment_code text nullable`
- `token_ciphertext text nullable`
- `provider_status varchar(100)`
- `provider_created_at`, `provider_paid_at`, `expires_at`
- `request_payload_redacted jsonb`
- `response_payload_redacted jsonb`
- `failure_code`, `failure_message`
- `created_at`, `updated_at`
- unique `(payment_id, attempt_no)`

Jangan menyimpan data kartu. Token rahasia/berumur pendek dienkripsi atau tidak disimpan jika tidak dibutuhkan.

#### `payment_status_history`

- `id bigserial PK`
- `payment_id`, `attempt_id nullable`
- `from_status`, `to_status`
- `source enum(API,DOKU_WEBHOOK,MIDTRANS_WEBHOOK,RECONCILIATION,ADMIN,SYSTEM)`
- `reason`
- `event_id uuid nullable`
- `actor_id nullable`
- `occurred_at`

#### `payment_webhooks`

- `id uuid PK`
- `gateway`
- `merchant_account_id nullable`
- `provider_event_id nullable`
- `gateway_order_id nullable`
- `headers_redacted jsonb`
- `payload jsonb`
- `payload_hash char(64)`
- `signature_valid boolean`
- `processing_status enum(RECEIVED,PROCESSED,IGNORED,FAILED,QUARANTINED)`
- `error_message`
- `received_at`, `processed_at`
- unique `(gateway, provider_event_id)` jika provider menjamin event ID
- fallback unique `(gateway, payload_hash)` sesuai kebutuhan

Raw payload penting untuk audit, tetapi PII/secrets wajib direduksi atau dienkripsi dan memiliki retention policy.

#### `idempotency_records`

- `id uuid PK`
- `client_id uuid FK`
- `idempotency_key varchar(150)`
- `request_hash char(64)`
- `resource_type`, `resource_id`
- `http_status integer`
- `response_body jsonb`
- `expires_at`, `created_at`
- unique `(client_id, idempotency_key)`

#### `callback_deliveries`

- `id uuid PK`
- `payment_id uuid FK`
- `event_type`
- `callback_url`
- `payload jsonb`
- `signature_key_version integer`
- `attempt_no integer`
- `status enum(PENDING,SENDING,SUCCEEDED,RETRY,DEAD_LETTER)`
- `http_status`, `response_excerpt`
- `next_retry_at`, `sent_at`, `created_at`
- unique `(payment_id, event_type, attempt_no)`

#### `refunds`

- `id uuid PK`
- `refund_no UNIQUE`
- `payment_id`, `attempt_id`
- `client_refund_reference`
- `amount bigint`
- `reason`
- `status enum(REQUESTED,PROCESSING,SUCCEEDED,FAILED,CANCELLED)`
- `gateway_refund_id`
- `requested_by`, `approved_by`
- `provider_payload_redacted jsonb`
- `created_at`, `processed_at`

#### `settlements` dan `settlement_details`

`settlements`:

- `id uuid PK`, `settlement_no UNIQUE`
- `client_id`, `organizer_id nullable`, `service_id nullable`
- `merchant_account_id`
- `period_start`, `period_end`
- `gross_amount`, `gateway_fee`, `platform_fee`, `tax_amount`, `adjustment_amount`, `net_amount`
- `currency`
- `status enum(DRAFT,VERIFIED,APPROVED,PAID,CANCELLED)`
- `bank_reference`, `paid_at`
- `created_by`, `approved_by`, `created_at`, `updated_at`

`settlement_details`:

- `id uuid PK`
- `settlement_id uuid FK`
- `payment_id uuid FK`
- `attempt_id uuid FK`
- `gross_amount`, `gateway_fee`, `platform_fee`, `tax_amount`, `adjustment_amount`, `net_amount`
- unique `(settlement_id, payment_id)`
- partial unique pada `payment_id` untuk mencegah settlement ganda, bila satu payment tidak boleh dipecah

### 6.3 Index Penting

```sql
CREATE INDEX ix_payment_client_paid_at
ON payment_transactions (client_id, paid_at DESC)
WHERE status IN ('PAID','PARTIALLY_REFUNDED','REFUNDED');

CREATE INDEX ix_payment_service_paid_at
ON payment_transactions (service_id, paid_at DESC);

CREATE INDEX ix_attempt_gateway_order
ON payment_attempts (gateway, gateway_order_id);

CREATE INDEX ix_webhook_unprocessed
ON payment_webhooks (received_at)
WHERE processing_status IN ('RECEIVED','FAILED');

CREATE INDEX ix_callback_due
ON callback_deliveries (next_retry_at)
WHERE status IN ('PENDING','RETRY');
```

Pertimbangkan table partitioning bulanan hanya setelah volume dan query plan membuktikan kebutuhan.

---

## 7. State Machine

### 7.1 Payment Transaction

```mermaid
stateDiagram-v2
    [*] --> CREATED
    CREATED --> PENDING: attempt dibuat
    PENDING --> PAID: webhook/reconciliation valid
    CREATED --> CANCELLED
    PENDING --> CANCELLED
    PENDING --> EXPIRED
    PENDING --> FAILED
    PAID --> REFUND_PENDING
    REFUND_PENDING --> PARTIALLY_REFUNDED
    REFUND_PENDING --> REFUNDED
    PARTIALLY_REFUNDED --> REFUND_PENDING
    PARTIALLY_REFUNDED --> REFUNDED
```

Aturan:

- status tidak boleh mundur karena webhook terlambat;
- `PAID` bersifat terminal untuk proses penerimaan, kecuali alur refund;
- webhook `PENDING` setelah `PAID` dicatat sebagai ignored, bukan menurunkan status;
- bila attempt lain melaporkan `PAID` setelah payment memiliki winning attempt, tandai sebagai kasus duplicate payment dan kirim alert untuk penanganan/refund;
- perubahan status selalu ditulis ke history dalam transaksi database yang sama.

### 7.2 Mapping Provider

Buat mapper eksplisit, bukan menyebarkan string status provider ke seluruh aplikasi.

Contoh konseptual Midtrans:

| Provider status | Fraud status | Internal attempt |
|---|---|---|
| `capture` | `accept` | `PAID` |
| `settlement` | apa pun yang valid | `PAID` |
| `pending` | — | `PENDING` |
| `deny` | — | `DENIED` |
| `cancel` | — | `CANCELLED` |
| `expire` | — | `EXPIRED` |
| `refund` | — | `REFUNDED` |
| `partial_refund` | — | `PARTIALLY_REFUNDED` |

Mapping DOKU harus disusun per produk/endpoint yang benar-benar diaktifkan dan diuji di sandbox. Simpan status mentah di `provider_status`, tetapi keputusan bisnis memakai enum internal.

---

## 8. Kontrak API Portal Layanan → Payment Portal

Base path: `/api/v1`

### 8.1 Header Autentikasi

```http
X-Client-ID: IWAPI
X-Key-ID: key-2026-01
X-Timestamp: 2026-09-18T07:30:00Z
X-Nonce: 725e351a-61d4-4d0f-908b-15d4ca770ed7
X-Signature: <base64-hmac-sha256>
Idempotency-Key: 165e9b5a-5569-4544-9a50-aa749995e187
Content-Type: application/json
```

Canonical string yang disarankan:

```text
HTTP_METHOD + "\n" +
PATH_WITH_QUERY + "\n" +
X_CLIENT_ID + "\n" +
X_KEY_ID + "\n" +
X_TIMESTAMP + "\n" +
X_NONCE + "\n" +
LOWERCASE_HEX_SHA256(RAW_REQUEST_BODY)
```

Signature:

```python
base64(hmac_sha256(api_secret, canonical_string_utf8))
```

Ketentuan:

- verifikasi signature dengan constant-time comparison;
- toleransi waktu maksimal ±5 menit;
- nonce hanya boleh dipakai sekali selama minimal 10 menit;
- signature dihitung dari raw body bytes, bukan JSON hasil parsing;
- reverse proxy tidak boleh mengubah path yang digunakan signer;
- gunakan HTTPS saja;
- IP allowlist bersifat pertahanan tambahan, bukan pengganti HMAC.

### 8.2 Initiate Payment

`POST /api/v1/client/payments`

Request:

```json
{
  "service_code": "IWBIF2026",
  "organizer_code": "IWAPI-PUSAT",
  "reference_id": "REG-2026-00123",
  "description": "IWBIF 2026 Registration",
  "amount": 2500000,
  "currency": "IDR",
  "customer": {
    "name": "Saptadi Nurfarid",
    "email": "customer@example.com",
    "phone": "+6281234567890"
  },
  "expires_at": "2026-09-19T07:30:00Z",
  "return_url": "https://iwbif.id/payment/result",
  "metadata": {
    "ticket_type": "DELEGATE"
  }
}
```

Response `201`:

```json
{
  "payment_id": "42a261dc-c09a-44a4-a78f-b89a1f37a295",
  "payment_no": "PAY-20260918-000001",
  "reference_id": "REG-2026-00123",
  "amount": 2500000,
  "currency": "IDR",
  "status": "CREATED",
  "expires_at": "2026-09-19T07:30:00Z",
  "payment_url": "https://pay.example.id/p/PAY-20260918-000001"
}
```

Idempotency behavior:

- key baru + request baru → buat dan simpan response;
- key sama + hash request sama → kembalikan response lama;
- key sama + hash berbeda → `409 IDEMPOTENCY_CONFLICT`;
- `reference_id` sama dengan idempotency key berbeda → kembalikan existing resource atau `409`, pilih satu kebijakan dan konsisten. Rekomendasi: `409 DUPLICATE_REFERENCE` beserta `payment_id` existing.

### 8.3 Get Payment

`GET /api/v1/client/payments/{payment_id}`

Hanya client pemilik yang boleh membaca.

### 8.4 Cancel Payment

`POST /api/v1/client/payments/{payment_id}/cancel`

- hanya `CREATED` atau `PENDING`;
- tidak menjamin pembatalan jika customer sudah membayar tetapi webhook belum datang;
- query provider bila perlu sebelum finalisasi;
- selalu idempotent.

### 8.5 Refund Request

`POST /api/v1/client/payments/{payment_id}/refunds`

Refund harus memiliki policy, role approval, audit trail, dan kemampuan provider/channel. Jangan menyamakan cancel dengan refund.

### 8.6 Error Envelope

```json
{
  "error": {
    "code": "DUPLICATE_REFERENCE",
    "message": "Reference telah memiliki payment",
    "request_id": "req_01J...",
    "details": {
      "payment_id": "42a261dc-c09a-44a4-a78f-b89a1f37a295"
    }
  }
}
```

Jangan mengembalikan stack trace, credential, raw provider response, atau SQL error.

---

## 9. Public Checkout API

Public checkout diakses customer melalui opaque `payment_no` atau signed short-lived token. Jangan mengekspos endpoint admin/client credential ke browser.

Endpoint:

- `GET /api/v1/public/payments/{payment_no}` — ringkasan aman;
- `GET /api/v1/public/payments/{payment_no}/channels` — channel eligible;
- `POST /api/v1/public/payments/{payment_no}/attempts` — pilih channel;
- `GET /api/v1/public/payments/{payment_no}/status` — polling terbatas;
- `GET /api/v1/public/attempts/{attempt_id}/instructions` — VA/code/instruksi aman.

Create attempt:

```json
{
  "channel_code": "DOKU_BSI_VA"
}
```

Response DOKU VA ter-normalisasi:

```json
{
  "attempt_id": "1f2f2c0a-25e8-4b51-a76d-849b7fb23082",
  "gateway": "DOKU",
  "channel_code": "DOKU_BSI_VA",
  "status": "PENDING",
  "amount": 2500000,
  "va_number": "90012345678901",
  "expires_at": "2026-09-19T07:30:00Z",
  "instructions": []
}
```

Response Midtrans:

```json
{
  "attempt_id": "7c5fd87c-b043-462a-b18f-1df1694a39fb",
  "gateway": "MIDTRANS",
  "channel_code": "MIDTRANS_SNAP",
  "status": "PENDING",
  "snap_token": "<short-lived-token>",
  "redirect_url": "https://..."
}
```

Rate limit create attempt. Sebelum membuat attempt baru, cek payment belum terminal dan gunakan row/advisory lock agar double-click tidak menciptakan dua attempt paralel.

---

## 10. Gateway Abstraction

Interface konseptual:

```python
from typing import Protocol

class PaymentGateway(Protocol):
    async def create_payment(self, command: CreateGatewayPayment) -> GatewayPaymentResult: ...
    async def get_status(self, gateway_order_id: str) -> GatewayStatusResult: ...
    async def cancel(self, gateway_order_id: str) -> GatewayActionResult: ...
    async def refund(self, command: RefundCommand) -> GatewayActionResult: ...
    async def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> VerifiedWebhook: ...
    def map_status(self, provider_status: str, payload: dict) -> AttemptStatus: ...
```

Adapter tidak boleh melakukan perubahan database. Service orchestration memanggil adapter lalu mengelola transaksi database.

### 10.1 Pola Outbound Call

1. lock payment;
2. reserve `attempt_no` dan buat attempt `INITIATED`;
3. commit reservation;
4. panggil provider dengan timeout;
5. update attempt berdasarkan response;
6. bila timeout/unknown, jangan langsung retry create memakai order ID baru;
7. query status dengan `gateway_order_id` yang sama lebih dulu;
8. semua request/response dicatat dalam bentuk redacted.

Ini mencegah transaksi ganda saat provider berhasil tetapi response ke Payment Portal terputus.

---

## 11. DOKU Direct API

### 11.1 Desain

Payment Portal mengelola tampilan channel. Setelah customer memilih channel, backend memilih endpoint/produk DOKU yang sesuai, membuat `gateway_order_id`, menandatangani request sesuai spesifikasi DOKU yang aktif, lalu mengembalikan hasil ter-normalisasi.

Contoh channel awal:

- BSI Virtual Account;
- BJB Virtual Account;
- BTN Virtual Account;
- Alfa Group/Alfamart;
- Indomaret.

Jangan membuat nomor VA/payment code sendiri kecuali kontrak/produk DOKU secara eksplisit mengizinkannya. Umumnya nomor/instruksi diambil dari response DOKU.

### 11.2 Signature

DOKU Direct API menggunakan header dan canonical signature yang ditentukan dokumentasi DOKU, yang dapat mencakup Client-Id, Request-Id, Request-Timestamp, Request-Target, digest body, dan HMAC. Implementasikan dalam `doku/signer.py`, buat unit test menggunakan contoh resmi, dan jangan menggeneralisasi signature internal Portal Layanan sebagai signature DOKU.

Aturan implementasi:

- `Request-Id` unik per request;
- timestamp UTC sesuai format provider;
- digest dibuat dari raw/minified body persis yang dikirim;
- `Request-Target` harus sama dengan path aktual;
- canonical component order harus persis;
- secret tidak pernah dicetak;
- gunakan environment base URL yang benar;
- sinkronkan waktu server dengan NTP.

### 11.3 Mapper per Product

Buat handler per keluarga produk jika payload/response berbeda:

```text
DokuGateway
├── DokuVirtualAccountHandler
├── DokuConvenienceStoreHandler
└── DokuWebhookVerifier
```

Mapping channel disimpan sebagai konfigurasi dan divalidasi terhadap daftar allowlist di kode. Jangan menerima `provider_code` bebas dari browser.

### 11.4 Respons yang Disimpan

- gateway order/invoice number;
- provider reference;
- VA number atau payment code;
- expiry;
- status provider;
- instruction metadata;
- sanitized provider response;
- HTTP status dan latency.

### 11.5 DOKU Webhook

Endpoint: `POST /api/v1/webhooks/doku/{merchant_code}`

Urutan:

1. baca raw body;
2. resolve merchant account dari route/key/header yang aman;
3. simpan receipt dengan payload hash;
4. verifikasi signature menggunakan aturan resmi DOKU;
5. jika invalid, tandai `QUARANTINED`, log security event, dan tolak;
6. cari attempt berdasarkan gateway order ID;
7. cocokkan amount dan currency dengan attempt;
8. lock payment dan attempt;
9. mapping status;
10. terapkan transition hanya jika valid;
11. simpan history dan outbox callback;
12. commit;
13. balas HTTP 2xx secepat mungkin.

Webhook boleh dikirim ulang dan harus idempotent. Jangan mengandalkan source IP sebagai satu-satunya autentikasi.

---

## 12. Midtrans Snap

### 12.1 Create Snap Transaction

Payment Portal membuat `gateway_order_id` unik dan meminta Snap token dari server-side API. Browser tidak boleh memegang Server Key.

Konsep payload:

```json
{
  "transaction_details": {
    "order_id": "PAY-20260918-000001-MT-01",
    "gross_amount": 2500000
  },
  "customer_details": {
    "first_name": "Saptadi",
    "email": "customer@example.com",
    "phone": "+6281234567890"
  },
  "callbacks": {
    "finish": "https://pay.example.id/p/PAY-20260918-000001/result"
  }
}
```

Kirim item details hanya jika jumlah seluruh item pasti sama dengan `gross_amount`. Bila Portal Layanan hanya mengirim total, jangan mengarang rincian item.

Gunakan Basic Authentication sesuai dokumentasi server-side Midtrans. Client Key hanya untuk frontend Snap; Server Key hanya di backend.

### 12.2 Frontend Snap

- backend mengembalikan Snap token;
- frontend memuat Snap JS dari environment yang sesuai;
- callback JS seperti `onSuccess` hanya untuk UX;
- status PAID yang otoritatif hanya dari webhook tervalidasi atau status API provider;
- user menutup popup bukan berarti payment gagal.

### 12.3 Midtrans Notification Verification

Endpoint: `POST /api/v1/webhooks/midtrans/{merchant_code}`

Verifikasi harus mengikuti dokumentasi resmi. Untuk signature notification yang menggunakan formula hash, lakukan perhitungan dari field persis sebagaimana didefinisikan provider dan Server Key milik merchant account. Tambahkan server-side status check ke Midtrans untuk defense in depth sebelum mengakui `PAID`, khususnya bila payload meragukan.

Minimal validasi:

- signature valid;
- `order_id` ditemukan;
- `gross_amount` numerik dan sama dengan attempt;
- merchant/environment cocok;
- status transition valid;
- untuk card capture, periksa fraud status sesuai aturan provider;
- notification duplicate menghasilkan HTTP 2xx tanpa side effect ganda.

### 12.4 Finish/Unfinish/Error URL

Redirect customer bukan webhook. Halaman result harus mengambil status terbaru dari Payment Portal dan menampilkan `PENDING` bila webhook belum diterima.

---

## 13. Webhook Processing yang Aman

### 13.1 Jangan Percaya Urutan Kedatangan

Provider dapat mengirim webhook duplicate, terlambat, atau tidak berurutan. Handler harus bersifat idempotent dan menggunakan state machine.

### 13.2 Transaksi Database

Pseudocode:

```python
async with session.begin():
    event = await webhook_repo.insert_or_get_duplicate(...)
    if event.already_processed:
        return success_response()

    attempt = await attempt_repo.get_for_update(gateway_order_id)
    verify_amount_currency(attempt, notification)
    new_status = gateway.map_status(notification)
    validate_transition(attempt.status, new_status)
    await attempt_repo.transition(...)

    payment = await payment_repo.get_for_update(attempt.payment_id)
    await payment_service.apply_attempt_result(payment, attempt, new_status)
    await history_repo.append(...)
    await outbox_repo.enqueue_callback_if_needed(...)
    await webhook_repo.mark_processed(event.id)
```

Gunakan transactional outbox agar perubahan `PAID` dan penjadwalan callback bersifat atomik.

### 13.3 Response

Balas cepat setelah data durable. Proses callback dan pekerjaan berat melalui worker. Bila terjadi kegagalan sementara sebelum commit, kembalikan status yang mendorong provider retry sesuai aturan provider.

---

## 14. Callback Payment Portal → Portal Layanan

Event minimum:

- `payment.pending`;
- `payment.paid`;
- `payment.expired`;
- `payment.cancelled`;
- `payment.failed`;
- `payment.refunded`;
- `payment.partially_refunded`.

Payload:

```json
{
  "event_id": "evt_01J...",
  "event_type": "payment.paid",
  "occurred_at": "2026-09-18T08:12:44Z",
  "data": {
    "payment_id": "42a261dc-c09a-44a4-a78f-b89a1f37a295",
    "payment_no": "PAY-20260918-000001",
    "reference_id": "REG-2026-00123",
    "client_code": "IWAPI",
    "service_code": "IWBIF2026",
    "amount": 2500000,
    "currency": "IDR",
    "status": "PAID",
    "gateway": "DOKU",
    "payment_method": "DOKU_BSI_VA",
    "paid_at": "2026-09-18T08:12:44Z"
  }
}
```

Header callback memakai HMAC canonical yang setara dengan inbound authentication, tetapi gunakan secret khusus callback. Portal Layanan harus:

- memverifikasi signature, timestamp, dan nonce/event ID;
- memastikan amount, currency, reference, dan client sesuai;
- memproses `event_id` secara idempotent;
- membalas 2xx hanya setelah perubahan bisnis tersimpan;
- tidak mengubah PAID menjadi UNPAID karena event lama.

Retry yang disarankan: segera, 1 menit, 5 menit, 15 menit, 1 jam, 6 jam, 24 jam; kemudian dead-letter dan alert. Retry menggunakan `event_id` dan payload yang sama.

Sediakan endpoint client untuk query status sebagai mekanisme pemulihan jika callback gagal.

---

## 15. Reporting dan Payment Ledger

Reporting membaca ledger internal, bukan menggabungkan raw response provider secara langsung.

### 15.1 Dimensi Report

- periode `paid_at`, `created_at`, atau settlement period;
- client;
- organizer;
- service/event;
- gateway;
- payment method;
- merchant account;
- payment status;
- settlement status;
- currency;
- external reference;
- payment number.

### 15.2 Endpoint Report

- `GET /api/v1/admin/reports/summary`
- `GET /api/v1/admin/reports/by-client`
- `GET /api/v1/admin/reports/by-service`
- `GET /api/v1/admin/reports/by-gateway`
- `GET /api/v1/admin/reports/by-method`
- `GET /api/v1/admin/reports/transactions`
- `POST /api/v1/admin/reports/exports`

Contoh:

```http
GET /api/v1/admin/reports/summary?date_from=2026-10-01&date_to=2026-10-31&client_code=IWAPI&service_code=IWBIF2026
```

Response:

```json
{
  "period": {"from": "2026-10-01", "to": "2026-10-31", "timezone": "Asia/Jakarta"},
  "currency": "IDR",
  "paid_transactions": 520,
  "gross_paid_amount": 1000000000,
  "refunded_amount": 25000000,
  "net_collected_amount": 975000000,
  "pending_amount": 45000000,
  "settled_amount": 800000000,
  "outstanding_settlement_amount": 175000000
}
```

Definisi metric harus terdokumentasi:

- Gross Paid = jumlah payment yang berhasil berdasarkan winning attempt;
- Refunded = jumlah refund sukses;
- Net Collected = Gross Paid − Refund sukses, bukan otomatis net settlement;
- Net Settlement = gross eligible − gateway fee − platform fee − tax ± adjustment;
- jangan menjumlahkan seluruh attempt karena akan menggandakan payment.

### 15.3 Query Dasar

```sql
SELECT
    c.code AS client_code,
    s.code AS service_code,
    a.gateway,
    ch.channel_code,
    COUNT(*) AS paid_transactions,
    SUM(p.amount) AS gross_paid
FROM payment_transactions p
JOIN clients c ON c.id = p.client_id
JOIN services s ON s.id = p.service_id
JOIN payment_attempts a ON a.id = p.winning_attempt_id
LEFT JOIN payment_channels ch ON ch.id = a.payment_channel_id
WHERE p.status IN ('PAID','PARTIALLY_REFUNDED','REFUNDED')
  AND p.paid_at >= :from_utc
  AND p.paid_at < :to_utc
GROUP BY c.code, s.code, a.gateway, ch.channel_code;
```

Gunakan half-open interval `[from, to)` dan konversi filter tanggal lokal ke UTC agar transaksi batas hari tidak salah.

### 15.4 Akses Data

- Super Admin: seluruh data;
- Finance Platform: transaksi dan settlement seluruh client sesuai otorisasi;
- Client Admin: hanya client sendiri;
- Organizer Admin: hanya organizer sendiri;
- Event/Service Admin: hanya service terkait;
- Auditor: read-only dan export terkontrol.

Terapkan filter tenant di repository/service dan pertimbangkan PostgreSQL Row Level Security sebagai lapisan tambahan.

---

## 16. Reconciliation

Webhook bukan satu-satunya mekanisme. Jalankan reconciliation job berkala:

1. ambil attempt `PENDING` melewati interval tertentu;
2. query status provider;
3. bandingkan provider dengan ledger;
4. perbarui melalui state machine yang sama;
5. catat source `RECONCILIATION`;
6. buat alert untuk mismatch amount, unknown order, atau duplicate payment;
7. impor/ambil settlement report provider bila tersedia;
8. tandai perbedaan fee dan settlement.

Jadwal awal:

- pending recent: setiap 5–10 menit;
- pending mendekati expiry: setiap 5 menit;
- daily reconciliation: setelah pergantian hari;
- settlement reconciliation: mengikuti jadwal provider;
- backfill 7–30 hari untuk menemukan notifikasi yang terlewat.

Gunakan rate limit dan batch size yang aman terhadap API provider.

---

## 17. Settlement

Settlement internal tidak otomatis berarti provider sudah mengirim dana. Simpan dua fakta secara terpisah:

1. payment berhasil;
2. dana provider telah direkonsiliasi/settled dan/atau diteruskan ke client.

Workflow:

```text
DRAFT → VERIFIED → APPROVED → PAID
```

Kontrol:

- pembuat dan penyetuju berbeda (maker-checker);
- detail transaksi tidak boleh berubah setelah approved;
- payment tidak boleh masuk dua settlement aktif;
- adjustment wajib alasan dan bukti;
- bank reference wajib ketika `PAID`;
- audit log immutable;
- refund/chargeback setelah settlement menghasilkan negative adjustment pada periode berikutnya, bukan mengubah diam-diam settlement lama.

Catatan legal/komersial: penggunaan satu merchant account untuk dana berbagai badan hukum/jenis kegiatan harus dikonfirmasi tertulis dengan provider dan pihak legal. Struktur sistem mendukung multi-merchant account untuk menghindari redesign.

---

## 18. Admin API dan UI Backend Support

Modul admin minimum:

- clients dan credential rotation;
- organizers;
- services/events;
- merchant accounts;
- routing rules;
- payment channels dan limit;
- payment transaction inquiry;
- webhook viewer yang sudah redacted;
- callback retry/dead-letter;
- reconciliation cases;
- refunds dengan approval;
- settlements;
- report dan export;
- audit log.

Setiap perubahan konfigurasi merchant/channel/routing harus memiliki audit record: siapa, kapan, before, after, alasan, dan request ID.

---

## 19. Security Checklist

### 19.1 API dan Network

- TLS 1.2+;
- endpoint provider webhook memiliki URL yang sulit salah konfigurasi tetapi tidak mengandalkan kerahasiaan URL;
- rate limiting per client/IP/endpoint;
- request body limit;
- strict content type;
- CORS hanya untuk frontend Payment Portal yang dikenal;
- admin endpoint tidak diekspos tanpa authentication dan RBAC;
- egress hanya ke domain provider/callback yang diizinkan jika memungkinkan;
- cegah SSRF: callback URL tidak boleh bebas dari request transaksi; gunakan URL terdaftar/snapshot hasil allowlist.

### 19.2 Data

- secret di vault/KMS atau terenkripsi;
- PII minimal dan retention terdefinisi;
- log redaction untuk Authorization, API key, signature, VA bila kebijakan mewajibkan masking, phone/email;
- backup terenkripsi dan restore test;
- tidak menyimpan PAN/CVV;
- database user least privilege;
- UUID publik dan authorization object-level;
- export report memiliki expiry serta access log.

### 19.3 Application

- HMAC constant-time;
- nonce replay protection;
- idempotency;
- row lock atau advisory lock pada perubahan payment;
- allowlist state transition;
- amount/currency invariant;
- no floating point untuk uang;
- secure random ID;
- dependency scanning;
- SAST/secret scanning;
- audit event tidak dapat diedit melalui API biasa.

---

## 20. Konfigurasi Environment

`.env.example` tanpa secret nyata:

```dotenv
APP_NAME="Payment Portal"
ENVIRONMENT=production
API_PREFIX=/api/v1
PUBLIC_BASE_URL=https://pay.example.id
LOG_LEVEL=INFO

DATABASE_URL=postgresql+asyncpg://payment_user:CHANGE_ME@127.0.0.1:5432/payment_portal
REDIS_URL=redis://127.0.0.1:6379/2

HMAC_CLOCK_SKEW_SECONDS=300
NONCE_TTL_SECONDS=600
IDEMPOTENCY_TTL_HOURS=48

CALLBACK_MAX_ATTEMPTS=7
CALLBACK_TIMEOUT_SECONDS=10

DOKU_SANDBOX_BASE_URL=<from-official-docs>
DOKU_PRODUCTION_BASE_URL=<from-official-docs>
MIDTRANS_IS_PRODUCTION=true

SENTRY_DSN=
OTEL_EXPORTER_OTLP_ENDPOINT=
```

Credential per merchant sebaiknya berada di database terenkripsi/secret manager, bukan menjadi variabel global tunggal, karena sistem bersifat multi-merchant.

Validasi saat startup:

- production tidak boleh memakai sandbox URL/key;
- encryption key tersedia;
- database migration sesuai;
- required callback/public URL HTTPS;
- timezone aplikasi UTC;
- worker/Redis connectivity sesuai fitur yang diaktifkan.

---

## 21. Logging, Audit, dan Monitoring

Gunakan structured JSON log dengan:

- `request_id`;
- `payment_id`;
- `payment_no`;
- `attempt_id`;
- `gateway_order_id`;
- `client_code`;
- `gateway`;
- endpoint;
- HTTP status;
- latency;
- error code.

Jangan log secret/raw Authorization/signature.

Metric minimum:

- request rate/error/latency;
- provider create success/error/timeout;
- webhook invalid signature;
- webhook processing lag;
- payment conversion per gateway/method;
- callback backlog/dead-letter;
- pending payment age;
- reconciliation mismatch;
- duplicate paid attempt;
- settlement outstanding.

Alert kritis:

- invalid signature spike;
- provider timeout/error spike;
- webhook berhenti diterima;
- callback backlog;
- database/Redis unavailable;
- duplicate payment;
- amount mismatch;
- reconciliation mismatch besar.

---

## 22. Testing Strategy

### 22.1 Unit Test

- canonical HMAC internal;
- DOKU signer official test vector;
- Midtrans notification verification test vector;
- provider status mapper;
- state transition;
- money/amount invariant;
- routing rule precedence;
- idempotency conflict;
- callback signature;
- report metric.

### 22.2 Integration Test

- PostgreSQL constraints dan locking;
- create payment concurrent;
- double-click create attempt;
- duplicate/out-of-order webhook;
- webhook PAID bersamaan dengan cancel;
- callback retry;
- refund dan settlement constraints;
- tenant isolation.

### 22.3 Contract/Sandbox Test

Untuk setiap merchant dan channel:

- create payment;
- obtain VA/code/token;
- success notification;
- pending;
- expiry;
- cancel bila didukung;
- refund bila didukung;
- invalid signature;
- duplicate notification;
- timeout dan status inquiry;
- amount boundary;
- reconciliation.

Jangan melakukan go-live channel hanya berdasarkan mock test.

### 22.4 UAT Matrix

| Case | DOKU VA | DOKU Retail | Midtrans Snap |
|---|---:|---:|---:|
| Create | ✓ | ✓ | ✓ |
| Pending | ✓ | ✓ | ✓ |
| Paid | ✓ | ✓ | ✓ |
| Expired | ✓ | ✓ | ✓ |
| Duplicate webhook | ✓ | ✓ | ✓ |
| Late webhook | ✓ | ✓ | ✓ |
| Report dimensions | ✓ | ✓ | ✓ |
| Callback retry | ✓ | ✓ | ✓ |
| Reconciliation | ✓ | ✓ | ✓ |

---

## 23. Deployment Produksi

### 23.1 Process

- `payment-api.service`: Gunicorn/Uvicorn workers;
- `payment-worker.service`: callback/reconciliation jobs;
- `payment-scheduler.service`: scheduled jobs;
- PostgreSQL;
- Redis;
- Nginx.

### 23.2 Gunicorn Contoh

```ini
[Unit]
Description=Payment Portal FastAPI
After=network.target

[Service]
User=payment
Group=www-data
WorkingDirectory=/var/www/fastapi_app/payment-portal
EnvironmentFile=/var/www/fastapi_app/payment-portal/.env
ExecStart=/var/www/fastapi_app/payment-portal/env/bin/gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --bind 127.0.0.1:8010 \
  --workers 4 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Sesuaikan worker terhadap CPU, DB pool, dan beban I/O. Jangan menyalakan scheduler yang sama pada setiap API worker.

### 23.3 Nginx Ringkas

```nginx
server {
    listen 443 ssl http2;
    server_name api-pay.example.id;

    client_max_body_size 2M;

    location / {
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 10s;
        proxy_read_timeout 60s;
    }
}
```

TLS certificate, security headers, rate limit, access log redaction, dan upstream tuning harus ditambahkan sesuai standar server.

### 23.4 Migration Release

Gunakan expand-and-contract:

1. backup dan verify restore point;
2. deploy migration backward-compatible;
3. deploy code;
4. backfill bila perlu;
5. aktifkan constraint/index berat secara aman;
6. hapus kolom lama pada release terpisah.

---

## 24. Tahapan Implementasi

### Fase 1 — Foundation

- setup project, config, DB, Alembic;
- client/service/organizer;
- HMAC + nonce + idempotency;
- payment transaction dan public checkout skeleton;
- audit/logging.

### Fase 2 — Midtrans Snap

- merchant account;
- Snap create transaction;
- frontend token contract;
- webhook verification dan status mapper;
- callback Portal Layanan.

Midtrans biasanya lebih cepat untuk end-to-end awal karena hosted checkout.

### Fase 3 — DOKU Direct API

- signer dan client;
- BSI/BJB/BTN VA satu per satu;
- Alfamart dan Indomaret;
- instruction rendering contract;
- webhook per product;
- sandbox contract tests.

Aktifkan channel secara feature flag setelah lulus UAT.

### Fase 4 — Report dan Reconciliation

- dashboard summary;
- drill-down client/event/gateway/method;
- exports;
- status inquiry jobs;
- discrepancy cases.

### Fase 5 — Settlement dan Refund

- fees/adjustment;
- maker-checker;
- settlement detail;
- refund workflow;
- audit/export.

### Fase 6 — Hardening dan Go-Live

- penetration/security review;
- load test;
- failover/backup restore test;
- provider production credential;
- limited canary client/channel;
- monitoring dan runbook;
- production sign-off.

---

## 25. Definition of Done

Satu channel dinyatakan selesai jika:

- API contract disetujui;
- migration dan indexes tersedia;
- signature test lulus;
- create/status/webhook flow lulus sandbox;
- duplicate dan out-of-order webhook aman;
- amount/currency mismatch ditolak;
- callback idempotent dan retry teruji;
- report menampilkan client/service/gateway/method dengan benar;
- log sudah redacted;
- metric dan alert aktif;
- dokumentasi konfigurasi dan runbook tersedia;
- UAT ditandatangani.

---

## 26. Runbook Insiden Singkat

### Webhook tidak masuk

1. cek endpoint/TLS/Nginx;
2. cek provider dashboard/config notification URL;
3. jalankan status inquiry untuk attempt terkait;
4. perbarui melalui reconciliation service, bukan SQL manual;
5. dokumentasikan incident.

### Signature invalid meningkat

1. jangan menonaktifkan verifikasi;
2. cek environment/key/merchant routing;
3. cek clock NTP dan raw body handling;
4. bandingkan canonical string secara aman tanpa mencetak secret;
5. blokir pola serangan bila relevan.

### Payment provider PAID, portal masih PENDING

1. query provider dari backend;
2. cocokkan `gateway_order_id`, amount, currency;
3. jalankan reconciliation idempotent;
4. pastikan callback/outbox diproduksi;
5. jangan mengubah database manual kecuali prosedur break-glass teraudit.

### Portal Layanan tidak menerima callback

1. cek callback delivery dan response;
2. pastikan URL masih allowlisted;
3. retry event yang sama;
4. Portal Layanan dapat melakukan GET status;
5. pindahkan ke dead-letter dan alert setelah retry habis.

---

## 27. Keputusan Arsitektur Final

1. `amount` ditentukan Portal Layanan dan dilindungi HMAC.
2. `reference_id` dibuat Portal Layanan.
3. `payment_id`, `attempt_id`, dan `gateway_order_id` dibuat Payment Portal.
4. Satu payment dapat memiliki beberapa attempt.
5. DOKU memakai Direct API dengan UI channel milik Payment Portal.
6. Midtrans memakai Snap hosted checkout.
7. Webhook tervalidasi/status inquiry adalah sumber status pembayaran, bukan callback JavaScript/redirect browser.
8. Semua gateway dinormalisasi ke internal ledger.
9. Report memakai winning attempt sehingga tidak terjadi double counting.
10. Database mendukung multi-client, organizer, service/event, merchant account, gateway, dan channel.
11. Callback ke Portal Layanan ditandatangani dan idempotent.
12. Settlement dipisahkan dari payment success.

---

## 28. Referensi Resmi yang Wajib Dijadikan Acuan Saat Coding

Karena endpoint, header, kode channel, payload, dan aturan aktivasi dapat berubah, developer wajib memeriksa dokumentasi resmi pada saat implementasi dan mencatat versi/tanggal verifikasi dalam ADR atau integration checklist.

- [DOKU Direct API](https://docs.doku.com/accept-payments/integration-tools/direct-api)
- [DOKU Payment Methods](https://docs.doku.com/accept-payments/payment-methods)
- [DOKU Payment Method Requirements and Limitations](https://docs.doku.com/accept-payments/payment-methods/requirements-and-limitations)
- [DOKU Payment Notification/Webhook](https://docs.doku.com/get-started/manage-business/set-up-integration/webhook-payment-notification)
- [Midtrans Snap Overview](https://docs.midtrans.com/docs/snap)
- [Midtrans Snap API](https://docs.midtrans.com/reference/snap-api)
- [Midtrans HTTP Notification/Webhook](https://docs.midtrans.com/docs/https-notification-webhooks)
- [Midtrans Transaction Status Lifecycle](https://docs.midtrans.com/docs/transaction-status-cycle)

Dokumentasi provider adalah otoritas untuk canonical signature, base URL, endpoint product, field wajib, status, retry expectation, dan channel code. Dokumen arsitektur ini tidak menggantikan kontrak provider.

---

## Lampiran A — Contoh Nomor

```text
payment_no      PAY-20260918-000001
DOKU attempt    PAY-20260918-000001-DK-01
Midtrans attempt PAY-20260918-000001-MT-02
settlement_no   SET-202610-000012
refund_no       RFD-202610-000007
```

Counter harus concurrency-safe. `payment_no` hanya label manusia; UUID tetap primary key.

## Lampiran B — Response Channel Eligibility

```json
{
  "payment_no": "PAY-20260918-000001",
  "amount": 2500000,
  "currency": "IDR",
  "channels": [
    {"code": "DOKU_BSI_VA", "name": "BSI Virtual Account", "category": "VIRTUAL_ACCOUNT"},
    {"code": "DOKU_BJB_VA", "name": "BJB Virtual Account", "category": "VIRTUAL_ACCOUNT"},
    {"code": "DOKU_BTN_VA", "name": "BTN Virtual Account", "category": "VIRTUAL_ACCOUNT"},
    {"code": "DOKU_ALFAMART", "name": "Alfamart", "category": "CONVENIENCE_STORE"},
    {"code": "DOKU_INDOMARET", "name": "Indomaret", "category": "CONVENIENCE_STORE"},
    {"code": "MIDTRANS_SNAP", "name": "Midtrans", "category": "HOSTED_CHECKOUT"}
  ]
}
```

Eligibility dihitung server-side dari status channel, routing merchant, amount limit, currency, service/client policy, dan kondisi provider.

## Lampiran C — Checklist Sebelum Mengaktifkan Merchant

- badan hukum dan penggunaan merchant disetujui provider;
- production client/server key diterima dengan aman;
- channel aktif di dashboard/provider;
- notification URL production terpasang;
- origin/finish URL sesuai;
- merchant routing rule benar;
- signature test production non-finansial/nominal terbatas berhasil;
- finance mengetahui fee dan settlement schedule;
- rekening settlement tervalidasi;
- callback client production diuji;
- monitoring aktif;
- rollback/disable channel tersedia.

