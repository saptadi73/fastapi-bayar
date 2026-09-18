# Admin Refund API

Fondasi refund maker-checker tersedia di `/api/v1/admin/refunds`. Semua endpoint memakai admin session cookie, origin check, dan CSRF token.

`GET /admin/refunds` membutuhkan `admin.refunds.read`. `POST /admin/refunds/request` membutuhkan `admin.refunds.request` dan menerima `{ "payment_id": "UUID", "amount": 10000, "reason": "..." }`. Payment harus `PAID` atau `PARTIALLY_REFUNDED`; jumlah refund aktif tidak boleh melebihi nominal payment.

`POST /admin/refunds/{id}/approve` dan `/reject` membutuhkan `admin.refunds.approve` serta `{ "expected_version": 1 }`. Reject wajib menyertakan `reason`. Pengaju admin tidak boleh menyetujui refund sendiri. Setiap keputusan menulis `AdminAudit` dan menaikkan `version`.

Approval internal menghasilkan status `APPROVED` dengan `provider_action: PENDING_ADAPTER`. Worker Midtrans memprosesnya memakai `refund_no` sebagai `refund_key`, lalu melakukan inquiry. Hanya riwayat dengan key dan nominal yang cocok yang menjadi `SUCCEEDED` dan mengubah ledger payment; `PROVIDER_ACCEPTED` tetap menunggu konfirmasi. Adapter DOKU, multi-merchant credentials, dan settlement reconciliation masih TODO.

Kontrak provider yang menjadi dasar tahap berikutnya:

- [Midtrans Refund Transactions](https://docs.midtrans.com/reference/refund-transaction): refund untuk transaksi settlement dan `refund_key` dipakai sebagai identifier retry yang sama.
- [Midtrans Get Transaction Status](https://docs.midtrans.com/reference/get-transaction-status): status response dapat membawa refund history.
- [DOKU Get Transaction Status](https://developers.doku.com/): status/riwayat refund harus dipetakan ke ledger internal sebelum payment menjadi `REFUNDED`.
