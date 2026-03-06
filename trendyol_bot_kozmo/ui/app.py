"""
ui.app — Ana Uygulama Penceresi
==================================
Emare Finance Design Guide uyumlu, modern arayuz.
"""

import sys
import tkinter as tk
from tkinter import ttk, font as tkfont
from datetime import datetime

from config import (
    MISSING_CREDS, MISSING_GEMINI,
    LIGHT_THEME, DARK_THEME,
    BRAND, COLORS, FONT_FAMILY,
)
from core.data import (
    app_settings, save_settings,
)
from core.processor import is_out_of_service_hours

from ui.tab_responses import ResponsesTab
from ui.tab_pending import PendingTab
from ui.tab_templates import TemplatesTab
from ui.tab_orders import OrdersTab
from ui.tab_log import LogTab
from ui.tab_reviews import ReviewsTab
from ui.tab_ai import AITab
from ui.tab_stats import StatsTab
from ui.tab_settings import SettingsTab

# Processor thread'inin ulasmasi icin global referans
_app_instance = None


def get_theme() -> dict:
    """Aktif temayi doner."""
    if app_settings.get('dark_mode', False):
        return DARK_THEME
    return LIGHT_THEME


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Kozmopol — Trendyol Akilli Musteri Hizmetleri v3.0")
        self.geometry("1400x900")
        self.minsize(1100, 700)

        self.out_of_office_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Hazir")
        self.theme = get_theme()

        self._setup_fonts()
        self._build_ui()
        self._apply_theme()

        # Ilk yukleme
        self.responses_tab.reload_list()
        self.pending_tab.refresh_list()
        self.log_tab.refresh_list()
        self.stats_tab.refresh()
        self.templates_tab.refresh_list()
        self.settings_tab.refresh_blacklist()

        # Global app referansi
        global _app_instance
        _app_instance = self

    # ─── Font Sistemi ───
    def _setup_fonts(self):
        """Emare Finance tipografi: Inter ailesi."""
        available = tkfont.families()
        base = FONT_FAMILY if FONT_FAMILY in available else 'Helvetica Neue'
        if base not in available:
            base = 'Helvetica'

        self.fonts = {
            'hero':      (base, 20, 'bold'),     # Logo / hero
            'h1':        (base, 16, 'bold'),      # Section baslik
            'h2':        (base, 14, 'bold'),      # Card baslik
            'h3':        (base, 12, 'bold'),      # Alt baslik
            'body':      (base, 12),              # Normal metin
            'body_sm':   (base, 11),              # Kucuk metin
            'small':     (base, 10),              # Footer, info
            'tiny':      (base, 9),               # Badge, etiket
            'mono':      ('SF Mono' if 'SF Mono' in available else 'Menlo'
                          if 'Menlo' in available else 'Courier', 11),
            'btn':       (base, 11, 'bold'),      # Buton
            'btn_sm':    (base, 10),              # Kucuk buton
            'stat_num':  (base, 28, 'bold'),      # Istatistik sayisi
            'stat_label': (base, 10),             # Istatistik etiketi
            'tab':       (base, 11),              # Sekme
        }

    # ─── UI Olustur ───
    def _build_ui(self):
        t = self.theme
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        # ── ttk Stilleri ──
        style.configure('.', font=self.fonts['body'])
        style.configure('TNotebook', background=t['bg'], borderwidth=0)
        style.configure('TNotebook.Tab',
                        padding=[16, 8],
                        font=self.fonts['tab'],
                        background=t['bg'],
                        foreground=t['fg'])
        style.map('TNotebook.Tab',
                  background=[('selected', t['accent']),
                              ('active', t.get('accent_hover', t['accent']))],
                  foreground=[('selected', COLORS['white']),
                              ('active', COLORS['white'])])

        style.configure('TFrame', background=t['bg'])
        style.configure('TLabel', background=t['bg'], foreground=t['fg'],
                        font=self.fonts['body'])
        style.configure('TLabelframe', background=t['bg'],
                        foreground=t['accent'],
                        font=self.fonts['h3'])
        style.configure('TLabelframe.Label', background=t['bg'],
                        foreground=t['accent'],
                        font=self.fonts['h3'])
        style.configure('TCheckbutton', background=t['bg'],
                        foreground=t['fg'], font=self.fonts['body_sm'])

        # Butonlar — brand gradient etkisi
        style.configure('TButton',
                        padding=[14, 6],
                        font=self.fonts['btn_sm'],
                        background=t['accent'],
                        foreground=COLORS['white'],
                        borderwidth=0)
        style.map('TButton',
                  background=[('active', t.get('accent_hover', t['accent'])),
                              ('pressed', BRAND[700])],
                  foreground=[('active', COLORS['white'])])

        # Primary buton (vurgulu)
        style.configure('Primary.TButton',
                        padding=[18, 8],
                        font=self.fonts['btn'],
                        background=BRAND[500],
                        foreground=COLORS['white'],
                        borderwidth=0)
        style.map('Primary.TButton',
                  background=[('active', BRAND[600]),
                              ('pressed', BRAND[700])])

        # Ghost buton (transparan)
        style.configure('Ghost.TButton',
                        padding=[12, 6],
                        font=self.fonts['btn_sm'],
                        background=t['bg'],
                        foreground=t['accent'],
                        borderwidth=1,
                        relief='solid')
        style.map('Ghost.TButton',
                  background=[('active', t.get('accent_light', t['bg']))],
                  foreground=[('active', t.get('accent_hover', t['accent']))])

        # Danger buton
        style.configure('Danger.TButton',
                        padding=[14, 6],
                        font=self.fonts['btn_sm'],
                        background=t['danger'],
                        foreground=COLORS['white'])
        style.map('Danger.TButton',
                  background=[('active', '#dc2626')])

        # Ozel label stilleri
        style.configure('Header.TLabel',
                        font=self.fonts['hero'],
                        foreground=t['header_fg'],
                        background=t.get('topbar_bg', t['bg']))
        style.configure('Muted.TLabel',
                        foreground=t['muted'],
                        font=self.fonts['body_sm'])
        style.configure('Success.TLabel',
                        foreground=t['success'],
                        font=self.fonts['h3'])
        style.configure('Warning.TLabel',
                        foreground=t['warning'],
                        font=self.fonts['h3'])
        style.configure('Danger.TLabel',
                        foreground=t['danger'],
                        font=self.fonts['h3'])
        style.configure('Brand.TLabel',
                        foreground=BRAND[500],
                        font=self.fonts['h2'])

        # Combobox
        style.configure('TCombobox', font=self.fonts['body_sm'])

        # Entry
        style.configure('TEntry', font=self.fonts['body_sm'])

        # Treeview markasi
        style.configure('Treeview',
                        background=t.get('card_bg', t['bg']),
                        foreground=t['fg'],
                        fieldbackground=t.get('card_bg', t['bg']),
                        borderwidth=0,
                        font=self.fonts['body_sm'],
                        rowheight=28)
        style.configure('Treeview.Heading',
                        background=t['accent'],
                        foreground=COLORS['white'],
                        font=self.fonts['h3'],
                        borderwidth=0)
        style.map('Treeview',
                  background=[('selected', BRAND[100])],
                  foreground=[('selected', BRAND[700])])
        style.map('Treeview.Heading',
                  background=[('active', t.get('accent_hover', t['accent']))])

        # Scrollbar
        style.configure('Vertical.TScrollbar',
                        background=t.get('bar_bg', BRAND[100]),
                        troughcolor=t.get('card_bg', t['bg']),
                        borderwidth=0,
                        arrowsize=0)

        # PanedWindow
        style.configure('TPanedwindow', background=t['bg'])

        # Separator
        style.configure('TSeparator', background=t.get('separator', BRAND[200]))

        # ═════════════════════════════════════════════════
        # ÜST BAR — Marka serit
        # ═════════════════════════════════════════════════
        topbar_bg = t.get('topbar_bg', t['bg'])
        self.topbar = tk.Frame(self, bg=topbar_bg, height=56)
        self.topbar.pack(fill='x', side='top')
        self.topbar.pack_propagate(False)

        # Sol: Logo ve baslik
        logo_frame = tk.Frame(self.topbar, bg=topbar_bg)
        logo_frame.pack(side='left', padx=(16, 0))

        # Logo kutusu ( EF → KP )
        logo_box = tk.Frame(logo_frame, bg=BRAND[500],
                            width=36, height=36)
        logo_box.pack(side='left', pady=10)
        logo_box.pack_propagate(False)
        tk.Label(logo_box, text="KP", fg=COLORS['white'],
                 bg=BRAND[500],
                 font=self.fonts['h2']).place(relx=0.5, rely=0.5,
                                              anchor='center')

        title_frame = tk.Frame(logo_frame, bg=topbar_bg)
        title_frame.pack(side='left', padx=(10, 0))
        tk.Label(title_frame, text="Kozmopol",
                 fg=t['header_fg'], bg=topbar_bg,
                 font=self.fonts['hero']).pack(anchor='w')
        tk.Label(title_frame, text="Akilli Musteri Hizmetleri v3.0",
                 fg=t['muted'], bg=topbar_bg,
                 font=self.fonts['tiny']).pack(anchor='w')

        # Sag: Durum badge'leri ve butonlar
        right_frame = tk.Frame(self.topbar, bg=topbar_bg)
        right_frame.pack(side='right', padx=(0, 16))

        self.theme_btn = tk.Button(
            right_frame,
            text="🌙" if not app_settings.get('dark_mode') else "☀️",
            font=self.fonts['body'],
            bg=t.get('accent_light', BRAND[50]),
            fg=t['accent'],
            bd=0, padx=10, pady=4,
            cursor='hand2',
            activebackground=t.get('highlight', BRAND[100]),
            command=self.toggle_theme)
        self.theme_btn.pack(side='right', padx=(8, 0), pady=12)

        # API / Gemini status
        if MISSING_CREDS:
            self._make_badge(right_frame, "API Devre Disi",
                             COLORS['red'], topbar_bg)
        if MISSING_GEMINI:
            self._make_badge(right_frame, "Gemini Devre Disi",
                             COLORS['amber'], topbar_bg)
        else:
            self._make_badge(right_frame, "Gemini Aktif",
                             COLORS['green'], topbar_bg)

        # Ince accent cizgi (topbar alt border)
        accent_line = tk.Frame(self, bg=t['accent'], height=2)
        accent_line.pack(fill='x', side='top')

        # ═════════════════════════════════════════════════
        # MESAI DISI BAR
        # ═════════════════════════════════════════════════
        cb_frame = tk.Frame(self, bg=t.get('accent_light', BRAND[50]))
        cb_frame.pack(fill='x', side='top', ipady=4)

        cb = tk.Checkbutton(
            cb_frame, text="  Mesai disi otomatik cevabi aktif et",
            variable=self.out_of_office_var,
            bg=t.get('accent_light', BRAND[50]),
            fg=t['fg'], selectcolor=t.get('accent_light', BRAND[50]),
            activebackground=t.get('accent_light', BRAND[50]),
            font=self.fonts['body_sm'],
            cursor='hand2')
        cb.pack(side='left', padx=(16, 0))

        self.work_status_var = tk.StringVar()
        self._update_work_status()
        tk.Label(cb_frame, textvariable=self.work_status_var,
                 fg=t['muted'],
                 bg=t.get('accent_light', BRAND[50]),
                 font=self.fonts['small']).pack(side='left', padx=(16, 0))

        # ═════════════════════════════════════════════════
        # DURUM CUBUGU (Alt)
        # ═════════════════════════════════════════════════
        self.status_frame = tk.Frame(self,
                                     bg=t.get('status_bg', BRAND[950]),
                                     height=28)
        self.status_frame.pack(fill='x', side='bottom')
        self.status_frame.pack_propagate(False)
        self.status_label = tk.Label(
            self.status_frame, textvariable=self.status_var,
            fg=t.get('status_fg', BRAND[200]),
            bg=t.get('status_bg', BRAND[950]),
            font=self.fonts['small'],
            anchor='w')
        self.status_label.pack(fill='x', padx=16, pady=4)

        # ═════════════════════════════════════════════════
        # SEKMELER (Notebook)
        # ═════════════════════════════════════════════════
        notebook = ttk.Notebook(self)
        notebook.pack(fill='both', expand=True, padx=0, pady=0)

        tab_frames = {}
        tab_defs = [
            ('responses', '  📋 Otomatik Yanitlar  '),
            ('pending',   '  ⏳ Bekleyen Sorular  '),
            ('templates', '  📑 Sablonlar  '),
            ('orders',    '  📦 Kargo & Iade  '),
            ('log',       '  📊 Soru Gecmisi  '),
            ('reviews',   '  ⭐ Yorumlar  '),
            ('ai',        '  🤖 AI Ayarlari  '),
            ('stats',     '  📈 Istatistikler  '),
            ('settings',  '  ⚙️ Ayarlar  '),
        ]
        for key, label in tab_defs:
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=label)
            tab_frames[key] = frame

        # Sekmeleri olustur
        self.responses_tab = ResponsesTab(self, tab_frames['responses'])
        self.pending_tab = PendingTab(self, tab_frames['pending'])
        self.templates_tab = TemplatesTab(self, tab_frames['templates'])
        self.orders_tab = OrdersTab(self, tab_frames['orders'])
        self.log_tab = LogTab(self, tab_frames['log'])
        self.reviews_tab = ReviewsTab(self, tab_frames['reviews'])
        self.ai_tab = AITab(self, tab_frames['ai'])
        self.stats_tab = StatsTab(self, tab_frames['stats'])
        self.settings_tab = SettingsTab(self, tab_frames['settings'])

    # ─── Badge yarat ───
    def _make_badge(self, parent, text, color, bg):
        """Kucuk durum badge'i olustur."""
        badge = tk.Frame(parent, bg=bg)
        badge.pack(side='right', padx=(8, 0), pady=12)
        # Nokta ikonu
        dot = tk.Canvas(badge, width=8, height=8, bg=bg,
                        highlightthickness=0)
        dot.pack(side='left', padx=(0, 4))
        dot.create_oval(1, 1, 7, 7, fill=color, outline=color)
        tk.Label(badge, text=text, fg=color, bg=bg,
                 font=self.fonts['tiny']).pack(side='left')

    # ─── Tema Uygula ───
    def _apply_theme(self):
        """Tum pencereye tema uygula."""
        t = self.theme
        self.configure(bg=t['bg'])

    # ─── Tema Degistir ───
    def toggle_theme(self):
        app_settings['dark_mode'] = not app_settings.get('dark_mode', False)
        save_settings()
        self.theme = get_theme()
        dark = app_settings['dark_mode']
        self.theme_btn.configure(
            text="☀️" if dark else "🌙")
        self._apply_theme()
        # ttk stillerini guncelle
        self._build_ui.__func__(self)
        self._set_status("Tema degistirildi: " + ("Karanlik" if dark else "Acik"))

    # ─── Mesai Durumu ───
    def _update_work_status(self):
        hrs = (f"{app_settings.get('work_hours_start', '10:00')}"
               f" – {app_settings.get('work_hours_end', '18:00')}")
        if is_out_of_service_hours():
            self.work_status_var.set(f"⏸  Mesai disi  ·  {hrs}")
        else:
            self.work_status_var.set(f"▶  Mesai icinde  ·  {hrs}")
        self.after(60000, self._update_work_status)

    # ─── Mousewheel (macOS + Linux + Windows) ───
    def _bind_mousewheel(self, canvas):
        if sys.platform == 'darwin':
            canvas.bind_all(
                '<MouseWheel>',
                lambda e: canvas.yview_scroll(-e.delta, 'units'))
        else:
            canvas.bind_all(
                '<MouseWheel>',
                lambda e: canvas.yview_scroll(-1 * (e.delta // 120), 'units'))
            canvas.bind_all(
                '<Button-4>', lambda e: canvas.yview_scroll(-1, 'units'))
            canvas.bind_all(
                '<Button-5>', lambda e: canvas.yview_scroll(1, 'units'))

    def _unbind_mousewheel(self, canvas):
        canvas.unbind_all('<MouseWheel>')
        if sys.platform != 'darwin':
            canvas.unbind_all('<Button-4>')
            canvas.unbind_all('<Button-5>')

    # ─── Durum & Yenileme ───
    def _set_status(self, text):
        self.status_var.set(
            f"  {text}    ·    {datetime.now().strftime('%H:%M:%S')}")

    def refresh_stats(self):
        """Istatistikleri yenile (disaridan cagrilabilir)."""
        if hasattr(self, 'stats_tab'):
            self.stats_tab.refresh()

    def refresh_all_tabs(self):
        """Tum sekmeleri guncelle (thread-safe)."""
        try:
            self.responses_tab.reload_list()
            self.pending_tab.refresh_list()
            self.log_tab.refresh_list()
            self.reviews_tab.refresh_list()
            self.stats_tab.refresh()
            self.templates_tab.refresh_list()
        except Exception:
            pass
