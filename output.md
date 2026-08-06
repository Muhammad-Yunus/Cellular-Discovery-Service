# API `/api/v1/missions` — Summary Update untuk FE Agent

## Ringkasan Perubahan

Endpoint `GET /api/v1/missions` sekarang mendukung:

1. **Filter by time range** (`start_time` & `end_time`)
2. **Parameter sort** yang lebih lengkap dengan validasi field

---

## 1. Parameter Sort (`sort`)

Filter berdasarkan kolom mission dengan format:

```
?sort=<field>        → ASC
?sort=-<field>       → DESC (default)
```

**Valid sort fields:**

| Field | Deskripsi |
|-------|-----------|
| `created_at` | Waktu mission dibuat |
| `name` | Nama mission |
| `description` | Deskripsi mission |

**Default:** `-created_at` (terbaru dulu)

**Behavior:**
- Field tidak valid → fallback ke `-created_at`, **tidak error**
- Prefix `-` → DESC; tanpa prefix → ASC

**Contoh:**
```
GET /api/v1/missions?sort=-created_at     # terbaru dulu (default)
GET /api/v1/missions?sort=name            # nama A-Z
GET /api/v1/missions?sort=-name           # nama Z-A
GET /api/v1/missions?sort=description     # deskripsi A-Z
GET /api/v1/missions?sort=invalid_field   # fallback ke -created_at (no error)
```

---

## 2. Filter Time Range (`start_time` & `end_time`)

Filter mission berdasarkan `created_at` dengan format ISO 8601 datetime:

```
?start_time=2026-08-01T00:00:00&end_time=2026-08-07T23:59:59
```

**Aturan validasi:**

| Aturan | HTTP Response |
|--------|---------------|
| `start_time <= end_time` ✅ | 200 OK |
| `start_time > end_time` ❌ | **422** `start_time cannot be greater than end_time` |
| Hanya `start_time` saja | 200 OK (filter `created_at >= start_time`) |
| Hanya `end_time` saja | 200 OK (filter `created_at <= end_time`) |
| Keduanya kosong / tidak dikirim | 200 OK (tidak ada filter) |

**Format yang didukung:**
- `2026-08-01T00:00:00`
- `2026-08-01T00:00:00Z` (UTC)
- `2026-08-01T00:00:00+07:00` (with timezone)
- `2026-08-01` (date only, akan jadi `00:00:00`)

**Contoh:**
```
GET /api/v1/missions?start_time=2026-08-04&end_time=2026-08-07
GET /api/v1/missions?end_time=2026-08-05
GET /api/v1/missions?start_time=2026-08-06T13:55:15
GET /api/v1/missions?start_time=2026-08-01T00:00:00&end_time=2026-08-07T23:59:59&sort=-created_at
```

---

## Response Format (tetap sama)

```json
{
  "items": [...],
  "total": 18,
  "page": 1,
  "page_size": 10
}
```

---

## Catatan untuk FE

1. **Sort parameter** — selalu kirim `-created_at` sebagai default untuk konsistensi
2. **Time range filter** — di FE, sebelum kirim request, validasi `start_time <= end_time` di client untuk UX lebih baik (tapi backend akan tetap return 422)
3. **Timezone** — kirim datetime dalam ISO 8601 dengan timezone untuk menghindari ambiguitas
4. **Combined filter** — `sort` dan `start_time`/`end_time` bisa dikombinasikan dengan filter lain (`status`, `search`)