"""
ui.tab_settings — Tab: Ayarlar
=================================
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from config import DEFAULT_SETTINGS, BRAND, COLORS
from core.data import (
    app_settings, save_settings,
    word_blacklist, save_blacklist,
    send_notification,
)
from ui.dialogs import open_edit_dialog


class SettingsTab:
    """Genel Ayarlar sekmesi."""

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self._build()

    def _build(self):
        canvas = tk.Canvas(self.parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            self.parent, orient='vertical', command=canvas.yview)
        settings_frame = ttk.Frame(canvas)
        settings_frame.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=settings_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        canvas.bind('<Enter>', lambda e: self.app._bind_mousewheel(canvas))
        canvas.bind('<Leave>', lambda e: self.app._unbind_mousewheel(canvas))

        # ─── Mesai Saatleri ───
        work_frame = ttk.LabelFrame(
            settings_frame, text="Mesai Saatleri", padding=12)
        work_frame.pack(fill='x', padx=12, pady=(12, 6))

        r = 0
        ttk.Label(work_frame, text="Baslangic:").grid(
            row=r, column=0, sticky='w', pady=4)
        self.work_start = tk.StringVar(
            value=app_settings.get('work_hours_start', '10:00'))
        ttk.Entry(work_frame, textvariable=self.work_start, width=8).grid(
            row=r, column=1, sticky='w', padx=4)

        ttk.Label(work_frame, text="Bitis:").grid(
            row=r, column=2, sticky='w', pady=4, padx=(16, 0))
        self.work_end = tk.StringVar(
            value=app_settings.get('work_hours_end', '18:00'))
        ttk.Entry(work_frame, textvariable=self.work_end, width=8).grid(
            row=r, column=3, sticky='w', padx=4)

        r += 1
        ttk.Label(work_frame, text="Calisma Gunleri:").grid(
            row=r, column=0, sticky='w', pady=4)
        days_frame = ttk.Frame(work_frame)
        days_frame.grid(row=r, column=1, columnspan=3, sticky='w')
        day_names = ['Pzt', 'Sal', 'Car', 'Per', 'Cum', 'Cmt', 'Paz']
        self.day_vars = []
        current_days = app_settings.get('work_days', [0, 1, 2, 3, 4])
        for i, day_name in enumerate(day_names):
            var = tk.BooleanVar(value=i in current_days)
            self.day_vars.append(var)
            ttk.Checkbutton(days_frame, text=day_name,
                            variable=var).pack(side='left', padx=2)

        # ─── Bildirimler ───
        notif_frame = ttk.LabelFrame(
            settings_frame, text="Bildirimler", padding=12)
        notif_frame.pack(fill='x', padx=12, pady=6)

        self.notif_enabled = tk.BooleanVar(
            value=app_settings.get('notifications_enabled', True))
        ttk.Checkbutton(notif_frame, text="Masaustu bildirimleri",
                        variable=self.notif_enabled).pack(anchor='w', pady=2)
        ttk.Button(
            notif_frame, text="Test Bildirimi Gonder",
            command=lambda: send_notification(
                "Kozmopol Test", "Bildirimler calisiyor!")
        ).pack(anchor='w', pady=4)

        # ─── Sorgulama ───
        poll_frame = ttk.LabelFrame(
            settings_frame, text="API Sorgulama", padding=12)
        poll_frame.pack(fill='x', padx=12, pady=6)

        ttk.Label(poll_frame, text="Sorgulama araligi (saniye):").pack(
            anchor='w')
        self.poll_interval = tk.StringVar(
            value=str(app_settings.get('poll_interval', 300)))
        ttk.Entry(poll_frame, textvariable=self.poll_interval,
                  width=10).pack(anchor='w', pady=4)

        # ─── Kara Liste ───
        blacklist_frame = ttk.LabelFrame(
            settings_frame, text="Kelime Kara Listesi", padding=12)
        blacklist_frame.pack(fill='x', padx=12, pady=6)

        ttk.Label(
            blacklist_frame,
            text="AI yanitlarinda bulunmamasi gereken kelimeler. "
                 "Tespit edilirse yanit otomatik onaya alinir.",
            style='Muted.TLabel', wraplength=600).pack(anchor='w', pady=(0, 4))

        self.blacklist_text = scrolledtext.ScrolledText(
            blacklist_frame, wrap='word', height=4, font=('Helvetica', 11))
        self.blacklist_text.pack(fill='x')

        bl_btn = ttk.Frame(blacklist_frame)
        bl_btn.pack(fill='x', pady=(4, 0))
        ttk.Button(bl_btn, text="Kelime Ekle",
                   command=self.add_blacklist_word).pack(side='left')
        ttk.Button(bl_btn, text="Seciliyi Sil",
                   command=self.remove_blacklist_word).pack(
            side='left', padx=(4, 0))

        # ─── Genel ───
        gen_frame = ttk.LabelFrame(
            settings_frame, text="Genel", padding=12)
        gen_frame.pack(fill='x', padx=12, pady=6)

        self.auto_cat = tk.BooleanVar(
            value=app_settings.get('auto_categorize', True))
        ttk.Checkbutton(gen_frame, text="Sorulari otomatik kategorize et",
                        variable=self.auto_cat).pack(anchor='w', pady=2)

        ttk.Label(gen_frame, text="Max yanit uzunlugu:").pack(
            anchor='w', pady=(8, 0))
        self.max_resp_len = tk.StringVar(
            value=str(app_settings.get('max_response_length', 500)))
        ttk.Entry(gen_frame, textvariable=self.max_resp_len,
                  width=10).pack(anchor='w', pady=4)

        # ─── Kaydet ───
        save_btn = ttk.Frame(settings_frame)
        save_btn.pack(fill='x', padx=12, pady=12)
        ttk.Button(save_btn, text="Tum Ayarlari Kaydet",
                   command=self.save_all).pack(side='right')
        ttk.Button(save_btn, text="Varsayilanlara Don",
                   command=self.reset).pack(side='right', padx=(0, 8))

    def refresh_blacklist(self):
        if not hasattr(self, 'blacklist_text'):
            return
        self.blacklist_text.delete('1.0', 'end')
        self.blacklist_text.insert('1.0', ', '.join(word_blacklist))

    def add_blacklist_word(self):
        def do_save(text, win):
            words = [w.strip() for w in text.split(',') if w.strip()]
            if not words:
                messagebox.showerror(
                    "Hata", "En az bir kelime girin.", parent=win)
                return
            for w in words:
                if w not in word_blacklist:
                    word_blacklist.append(w)
            save_blacklist()
            self.refresh_blacklist()
            self.app._set_status(f"{len(words)} kelime kara listeye eklendi")
            win.destroy()

        open_edit_dialog(
            self.app, "Kara Listeye Ekle (virgul ile)", '',
            do_save, lambda w: w.destroy())

    def remove_blacklist_word(self):
        def do_save(text, win):
            words = [w.strip().lower() for w in text.split(',') if w.strip()]
            removed = 0
            for w in words:
                matching = [bw for bw in word_blacklist if bw.lower() == w]
                for m in matching:
                    word_blacklist.remove(m)
                    removed += 1
            save_blacklist()
            self.refresh_blacklist()
            self.app._set_status(f"{removed} kelime kara listeden cikarildi")
            win.destroy()

        open_edit_dialog(
            self.app, "Kara Listeden Cikar (virgul ile)",
            ', '.join(word_blacklist),
            do_save, lambda w: w.destroy())

    def save_all(self):
        try:
            app_settings['work_hours_start'] = self.work_start.get()
            app_settings['work_hours_end'] = self.work_end.get()
            app_settings['work_days'] = [
                i for i, v in enumerate(self.day_vars) if v.get()]
            app_settings['notifications_enabled'] = self.notif_enabled.get()
            app_settings['poll_interval'] = int(self.poll_interval.get())
            app_settings['auto_categorize'] = self.auto_cat.get()
            app_settings['max_response_length'] = int(self.max_resp_len.get())

            bl_text = self.blacklist_text.get('1.0', 'end').strip()
            new_bl = [w.strip() for w in bl_text.split(',') if w.strip()]
            word_blacklist.clear()
            word_blacklist.extend(new_bl)
            save_blacklist()

            save_settings()
            self.app._update_work_status()
            self.app._set_status("Tum ayarlar kaydedildi")
        except ValueError as e:
            messagebox.showerror("Hata", f"Gecersiz deger: {e}")

    def reset(self):
        if not messagebox.askyesno(
                "Onayla",
                "Tum ayarlari varsayilanlara dondurmek istiyor musunuz?"):
            return
        app_settings.clear()
        app_settings.update(DEFAULT_SETTINGS)
        save_settings()
        self.work_start.set(app_settings['work_hours_start'])
        self.work_end.set(app_settings['work_hours_end'])
        for i, v in enumerate(self.day_vars):
            v.set(i in app_settings['work_days'])
        self.notif_enabled.set(app_settings['notifications_enabled'])
        self.poll_interval.set(str(app_settings['poll_interval']))
        self.auto_cat.set(app_settings['auto_categorize'])
        self.max_resp_len.set(str(app_settings['max_response_length']))
        self.app._set_status("Ayarlar varsayilanlara donduruldu")
