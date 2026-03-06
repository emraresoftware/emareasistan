"""
ui.tab_orders — Tab: Kargo & Iade
===================================
"""

import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime

from api.trendyol import get_orders, get_claims


class OrdersTab:
    """Kargo & Iade sekmesi."""

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self._build()

    def _build(self):
        top = ttk.Frame(self.parent)
        top.pack(fill='x', padx=8, pady=6)

        ttk.Label(top, text="Son").pack(side='left')
        self.days_var = tk.StringVar(value='7')
        ttk.Combobox(
            top, textvariable=self.days_var,
            values=['3', '7', '14', '30'],
            width=5, state='readonly').pack(side='left', padx=4)
        ttk.Label(top, text="gun").pack(side='left')

        ttk.Button(top, text="Siparisleri Getir",
                   command=self.fetch_orders).pack(side='left', padx=(12, 0))
        ttk.Button(top, text="Iadeleri Getir",
                   command=self.fetch_claims).pack(side='left', padx=(6, 0))

        paned = ttk.PanedWindow(self.parent, orient='vertical')
        paned.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        # Siparis
        order_frame = ttk.LabelFrame(paned, text="Siparisler", padding=4)
        paned.add(order_frame, weight=1)

        order_cols = ('siparis_no', 'tarih', 'durum', 'kargo', 'urun', 'musteri')
        self.order_tree = ttk.Treeview(
            order_frame, columns=order_cols, show='headings', height=10)
        for col, heading, w in [
            ('siparis_no', 'Siparis No', 130), ('tarih', 'Tarih', 130),
            ('durum', 'Durum', 100), ('kargo', 'Kargo', 140),
            ('urun', 'Urun', 250), ('musteri', 'Musteri', 150),
        ]:
            self.order_tree.heading(col, text=heading)
            self.order_tree.column(col, width=w, minwidth=80)

        o_scroll = ttk.Scrollbar(
            order_frame, orient='vertical', command=self.order_tree.yview)
        self.order_tree.configure(yscrollcommand=o_scroll.set)
        self.order_tree.pack(fill='both', expand=True, side='left')
        o_scroll.pack(side='right', fill='y')

        # Iade
        claim_frame = ttk.LabelFrame(paned, text="Iadeler / Talepler", padding=4)
        paned.add(claim_frame, weight=1)

        claim_cols = ('talep_no', 'tarih', 'durum', 'sebep', 'urun')
        self.claim_tree = ttk.Treeview(
            claim_frame, columns=claim_cols, show='headings', height=8)
        for col, heading, w in [
            ('talep_no', 'Talep No', 120), ('tarih', 'Tarih', 120),
            ('durum', 'Durum', 120), ('sebep', 'Sebep', 200),
            ('urun', 'Urun', 300),
        ]:
            self.claim_tree.heading(col, text=heading)
            self.claim_tree.column(col, width=w, minwidth=80)

        c_scroll = ttk.Scrollbar(
            claim_frame, orient='vertical', command=self.claim_tree.yview)
        self.claim_tree.configure(yscrollcommand=c_scroll.set)
        self.claim_tree.pack(fill='both', expand=True, side='left')
        c_scroll.pack(side='right', fill='y')

    # ─── Siparis ───
    def fetch_orders(self):
        self.app._set_status("Siparisler yukleniyor...")
        self.app.update_idletasks()

        def _fetch():
            days = int(self.days_var.get())
            orders = get_orders(days=days)
            self.app.after(0, lambda: self._populate_orders(orders))

        threading.Thread(target=_fetch, daemon=True).start()

    def _populate_orders(self, orders):
        for item in self.order_tree.get_children():
            self.order_tree.delete(item)
        count = 0
        for o in orders:
            for line in o.get('lines', [{}]):
                order_no = o.get('orderNumber', '')
                ts = o.get('orderDate')
                date_str = ''
                if ts:
                    date_str = datetime.fromtimestamp(
                        ts / 1000).strftime('%Y-%m-%d %H:%M')
                status = o.get('status', '')
                cargo = line.get('cargoProviderName', '')
                product = (line.get('productName') or '')[:60]
                customer = (f"{o.get('customerFirstName', '')} "
                            f"{o.get('customerLastName', '')}")
                self.order_tree.insert(
                    '', 'end',
                    values=(order_no, date_str, status,
                            cargo, product, customer))
                count += 1
        self.app._set_status(f"{count} siparis satiri yuklendi")

    # ─── Iade ───
    def fetch_claims(self):
        self.app._set_status("Iadeler yukleniyor...")
        self.app.update_idletasks()

        def _fetch():
            claims = get_claims()
            self.app.after(0, lambda: self._populate_claims(claims))

        threading.Thread(target=_fetch, daemon=True).start()

    def _populate_claims(self, claims):
        for item in self.claim_tree.get_children():
            self.claim_tree.delete(item)
        count = 0
        for c in claims:
            for ci in c.get('items', [{}]):
                claim_no = c.get('id', '')
                ts = c.get('createdDate')
                date_str = ''
                if ts:
                    date_str = datetime.fromtimestamp(
                        ts / 1000).strftime('%Y-%m-%d')
                status = ci.get('claimItemStatus', c.get('status', ''))
                reason_obj = ci.get('customerClaimItemReason')
                reason = ''
                if isinstance(reason_obj, dict):
                    reason = reason_obj.get('name', '')
                product = (ci.get('productName') or '')[:60]
                self.claim_tree.insert(
                    '', 'end',
                    values=(claim_no, date_str, status, reason, product))
                count += 1
        self.app._set_status(f"{count} iade/talep yuklendi")
