# Backfill Portal Identity

`backfill_portal_identity.py` hanya menerima mapping eksplisit yang telah disetujui.
Tidak ada tebakan dari service, nama client, atau data gateway. CSV wajib memiliki:

`payment_id,event_id,event_name,email,user_name`

Default adalah dry-run:

```powershell
python scripts/backfill_portal_identity.py .\approved-mapping.csv
```

Apply hanya boleh dilakukan setelah mapping disetujui dan disertai identitas approval
serta alasan:

```powershell
python scripts/backfill_portal_identity.py .\approved-mapping.csv `
  --apply --approved-by "admin@example.com" --reason "Mapping event dari sistem Event v3"
```

Script menolak payment yang sudah memiliki snapshot event/email berbeda, mengisi hanya
identity yang valid, mengunci payment selama proses, dan menulis audit tanpa email
mentah. Backup database dan review CSV wajib dilakukan sebelum `--apply`.
