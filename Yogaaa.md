# Simulasi Pengangkutan Sampah
### Tugas Besar – Dasar Kecerdasan Artificial

---

## Daftar Isi

1. [Deskripsi Proyek](#1-deskripsi-proyek)
2. [Spesifikasi Sistem](#2-spesifikasi-sistem)
3. [Alur Program (Flow)](#3-alur-program-flow)
4. [Struktur Program & Penjelasan Cell](#4-struktur-program--penjelasan-cell)
5. [Algoritma Heuristik & Penjatahan](#5-algoritma-heuristik--penjatahan)
6. [Rumus & Perhitungan](#6-rumus--perhitungan)
7. [Dokumentasi Visualisasi](#7-dokumentasi-visualisasi)
8. [Cara Menjalankan](#8-cara-menjalankan)
9. [Contoh Output](#9-contoh-output)
10. [Catatan Teknis & Desain Decision](#10-catatan-teknis--desain-decision)

---

## 1. Deskripsi Proyek

Program ini mensimulasikan sistem pengangkutan sampah di sebuah desa padat penduduk menggunakan **algoritma heuristik berbasis penjatahan wilayah**. Simulasi melibatkan tiga jenis entitas utama — rumah penduduk, gerobak sampah, dan truk sampah — yang berinteraksi secara *real-time* dalam satu peta acak berukuran 50×50 satuan jarak.

Sebelum simulasi dimulai, sistem melakukan **Pre-Assignment (Penjatahan)**: setiap TPS ditetapkan sebagai "komando wilayah" yang bertanggung jawab atas sejumlah rumah, gerobak, dan truk. Hal ini mencegah gerobak berebut rumah yang sama dan membatasi pergerakan agen ke zona masing-masing.

Semua agen berjalan **secara paralel** dalam satu *concurrent event-driven loop*: setiap iterasi memilih agen dengan jam (`time`) terkecil, sehingga gerobak (mulai 06:00) dan truk (mulai 08:00) benar-benar beroperasi bersamaan di peta yang sama.

**Tujuan utama:**
- Menentukan rute efisien bagi gerobak dan truk dalam zona masing-masing
- Mengoptimalkan penggunaan waktu operasi yang terbatas
- Mencegah konflik antar agen melalui sistem penjatahan wilayah
- Memberikan mekanisme *Work Stealing* untuk truk agar membantu zona lain setelah tugasnya selesai

---

## 2. Spesifikasi Sistem

### Parameter Lingkungan

| Parameter | Nilai | Keterangan |
|---|---|---|
| Jumlah Rumah | 100 | Tetap |
| Ukuran Grid | 50 × 50 | Satuan jarak |
| Sampah per Rumah | 0 – 7 kg | Acak setiap sesi |
| Jumlah Gerobak | 5 – 7 | Acak saat inisialisasi |
| Jumlah Truk | 2 – 4 | Acak saat inisialisasi |
| Jumlah TPS | 3 | Tetap |

### Parameter Kapasitas

| Agen | Kapasitas |
|---|---|
| Gerobak Sampah | 15 kg |
| Truk Sampah | 200 kg |
| TPS | 400 – 500 kg (acak per TPS) |

### Parameter Waktu Operasi

| Agen | Mulai | Selesai |
|---|---|---|
| Gerobak | 06:00 | 15:00 |
| Truk | 08:00 | 17:00 |

### Parameter Waktu Loading & Travel

| Operasi | Nilai |
|---|---|
| Loading gerobak (ambil/transfer) | 2 menit per kg |
| Loading truk (ke TPS) | 2 menit per 10 kg |
| Travel gerobak | 3 menit per 1 satuan jarak |
| Travel truk | 3 menit per 5 satuan jarak (= 0,6 menit/satuan) |

---

## 3. Alur Program (Flow)

```
[Inisialisasi Data Acak]
        ↓
[PRE-ASSIGNMENT]
  Fase 1: TPS assign rumah terdekat (kuota 34/33/33)
  Fase 2: TPS rekrut gerobak terdekat (Round-Robin)
  Fase 3: TPS assign truk (1 per TPS, ekstra ke TPS terbesar)
        ↓
[Visualisasi Peta Awal]
        ↓
[SIMULASI CONCURRENT]
  Loop: pilih agen dengan time terkecil
    → Gerobak: ambil sampah di zona sendiri → transfer ke truk bila berpapasan
    → Truk: zona sendiri dulu → Work Stealing bila zona bersih
        ↓
[Laporan Hasil + Log Pergerakan + Visualisasi Akhir]
```

---

## 4. Struktur Program & Penjelasan Cell

Notebook terdiri dari **12 cell aktif** yang diurutkan sebagai berikut:

---

### Cell 1 — Import & Const

Memuat semua library yang dibutuhkan dan mendefinisikan seluruh konstanta program.

```python
import random, math
from dataclasses import dataclass
from typing import List, Optional, Tuple
```

Konstanta yang didefinisikan:

| Konstanta | Nilai | Keterangan |
|---|---|---|
| `NUM_HOUSES` | `100` | Jumlah rumah |
| `GRID_SIZE` | `50` | Ukuran grid satu sisi |
| `NUM_TPS` | `3` | Jumlah TPS |
| `CAP_GEROBAK` | `15` | Kapasitas gerobak (kg) |
| `CAP_TRUK` | `200` | Kapasitas truk (kg) |
| `GEROBAK_START/END` | `360 / 900` | Menit operasi gerobak (06:00–15:00) |
| `TRUK_START/END` | `480 / 1020` | Menit operasi truk (08:00–17:00) |
| `GEROBAK_LOAD_PER_KG` | `2` | Menit loading gerobak per kg |
| `TRUK_LOAD_PER_10KG` | `2` | Menit loading truk per 10 kg |
| `GEROBAK_TRAVEL_PER_DIST` | `3` | Menit travel gerobak per satuan jarak |
| `TRUK_TRAVEL_PER_5DIST` | `3` | Menit travel truk per 5 satuan jarak |

> **Catatan:** `SEED` tidak di-hardcode. Tiap run menggunakan `random.seed()` (waktu sistem) sehingga hasilnya selalu berbeda. Seed yang dipakai dicetak di Cell 6 agar bisa direproduksi jika perlu.

---

### Cell 2 — Helper Functions

Berisi fungsi utilitas dasar yang dipakai di seluruh program.

| Fungsi | Kegunaan |
|---|---|
| `mins_to_hhmm(m)` | Konversi menit (int) ke format `"HH:MM"` |
| `euclidean(a, b)` | Hitung jarak Euclidean antara dua titik 2D |
| `gerobak_travel_time(dist)` | Hitung waktu tempuh gerobak dari jarak |
| `truk_travel_time(dist)` | Hitung waktu tempuh truk dari jarak |
| `gerobak_load_time(kg)` | Hitung waktu loading gerobak dari berat |
| `truk_load_time(kg)` | Hitung waktu loading truk dari berat |

Rumus lengkap tiap fungsi dibahas di [Bagian 6 — Rumus & Perhitungan](#6-rumus--perhitungan).

---

### Cell 3 — Data Classes

Mendefinisikan tiga struktur data utama menggunakan `@dataclass`.

#### `House` — Rumah Penduduk

| Atribut | Tipe | Keterangan |
|---|---|---|
| `id` | `int` | ID unik (1–100) |
| `x`, `y` | `float` | Koordinat posisi di grid |
| `trash_initial` | `float` | Sampah awal hari ini (kg) |
| `trash_remaining` | `float` | Sisa sampah yang belum diambil (kg) |
| `assigned_tps` | `int` | ID TPS yang bertanggung jawab atas rumah ini (diisi saat pre-assignment) |

#### `TPS` — Tempat Pembuangan Sampah Akhir

| Atribut | Tipe | Keterangan |
|---|---|---|
| `id` | `int` | ID TPS (1–3) |
| `x`, `y` | `float` | Koordinat posisi |
| `capacity` | `float` | Kapasitas maksimum harian (kg) |
| `stored` | `float` | Sampah yang sudah masuk hari ini (kg) |
| `available` *(property)* | `float` | Sisa kapasitas = `capacity - stored` |

#### `LogEntry` — Catatan Pergerakan

| Atribut | Keterangan |
|---|---|
| `actor` | Nama agen, misal `"Gerobak-1"` atau `"Truk-2"` |
| `time` | Waktu kejadian dalam format `"HH:MM"` |
| `event` | Kode kejadian (lihat tabel di bawah) |
| `detail` | Deskripsi lengkap kejadian |

Daftar kode event:

| Event | Aktor | Keterangan |
|---|---|---|
| `MULAI` | Semua | Agen mulai beroperasi |
| `AMBIL_SAMPAH` | Gerobak, Truk | Mengambil sampah dari rumah |
| `BUANG_TPS` | Gerobak, Truk | Membuang muatan ke TPS |
| `TITIP_TRUK` | Gerobak | Transfer muatan ke truk |
| `TERIMA_GEROBAK` | Truk | Menerima muatan dari gerobak |
| `SELESAI_WAKTU` | Semua | Berhenti karena jam operasi habis |
| `SELESAI_SAMPAH` | Semua | Berhenti karena tidak ada sampah tersisa di zonanya |
| `ERROR` | Semua | TPS penuh atau kondisi tidak terduga |

---

### Cell 4 — Agent Classes: `Gerobak` & `Truk`

Mendefinisikan dua class agen dengan method masing-masing.

#### Kelas `Gerobak`

| Atribut | Keterangan |
|---|---|
| `id`, `x`, `y` | Identitas dan posisi saat ini |
| `load` | Muatan saat ini (kg) |
| `time` | Jam internal agen (menit sejak 00:00), mulai `GEROBAK_START` |
| `total_dist` | Akumulasi total jarak tempuh |
| `total_time_travel` | Akumulasi total waktu perjalanan (menit) |
| `total_time_load` | Akumulasi total waktu loading (menit) |
| `trips_to_tps` | Jumlah trip ke TPS |
| `trips_to_truk` | Jumlah kali transfer ke truk |
| `home_tps_id` | ID TPS zona kerja gerobak ini (diisi saat pre-assignment) |

| Metode | Keterangan |
|---|---|
| `move_to(tx, ty)` | Pindah ke koordinat target, update `time`, `total_dist`, `total_time_travel` |
| `collect_from_house(house, kg)` | Ambil `kg` kg dari rumah, update `load` dan `time` dengan loading time |
| `dump_to_tps(tps)` | Buang seluruh muatan ke TPS, reset `load = 0` |
| `dump_to_truck(truk, kg)` | Transfer `kg` kg ke truk, kurangi `load` gerobak |

#### Kelas `Truk`

| Atribut | Keterangan |
|---|---|
| `id`, `x`, `y` | Identitas dan posisi saat ini |
| `home_tps` | Objek TPS zona utama truk |
| `home_tps_id` | ID TPS zona kerja truk ini (diisi saat pre-assignment) |
| `load` | Muatan saat ini (kg) |
| `time` | Jam internal agen, mulai `TRUK_START` (08:00 = 480 menit) |
| `trips_to_tps` | Jumlah trip ke TPS |
| `received_from_gerobak_kg` | Total sampah yang diterima dari gerobak via transfer |

---

### Cell 5 — Definisi `generate_map()`

Mendefinisikan fungsi pembuat peta.

Cara kerja:
1. Generate 100 posisi rumah secara acak di grid menggunakan `random.uniform`
2. Setiap posisi dicek keunikannya menggunakan `set`
3. Sampah per rumah di-random antara 0–7 kg
4. Setelah semua rumah selesai, generate 3 posisi TPS dari koordinat yang belum terpakai
5. Kapasitas tiap TPS di-random antara 400–500 kg

---

### Cell 6 — Inisialisasi Data + Pre-Assignment

Inisialisasi semua data acak, koordinat, dan menjalankan **tiga fase pre-assignment**.

```
random.seed()   ← acak berdasarkan waktu sistem
  └─ random.randint(5, 7)            → NUM_GEROBAK
  └─ random.randint(2, 4)            → NUM_TRUK
  └─ generate_map()
       └─ random.uniform × 100       → posisi (x,y) rumah
       └─ random.uniform × 100       → sampah tiap rumah
       └─ random.uniform × 3         → posisi (x,y) TPS
       └─ random.uniform × 3         → kapasitas tiap TPS
  └─ random.uniform × NUM_GEROBAK    → posisi awal tiap gerobak
```

Setelah generate, disimpan snapshot koordinat untuk verifikasi:

```python
_snapshot_houses  = {h.id: (h.x, h.y) for h in houses}
_snapshot_tps     = {t.id: (t.x, t.y) for t in tps_list}
_snapshot_gerobak = {g.id: (g.x, g.y) for g in gerobak_list}
```

Kemudian dijalankan pre-assignment:

```
Fase 1 → assign_houses_to_tps()   : TPS pilih rumah terdekat, kuota merata
Fase 2 → recruit_gerobak_to_tps() : TPS rekrut gerobak terdekat, Round-Robin
Fase 3 → assign_truk_to_tps()     : 1 truk per TPS, ekstra ke TPS terbesar
```

---

### Cell 7 — Visualisasi Peta Penduduk

Menampilkan peta desa **sebelum** simulasi menggunakan `matplotlib` scatter plot.

Lihat penjelasan visual lengkap di [Bagian 7.1](#71-visualisasi-peta-penduduk-cell-7).

---

### Cell 8 — Fungsi Heuristik & Pre-Assignment

Berisi fungsi heuristik inti dan fungsi pre-assignment baru.

| Fungsi | Kategori | Keterangan |
|---|---|---|
| `nearest_tps(pos, tps_list)` | Greedy Nearest Feasible | Temukan TPS terdekat berkapasitas |
| `nearest_house(pos, houses)` | Nearest Neighbor | Temukan rumah terdekat dari daftar |
| `cost_benefit_transfer(g, t, tps_list)` | Cost-Benefit Analysis | Transfer ke truk atau ke TPS? |
| `greedy_batch_plan(truk, houses)` | Greedy Capacity Fill | Rencanakan batch rumah untuk truk |
| `assign_houses_to_tps(houses, tps_list)` | **Pre-Assignment** | Penjatahan rumah ke TPS (Nearest N) |
| `recruit_gerobak_to_tps(gerobak_list, tps_list, houses)` | **Pre-Assignment** | TPS rekrut gerobak terdekat |
| `assign_truk_to_tps(truk_list, tps_list, houses)` | **Pre-Assignment** | Assign truk ke TPS |
| `cari_rumah_gerobak(g, houses)` | **Zona Filter** | Cari rumah hanya di zona TPS sendiri |
| `cari_rumah_truk(t, houses)` | **Work Stealing** | Zona sendiri dulu, baru lintas zona |

---

### Cell 9 — Simulasi Utama (Concurrent Event-Driven + Penjatahan)

Cell dimulai dengan **reset state** seluruh agen, lalu menjalankan **satu loop concurrent** untuk semua agen.

**Reset state sebelum simulasi:**
- `house.trash_remaining = house.trash_initial` untuk semua rumah
- `tps.stored = 0` untuk semua TPS
- `all_logs = []` dikosongkan agar tidak menumpuk dari run sebelumnya
- Semua agen dikembalikan ke posisi awal dengan `time`, `load`, `total_dist` di-nol-kan

**Loop Concurrent (satu `while` loop untuk semua agen):**

```python
agent_type, idx, agent = min(candidates, key=lambda x: x[2].time)
```

- **Aksi Gerobak** — hanya mencari rumah di zona `home_tps_id`-nya sendiri melalui `cari_rumah_gerobak()`. Tidak ada Work Stealing.
- **Aksi Truk** — prioritas zona `home_tps_id` sendiri. Jika zona bersih → Work Stealing: bantu zona lain.
- **Transfer Gerobak → Truk** — terjadi saat berpapasan (radius < 5 satuan) dan *cost-benefit analysis* menyatakan transfer lebih hemat.

---

### Cell 10 — Laporan Hasil Simulasi

Mencetak laporan terstruktur ke console:

1. Laporan per truk: jarak, waktu perjalanan, waktu loading, total waktu operasi, jam selesai, jumlah trip, sampah dibuang, sisa, **bertemu gerobak** (Ya/Tidak), **transfer dari gerobak** (kg)
2. Total semua truk
3. Laporan per gerobak: jarak, waktu, trip ke TPS, transfer ke truk, sisa, **zona TPS**
4. Total semua gerobak
5. Status tiap TPS dengan progress bar ASCII (`█░`)
6. Sisa sampah rumah tangga (jumlah rumah, top 5 terbanyak)
7. Neraca sampah lengkap + persentase efisiensi
8. **Ringkasan akhir**: total iterasi, total event, jam seluruh operasi selesai, progres rumah (terambil/total)

---

### Cell 11 — Report Transparansi Pergerakan

Mencetak log pergerakan dalam tiga format:
1. **Per aktor** — semua event dari satu agen dikelompokkan bersama
2. **Kronologi gabungan** — semua event diurutkan berdasarkan waktu `HH:MM`, memperlihatkan seluruh agen berjalan bersamaan
3. **Ringkasan Transfer Gerobak → Truk** — tabel: jam kejadian, gerobak pengirim, truk penerima, berat transfer, total keseluruhan

---

### Cell 12 — Visualisasi Hasil 4 Panel

Menampilkan empat grafik sekaligus. Penjelasan lengkap di [Bagian 7.2](#72-visualisasi-hasil--4-panel-cell-12).

---

## 5. Algoritma Heuristik & Penjatahan

Program menggunakan dua lapisan algoritma: **Pre-Assignment** (sebelum simulasi) dan **Heuristik Routing** (saat simulasi berlangsung).

---

### 5.1 Pre-Assignment — Penjatahan Wilayah

**Kategori:** Quota-Based Spatial Assignment

Sebelum simulasi dimulai, seluruh rumah, gerobak, dan truk dibagi ke dalam tiga zona berdasarkan TPS sebagai pusat wilayah.

#### Fase 1 — Assign Rumah ke TPS (Nearest N)

Setiap TPS memilih rumah-rumah terdekat hingga kuota terpenuhi (`ceil(100/3) = 34`). Rumah yang sudah dipilih tidak bisa dipilih TPS lain.

```python
quota = math.ceil(len(houses) / len(tps_list))  # = 34
for tps in tps_list:
    while count < quota and unassigned:
        best = min(unassigned, key=lambda h: euclidean(tps.pos, h.pos))
        best.assigned_tps = tps.id
        unassigned.remove(best)
```

**Mengapa bukan Voronoi/Kluster?** Kluster berbasis jarak akan menghasilkan zona tidak merata bila dua TPS kebetulan berdekatan. Nearest N dengan kuota tetap tidak bergantung pada posisi relatif antar TPS.

#### Fase 2 — TPS Rekrut Gerobak Terdekat (Round-Robin)

TPS bertindak sebagai *recruiter* — memilih gerobak berdasarkan jarak dari posisi spawn gerobak. TPS dengan lebih banyak rumah mendapat jatah gerobak lebih banyak.

```
Jatah: modal 1 gerobak per TPS, sisa dibagi Round-Robin dari TPS terbesar.

Contoh (7 gerobak, TPS-1=34, TPS-2=33, TPS-3=33):
  Jatah: TPS-1=3, TPS-2=2, TPS-3=2

  Ronde 1: TPS-1 klaim gerobak terdekat → TPS-2 → TPS-3
  Ronde 2: TPS-1 → TPS-2 → TPS-3
  Ronde 3: TPS-1 (terakhir)
```

#### Fase 3 — Assign Truk ke TPS

| NUM_TRUK | Distribusi |
|---|---|
| **2 truk** | TPS terbesar → 1 truk, TPS ke-2 → 1 truk, TPS terkecil → 0 truk |
| **3 truk** | Masing-masing TPS → 1 truk |
| **4 truk** | TPS terbesar → 2 truk, TPS lainnya → 1 truk |

---

### 5.2 Nearest Neighbor — Routing Gerobak (di Zona Sendiri)

**Digunakan oleh:** Gerobak sampah  
**Kategori:** Konstruktif Greedy / Nearest Neighbor Search

Setiap kali gerobak selesai mengambil sampah, gerobak mencari rumah terdekat berikutnya — **namun hanya dari rumah yang `assigned_tps` == `home_tps_id` gerobak tersebut**.

```python
def cari_rumah_gerobak(g, houses):
    zona = [h for h in houses if h.assigned_tps == g.home_tps_id
            and h.trash_remaining > 0.01]
    return min(zona, key=lambda h: euclidean(g.pos, (h.x, h.y))) if zona else None
```

**Tidak ada Work Stealing untuk gerobak** — gerobak berhenti ketika zonanya bersih, meski masih ada waktu tersisa. Alasan: kapasitas kecil (15 kg) dan jam operasi lebih pendek; lintas zona tidak worth it dari sisi efisiensi.

---

### 5.3 Greedy Capacity Fill — Routing Truk + Work Stealing

**Digunakan oleh:** Truk sampah  
**Kategori:** Greedy Batch + Work Stealing

Truk merencanakan batch hingga 6 rumah terdekat, **diprioritaskan dari zona sendiri dulu**. Jika zona sendiri sudah bersih, truk berpindah ke zona mana saja yang masih ada sampahnya (*Work Stealing*).

```python
zona_sendiri = [h for h in houses if h.assigned_tps == t.home_tps_id
                and h.trash_remaining > 0.01]
if zona_sendiri:
    plan = greedy_batch_plan(t, zona_sendiri)   # zona sendiri
else:
    plan = greedy_batch_plan(t, houses)         # work stealing
```

**Mengapa truk boleh Work Stealing tapi gerobak tidak?**  
Truk berkapasitas 200 kg dan beroperasi hingga 17:00 (2 jam lebih lama dari gerobak). Perjalanan lintas zona jauh lebih worth it untuk truk karena sekali jalan bisa mengangkut banyak sampah.

---

### 5.4 Cost-Benefit Analysis — Keputusan Transfer Gerobak → Truk

**Digunakan oleh:** Gerobak (saat berpapasan dengan truk)  
**Kategori:** Cost-Benefit Heuristic / Decision Rule

```
Skenario A (transfer ke truk):   Waktu_A = travel(gerobak → truk) + loading
Skenario B (gerobak langsung ke TPS): Waktu_B = travel(gerobak → TPS) + loading

Jika dist(gerobak, truk) < dist(gerobak, TPS) × 0.75 dan gerobak.load >= 3 kg:
    → Pilih transfer (truk minimal 25% lebih dekat dari TPS)
```

**Guard conditions:**
- `truk.load + gerobak.load > CAP_TRUK * 0.98` → skip (truk hampir penuh)
- `gerobak.load < 1.0` → skip (muatan terlalu kecil, tidak worth it)

---

### 5.5 Greedy Nearest Feasible — Pemilihan TPS Tujuan

**Digunakan oleh:** Gerobak dan Truk (saat hendak membuang muatan)

```python
def nearest_tps(pos, tps_list):
    candidates = [t for t in tps_list if t.available > 0.5]
    return min(candidates, key=lambda t: euclidean(pos, (t.x, t.y)))
```

Jika semua TPS penuh, fungsi mengembalikan `None` dan agen dicatat sebagai error.

---

### Ringkasan Algoritma

| No | Algoritma | Kapan Dijalankan | Digunakan Oleh | Tujuan |
|---|---|---|---|---|
| 5.1a | Nearest N Assignment | Pre-simulasi | TPS → Rumah | Batasi 34/33/33 rumah per TPS |
| 5.1b | Round-Robin Rekrutmen | Pre-simulasi | TPS → Gerobak | Distribusi gerobak adil berdasarkan beban |
| 5.1c | Assign Truk | Pre-simulasi | TPS → Truk | 1 truk per TPS, ekstra ke TPS terbesar |
| 5.2 | Nearest Neighbor (Zona) | Saat simulasi | Gerobak | Pilih rumah terdekat di zona sendiri |
| 5.3 | Greedy Batch + Work Stealing | Saat simulasi | Truk | Batch zona sendiri, lalu bantu zona lain |
| 5.4 | Cost-Benefit Transfer | Saat simulasi | Gerobak | Transfer ke truk atau ke TPS? |
| 5.5 | Greedy Nearest Feasible | Saat simulasi | Gerobak & Truk | Pilih TPS terdekat yang masih ada kapasitas |

---

## 6. Rumus & Perhitungan

### 6.1 Jarak Euclidean

```
d(A, B) = sqrt((xB - xA)^2 + (yB - yA)^2)
```

**Contoh:** Gerobak di (10, 5) menuju rumah di (13, 9):
```
d = sqrt((13-10)^2 + (9-5)^2) = sqrt(9 + 16) = sqrt(25) = 5.0 satuan jarak
```

---

### 6.2 Waktu Tempuh Gerobak

```
T_travel_gerobak = jarak × 3 menit/satuan
```

**Contoh:** Jarak 5 satuan → `5 × 3 = 15 menit`

---

### 6.3 Waktu Tempuh Truk

```
T_travel_truk = jarak × (3/5) = jarak × 0.6 menit/satuan
```

**Contoh:** Jarak 10 satuan → `10 × 0.6 = 6 menit`

---

### 6.4 Waktu Loading Gerobak

Berlaku untuk mengambil dari rumah dan transfer ke truk.

```
T_load_gerobak = berat_kg × 2 menit/kg
```

**Contoh:** Mengambil 6 kg → `6 × 2 = 12 menit`

---

### 6.5 Waktu Loading Truk

Berlaku untuk membuang muatan ke TPS.

```
T_load_truk = (berat_kg / 10) × 2 = berat_kg / 5 menit
```

**Contoh:** Membuang 120 kg ke TPS → `(120/10) × 2 = 24 menit`

---

### 6.6 Kuota Rumah per TPS

```
kuota = ceil(NUM_HOUSES / NUM_TPS) = ceil(100 / 3) = 34
```

TPS-1 mendapat 34 rumah, TPS-2 dan TPS-3 masing-masing 33 rumah (sisa 1 dialokasikan ke TPS dengan kuota belum penuh).

---

### 6.7 Total Waktu Operasi per Agen

```
T_operasi = min(agen.time, batas_jam) - jam_mulai
```

Di mana `batas_jam` = `GEROBAK_END` (900) atau `TRUK_END` (1020).

---

### 6.8 Waktu Idle

```
T_idle = T_operasi - T_travel - T_load
```

---

### 6.9 Efisiensi Pengangkutan

```
Efisiensi ke TPS (%) = (total_di_TPS / total_sampah_awal) × 100

Sampah terangkut (%) = (di_TPS + sisa_gerobak + sisa_truk) / total_awal × 100
```

---

### 6.10 Neraca Sampah (Verifikasi Konservasi)

```
Total awal = di TPS + sisa gerobak + sisa truk + sisa di rumah
```

Jika selisih > 0.01 kg, ada bug di logika pengurangan sampah.

---

## 7. Dokumentasi Visualisasi

### 7.1 Visualisasi Peta Penduduk (Cell 7)

**Judul:** *Peta Desa – Distribusi Sampah & Lokasi TPS*  
**Ditampilkan:** Sebelum simulasi dimulai

| Elemen Visual | Representasi |
|---|---|
| Titik kecil berwarna | Rumah penduduk |
| Warna titik kuning | Rumah dengan sampah sedikit (mendekati 0 kg) |
| Warna titik merah tua | Rumah dengan sampah banyak (mendekati 7 kg) |
| Colorbar di sisi kanan | Skala warna: 0–7 kg |
| Kotak hijau tua | TPS-1 |
| Kotak biru tua | TPS-2 |
| Kotak merah tua | TPS-3 |

---

### 7.2 Visualisasi Hasil — 4 Panel (Cell 12)

**Judul:** *Hasil Simulasi Pengangkutan Sampah*

#### Panel Kiri Atas — Peta Akhir Desa

| Elemen Visual | Representasi |
|---|---|
| Titik hijau | Rumah sudah bersih (`trash_remaining < 0.1 kg`) |
| Titik oranye | Rumah dengan sisa sampah 0.1 – 3 kg |
| Titik merah | Rumah dengan sisa sampah ≥ 3 kg (belum tertangani) |
| Segitiga biru `^` | Posisi **akhir** gerobak |
| Berlian ungu `D` | Posisi **akhir** truk |

#### Panel Kanan Atas — Jarak Tempuh per Agen

Bar chart total jarak tempuh masing-masing agen. Batang hijau = Gerobak, Batang biru = Truk.

#### Panel Kiri Bawah — Status Kapasitas TPS

Stacked bar chart: batang oranye (sampah tersimpan) + abu-abu (sisa kapasitas).

#### Panel Kanan Bawah — Breakdown Waktu per Agen

Stacked bar chart komposisi: biru (travel) + oranye (loading) + abu-abu (idle).

---

## 8. Cara Menjalankan

### Prasyarat

```bash
pip install jupyter matplotlib numpy
```

### Menjalankan Notebook

```bash
jupyter notebook Yogaaa.ipynb
```

Kemudian jalankan cell **secara berurutan dari atas ke bawah**.

### Urutan Eksekusi yang Wajib Dipatuhi

```
Cell 1  → Konstanta
Cell 2  → Helper functions
Cell 3  → Data classes (House, TPS, LogEntry)
Cell 4  → Agent classes (Gerobak, Truk)
Cell 5  → Definisi generate_map()
Cell 6  → Inisialisasi + Pre-Assignment  ← penting: jalankan sekali saja
Cell 7  → Visualisasi peta awal
Cell 8  → Fungsi heuristik + pre-assignment
Cell 9  → Simulasi utama
Cell 10 → Laporan hasil
Cell 11 → Log pergerakan
Cell 12 → Visualisasi hasil 4 panel
```

### Mengubah Konfigurasi

| Yang Ingin Diubah | Caranya |
|---|---|
| Hasil simulasi berbeda | Jalankan ulang dari Cell 6 (seed berubah otomatis) |
| Lebih banyak rumah | Ubah `NUM_HOUSES` di Cell 1 |
| Kapasitas gerobak/truk berbeda | Ubah `CAP_GEROBAK` / `CAP_TRUK` di Cell 1 |
| Jam operasi berbeda | Ubah `GEROBAK_START/END` atau `TRUK_START/END` di Cell 1 |

---

## 9. Contoh Output

### Pre-Assignment (Diprint Saat Cell 6 Dijalankan)

```
Menjalankan pre-assignment...

Fase 1 — Assign rumah ke TPS (Nearest N, kuota merata):
  TPS-1 (27.3,41.7) -> 34 rumah
  TPS-2 (7.4,6.4)   -> 33 rumah
  TPS-3 (44.9,39.8) -> 33 rumah

Fase 2 — TPS rekrut gerobak terdekat (Round-Robin):
  TPS-1 -> Gerobak [4, 1, 6] (3 gerobak)
  TPS-2 -> Gerobak [2, 7]    (2 gerobak)
  TPS-3 -> Gerobak [3, 5]    (2 gerobak)

Fase 3 — Assign truk ke TPS:
  TPS-1 -> Truk [1] (1 truk)
  TPS-2 -> Truk [2] (1 truk)
  TPS-3 -> Truk []  (0 truk)   ← Work Stealing dari truk lain bila perlu
```

### Ringkasan Simulasi

```
Simulasi selesai (12453 iterasi)
Total event tercatat: 142

Seluruh operasi selesai pada : 14:37
Sisa Rumah (belum terambil)  : 0 rumah
Sisa Rumah (terambil)        : 100/100 completed
```

### Contoh Log Kronologi (Terlihat Bersamaan)

```
06:00   Gerobak-1    MULAI        Posisi awal (43.4,11.7) | zona TPS-1
06:00   Gerobak-2    MULAI        Posisi awal (13.5,6.7)  | zona TPS-2
06:11   Gerobak-2    AMBIL_SAMPAH Rumah-15 (14.5,4.0) ambil 1.63kg ...
06:18   Gerobak-1    AMBIL_SAMPAH Rumah-39 (43.5,14.9) ambil 4.47kg ...
08:00   Truk-1       MULAI        Mulai dari TPS-1 (27.3,41.7)
08:00   Truk-2       MULAI        Mulai dari TPS-2 (7.4,6.4)
09:32   Gerobak-2    TITIP_TRUK   Transfer 5.89kg ke Truk-1 ...
```

### Contoh Ringkasan Transfer

```
═══════════════════════════════════════════════════════════════════
RINGKASAN TRANSFER GEROBAK → TRUK
═══════════════════════════════════════════════════════════════════
Jam      Dari         Ke           Transfer     Detail
───────────────────────────────────────────────────────────────────
09:32    Gerobak-2    Truk-1       5.89      kg  Transfer 5.89kg ke Truk-1
───────────────────────────────────────────────────────────────────
Total kejadian transfer : 1 kali
Total sampah ditransfer : 5.89 kg
```

---

## 10. Catatan Teknis & Desain Decision

### Mengapa Penjatahan (Quota), Bukan Kluster/Voronoi?

Kluster berbasis jarak (Voronoi) menghasilkan zona tidak merata bila dua TPS kebetulan berdekatan — zona mereka akan menjadi strip sempit sementara TPS ketiga menguasai hampir seluruh peta. Sistem **Nearest N dengan kuota tetap** tidak bergantung pada posisi relatif TPS: 34/33/33 rumah selalu terpenuhi terlepas dari letak TPS di peta yang acak.

---

### Mengapa TPS yang Merekrut Gerobak (Bukan Sebaliknya)?

Karena posisi spawn gerobak bersifat acak, jika gerobak yang memilih TPS maka gerobak yang spawn jauh di ujung peta bisa saja ditugaskan ke TPS di sisi berlawanan. Dengan **TPS sebagai recruiter**, gerobak yang sudah dekat secara alami masuk ke zona yang tepat.

---

### Mengapa Truk Boleh Work Stealing Tapi Gerobak Tidak?

| Aspek | Gerobak | Truk |
|---|---|---|
| Kapasitas | 15 kg | 200 kg |
| Jam selesai | 15:00 | 17:00 |
| Worth it lintas zona? | Tidak (kecil, pendek) | Ya (besar, panjang) |

Gerobak yang selesai di zona sendiri lebih baik berhenti daripada menempuh jarak jauh untuk mengangkut sampah yang sedikit. Truk dengan kapasitas 200 kg bisa mengambil banyak sampah dari zona lain dalam satu trip — efisiensi per km-nya jauh lebih tinggi.

---

### Concurrent Event-Driven Simulation

Seluruh agen dikelola dalam **satu `while` loop** bersama. Setiap iterasi, agen dengan nilai `time` terkecil dipilih untuk satu langkah berikutnya — mirip *priority queue*.

```
while not (semua_selesai):
    agent = min(semua_agen_aktif, key=lambda a: a.time)
    jalankan_satu_langkah(agent)
```

Gerobak dan truk berada dalam satu *timeline*, sehingga posisi truk bisa dibandingkan dengan posisi gerobak secara *real-time* → transfer bisa terjadi kapan saja saat mereka berpapasan.

---

### Hard Stop Waktu Operasi

Setiap setelah operasi `move_to()` dan `collect_from_house()`, program selalu mengecek:

```python
if g.time >= GEROBAK_END:
    gerobak_done[idx] = True
    g.log("SELESAI_WAKTU", ...)
    continue
```

Ini memastikan simulasi **langsung berhenti** di jam operasi meski sedang di tengah aksi.

---

### Snapshot Verification

Tiga `dict` snapshot disimpan setelah inisialisasi untuk verifikasi koordinat:

```python
_snapshot_houses  = {h.id: (h.x, h.y) for h in houses}
_snapshot_tps     = {t.id: (t.x, t.y) for t in tps_list}
_snapshot_gerobak = {g.id: (g.x, g.y) for g in gerobak_list}
```

Diverifikasi sebelum simulasi dan sebelum visualisasi untuk mencegah bug koordinat yang tidak terdeteksi.

---