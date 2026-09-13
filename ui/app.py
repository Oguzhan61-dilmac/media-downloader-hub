import os
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from typing import Optional, Dict, Any
import datetime

import customtkinter as ctk

from downloader.utils import (
    get_default_download_dir,
    load_saved_download_dir,
    save_download_dir,
    is_valid_url
)
from downloader.engine import DownloaderTask
from ui.theme import (
    APP_TITLE,
    APP_SUBTITLE,
    APP_VERSION,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    COLORS,
    FORMAT_OPTIONS,
)


class MediaDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Appearance configuration
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Window settings
        self.title(f"{APP_TITLE} {APP_VERSION}")
        self.geometry(f"{WINDOW_WIDTH}x740")
        self.minsize(740, 660)
        self.configure(fg_color=COLORS["bg_dark"])

        # Load saved download directory or fallback to default
        self.download_dir = load_saved_download_dir()
        self.current_task: Optional[DownloaderTask] = None
        self.is_downloading = False

        # Build Interface
        self._create_layout()

    def _create_layout(self):
        """Builds all UI components inside scrollable main container."""
        self.main_container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0
        )
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)

        self._build_header()
        self._build_url_card()
        self._build_options_card()
        self._build_auto_subtitle_card()
        self._build_progress_card()
        self._build_log_drawer()

    def _build_header(self):
        """Application header banner."""
        header_frame = ctk.CTkFrame(
            self.main_container,
            fg_color=COLORS["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["card_border"]
        )
        header_frame.pack(fill="x", pady=(0, 15), padx=2)

        title_label = ctk.CTkLabel(
            header_frame,
            text=f"🎬 {APP_TITLE}",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=COLORS["accent"]
        )
        title_label.pack(anchor="w", padx=20, pady=(15, 2))

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text=f"{APP_SUBTITLE} • Rutube, YouTube & Yapay Zeka Türkçe Altyazı",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLORS["text_secondary"]
        )
        subtitle_label.pack(anchor="w", padx=20, pady=(0, 15))

    def _build_url_card(self):
        """Video URL Input Card with Paste & Clear controls."""
        card = ctk.CTkFrame(
            self.main_container,
            fg_color=COLORS["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["card_border"]
        )
        card.pack(fill="x", pady=(0, 15), padx=2)

        card_title = ctk.CTkLabel(
            card,
            text="🔗 Video Bağlantısı (URL)",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        card_title.pack(anchor="w", padx=18, pady=(15, 8))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(0, 15))

        self.url_entry = ctk.CTkEntry(
            row,
            placeholder_text="https://rutube.ru/video/... veya https://youtube.com/watch?v=...",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color=COLORS["input_bg"],
            border_color=COLORS["input_border"],
            height=40
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        paste_btn = ctk.CTkButton(
            row,
            text="📋 Yapıştır",
            width=90,
            height=40,
            fg_color=COLORS["card_border"],
            hover_color="#3A405B",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._on_paste_url
        )
        paste_btn.pack(side="left", padx=(0, 6))

        clear_btn = ctk.CTkButton(
            row,
            text="❌ Temizle",
            width=80,
            height=40,
            fg_color=COLORS["card_border"],
            hover_color="#3A405B",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._on_clear_url
        )
        clear_btn.pack(side="left")

    def _build_options_card(self):
        """Format menu and download folder selection card."""
        card = ctk.CTkFrame(
            self.main_container,
            fg_color=COLORS["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["card_border"]
        )
        card.pack(fill="x", pady=(0, 15), padx=2)

        options_grid = ctk.CTkFrame(card, fg_color="transparent")
        options_grid.pack(fill="x", padx=18, pady=15)

        # Format Picker
        fmt_label = ctk.CTkLabel(
            options_grid,
            text="⚙️ Kalite / Format Seçimi",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        fmt_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.format_option_menu = ctk.CTkOptionMenu(
            options_grid,
            values=FORMAT_OPTIONS,
            height=38,
            width=240,
            fg_color=COLORS["input_bg"],
            button_color=COLORS["card_border"],
            button_hover_color="#3A405B",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            dropdown_font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.format_option_menu.set(FORMAT_OPTIONS[0])
        self.format_option_menu.grid(row=1, column=0, sticky="w", padx=(0, 20))

        # Download Directory Selector
        dir_label = ctk.CTkLabel(
            options_grid,
            text="📁 İndirme Dizini",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        dir_label.grid(row=0, column=1, sticky="w", pady=(0, 6))

        dir_row = ctk.CTkFrame(options_grid, fg_color="transparent")
        dir_row.grid(row=1, column=1, sticky="ew")
        options_grid.grid_columnconfigure(1, weight=1)

        self.dir_entry = ctk.CTkEntry(
            dir_row,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLORS["input_bg"],
            border_color=COLORS["input_border"],
            height=38
        )
        self.dir_entry.insert(0, self.download_dir)
        self.dir_entry.configure(state="readonly")
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        browse_btn = ctk.CTkButton(
            dir_row,
            text="Gözat...",
            width=80,
            height=38,
            fg_color=COLORS["card_border"],
            hover_color="#3A405B",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._on_browse_directory
        )
        browse_btn.pack(side="right")

    def _build_auto_subtitle_card(self):
        """Auto Subtitle & Hardsub configuration card."""
        card = ctk.CTkFrame(
            self.main_container,
            fg_color=COLORS["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["card_border"]
        )
        card.pack(fill="x", pady=(0, 15), padx=2)

        header_row = ctk.CTkFrame(card, fg_color="transparent")
        header_row.pack(fill="x", padx=18, pady=(15, 8))

        self.auto_sub_check = ctk.CTkCheckBox(
            header_row,
            text="[X] İndirme bittikten sonra otomatik Türkçe altyazı ekle (Auto Subtitle & Hardsub)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["accent"],
            border_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"]
        )
        self.auto_sub_check.select()
        self.auto_sub_check.pack(side="left")

        langs_grid = ctk.CTkFrame(card, fg_color="transparent")
        langs_grid.pack(fill="x", padx=18, pady=(0, 15))

        # Source Language Dropdown
        ctk.CTkLabel(
            langs_grid,
            text="Kaynak Dil:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_secondary"]
        ).pack(side="left", padx=(0, 6))

        self.sub_src_lang_map = {
            "Rusça (ru)": "ru",
            "Otomatik (auto)": "auto",
            "İngilizce (en)": "en",
            "Almanca (de)": "de"
        }

        self.sub_src_menu = ctk.CTkOptionMenu(
            langs_grid,
            values=list(self.sub_src_lang_map.keys()),
            height=32,
            width=140,
            fg_color=COLORS["input_bg"],
            button_color=COLORS["card_border"],
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        self.sub_src_menu.set("Rusça (ru)")
        self.sub_src_menu.pack(side="left", padx=(0, 20))

        # Target Language Dropdown
        ctk.CTkLabel(
            langs_grid,
            text="Hedef Çeviri Dili:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_secondary"]
        ).pack(side="left", padx=(0, 6))

        self.sub_tgt_lang_map = {
            "Türkçe (tr)": "tr",
            "İngilizce (en)": "en",
            "İspanyolca (es)": "es",
            "Almanca (de)": "de",
            "Fransızca (fr)": "fr",
            "Arapça (ar)": "ar",
            "Rusça (ru)": "ru",
        }

        self.sub_tgt_menu = ctk.CTkOptionMenu(
            langs_grid,
            values=list(self.sub_tgt_lang_map.keys()),
            height=32,
            width=150,
            fg_color=COLORS["input_bg"],
            button_color=COLORS["card_border"],
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        self.sub_tgt_menu.set("Türkçe (tr)")
        self.sub_tgt_menu.pack(side="left")

    def _build_progress_card(self):
        """Download progress bar, status metrics, and action buttons."""
        card = ctk.CTkFrame(
            self.main_container,
            fg_color=COLORS["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["card_border"]
        )
        card.pack(fill="x", pady=(0, 15), padx=2)

        status_row = ctk.CTkFrame(card, fg_color="transparent")
        status_row.pack(fill="x", padx=18, pady=(15, 6))

        self.status_title_label = ctk.CTkLabel(
            status_row,
            text="Durum: Hazır",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        self.status_title_label.pack(side="left")

        self.percent_label = ctk.CTkLabel(
            status_row,
            text="%0.0",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=COLORS["accent"]
        )
        self.percent_label.pack(side="right")

        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(
            card,
            height=14,
            corner_radius=7,
            fg_color=COLORS["progress_bg"],
            progress_color=COLORS["accent"]
        )
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", padx=18, pady=(0, 15))

        # Metrics row
        metrics_grid = ctk.CTkFrame(card, fg_color="transparent")
        metrics_grid.pack(fill="x", padx=18, pady=(0, 15))
        for col in range(3):
            metrics_grid.columnconfigure(col, weight=1)

        self.speed_val = ctk.CTkLabel(
            metrics_grid,
            text="🚀 Hız: 0.0 B/s",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_secondary"]
        )
        self.speed_val.grid(row=0, column=0, sticky="w")

        self.eta_val = ctk.CTkLabel(
            metrics_grid,
            text="⏱️ Kalan Süre: --:--",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_secondary"]
        )
        self.eta_val.grid(row=0, column=1, sticky="")

        self.size_val = ctk.CTkLabel(
            metrics_grid,
            text="📦 Boyut: 0 B / 0 B",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_secondary"]
        )
        self.size_val.grid(row=0, column=2, sticky="e")

        # Action Buttons
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=18, pady=(0, 18))

        self.start_btn = ctk.CTkButton(
            btn_row,
            text="⬇️ İNDİRMEYİ BAŞLAT",
            height=46,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#0F111A",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            command=self._on_start_download
        )
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.cancel_btn = ctk.CTkButton(
            btn_row,
            text="⏹️ İptal Et",
            width=120,
            height=46,
            fg_color=COLORS["error"],
            hover_color="#D32F2F",
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            state="disabled",
            command=self._on_cancel_download
        )
        self.cancel_btn.pack(side="right")

    def _build_log_drawer(self):
        """Expandable log console."""
        self.log_visible = False

        toggle_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        toggle_frame.pack(fill="x", pady=(0, 5), padx=2)

        self.log_toggle_btn = ctk.CTkButton(
            toggle_frame,
            text="📜 Detaylı Log Paneli (Göster ▶)",
            fg_color="transparent",
            hover_color=COLORS["card_bg"],
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
            anchor="w",
            command=self._toggle_log_drawer
        )
        self.log_toggle_btn.pack(side="left")

        self.log_box = ctk.CTkTextbox(
            self.main_container,
            height=120,
            fg_color=COLORS["input_bg"],
            border_color=COLORS["input_border"],
            border_width=1,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#00E5FF"
        )

    def _toggle_log_drawer(self):
        if self.log_visible:
            self.log_box.pack_forget()
            self.log_toggle_btn.configure(text="📜 Detaylı Log Paneli (Göster ▶)")
            self.log_visible = False
        else:
            self.log_box.pack(fill="x", pady=(0, 15), padx=2)
            self.log_toggle_btn.configure(text="📜 Detaylı Log Paneli (Gizle ▼)")
            self.log_visible = True

    def append_log(self, msg: str):
        def _do_append():
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            self.log_box.insert("end", f"[{timestamp}] {msg}\n")
            self.log_box.see("end")

        self.after(0, _do_append)

    # Actions
    def _on_paste_url(self):
        try:
            clipboard_text = self.clipboard_get()
            if clipboard_text:
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, clipboard_text.strip())
                self.append_log("Panodan yapıştırıldı.")
        except Exception:
            messagebox.showinfo("Pano Boş", "Panoda yapıştırılacak metin bulunamadı.")

    def _on_clear_url(self):
        self.url_entry.delete(0, "end")

    def _on_browse_directory(self):
        """Opens directory picker dialog and persists selected path."""
        selected_dir = filedialog.askdirectory(
            title="İndirme Klasörünü Seçin",
            initialdir=self.download_dir
        )
        if selected_dir and os.path.exists(selected_dir):
            self.download_dir = selected_dir
            save_download_dir(selected_dir)
            self.dir_entry.configure(state="normal")
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, self.download_dir)
            self.dir_entry.configure(state="readonly")
            self.append_log(f"Yeni indirme klasörü seçildi ve kaydedildi: {selected_dir}")

    def _on_start_download(self):
        url = self.url_entry.get().strip()

        if not url:
            messagebox.showwarning("Eksik Bilgi", "Lütfen indirmek istediğiniz video adresini (URL) girin.")
            return

        if not is_valid_url(url):
            messagebox.showerror("Geçersiz URL", "Girdiğiniz bağlantı geçerli bir web adresi değil.\nLütfen 'http://' veya 'https://' içeren tam bir adres girin.")
            return

        if self.is_downloading:
            return

        self.is_downloading = True
        self.start_btn.configure(state="disabled", fg_color="#3A405B", text="⏳ İŞLENİYOR...")
        self.cancel_btn.configure(state="normal")
        self.progress_bar.set(0.0)
        self.percent_label.configure(text="%0.0")
        self.status_title_label.configure(text="Durum: İndirme Başlatılıyor...", text_color=COLORS["accent"])
        self.speed_val.configure(text="🚀 Hız: 0.0 B/s")
        self.eta_val.configure(text="⏱️ Kalan Süre: --:--")
        self.size_val.configure(text="📦 Boyut: -- / --")

        format_opt = self.format_option_menu.get()
        auto_sub = bool(self.auto_sub_check.get())
        src_lang = self.sub_src_lang_map.get(self.sub_src_menu.get(), "ru")
        
        tgt_val = self.sub_tgt_menu.get()
        tgt_lang = self.sub_tgt_lang_map.get(tgt_val)
        if not tgt_lang:
            import re
            m = re.search(r"\(([a-z]{2})\)", tgt_val)
            tgt_lang = m.group(1) if m else "tr"

        self.current_task = DownloaderTask(
            url=url,
            output_dir=self.download_dir,
            format_option=format_opt,
            on_progress=self._safe_on_progress,
            on_completion=self._safe_on_completion,
            on_log=self.append_log,
            auto_subtitle=auto_sub,
            sub_source_lang=src_lang,
            sub_target_lang=tgt_lang,
            on_sub_progress=self._safe_on_sub_progress
        )
        self.current_task.start()

    def _on_cancel_download(self):
        if self.current_task and self.is_downloading:
            self.current_task.cancel()
            self.status_title_label.configure(text="Durum: İptal Ediliyor...", text_color=COLORS["warning"])

    def _safe_on_progress(self, progress_data: Dict[str, Any]):
        self.after(0, lambda: self._update_progress_ui(progress_data))

    def _update_progress_ui(self, data: Dict[str, Any]):
        if not self.is_downloading:
            return

        status = data.get("status")
        percent = data.get("percent", 0.0)
        
        self.progress_bar.set(percent / 100.0)
        self.percent_label.configure(text=f"%{percent:.1f}")

        if status == "downloading":
            filename = data.get("filename", "")
            disp_name = (filename[:32] + "...") if len(filename) > 35 else filename
            self.status_title_label.configure(
                text=f"İndiriliyor: {disp_name}" if disp_name else "Durum: İndiriliyor...",
                text_color=COLORS["accent"]
            )
            self.speed_val.configure(text=f"🚀 Hız: {data.get('speed_str', '0 B/s')}")
            self.eta_val.configure(text=f"⏱️ Kalan Süre: {data.get('eta_str', '--:--')}")
            self.size_val.configure(text=f"📦 Boyut: {data.get('size_str', '-- / --')}")

        elif status == "processing":
            self.status_title_label.configure(text="Durum: Video İndirildi - Altyazı Hazırlanıyor...", text_color=COLORS["warning"])
            self.speed_val.configure(text="🚀 Hız: --")
            self.eta_val.configure(text="⏱️ Kalan Süre: Tamamlanıyor...")

    def _safe_on_sub_progress(self, step_idx: int, step_name: str, pct: float, detail: str):
        self.after(0, lambda: self._update_sub_progress_ui(step_idx, step_name, pct, detail))

    def _update_sub_progress_ui(self, step_idx: int, step_name: str, pct: float, detail: str):
        if not self.is_downloading:
            return

        self.progress_bar.set(pct / 100.0)
        self.percent_label.configure(text=f"%{pct:.0f}")
        self.status_title_label.configure(text=f"Altyazı Adımı ({step_idx}/3): {step_name}", text_color=COLORS["accent"])
        self.speed_val.configure(text=f"Adım: {step_idx}/3")
        self.eta_val.configure(text=detail)

    def _safe_on_completion(self, success: bool, message: str, info: Optional[Dict[str, Any]]):
        self.after(0, lambda: self._handle_completion(success, message, info))

    def _handle_completion(self, success: bool, message: str, info: Optional[Dict[str, Any]]):
        self.is_downloading = False
        self.start_btn.configure(
            state="normal",
            fg_color=COLORS["accent"],
            text="⬇️ İNDİRMEYİ BAŞLAT"
        )
        self.cancel_btn.configure(state="disabled")

        if success:
            self.progress_bar.set(1.0)
            self.percent_label.configure(text="%100.0")
            self.status_title_label.configure(text="Durum: İşlem Tamamlandı! 🎉", text_color=COLORS["success"])
            self.speed_val.configure(text="🚀 Hız: Tamamlandı")
            self.eta_val.configure(text="⏱️ Kalan Süre: 00:00")
            messagebox.showinfo("Başarılı", message)
        else:
            if "iptal" in message.lower():
                self.status_title_label.configure(text="Durum: İptal Edildi ⏹️", text_color=COLORS["warning"])
                messagebox.showwarning("İptal Edildi", message)
            else:
                self.status_title_label.configure(text="Durum: Hata Oluştu ❌", text_color=COLORS["error"])
                messagebox.showerror("Hata Oluştu", message)
