# Identitas Portal, Event dan Pembayar

Kontrak aktif setelah migration 0010. Ini perubahan breaking untuk POST client payments:
event_id, event_name dan customer.email wajib pada request baru. API login admin tetap
belum tersedia. PortalUser adalah pembayar dari client, bukan akun login admin Payment.

## Identitas dan batas unik

| Entitas | Identitas | Nama |
| --- | --- | --- |
| Client/Portal | UUID client internal; code menjadi client_id OAuth | clients.name dari registrasi operator |
| Event | (client UUID, event_id dari Portal) | event_name |
| Pembayar | (client UUID, email ternormalisasi) | customer.name |
| Order | payment_id/payment_no; reference_id unik per client | description opsional |

client_id OAuth adalah code, sedangkan data.client_id pada response payment adalah UUID
internal. Jangan menukarnya. Body create tidak menentukan client_id/client_name;
identitas client selalu dari JWT dan record client terdaftar.
event_id berupa string stabil maksimal 150 karakter, case-sensitive dan trim whitespace.
event_name maksimal 250 karakter, customer.name maksimal 200; wajib nonblank.

Satu client dapat memiliki banyak event; event_id yang sama di dua client adalah dua
event berbeda. Satu email boleh memiliki beberapa order untuk event yang sama,
dengan reference_id berbeda. Tidak ada unique order (client,event,email).
Ini mengikuti rekomendasi multiple orders; bukan kebijakan satu tiket per orang.

service_code tetap wajib untuk kategori/routing layanan yang didaftarkan operator;
bukan pengganti event_id. Satu service dapat dipakai banyak event.
Event/pembayar otomatis dibuat saat create payment pertama berhasil, dalam transaksi
yang sama. Client terautentikasi berwenang mengirim identitas event di lingkupnya sendiri;
master event tetap read-only di admin, sedangkan PortalUser dapat dikelola SUPER_ADMIN
melalui endpoint admin. Email PortalUser immutable; perubahan nama memakai
`expected_version`, dan penghapusan ditolak bila sudah direferensikan transaksi.

## Email dan data historis

Email wajib valid, dipangkas whitespace, lalu lowercase seluruh alamat sebagai kebijakan
identitas aplikasi. Tidak menghapus titik atau +tag. Portal Event harus menerapkan
kebijakan pencocokan yang sama; ini bukan klaim bahwa semua mail server case-insensitive.
Email dari dua client tidak digabung menjadi satu user global. Perubahan email membuat
identitas pembayar baru; belum ada fitur merge akun.

Payment mempercayai backend client terautentikasi sebagai sumber data; validasi format
email bukan bukti kepemilikan email/keanggotaan user. Portal harus memverifikasi user
terdaftar dan harga/order dari sistemnya sebelum request.

Nama event/pembayar pada master diperbarui ketika order baru diterima. Order menyimpan
snapshot client_name, event_id/event_name dan customer_name/customer_email saat create.
Perubahan nama berikutnya tidak menulis ulang snapshot order lama.
Constraint unik melindungi master dan FK komposit memastikan link order ke master
tidak menyeberang client. Pembuatan order tetap diserialisasi dengan client row lock.

Migration tidak mengarang email atau event untuk data lama: kolom snapshot/link baru
nullable, email historis tetap nullable. Response order lama dapat berisi null.
Backfill hanya boleh dari mapping data asli yang disetujui, bukan nama service tebakan.

## Request dan response

POST /api/v1/client/payments dengan Bearer JWT backend dan Idempotency-Key:

```json
{
  "service_code": "EVENT",
  "event_id": "EVT-2026-001",
  "event_name": "Konferensi Tahunan",
  "reference_id": "REG-0001",
  "amount": 150000,
  "currency": "IDR",
  "customer": {"name": "Peserta", "email": "peserta@example.com"}
}
```

Respons create/GET client payment menambahkan client_id (UUID), client_name,
event_id, event_name, customer.name dan customer.email pada data. Informasi ini hanya
untuk backend client pemilik. Checkout publik tetap tidak menampilkan email/nama pembayar.
Callback baru menambahkan event_id/event_name; event callback yang sudah antre tetap
memakai payload snapshot lamanya dan mungkin belum berisi kedua field ini.

Retry menggunakan payload/key yang sama; perubahan event/email dengan key sama
menghasilkan 409 IDEMPOTENCY_CONFLICT. Event/email kosong atau invalid -> 422.
Replay record idempotency lama dapat memiliki response tanpa field identitas baru.
Request format lama tanpa event/email sekarang ditolak schema sebelum replay; jangan
membuat reference baru untuk membayar ulang order lama. Gunakan GET payment atau
renew checkout milik order existing melalui backend; bila perlu eskalasi operator.

Kontrak ini juga berlaku untuk payload Portal Event yang sudah terdaftar: setiap
request create payment wajib mengirim ketiga field tersebut. Tidak ada fallback
tebakan dari `service_code`, dan tidak ada admin rename event yang menulis ulang
snapshot order historis.

Gateway payload/protokol Midtrans/DOKU tidak diubah pada iterasi ini. Kewajiban email
adalah aturan identitas Payment Portal, bukan klaim kewajiban universal gateway.
