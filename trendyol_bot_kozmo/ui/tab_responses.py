"""
ui.tab_responses — Tab: Otomatik Yanitlar
==========================================
"""

import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

from config import QUESTION_CATEGORIES, BRAND, COLORS
from core.data import (
    automated_responses, normalize_dict, normalize_key_text,
    save_responses, load_responses, categorize_question,
)
from ui.dialogs import open_edit_dialog


class ResponsesTab:
    """Otomatik Yanitlar sekmesi."""

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self.selected_key = None
        self._build()

    # ─── UI Olustur ───
    def _build(self):
        top = ttk.Frame(self.parent)
        top.pack(fill='x', padx=8, pady=6)

        ttk.Label(top, text="Ara:").pack(side='left')
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *_: self.reload_list())
        ttk.Entry(top, textvariable=self.search_var, width=30).pack(
            side='left', padx=(4, 12))

        ttk.Button(top, text="Yeni Ekle", command=self.add_new).pack(side='left')
        ttk.Button(top, text="Seciliyi Sil",
                   command=self.delete_selected).pack(side='left', padx=(6, 0))

        ttk.Button(top, text="CSV Aktar",
                   command=self.export_csv).pack(side='right')
        ttk.Button(top, text="CSV Yukle",
                   command=self.import_csv).pack(side='right', padx=(0, 6))
        ttk.Button(
            top, text="Yenile",
            command=lambda: [load_responses(), self.reload_list()]
        ).pack(side='right', padx=(0, 6))

        # Kaydirma alani
        container = ttk.Frame(self.parent)
        container.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        self.canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        self.scroll = ttk.Scrollbar(
            container, orient='vertical', command=self.canvas.yview)
        self.list_frame = ttk.Frame(self.canvas)
        self.list_frame.bind(
            '<Configure>',
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox('all')))
        self.canvas.create_window((0, 0), window=self.list_frame, anchor='nw')
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.scroll.pack(side='right', fill='y')

        self.canvas.bind(
            '<Enter>', lambda e: self.app._bind_mousewheel(self.canvas))
        self.canvas.bind(
            '<Leave>', lambda e: self.app._unbind_mousewheel(self.canvas))

    # ─── Liste Yenile ───
    def reload_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()

        normalized = normalize_dict(automated_responses)
        automated_responses.clear()
        automated_responses.update(normalized)

        search_text = self.search_var.get().lower().strip() if hasattr(
            self, 'search_var') else ''

        items = sorted(automated_responses.items(),
                       key=lambda kv: ', '.join(kv[0]))
        if search_text:
            items = [
                (k, v) for k, v in items
                if search_text in ', '.join(k) or search_text in v.lower()
            ]

        if not items:
            ttk.Label(self.list_frame, text="(Kayit yok)",
                      style='Muted.TLabel').pack(anchor='w', pady=6)
            self.selected_key = None
            return

        ttk.Label(self.list_frame, text=f"Toplam {len(items)} kayit",
                  style='Muted.TLabel').pack(anchor='w', pady=(0, 4))

        t = self.app.theme
        card_bg = t.get('card_bg', BRAND[50])
        card_border = t.get('card_border', BRAND[100])
        fg = t.get('fg', COLORS['gray_800'])
        f = self.app.fonts

        for key_tuple, resp in items:
            block = tk.Frame(self.list_frame, bd=1,
                             relief='solid', bg=card_bg,
                             highlightbackground=card_border,
                             highlightthickness=1)
            block.pack(fill='x', pady=4, padx=2)
            block.grid_columnconfigure(1, weight=1)

            soru_text = ', '.join(key_tuple)
            sample_text = ' '.join(key_tuple)
            cat = categorize_question(sample_text)
            cat_info = QUESTION_CATEGORIES.get(cat, {})
            cat_label = cat_info.get('icon', '') + ' ' + cat_info.get('label', cat)

            lbl_cat = tk.Label(block, text=cat_label,
                               font=f['tiny'],
                               fg=cat_info.get('color', t['muted']), bg=card_bg)
            lbl_cat.grid(row=0, column=0, columnspan=2,
                         sticky='w', padx=(10, 4), pady=(6, 0))

            lbl_sk = tk.Label(block, text="Soru :", fg=BRAND[500],
                              font=f['h3'], bg=card_bg)
            lbl_sv = tk.Label(block, text=soru_text, fg=BRAND[600],
                              font=f['body'], bg=card_bg)
            lbl_ck = tk.Label(block, text="Cevap :",
                              font=f['h3'], fg=fg, bg=card_bg)
            lbl_cv = tk.Label(block, text=resp, fg=fg,
                              font=f['body'], justify='left',
                              wraplength=900, bg=card_bg)

            lbl_sk.grid(row=1, column=0, sticky='nw', padx=(8, 4), pady=(2, 2))
            lbl_sv.grid(row=1, column=1, sticky='nw', padx=(0, 8), pady=(2, 2))
            lbl_ck.grid(row=2, column=0, sticky='nw', padx=(8, 4), pady=(0, 6))
            lbl_cv.grid(row=2, column=1, sticky='w', padx=(0, 8), pady=(0, 6))

            for lab, handler in (
                (lbl_sv, self.edit_question),
                (lbl_cv, self.edit_answer),
                (lbl_sk, self.edit_question),
                (lbl_ck, self.edit_answer),
            ):
                lab.configure(cursor='hand2')
                lab.bind('<Button-1>',
                         lambda e, k=key_tuple, h=handler: h(k))

            block.bind('<Button-1>',
                       lambda e, k=key_tuple: self._select(k))
            for lab in (lbl_cat, lbl_sk, lbl_sv, lbl_ck, lbl_cv):
                lab.bind('<Button-1>',
                         lambda e, k=key_tuple: self._select(k), add='+')

    def _select(self, key_tuple):
        self.selected_key = key_tuple

    # ─── CRUD ───
    def edit_question(self, key_tuple):
        old_q = ', '.join(key_tuple)

        def do_save(new_text, win):
            new_key = normalize_key_text(new_text)
            if not new_key:
                messagebox.showerror(
                    "Hata", "En az bir anahtar kelime girin.", parent=win)
                return
            resp = automated_responses.get(key_tuple, '')
            if key_tuple in automated_responses:
                del automated_responses[key_tuple]
            automated_responses[new_key] = resp
            self._persist("Soru guncellendi")
            win.destroy()

        def do_delete(win):
            if messagebox.askyesno("Sil", "Bu kaydi silmek istiyor musunuz?",
                                   parent=win):
                if key_tuple in automated_responses:
                    del automated_responses[key_tuple]
                self._persist("Kayit silindi")
                win.destroy()

        open_edit_dialog(self.app, "Soru Duzenle", old_q, do_save, do_delete)

    def edit_answer(self, key_tuple):
        old_a = automated_responses.get(key_tuple, '')

        def do_save(new_text, win):
            if not new_text:
                messagebox.showerror("Hata", "Cevap metni bos olamaz.",
                                     parent=win)
                return
            automated_responses[key_tuple] = new_text
            self._persist("Cevap guncellendi")
            win.destroy()

        def do_delete(win):
            if messagebox.askyesno("Sil", "Bu kaydi silmek istiyor musunuz?",
                                   parent=win):
                if key_tuple in automated_responses:
                    del automated_responses[key_tuple]
                self._persist("Kayit silindi")
                win.destroy()

        open_edit_dialog(self.app, "Cevap Duzenle", old_a, do_save, do_delete)

    def add_new(self):
        def do_save_soru(new_text, win):
            key = normalize_key_text(new_text)
            if not key:
                messagebox.showerror(
                    "Hata", "En az bir anahtar kelime girin.", parent=win)
                return
            win.destroy()

            def do_save_cevap(a_text, w2):
                if not a_text:
                    messagebox.showerror("Hata", "Cevap metni bos olamaz.",
                                         parent=w2)
                    return
                automated_responses[key] = a_text
                self._persist("Yeni kayit eklendi")
                w2.destroy()

            open_edit_dialog(self.app, "Cevap Ekle", '',
                             do_save_cevap, lambda w: w.destroy())

        open_edit_dialog(
            self.app, "Soru Ekle (anahtar kelimeler, virgul ile)", '',
            do_save_soru, lambda w: w.destroy())

    def delete_selected(self):
        if not self.selected_key:
            messagebox.showwarning("Uyari", "Silmek icin bir kayit tiklayin.")
            return
        if messagebox.askyesno("Sil", "Bu kaydi silmek istediginize emin misiniz?"):
            if self.selected_key in automated_responses:
                del automated_responses[self.selected_key]
            self._persist("Kayit silindi")
            self.selected_key = None

    # ─── CSV ───
    def export_csv(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV', '*.csv')],
            initialfile=f'responses_{datetime.now().strftime("%Y%m%d")}.csv')
        if not filepath:
            return
        try:
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['Anahtar Kelimeler', 'Yanit'])
                for key_tuple, resp in sorted(automated_responses.items()):
                    writer.writerow([','.join(key_tuple), resp])
            self.app._set_status(f"Yanitlar disa aktarildi: {filepath}")
        except Exception as e:
            messagebox.showerror("Hata", f"Disa aktarma hatasi: {e}")

    def import_csv(self):
        filepath = filedialog.askopenfilename(
            filetypes=[('CSV', '*.csv'), ('Tüm Dosyalar', '*.*')])
        if not filepath:
            return
        try:
            imported = 0
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if len(row) >= 2:
                        key = normalize_key_text(row[0])
                        if key:
                            automated_responses[key] = row[1].strip()
                            imported += 1
            save_responses()
            self.reload_list()
            self.app.refresh_stats()
            self.app._set_status(f"{imported} yanit kurali iceri aktarildi")
        except Exception as e:
            messagebox.showerror("Hata", f"Iceri aktarma hatasi: {e}")

    # ─── Yardimci ───
    def _persist(self, msg="Kaydedildi"):
        save_responses()
        load_responses()
        self.reload_list()
        self.app.refresh_stats()
        self.app._set_status(msg)
