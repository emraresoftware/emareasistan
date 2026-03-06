"""
ui.tab_reviews — Tab: Musteri Yorumlari
=========================================
"""

import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from collections import Counter

from core.data import product_reviews, save_reviews
from core.metrics import get_review_sentiment_stats
from api.trendyol import fetch_all_reviews


class ReviewsTab:
    """Musteri Yorumlari sekmesi."""

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self._build()

    def _build(self):
        top = ttk.Frame(self.parent)
        top.pack(fill='x', padx=8, pady=6)

        ttk.Button(top, text="Yorumlari Cek (API)",
                   command=self.fetch_from_api).pack(side='left')
        ttk.Button(top, text="Yenile",
                   command=self.refresh_list).pack(side='left', padx=(6, 0))
        ttk.Button(top, text="Yorum Analizi",
                   command=self.show_analysis).pack(side='left', padx=(6, 0))
        ttk.Button(top, text="Yorumlari Temizle",
                   command=self.clear).pack(side='left', padx=(6, 0))

        ttk.Label(top, text="Ara:").pack(side='left', padx=(18, 0))
        self.search_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.search_var, width=25).pack(
            side='left', padx=(4, 0))
        ttk.Button(top, text="Filtrele",
                   command=self.refresh_list).pack(side='left', padx=(4, 0))

        filter_frame = ttk.Frame(self.parent)
        filter_frame.pack(fill='x', padx=8, pady=(0, 4))
        ttk.Label(filter_frame, text="Urun:").pack(side='left')
        self.product_var = tk.StringVar(value='Tumu')
        self.product_combo = ttk.Combobox(
            filter_frame, textvariable=self.product_var,
            values=['Tumu'], width=60, state='readonly')
        self.product_combo.pack(side='left', padx=(4, 8))
        ttk.Label(filter_frame, text="Min Puan:").pack(side='left')
        self.min_rate_var = tk.StringVar(value='0')
        ttk.Combobox(
            filter_frame, textvariable=self.min_rate_var,
            values=['0', '1', '2', '3', '4', '5'],
            width=4, state='readonly').pack(side='left', padx=(4, 0))

        self.summary_var = tk.StringVar(value="Henuz yorum yuklenmedi")
        ttk.Label(self.parent, textvariable=self.summary_var,
                  style='Muted.TLabel').pack(anchor='w', padx=8, pady=(0, 4))

        tree_frame = ttk.Frame(self.parent)
        tree_frame.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        rev_cols = ('urun', 'kullanici', 'puan', 'tarih', 'yorum')
        self.tree = ttk.Treeview(
            tree_frame, columns=rev_cols, show='headings', height=20)
        self.tree.heading('urun', text='Urun')
        self.tree.heading('kullanici', text='Kullanici')
        self.tree.heading('puan', text='Puan')
        self.tree.heading('tarih', text='Tarih')
        self.tree.heading('yorum', text='Yorum')

        self.tree.column('urun', width=200, minwidth=120)
        self.tree.column('kullanici', width=100, minwidth=70)
        self.tree.column('puan', width=60, minwidth=40)
        self.tree.column('tarih', width=90, minwidth=70)
        self.tree.column('yorum', width=500, minwidth=250)

        r_scroll = ttk.Scrollbar(
            tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=r_scroll.set)
        self.tree.pack(fill='both', expand=True, side='left')
        r_scroll.pack(side='right', fill='y')

        self.tree.bind('<Double-1>', self._show_detail)

    def fetch_from_api(self):
        self.app._set_status("Yorumlar API'den cekiliyor...")
        self.app.update_idletasks()

        def _fetch():
            total, prod_count = fetch_all_reviews(max_pages=20)
            self.app.after(0, lambda: self._on_fetched(total, prod_count))

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_fetched(self, total, prod_count):
        self._update_product_combo()
        self.refresh_list()
        self.app._set_status(f"{total} yorum cekildi ({prod_count} urun)")

    def _update_product_combo(self):
        products = ['Tumu'] + sorted(product_reviews.keys())
        self.product_combo['values'] = products

    def refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        search = self.search_var.get().lower().strip()
        product_filter = self.product_var.get()
        min_rate = int(self.min_rate_var.get() or '0')

        total_count = 0
        shown_count = 0
        avg_rate_sum = 0
        avg_rate_n = 0

        for prod_name, reviews in sorted(product_reviews.items()):
            if product_filter != 'Tumu' and prod_name != product_filter:
                continue
            for rev in reviews:
                total_count += 1
                rate = rev.get('rate', 0)
                comment = rev.get('comment', '')
                user = rev.get('user', '').strip() or 'Anonim'
                date = rev.get('date', '')

                avg_rate_sum += rate
                avg_rate_n += 1

                if rate < min_rate:
                    continue
                if search and search not in comment.lower():
                    continue

                stars = '*' * rate
                self.tree.insert(
                    '', 'end',
                    values=(prod_name[:40], user[:20],
                            f"{stars} ({rate})", date, comment[:150]))
                shown_count += 1

        avg_str = ''
        if avg_rate_n > 0:
            avg_str = f" | Ort. puan: {avg_rate_sum / avg_rate_n:.1f}"
        self.summary_var.set(
            f"Toplam {total_count} yorum, "
            f"{len(product_reviews)} urun | "
            f"Gosterilen: {shown_count}{avg_str}")

    def _show_detail(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])['values']
        detail = (
            f"Urun: {vals[0]}\nKullanici: {vals[1]}\n"
            f"Puan: {vals[2]}\nTarih: {vals[3]}\n\n"
            f"Yorum:\n{vals[4]}")
        win = tk.Toplevel(self.app)
        win.title("Yorum Detayi")
        win.geometry("600x350")
        win.transient(self.app)
        txt = scrolledtext.ScrolledText(
            win, wrap='word', font=('Helvetica', 11))
        txt.pack(fill='both', expand=True, padx=10, pady=10)
        txt.insert('1.0', detail)
        txt.configure(state='disabled')

    def show_analysis(self):
        stats = get_review_sentiment_stats()
        if not stats or stats.get('total', 0) == 0:
            messagebox.showinfo("Bilgi", "Henuz yorum yuklenmedi.")
            return

        win = tk.Toplevel(self.app)
        win.title("Yorum Analizi")
        win.geometry("700x550")
        win.transient(self.app)

        txt = scrolledtext.ScrolledText(
            win, wrap='word', font=('Courier', 11))
        txt.pack(fill='both', expand=True, padx=10, pady=10)

        t = stats['total']
        lines = [
            "=== YORUM DUYGU ANALIZI ===\n",
            f"Toplam Yorum: {t}",
            f"Ortalama Puan: {stats['avg_rate']:.1f} / 5\n",
            f"Olumlu (4-5): {stats['positive']} ({stats['positive']/t*100:.0f}%)",
            f"Notr (3): {stats['neutral']} ({stats['neutral']/t*100:.0f}%)",
            f"Olumsuz (1-2): {stats['negative']} ({stats['negative']/t*100:.0f}%)\n",
            "--- Urun Bazinda Analiz ---",
        ]

        sorted_products = sorted(
            stats['by_product'].items(), key=lambda x: x[1]['avg'])
        for prod_name, ps in sorted_products:
            lines.append(f"\n{prod_name[:50]}")
            lines.append(
                f"  Yorum: {ps['total']} | Ort: {ps['avg']:.1f} | "
                f"Olumlu: {ps['positive']} | Olumsuz: {ps['negative']}")

        # Kelime frekans analizi
        all_words = Counter()
        stop_words = {'bir', 've', 'ile', 'bu', 'da', 'de', 'mi',
                      'cok', 'ama', 'icin', 'ben', 'var', 'yok',
                      'evet', 'hayir', 'olan', 'gibi', 'daha'}
        for reviews in product_reviews.values():
            for rev in reviews:
                comment = (rev.get('comment') or '').lower()
                words = re.findall(r'\w+', comment)
                for w in words:
                    if len(w) > 2 and w not in stop_words:
                        all_words[w] += 1

        if all_words:
            lines.append("\n--- En Sik Gecen Kelimeler ---")
            for word, count in all_words.most_common(20):
                bar = '#' * min(count, 30)
                lines.append(f"  {word:15s} {count:4d} {bar}")

        txt.insert('1.0', '\n'.join(lines))
        txt.configure(state='disabled')

    def clear(self):
        if messagebox.askyesno(
                "Temizle",
                "Tum cache'lenmis yorumlari silmek istediginize emin misiniz?"):
            product_reviews.clear()
            save_reviews()
            self.refresh_list()
            self.app._set_status("Yorumlar temizlendi")
