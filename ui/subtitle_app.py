import os
import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional, Dict, Any

import customtkinter as ctk

from subtitle_engine.pipeline import SubtitlePipelineTask
from ui.theme import COLORS


class AutoSubtitleApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Appearance settings
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Window configuration
        self.title("Auto Subtitle & Translator Engine v1.0")
        self.geometry("820x760")
        self.minsize(760, 680)
        self.configure(fg_color=COLORS["bg_dark"])

        # State Variables
        self.selected_video_path = ""
        self.output_dir_path = ""
        self.is_processing = False
        self.current_task: Optional[SubtitlePipelineTask] = None

        # Build Interface
        self._create_layout()

    def _create_layout(self):
        """Builds scrollable main frame containing all control cards."""
        self.main_container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0
        )
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)

        self._build_header()
        self._build_file_selection_card()
        self._build_language_card()
        self._build_style_card()
        self._build_progress_card()
        self._build_log_drawer()

    def _build_header(self):
        """Header Banner."""
        card = ctk.CTkFrame(
            self.main_container,
            fg_color=COLORS["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["card_border"]
        )
        card.pack(fill="x", pady=(0, 15), padx=2)

        title = ctk.CTkLabel(
            card,
            text="🎙️ Auto Subtitle & Translator Engine",
            font=ctk.CTkFont(family="Segoe UI", size=23, weight="bold"),
            text_color=COLORS["accent"]
        )
        title.pack(anchor="w", padx=20, pady=(15, 2))

        sub = ctk.CTkLabel(
            card,
            text="Yapay Zeka Ses Tanıma (faster-whisper) • Türkçe Bağlamsal Çeviri • FFmpeg Hardsub Gömücü",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLORS["text_secondary"]
        )
        sub.pack(anchor="w", padx=20, pady=(0, 15))

    def _build_file_selection_card(self):
        """Video & Output Folder selector card."""
        card = ctk.CTkFrame(
            self.main_container,
            fg_color=COLORS["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["card_border"]
        )
        card.pack(fill="x", pady=(0, 15), padx=2)

        ctk.CTkLabel(
            card,
            text="📁 Video ve Çıktı Konumu",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w", padx=18, pady=(15, 8))

        # Row 1: Video File Selection
        v_row = ctk.CTkFrame(card, fg_color="transparent")
        v_row.pack(fill="x", padx=18, pady=(0, 10))

        self.video_entry = ctk.CTkEntry(
            v_row,
            placeholder_text="Lütfen çevrilecek video dosyasını seçin (.mp4, .mkv, .avi, .mov)...",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLORS["input_bg"],
            border_color=COLORS["input_border"],
            height=38
        )
        self.video_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        v_btn = ctk.CTkButton(
            v_row,
            text="🎬 Video Seç",
            width=110,
            height=38,
            fg_color=COLORS["card_border"],
            hover_color="#3A405B",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._on_select_video
        )
        v_btn.pack(side="right")

        # Row 2: Output Directory Selection
        d_row = ctk.CTkFrame(card, fg_color="transparent")
        d_row.pack(fill="x", padx=18, pady=(0, 15))

        self.dir_entry = ctk.CTkEntry(
            d_row,
            placeholder_text="Çıktı klasörü (Varsayılan: Video ile aynı klasör)...",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLORS["input_bg"],
            border_color=COLORS["input_border"],
            height=38
        )
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        d_btn = ctk.CTkButton(
            d_row,
            text="📂 Klasör Seç",
            width=110,
            height=38,
            fg_color=COLORS["card_border"],
            hover_color="#3A405B",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._on_select_output_dir
        )
        d_btn.pack(side="right")

    def _build_language_card(self):
        """Source / Target languages and API Key card."""
        card = ctk.CTkFrame(
            self.main_container,
            fg_color=COLORS["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["card_border"]
        )
        card.pack(fill="x", pady=(0, 15), padx=2)

        ctk.CTkLabel(
            card,
            text="🌐 Dil ve Yapay Zeka Çeviri Ayarları",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w", padx=18, pady=(15, 8))

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=18, pady=(0, 15))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        # Source Lang
        ctk.CTkLabel(
            grid,
            text="Kaynak Dil (Videodaki Konuşma):",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_primary"]
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.lang_map = {
            "Rusça (ru)": "ru",
            "Otomatik Tespit (auto)": "auto",
            "İngilizce (en)": "en",
            "Almanca (de)": "de",
            "Fransızca (fr)": "fr",
            "İspanyolca (es)": "es"
        }

        self.src_lang_menu = ctk.CTkOptionMenu(
            grid,
            values=list(self.lang_map.keys()),
            height=38,
            fg_color=COLORS["input_bg"],
            button_color=COLORS["card_border"],
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.src_lang_menu.set("Rusça (ru)")
        self.src_lang_menu.grid(row=1, column=0, sticky="ew", padx=(0, 10))

        # Target Lang
        ctk.CTkLabel(
            grid,
            text="Hedef Çeviri Dili:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_primary"]
        ).grid(row=0, column=1, sticky="w", pady=(0, 4))

        self.tgt_lang_menu = ctk.CTkOptionMenu(
            grid,
            values=["Türkçe (tr)", "İngilizce (en)", "Almanca (de)"],
            height=38,
            fg_color=COLORS["input_bg"],
            button_color=COLORS["card_border"],
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.tgt_lang_menu.set("Türkçe (tr)")
        self.tgt_lang_menu.grid(row=1, column=1, sticky="ew")

        # LLM API Key Entry Row
        key_frame = ctk.CTkFrame(card, fg_color="transparent")
        key_frame.pack(fill="x", padx=18, pady=(5, 15))

        ctk.CTkLabel(
            key_frame,
            text="🔑 LLM Çeviri API Anahtarı (Opsiyonel):",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w", pady=(0, 4))

        self.api_key_entry = ctk.CTkEntry(
            key_frame,
            placeholder_text="Boş bırakılırsa bağlamsal ücretsiz çeviri servisi kullanılır (sk-...)",
            show="•",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLORS["input_bg"],
            border_color=COLORS["input_border"],
            height=38
        )
        self.api_key_entry.pack(fill="x")

    def _build_style_card(self):
        """Subtitle styling (Font size, Color, Shadow) card."""
        card = ctk.CTkFrame(
            self.main_container,
            fg_color=COLORS["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["card_border"]
        )
        card.pack(fill="x", pady=(0, 15), padx=2)

        ctk.CTkLabel(
            card,
            text="🎨 Altyazı Görünüm & Stil Ayarları",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w", padx=18, pady=(15, 8))

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=18, pady=(0, 15))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.columnconfigure(2, weight=1)

        # Font Size
        ctk.CTkLabel(
            grid,
            text="Font Boyutu:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_primary"]
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.font_size_menu = ctk.CTkOptionMenu(
            grid,
            values=["18 pt", "22 pt", "24 pt (Varsayılan)", "28 pt", "32 pt"],
            height=36,
            fg_color=COLORS["input_bg"],
            button_color=COLORS["card_border"],
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.font_size_menu.set("24 pt (Varsayılan)")
        self.font_size_menu.grid(row=1, column=0, sticky="ew", padx=(0, 10))

        # Color Selection
        ctk.CTkLabel(
            grid,
            text="Yazı Rengi:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_primary"]
        ).grid(row=0, column=1, sticky="w", pady=(0, 4))

        self.color_map = {
            "🟡 Sarı (#FFFF00)": "#FFFF00",
            "⚪ Beyaz (#FFFFFF)": "#FFFFFF",
            "🔵 Cyan (#00FFFF)": "#00FFFF"
        }

        self.color_menu = ctk.CTkOptionMenu(
            grid,
            values=list(self.color_map.keys()),
            height=36,
            fg_color=COLORS["input_bg"],
            button_color=COLORS["card_border"],
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.color_menu.set("🟡 Sarı (#FFFF00)")
        self.color_menu.grid(row=1, column=1, sticky="ew", padx=(0, 10))

        # Toggles frame
        toggles = ctk.CTkFrame(grid, fg_color="transparent")
        toggles.grid(row=1, column=2, sticky="ew")

        self.shadow_check = ctk.CTkCheckBox(
            toggles,
            text="Siyah Sınır/Gölge",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            border_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"]
        )
        self.shadow_check.select()
        self.shadow_check.pack(anchor="w", pady=(0, 4))

        self.hardsub_check = ctk.CTkCheckBox(
            toggles,
            text="Videoya Göm (MP4)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            border_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"]
        )
        self.hardsub_check.select()
        self.hardsub_check.pack(anchor="w")

    def _build_progress_card(self):
        """Step progress indicators & action buttons."""
        card = ctk.CTkFrame(
            self.main_container,
            fg_color=COLORS["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["card_border"]
        )
        card.pack(fill="x", pady=(0, 15), padx=2)

        # Header status row
        s_row = ctk.CTkFrame(card, fg_color="transparent")
        s_row.pack(fill="x", padx=18, pady=(15, 6))

        self.step_label = ctk.CTkLabel(
            s_row,
            text="Durum: İşlem İçin Hazır",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        self.step_label.pack(side="left")

        self.pct_label = ctk.CTkLabel(
            s_row,
            text="%0.0",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=COLORS["accent"]
        )
        self.pct_label.pack(side="right")

        # Step badges row (4 stages)
        steps_box = ctk.CTkFrame(card, fg_color=COLORS["input_bg"], corner_radius=8)
        steps_box.pack(fill="x", padx=18, pady=(0, 12))

        self.step_badges = []
        step_titles = ["1. Ses", "2. Whisper", "3. Çeviri", "4. FFmpeg"]

        for i, title in enumerate(step_titles):
            lbl = ctk.CTkLabel(
                steps_box,
                text=title,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=COLORS["text_secondary"]
            )
            lbl.pack(side="left", fill="x", expand=True, pady=8)
            self.step_badges.append(lbl)

        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(
            card,
            height=14,
            corner_radius=7,
            fg_color=COLORS["progress_bg"],
            progress_color=COLORS["accent"]
        )
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", padx=18, pady=(0, 12))

        self.detail_label = ctk.CTkLabel(
            card,
            text="Lütfen video dosyasını seçip 'ALTYAZI OLUŞTUR VE ÇEVİR' düğmesine basın.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_secondary"]
        )
        self.detail_label.pack(anchor="w", padx=18, pady=(0, 15))

        # Action Buttons
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=18, pady=(0, 18))

        self.start_btn = ctk.CTkButton(
            btn_row,
            text="🚀 ALTYAZI OLUŞTUR VE ÇEVİR",
            height=46,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#0F111A",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            command=self._on_start_pipeline
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
            command=self._on_cancel_pipeline
        )
        self.cancel_btn.pack(side="right")

    def _build_log_drawer(self):
        """Diagnostic log console drawer."""
        self.log_visible = False

        toggle_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        toggle_frame.pack(fill="x", pady=(0, 5), padx=2)

        self.log_toggle_btn = ctk.CTkButton(
            toggle_frame,
            text="📜 Detaylı İşlem Logları (Göster ▶)",
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
            self.log_toggle_btn.configure(text="📜 Detaylı İşlem Logları (Göster ▶)")
            self.log_visible = False
        else:
            self.log_box.pack(fill="x", pady=(0, 15), padx=2)
            self.log_toggle_btn.configure(text="📜 Detaylı İşlem Logları (Gizle ▼)")
            self.log_visible = True

    def append_log(self, msg: str):
        def _do():
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self.log_box.insert("end", f"[{ts}] {msg}\n")
            self.log_box.see("end")

        self.after(0, _do)

    # Event Handlers
    def _on_select_video(self):
        file_path = filedialog.askopenfilename(
            title="Video Dosyasını Seçin",
            filetypes=[
                ("Video Dosyaları", "*.mp4 *.mkv *.avi *.mov *.webm *.flv"),
                ("Tüm Dosyalar", "*.*")
            ]
        )
        if file_path:
            self.selected_video_path = file_path
            self.video_entry.delete(0, "end")
            self.video_entry.insert(0, file_path)

            if not self.dir_entry.get().strip():
                default_dir = os.path.dirname(file_path)
                self.output_dir_path = default_dir
                self.dir_entry.delete(0, "end")
                self.dir_entry.insert(0, default_dir)

            self.append_log(f"Video seçildi: {os.path.basename(file_path)}")

    def _on_select_output_dir(self):
        d_path = filedialog.askdirectory(title="Çıktı Klasörünü Seçin")
        if d_path:
            self.output_dir_path = d_path
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, d_path)
            self.append_log(f"Çıktı klasörü seçildi: {d_path}")

    def _on_start_pipeline(self):
        video_path = self.video_entry.get().strip()
        out_dir = self.dir_entry.get().strip()

        if not video_path or not os.path.isfile(video_path):
            messagebox.showwarning("Eksik Dosya", "Lütfen geçerli bir video dosyası seçin.")
            return

        if not out_dir:
            out_dir = os.path.dirname(video_path)

        if self.is_processing:
            return

        self.is_processing = True
        self.start_btn.configure(state="disabled", fg_color="#3A405B", text="⏳ İŞLENİYOR...")
        self.cancel_btn.configure(state="normal")
        self.progress_bar.set(0.0)
        self.pct_label.configure(text="%0.0")

        # Parse style options
        f_size_str = self.font_size_menu.get().split()[0]
        font_size = int(f_size_str) if f_size_str.isdigit() else 24
        color_hex = self.color_map.get(self.color_menu.get(), "#FFFF00")
        has_shadow = bool(self.shadow_check.get())
        burn_mp4 = bool(self.hardsub_check.get())
        src_lang = self.lang_map.get(self.src_lang_menu.get(), "ru")
        tgt_lang = "tr" if "Türkçe" in self.tgt_lang_menu.get() else "en"
        api_key = self.api_key_entry.get().strip()

        # Instantiate task runner
        self.current_task = SubtitlePipelineTask(
            video_path=video_path,
            output_dir=out_dir,
            source_lang=src_lang,
            target_lang=tgt_lang,
            api_key=api_key,
            model_size="base",
            font_size=font_size,
            color_hex=color_hex,
            has_outline_shadow=has_shadow,
            burn_hardsub=burn_mp4,
            on_progress=self._safe_on_progress,
            on_log=self.append_log,
            on_complete=self._safe_on_complete
        )
        self.current_task.start()

    def _on_cancel_pipeline(self):
        if self.current_task and self.is_processing:
            self.current_task.cancel()
            self.step_label.configure(text="Durum: İptal Ediliyor...", text_color=COLORS["warning"])

    def _safe_on_progress(self, step_idx: int, step_name: str, pct: float, detail: str):
        self.after(0, lambda: self._update_progress_ui(step_idx, step_name, pct, detail))

    def _update_progress_ui(self, step_idx: int, step_name: str, pct: float, detail: str):
        if not self.is_processing:
            return

        self.progress_bar.set(pct / 100.0)
        self.pct_label.configure(text=f"%{pct:.1f}")
        self.step_label.configure(text=f"Durum: {step_name}", text_color=COLORS["accent"])
        self.detail_label.configure(text=detail)

        # Highlight current active step badge
        for i, badge in enumerate(self.step_badges, start=1):
            if i == step_idx:
                badge.configure(text_color=COLORS["accent"])
            elif i < step_idx:
                badge.configure(text_color=COLORS["success"])
            else:
                badge.configure(text_color=COLORS["text_secondary"])

    def _safe_on_complete(self, success: bool, msg: str, outputs: Dict[str, str]):
        self.after(0, lambda: self._handle_completion(success, msg, outputs))

    def _handle_completion(self, success: bool, msg: str, outputs: Dict[str, str]):
        self.is_processing = False
        self.start_btn.configure(
            state="normal",
            fg_color=COLORS["accent"],
            text="🚀 ALTYAZI OLUŞTUR VE ÇEVİR"
        )
        self.cancel_btn.configure(state="disabled")

        if success:
            self.progress_bar.set(1.0)
            self.pct_label.configure(text="%100.0")
            self.step_label.configure(text="Durum: İşlem Tamamlandı! 🎉", text_color=COLORS["success"])
            self.detail_label.configure(text="Altyazılı video ve .srt dosyası hazır.")
            messagebox.showinfo("İşlem Başarılı", msg)
        else:
            if "iptal" in msg.lower():
                self.step_label.configure(text="Durum: İptal Edildi ⏹️", text_color=COLORS["warning"])
                messagebox.showwarning("İptal Edildi", msg)
            else:
                self.step_label.configure(text="Durum: Hata Oluştu ❌", text_color=COLORS["error"])
                messagebox.showerror("İşlem Hatası", msg)
