"""
ui.tab_log — Tab: Soru Gecmisi
=================================
"""

import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from datetime import datetime

from config import QUESTION_CATEGORIES, METHOD_LABELS, BRAND, COLORS
from core.data import question_log, load_question_log
from core.metrics import generate_daily_report


class LogTab:
    """Soru Gecmisi sekmesi."""

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self._build()

    def _build(self):
        top = ttk.Frame(self.parent)
        top.pack(fill='x', padx=8, pady=6)

        ttk.Label(top, text="Yontem:").pack(side='left')
        self.filter_var = tk.StringVar(value='Tumu')
        ttk.Combobox(
            top, textvariable=self.filter_var,
            values=[
                'Tumu', 'keyword', 'fuzzy', 'gemini',
                'manual_approved', 'manual_edited', 'template',
                'out_of_service', 'pending', 'no_match',
            ],
            width=16, state='readonly').pack(side='left', padx=4)

        ttk.Label(top, text="Kategori:").pack(side='left', padx=(8, 0))
        self.cat_filter_var = tk.StringVar(value='Tumu')
        ttk.Combobox(
            top, textvariable=self.cat_filter_var,
            values=['Tumu'] + [c['label'] for c in QUESTION_CATEGORIES.values()],
            width=18, state='readonly').pack(side='left', padx=4)

        ttk.Button(top, text="Filtrele",
                   command=self.refresh_list).pack(side='left', padx=4)
        ttk.Button(
            top, text="Yenile",
            command=lambda: [load_question_log(), self.refresh_list()]
        ).pack(side='left', padx=4)
        ttk.Button(top, text="Gunluk Rapor",
                   command=self.show_daily_report).pack(side='right')
        ttk.Button(top, text="CSV Disa Aktar",
                   command=self.export_csv).pack(side='right', padx=(0, 6))

        # Treeview
        tree_frame = ttk.Frame(self.parent)
        tree_frame.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        log_cols = ('zaman', 'kategori', 'soru', 'yanit', 'yontem')
        self.tree = ttk.Treeview(
            tree_frame, columns=log_cols, show='headings', height=25)
        self.tree.heading('zaman', text='Zaman')
        self.tree.heading('kategori', text='Kategori')
        self.tree.heading('soru', text='Soru')
        self.tree.heading('yanit', text='Yanit')
        self.tree.heading('yontem', text='Yontem')

        self.tree.column('zaman', width=120, minwidth=100)
        self.tree.column('kategori', width=100, minwidth=80)
        self.tree.column('soru', width=300, minwidth=200)
        self.tree.column('yanit', width=400, minwidth=200)
        self.tree.column('yontem', width=110, minwidth=80)

        l_scroll = ttk.Scrollbar(
            tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=l_scroll.set)
        self.tree.pack(fill='both', expand=True, side='left')
        l_scroll.pack(side='right', fill='y')

        self.tree.bind('<Double-1>', self._show_detail)

    def refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        filt = self.filter_var.get() if hasattr(self, 'filter_var') else 'Tumu'
        cat_filt = self.cat_filter_var.get() if hasattr(
            self, 'cat_filter_var') else 'Tumu'

        for entry in reversed(question_log):
            m = entry.get('method', '')
            if filt != 'Tumu' and m != filt:
                continue

            cat = entry.get('category', 'diger')
            cat_info = QUESTION_CATEGORIES.get(cat, {})
            cat_label = cat_info.get('label', cat)
            if cat_filt != 'Tumu' and cat_label != cat_filt:
                continue

            ts = entry.get('timestamp', '')[:16].replace('T', ' ')
            q = entry.get('question', '')[:80]
            a = entry.get('answer', '')[:80]
            self.tree.insert(
                '', 'end',
                values=(ts, cat_label, q, a, METHOD_LABELS.get(m, m)))

    def _show_detail(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])['values']
        detail = (
            f"Zaman: {vals[0]}\nKategori: {vals[1]}\n\n"
            f"Soru: {vals[2]}\n\nYanit: {vals[3]}\n\nYontem: {vals[4]}")

        win = tk.Toplevel(self.app)
        win.title("Soru Detayi")
        win.geometry("600x400")
        win.transient(self.app)
        txt = scrolledtext.ScrolledText(
            win, wrap='word', font=('Helvetica', 11))
        txt.pack(fill='both', expand=True, padx=10, pady=10)
        txt.insert('1.0', detail)
        txt.configure(state='disabled')

    def show_daily_report(self):
        report = generate_daily_report()
        win = tk.Toplevel(self.app)
        win.title("Gunluk Rapor")
        win.geometry("650x500")
        win.transient(self.app)
        txt = scrolledtext.ScrolledText(
            win, wrap='word', font=('Courier', 11))
        txt.pack(fill='both', expand=True, padx=10, pady=10)
        txt.insert('1.0', report)
        txt.configure(state='disabled')

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill='x', padx=10, pady=(0, 10))

        def copy_report():
            self.app.clipboard_clear()
            self.app.clipboard_append(report)
            self.app._set_status("Rapor panoya kopyalandi")

        ttk.Button(btn_frame, text="Kopyala", command=copy_report).pack(
            side='right')

    def export_csv(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV', '*.csv')],
            initialfile=f'kozmopol_log_{datetime.now().strftime("%Y%m%d")}.csv')
        if not filepath:
            return
        try:
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Zaman', 'Soru ID', 'Soru', 'Yanit',
                    'Yontem', 'Kategori', 'Urun'])
                for entry in question_log:
                    writer.writerow([
                        entry.get('timestamp', ''),
                        entry.get('question_id', ''),
                        entry.get('question', ''),
                        entry.get('answer', ''),
                        entry.get('method', ''),
                        entry.get('category', ''),
                        entry.get('product_info', ''),
                    ])
            self.app._set_status(f"Log disa aktarildi: {filepath}")
        except Exception as e:
            messagebox.showerror("Hata", f"Disa aktarma hatasi: {e}")
