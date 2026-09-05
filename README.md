# Pemantau Kualitas Udara (Air Quality Monitor)

Aplikasi desktop berbasis Python Tkinter untuk memantau indeks kualitas udara (AQI) dan konsentrasi polutan realtime di berbagai kota dunia menggunakan API Ninjas Air Quality.

## Kenapa Ini Dibuat

Aplikasi desktop GUI sederhana kerap rentan terhadap race condition: pengguna menekan tombol atau tombol Enter berulang kali saat latensi jaringan tinggi, memicu multi-thread liar yang saling menimpa data (*stale response*), membekukan antarmuka (*UI freezing*), atau crash karena penanganan error jaringan yang minim. 

Proyek ini dibangun dengan arsitektur modular, thread-safe, dan zero-dependency tambahan (menggunakan Standard Library Python) guna memastikan keandalan pemantauan data lingkungan secara realtime.

## Cara Kerja (Under the Hood)

- **Pemisahan Layer API Client**: Seluruh komunikasi HTTP dan parsing respon diisolasi ke dalam class `AirQualityClient`, menghasilkan struktur data immutable `AirQualityReport` dan `PollutantItem`.
- **Atomic State Guarding**: Pencegahan spam tombol "Cari" dan tombol Enter melalui pengecekan status loading atomik sebelum thread pekerja dijalankan.
- **Request Sequencing**: Setiap request diberi ID monotonik bertambah. Respon dari request lama yang terlambat secara otomatis diabaikan agar tidak menimpa data kota yang baru dicari.
- **Penanganan Error Terstruktur**: Memetakan respon HTTP ke exception spesifik (`CityNotFoundError`, `AuthenticationError`, `RateLimitError`, `NetworkTimeoutError`) dengan pesan yang jelas kepada pengguna.
- **Zero-Trust Credential Isolation**: Tidak menyimpan hardcoded API key dalam kode sumber. API key dibaca secara aman dari environment variable sistem (`API_NINJAS_KEY` / `API_KEY`) atau file `.env` lokal.

## Parameter Polutan

| Parameter | Polutan | Satuan |
|---|---|---|
| **PM2.5** | Partikel Halus | ug/m3 |
| **PM10** | Partikel Kasar | ug/m3 |
| **O3** | Ozon Permukaan | ug/m3 |
| **NO2** | Nitrogen Dioksida | ug/m3 |
| **SO2** | Sulfur Dioksida | ug/m3 |
| **CO** | Karbon Monoksida | ug/m3 |

## Konfigurasi API Key

Aplikasi ini memerlukan API Key dari **API Ninjas**. Pengguna yang meng-clone repository ini wajib membuat API Key sendiri:

1. **Daftar Akun**: Buka [https://api-ninjas.com/](https://api-ninjas.com/) dan buat akun gratis.
2. **Salin API Key**: Buka dashboard akun Anda di API Ninjas lalu salin API Key yang tertera.
3. **Buat File `.env`**:
   Salin template `.env.example` ke `.env`:
   ```bash
   cp .env.example .env
   ```
4. **Isi API Key**:
   Buka file `.env` dan masukkan API Key Anda:
   ```env
   API_NINJAS_KEY=api_key_anda_disini
   ```
   > File `.env` secara default sudah tercatat dalam `.gitignore` sehingga credential Anda tidak akan bocor ke GitHub.

## Quickstart

### 1. Prasyarat
Python 3.10+ (sudah menyertakan modul standar `tkinter` dan `urllib`).

### 2. Jalankan Aplikasi
```bash
# Clone repository
git clone https://github.com/yanzyuyu/kuallitasudara.git
cd kuallitasudara

# Buat dan isi file .env sesuai panduan di atas
cp .env.example .env

# Jalankan GUI
python app.py
```

### 3. Eksekusi Unit Test
```bash
python -m unittest test_app.py
```

Output eksekusi:
```bash
$ python -m unittest test_app.py
........
----------------------------------------------------------------------
Ran 8 tests in 3.126s

OK
```

## Struktur Proyek

```
kuallitasudara/
├── app.py          # Implementasi GUI Tkinter & AirQualityClient
├── test_app.py     # Unit test otomatis untuk client dan klasifikasi AQI
├── .env.example    # Template konfigurasi environment variable
├── .gitignore      # Aturan ignorir cache, file konfigurasi, dan scratch
└── README.md       # Dokumentasi teknis proyek
```
