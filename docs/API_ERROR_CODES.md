# API Error Codes

Semua error memakai envelope berikut dan tidak mengembalikan exception, credential,
password, token, atau raw request body:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Pesan aman untuk operator/user",
    "request_id": "req_...",
    "details": null
  }
}
```

`request_id` dicatat frontend untuk tracing dan dikirimkan ke tim backend; jangan
menjadikannya credential atau menampilkannya sebagai detail teknis exception.

## Authentication dan authorization

| Code | HTTP | Tindakan frontend |
| --- | ---: | --- |
| `AUTH_REQUIRED` | 401 | Kirim Bearer token yang valid. |
| `INVALID_ACCESS_TOKEN` | 401 | Minta token client baru. |
| `INSUFFICIENT_SCOPE` | 403 | Tampilkan forbidden; jangan retry otomatis. |
| `CLIENT_NOT_FOUND` | 401/404 | Verifikasi konfigurasi client/backend. |
| `INVALID_CHECKOUT_TOKEN` | 401 | Minta checkout link baru dari Portal Event. |
| `ADMIN_SESSION_REQUIRED` / `ADMIN_SESSION_INVALID` | 401 | Login admin ulang. |
| `ADMIN_FORBIDDEN` / `ADMIN_ORIGIN_DENIED` / `ADMIN_CSRF_INVALID` | 403 | Tampilkan forbidden/security error. |
| `ADMIN_LOGIN_FAILED` | 401 | Tampilkan pesan login generik. |
| `ADMIN_LOGIN_RATE_LIMIT` | 429 | Hormati `Retry-After`. |

## Validation dan conflict

| Code | HTTP | Tindakan frontend |
| --- | ---: | --- |
| `VALIDATION_ERROR` | 422 | Tampilkan error field dari `details`. |
| `INVALID_IDEMPOTENCY_KEY` | 422 | Buat key unik 1-150 karakter. |
| `IDEMPOTENCY_CONFLICT` | 409 | Jangan mengganti key; periksa request sebelumnya. |
| `DUPLICATE_REFERENCE` | 409 | Gunakan reference yang benar atau ambil payment existing. |
| `CLIENT_VERSION_CONFLICT` / `SERVICE_VERSION_CONFLICT` / `VERSION_CONFLICT` | 409 | Reload resource lalu minta konfirmasi ulang. |
| `INVALID_DATE_RANGE` / `INVALID_CURSOR` | 422 | Perbaiki filter atau cursor export. |
| `CLIENT_FILTER_REQUIRED` | 422 | Sertakan `client_id` saat memakai `event_id`. |
| `UNSUPPORTED_CHANNEL` / `UNSUPPORTED_CURRENCY` | 422 | Tampilkan channel/currency tidak tersedia. |

## Payment dan checkout state

| Code | HTTP | Tindakan frontend |
| --- | ---: | --- |
| `PAYMENT_NOT_FOUND` / `ATTEMPT_NOT_FOUND` | 404 | Refresh resource atau tampilkan tidak ditemukan. |
| `PAYMENT_EXPIRED` / `CHECKOUT_UNAVAILABLE` | 409 | Minta checkout/payment baru. |
| `ATTEMPT_IN_PROGRESS` / `GATEWAY_OUTCOME_UNKNOWN` | 409/503 | Poll status/inquiry; jangan create order baru otomatis. |
| `INVALID_STATUS_TRANSITION` | 409 | Refresh status ledger. |
| `REFUND_NOT_ALLOWED` / `REFUND_LIMIT_EXCEEDED` | 409/422 | Tampilkan policy refund. |
| `REFUND_SELF_APPROVAL` | 403 | Pengaju tidak boleh approve refund sendiri. |
| `RECONCILIATION_NOT_REQUIRED` / `RECONCILIATION_UNSUPPORTED` | 409/422 | Tampilkan status antrean/provider. |

## Provider dan webhook

| Code | HTTP | Tindakan frontend/operator |
| --- | ---: | --- |
| `GATEWAY_NOT_CONFIGURED` | 503 | Eskalasi konfigurasi backend; jangan retry cepat. |
| `GATEWAY_CREATE_FAILED` / `GATEWAY_INQUIRY_FAILED` | 502 | Tampilkan gangguan provider dan simpan `request_id`. |
| `GATEWAY_ORDER_MISMATCH` / `GATEWAY_AMOUNT_MISMATCH` | 409/502 | Quarantine/escalate; jangan ubah ledger manual dari UI. |
| `INVALID_GATEWAY_RESPONSE` | 502 | Eskalasi provider/integration team. |
| `INVALID_GATEWAY_SIGNATURE` | 401 | Tolak webhook; jangan retry dari frontend. |
| `UNKNOWN_PROVIDER_STATUS` / `LATE_STATUS_REVIEW_REQUIRED` | 409/422 | Tunggu reconciliation/operator review. |
| `REFUND_RECONCILIATION_REQUIRED` | 409 | Jangan tandai refund sukses dari response browser. |
| `DOKU_MANUAL_REFUND_REQUIRED` | — | Ikuti proses manual DOKU; ledger belum `REFUNDED`. |

Status `5xx` dapat dicoba ulang dengan exponential backoff hanya untuk operasi yang
memiliki idempotency/queue contract. Jangan retry create payment tanpa idempotency key.
