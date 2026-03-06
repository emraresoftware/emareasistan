"""
ui.tab_stats — Tab: Istatistikler
====================================
"""

import tkinter as tk
from tkinter import ttk

from config import QUESTION_CATEGORIES, METHOD_LABELS, BRAND, COLORS
from core.data import automated_responses, pending_questions
from core.metrics import get_performance_metrics


class StatsTab:
    """Istatistikler sekmesi."""

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self._build()

    def _build(self):
        frame = ttk.Frame(self.parent)
        frame.pack(fill='both', expand=True, padx=12, pady=8)

        ttk.Button(frame, text="Istatistikleri Guncelle",
                   command=self.refresh).pack(anchor='e', pady=(0, 8))

        self.cards_frame = ttk.Frame(frame)
        self.cards_frame.pack(fill='x', pady=(0, 12))

        self.detail_frame = ttk.Frame(frame)
        self.detail_frame.pack(fill='both', expand=True)

    def refresh(self):
        if not hasattr(self, 'cards_frame'):
            return
        for w in self.cards_frame.winfo_children():
            w.destroy()
        for w in self.detail_frame.winfo_children():
            w.destroy()

        metrics = get_performance_metrics()

        total = metrics['total_questions']
        today_count = metrics['today_questions']
        week_count = metrics['week_questions']
        method_counts = metrics['method_counts']

        active_pending = sum(
            1 for p in pending_questions
            if p.get('status') in ('pending', 'no_match'))

        auto_rate_pct = f"{metrics['auto_rate']:.0%}" if total > 0 else "N/A"

        # Kartlar — brand renk paleti
        cards = [
            ("Toplam Soru", str(total), BRAND[500]),
            ("Bugun", str(today_count), COLORS['green']),
            ("Bu Hafta", str(week_count), COLORS['amber']),
            ("Oto Yanit Kurali", str(len(automated_responses)), COLORS['purple']),
            ("Bekleyen", str(active_pending), COLORS['red']),
            ("Oto Cozum Orani", auto_rate_pct, COLORS['cyan']),
        ]

        t = self.app.theme
        f = self.app.fonts
        card_bg = t.get('card_bg', BRAND[50])

        for i, (label, value, color) in enumerate(cards):
            card = tk.Frame(self.cards_frame, bg=card_bg,
                            highlightbackground=t.get('card_border', BRAND[100]),
                            highlightthickness=1)
            card.grid(row=0, column=i, padx=6, pady=4, sticky='nsew')
            self.cards_frame.columnconfigure(i, weight=1)

            tk.Label(card, text=value,
                     font=f['stat_num'],
                     fg=color, bg=card_bg).pack(pady=(12, 0))
            tk.Label(card, text=label,
                     font=f['stat_label'],
                     fg=t.get('muted', COLORS['gray_500']),
                     bg=card_bg).pack(pady=(0, 12))

        # Detay panelleri
        detail_paned = ttk.PanedWindow(
            self.detail_frame, orient='horizontal')
        detail_paned.pack(fill='both', expand=True)

        # Sol: Yontem dagilimi
        left_panel = ttk.LabelFrame(
            detail_paned, text="Yanit Yontemi Dagilimi", padding=8)
        detail_paned.add(left_panel, weight=1)

        colors = {
            'keyword': COLORS['green'], 'fuzzy': COLORS['green_light'],
            'gemini': BRAND[500], 'manual_approved': COLORS['cyan'],
            'manual_edited': '#0d9488', 'template': BRAND[700],
            'out_of_service': COLORS['amber'], 'pending': '#eab308',
            'no_match': COLORS['red'],
        }

        bar_frame = ttk.Frame(left_panel)
        bar_frame.pack(fill='x', padx=4)

        bar_bg_color = t.get('bar_bg', BRAND[100])

        for method, count in sorted(
                method_counts.items(), key=lambda x: -x[1]):
            row = ttk.Frame(bar_frame)
            row.pack(fill='x', pady=2)

            label = METHOD_LABELS.get(method, method)
            pct = (count / total * 100) if total > 0 else 0

            ttk.Label(row, text=label, width=20).pack(side='left')

            bar_container = tk.Frame(row, bg=bar_bg_color, height=18)
            bar_container.pack(side='left', fill='x', expand=True, padx=4)
            bar_container.pack_propagate(False)

            if pct > 0:
                bar = tk.Frame(bar_container,
                               bg=colors.get(method, '#999'), height=18)
                bar.place(relwidth=max(pct / 100, 0.01), relheight=1)

            ttk.Label(row, text=f"{count} ({pct:.0f}%)", width=12).pack(
                side='right')

        # Sag paneller
        right_panel = ttk.Frame(detail_paned)
        detail_paned.add(right_panel, weight=1)

        # Kategori
        cat_frame = ttk.LabelFrame(
            right_panel, text="Kategori Dagilimi", padding=8)
        cat_frame.pack(fill='x', padx=4, pady=(0, 8))

        cat_dist = metrics['category_distribution']
        for cat_code, count in sorted(cat_dist.items(), key=lambda x: -x[1]):
            cat_info = QUESTION_CATEGORIES.get(cat_code, {})
            cat_label = cat_info.get('label', cat_code)
            cat_icon = cat_info.get('icon', '')
            cat_color = cat_info.get('color', '#999')
            pct = (count / total * 100) if total > 0 else 0

            cat_bar_bg = t.get('bar_bg', BRAND[100])

            row = ttk.Frame(cat_frame)
            row.pack(fill='x', pady=1)
            tk.Label(row, text=f"{cat_icon} {cat_label}",
                     font=f['small'], width=20, anchor='w').pack(
                side='left')
            bar_c = tk.Frame(row, bg=cat_bar_bg, height=14)
            bar_c.pack(side='left', fill='x', expand=True, padx=4)
            bar_c.pack_propagate(False)
            if pct > 0:
                bar = tk.Frame(bar_c, bg=cat_color, height=14)
                bar.place(relwidth=max(pct / 100, 0.01), relheight=1)
            ttk.Label(row, text=f"{count}", width=6).pack(side='right')

        # Saatlik
        hour_frame = ttk.LabelFrame(
            right_panel, text="Saatlik Dagilim", padding=8)
        hour_frame.pack(fill='both', expand=True, padx=4)

        hourly = metrics['hourly_distribution']
        max_hour_count = max(hourly.values()) if hourly else 1
        hour_bar_bg = t.get('bar_bg', BRAND[100])
        for hour in range(8, 22):
            count = hourly.get(hour, 0)
            pct = (count / max_hour_count) if max_hour_count > 0 else 0
            row = ttk.Frame(hour_frame)
            row.pack(fill='x', pady=0)
            tk.Label(row, text=f"{hour:02d}:00",
                     font=f['tiny'], width=6).pack(side='left')
            bar_c = tk.Frame(row, bg=hour_bar_bg, height=10)
            bar_c.pack(side='left', fill='x', expand=True, padx=2)
            bar_c.pack_propagate(False)
            if pct > 0:
                bar = tk.Frame(bar_c, bg=BRAND[500], height=10)
                bar.place(relwidth=max(pct, 0.01), relheight=1)
            tk.Label(row, text=str(count),
                     font=f['tiny'], width=4).pack(side='right')
