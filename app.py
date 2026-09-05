from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://api.api-ninjas.com/v1/airquality"

AQI_LEVELS = [
    (50, "Baik", "#10b981", "#ffffff"),
    (100, "Sedang", "#f59e0b", "#000000"),
    (150, "Tidak Sehat (Sensitif)", "#f97316", "#ffffff"),
    (200, "Tidak Sehat", "#ef4444", "#ffffff"),
    (300, "Sangat Tidak Sehat", "#8b5cf6", "#ffffff"),
    (float("inf"), "Berbahaya", "#7f1d1d", "#ffffff"),
]

POLLUTANT_CATALOG = [
    ("PM2.5", "Partikel Halus (PM2.5)", "ug/m3"),
    ("PM10", "Partikel Kasar (PM10)", "ug/m3"),
    ("O3", "Ozon (O3)", "ug/m3"),
    ("NO2", "Nitrogen Dioksida (NO2)", "ug/m3"),
    ("SO2", "Sulfur Dioksida (SO2)", "ug/m3"),
    ("CO", "Karbon Monoksida (CO)", "ug/m3"),
]

class AirQualityError(Exception):
    pass

class CityNotFoundError(AirQualityError):
    pass

class AuthenticationError(AirQualityError):
    pass

class RateLimitError(AirQualityError):
    pass

class NetworkTimeoutError(AirQualityError):
    pass

@dataclass(frozen=True)
class PollutantItem:
    code: str
    label: str
    concentration: str
    aqi: str

@dataclass(frozen=True)
class AirQualityReport:
    city: str
    overall_aqi: int | None
    pollutants: list[PollutantItem]
    fetched_at: datetime

def parse_local_env(env_path: Path) -> dict[str, str]:
    if not env_path.is_file():
        return {}
    records = {}
    try:
        with open(env_path, "r", encoding="utf-8") as stream:
            for line in stream:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                records[key.strip()] = val.strip().strip("\"'")
    except OSError:
        pass
    return records

def resolve_api_key() -> str:
    env_file = Path(__file__).resolve().parent / ".env"
    local_vars = parse_local_env(env_file)
    return (
        os.environ.get("API_NINJAS_KEY")
        or os.environ.get("API_KEY")
        or local_vars.get("API_NINJAS_KEY")
        or local_vars.get("API_KEY")
        or ""
    )

def get_aqi_info(aqi_val: int | float | None) -> tuple[str, str, str]:
    if aqi_val is None:
        return "-", "#64748b", "#ffffff"
    for threshold, label, bg, fg in AQI_LEVELS:
        if aqi_val <= threshold:
            return label, bg, fg
    return "Berbahaya", "#7f1d1d", "#ffffff"

class AirQualityClient:
    def __init__(self, api_key: str | None = None, timeout_seconds: float = 10.0):
        self.api_key = api_key if api_key is not None else resolve_api_key()
        self.timeout_seconds = timeout_seconds

    def fetch(self, city: str) -> AirQualityReport:
        if not self.api_key:
            raise AuthenticationError(
                "API Key belum dikonfigurasi. Dapatkan API Key gratis di https://api-ninjas.com/ dan masukkan ke file .env"
            )

        normalized_city = city.strip()
        if not normalized_city:
            raise ValueError("Nama kota tidak boleh kosong")

        query = urllib.parse.urlencode({"city": normalized_city})
        url = f"{BASE_URL}?{query}"
        request = urllib.request.Request(
            url,
            headers={
                "X-Api-Key": self.api_key,
                "User-Agent": "AirQualityMonitor/2.0",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            self._handle_http_error(exc)
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise NetworkTimeoutError("Koneksi timeout saat menghubungi server API")
            raise AirQualityError(f"Koneksi jaringan gagal: {exc.reason}")
        except TimeoutError:
            raise NetworkTimeoutError("Koneksi timeout saat menghubungi server API")
        except json.JSONDecodeError:
            raise AirQualityError("Format data respon server tidak valid")

        return self._build_report(normalized_city, payload)

    def _handle_http_error(self, exc: urllib.error.HTTPError) -> None:
        detail = ""
        try:
            body = json.loads(exc.read().decode("utf-8"))
            if isinstance(body, dict):
                detail = body.get("error", "")
        except Exception:
            pass

        if exc.code == 400:
            lowered = detail.lower()
            if "city" in lowered:
                raise CityNotFoundError(detail or "Kota tidak ditemukan")
            if "key" in lowered:
                raise AuthenticationError(detail or "API Key tidak valid")
            raise AirQualityError(detail or "Permintaan tidak valid")

        if exc.code in (401, 403):
            raise AuthenticationError("Akses ditolak: periksa validitas API Key")

        if exc.code == 429:
            raise RateLimitError("Batas kuota request API Ninjas telah tercapai")

        if exc.code >= 500:
            raise AirQualityError(f"Server API Ninjas sedang mengalami gangguan (HTTP {exc.code})")

        raise AirQualityError(detail or f"Kesalahan HTTP {exc.code}")

    def _build_report(self, city: str, payload: dict) -> AirQualityReport:
        if not isinstance(payload, dict):
            raise AirQualityError("Format payload tidak valid")

        overall_val = payload.get("overall_aqi")
        overall_aqi = int(overall_val) if isinstance(overall_val, (int, float)) else None

        items: list[PollutantItem] = []
        for code, label, _ in POLLUTANT_CATALOG:
            node = payload.get(code)
            if isinstance(node, dict):
                raw_conc = node.get("concentration")
                raw_aqi = node.get("aqi")
                conc_text = f"{raw_conc:.2f}" if isinstance(raw_conc, (int, float)) else str(raw_conc or "-")
                aqi_text = str(raw_aqi) if raw_aqi is not None else "-"
                items.append(
                    PollutantItem(
                        code=code,
                        label=label,
                        concentration=conc_text,
                        aqi=aqi_text,
                    )
                )

        return AirQualityReport(
            city=city,
            overall_aqi=overall_aqi,
            pollutants=items,
            fetched_at=datetime.now(),
        )

class AirQualityApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.client = AirQualityClient()
        self.is_loading = False
        self.active_request_id = 0

        self.root.title("Air Quality Monitor")
        self.root.configure(bg="#f8fafc")
        self.center_window(560, 680)
        self.root.minsize(500, 600)

        self.init_styles()
        self.build_ui()
        self.fetch_data()

    def center_window(self, width: int, height: int):
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        pos_x = max(0, (screen_w - width) // 2)
        pos_y = max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    def init_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", background="#f8fafc", foreground="#1e293b", font=("Segoe UI", 10))
        style.configure(
            "Treeview",
            font=("Segoe UI", 10),
            rowheight=32,
            background="#ffffff",
            fieldbackground="#ffffff",
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background="#e2e8f0",
            foreground="#334155",
            relief="flat",
        )
        style.map(
            "Treeview",
            background=[("selected", "#e2e8f0")],
            foreground=[("selected", "#0f172a")],
        )

    def build_ui(self):
        header_frame = tk.Frame(self.root, bg="#0f172a", padx=20, pady=18)
        header_frame.pack(fill=tk.X)

        title_lbl = tk.Label(
            header_frame,
            text="Pemantau Kualitas Udara",
            font=("Segoe UI", 16, "bold"),
            fg="#f8fafc",
            bg="#0f172a",
        )
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(
            header_frame,
            text="Data realtime indeks polusi udara berbasis API Ninjas",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#0f172a",
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        search_frame = tk.Frame(self.root, bg="#f8fafc", padx=20, pady=14)
        search_frame.pack(fill=tk.X)

        lbl = tk.Label(search_frame, text="Kota:", font=("Segoe UI", 10, "bold"), bg="#f8fafc", fg="#334155")
        lbl.pack(side=tk.LEFT, padx=(0, 10))

        self.city_var = tk.StringVar(value="London")
        self.city_entry = tk.Entry(
            search_frame,
            textvariable=self.city_var,
            font=("Segoe UI", 11),
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground="#cbd5e1",
        )
        self.city_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=5)
        self.city_entry.bind("<Return>", self._on_return_pressed)

        self.search_btn = tk.Button(
            search_frame,
            text="Cari",
            command=self.fetch_data,
            font=("Segoe UI", 10, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief="flat",
            padx=18,
            pady=4,
            cursor="hand2",
        )
        self.search_btn.pack(side=tk.RIGHT)

        card_wrap = tk.Frame(self.root, bg="#f8fafc")
        card_wrap.pack(fill=tk.X, padx=20, pady=(0, 14))

        self.card = tk.Frame(card_wrap, bg="#ffffff", relief="solid", bd=1, highlightthickness=0)
        self.card.pack(fill=tk.X)

        self.card_inner = tk.Frame(self.card, bg="#ffffff", padx=18, pady=16)
        self.card_inner.pack(fill=tk.X)

        self.city_display = tk.Label(
            self.card_inner,
            text="London",
            font=("Segoe UI", 15, "bold"),
            bg="#ffffff",
            fg="#0f172a",
        )
        self.city_display.pack(anchor="w")

        aqi_container = tk.Frame(self.card_inner, bg="#ffffff", pady=8)
        aqi_container.pack(fill=tk.X)

        self.aqi_num = tk.Label(
            aqi_container,
            text="--",
            font=("Segoe UI", 40, "bold"),
            bg="#ffffff",
            fg="#2563eb",
        )
        self.aqi_num.pack(side=tk.LEFT, padx=(0, 14))

        badge_container = tk.Frame(aqi_container, bg="#ffffff")
        badge_container.pack(side=tk.LEFT, fill=tk.Y, pady=6)

        aqi_caption = tk.Label(
            badge_container,
            text="Indeks Keseluruhan (Overall AQI)",
            font=("Segoe UI", 9),
            bg="#ffffff",
            fg="#64748b",
        )
        aqi_caption.pack(anchor="w")

        self.aqi_status = tk.Label(
            badge_container,
            text="Memuat...",
            font=("Segoe UI", 10, "bold"),
            bg="#e2e8f0",
            fg="#334155",
            padx=10,
            pady=3,
        )
        self.aqi_status.pack(anchor="w", pady=(4, 0))

        table_frame = tk.Frame(self.root, bg="#f8fafc", padx=20)
        table_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("parameter", "conc", "aqi")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=6)
        self.tree.heading("parameter", text="Parameter Polutan", anchor="w")
        self.tree.heading("conc", text="Konsentrasi (ug/m3)", anchor="center")
        self.tree.heading("aqi", text="Nilai AQI", anchor="center")

        self.tree.column("parameter", anchor="w", width=220)
        self.tree.column("conc", anchor="center", width=140)
        self.tree.column("aqi", anchor="center", width=100)

        tree_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_bar = tk.Label(
            self.root,
            text="Siap",
            font=("Segoe UI", 9),
            bg="#e2e8f0",
            fg="#475569",
            anchor="w",
            padx=14,
            pady=7,
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def _on_return_pressed(self, _):
        if not self.is_loading:
            self.fetch_data()

    def set_loading_state(self, loading: bool):
        if loading:
            self.search_btn.config(state=tk.DISABLED, text="...")
            self.city_entry.config(state=tk.DISABLED)
            self.status_bar.config(text="Mengambil data dari server...")
        else:
            self.search_btn.config(state=tk.NORMAL, text="Cari")
            self.city_entry.config(state=tk.NORMAL)

    def fetch_data(self):
        if self.is_loading:
            return

        city = self.city_var.get().strip()
        if not city:
            messagebox.showwarning("Peringatan", "Masukkan nama kota terlebih dahulu.")
            return

        self.is_loading = True
        self.active_request_id += 1
        current_request_id = self.active_request_id

        self.set_loading_state(True)
        threading.Thread(
            target=self._worker,
            args=(current_request_id, city),
            daemon=True,
        ).start()

    def _worker(self, request_id: int, city: str):
        try:
            report = self.client.fetch(city)
            self.root.after(0, self._on_success, request_id, report)
        except CityNotFoundError as exc:
            self.root.after(0, self._on_error, request_id, city, str(exc), "warning")
        except (AuthenticationError, RateLimitError, NetworkTimeoutError, AirQualityError) as exc:
            self.root.after(0, self._on_error, request_id, city, str(exc), "error")
        except Exception as exc:
            self.root.after(0, self._on_error, request_id, city, f"Terjadi kesalahan tak terduga: {exc}", "error")

    def _on_success(self, request_id: int, report: AirQualityReport):
        if request_id != self.active_request_id:
            return
        self.is_loading = False
        self.set_loading_state(False)
        self.render_report(report)

    def _on_error(self, request_id: int, city: str, message: str, level: str):
        if request_id != self.active_request_id:
            return
        self.is_loading = False
        self.set_loading_state(False)
        self.render_error(city, message, level)

    def render_error(self, city: str, message: str, level: str):
        self.city_display.config(text=city.title())
        self.aqi_num.config(text="--", fg="#94a3b8")
        self.aqi_status.config(text="Gagal", bg="#fee2e2", fg="#991b1b")
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.status_bar.config(text=f"[Error] {message}")
        if level == "warning":
            messagebox.showwarning("Informasi", message)
        else:
            messagebox.showerror("Kesalahan", message)

    def render_report(self, report: AirQualityReport):
        self.city_display.config(text=report.city.title())

        overall = report.overall_aqi
        self.aqi_num.config(text=str(overall) if overall is not None else "--")

        status_text, bg_color, fg_color = get_aqi_info(overall)
        self.aqi_status.config(text=status_text, bg=bg_color, fg=fg_color)
        self.aqi_num.config(fg=bg_color)

        for item in self.tree.get_children():
            self.tree.delete(item)

        for pol in report.pollutants:
            self.tree.insert("", tk.END, values=(pol.label, pol.concentration, pol.aqi))

        timestamp = report.fetched_at.strftime("%H:%M:%S")
        self.status_bar.config(text=f"[OK] Diperbarui pukul {timestamp} untuk {report.city.title()}")

def main():
    root = tk.Tk()
    AirQualityApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
