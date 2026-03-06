"""
ui.tab_ai — Tab: AI Ayarlari
===============================
"""

import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from config import MISSING_GEMINI, QUESTION_CATEGORIES, BRAND, COLORS
from core.data import (
    gemini_config, save_gemini_config,
    categorize_question, product_reviews,
)
from core.matcher import (
    exact_keyword_match, fuzzy_keyword_match, get_quick_suggestions,
)
from api.trendyol import find_relevant_reviews
from api.gemini import generate_gemini_response


class AITab:
    """AI Ayarlari sekmesi."""

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self._build()

    def _build(self):
        main = ttk.Frame(self.parent)
        main.pack(fill='both', expand=True, padx=12, pady=8)

        # Sol: Ayarlar
        left = ttk.LabelFrame(main, text="Gemini AI Yapilandirmasi", padding=10)
        left.pack(side='left', fill='both', expand=True, padx=(0, 6))

        self.enabled_var = tk.BooleanVar(
            value=gemini_config.get('enabled', True))
        ttk.Checkbutton(left, text="Gemini AI Aktif",
                        variable=self.enabled_var).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=4)

        self.autosend_var = tk.BooleanVar(
            value=gemini_config.get('auto_send', False))
        ttk.Checkbutton(
            left, text="AI yanitlarini otomatik gonder (guven esigi uzerinde)",
            variable=self.autosend_var).grid(
            row=1, column=0, columnspan=2, sticky='w', pady=4)

        ttk.Label(left, text="Model:").grid(row=2, column=0, sticky='w', pady=4)
        self.model_var = tk.StringVar(
            value=gemini_config.get('model', 'gemini-2.0-flash'))
        ttk.Combobox(
            left, textvariable=self.model_var,
            values=[
                'gemini-2.0-flash',
                'gemini-2.0-flash-lite',
                'gemini-2.5-pro-preview-05-06',
                'gemini-2.5-flash-preview-05-20',
            ],
            width=35).grid(row=2, column=1, sticky='w', pady=4, padx=4)

        ttk.Label(left, text="Sicaklik (0-1):").grid(
            row=3, column=0, sticky='w', pady=4)
        self.temp_var = tk.StringVar(
            value=str(gemini_config.get('temperature', 0.3)))
        ttk.Entry(left, textvariable=self.temp_var, width=10).grid(
            row=3, column=1, sticky='w', pady=4, padx=4)

        ttk.Label(left, text="Max Token:").grid(
            row=4, column=0, sticky='w', pady=4)
        self.maxtok_var = tk.StringVar(
            value=str(gemini_config.get('max_tokens', 500)))
        ttk.Entry(left, textvariable=self.maxtok_var, width=10).grid(
            row=4, column=1, sticky='w', pady=4, padx=4)

        ttk.Label(left, text="Guven Esigi (0-1):").grid(
            row=5, column=0, sticky='w', pady=4)
        self.conf_var = tk.StringVar(
            value=str(gemini_config.get('confidence_threshold', 0.7)))
        ttk.Entry(left, textvariable=self.conf_var, width=10).grid(
            row=5, column=1, sticky='w', pady=4, padx=4)

        ttk.Label(left, text="Bulanik Esik (0-1):").grid(
            row=6, column=0, sticky='w', pady=4)
        self.fuzzy_var = tk.StringVar(
            value=str(gemini_config.get('fuzzy_threshold', 0.65)))
        ttk.Entry(left, textvariable=self.fuzzy_var, width=10).grid(
            row=6, column=1, sticky='w', pady=4, padx=4)

        ttk.Label(left, text="Sistem Promptu:").grid(
            row=7, column=0, sticky='nw', pady=4)
        self.prompt_text = scrolledtext.ScrolledText(
            left, wrap='word', width=50, height=10, font=('Courier', 10))
        self.prompt_text.grid(row=7, column=1, sticky='nsew', pady=4, padx=4)
        self.prompt_text.insert('1.0', gemini_config.get('system_prompt', ''))
        left.rowconfigure(7, weight=1)
        left.columnconfigure(1, weight=1)

        ttk.Button(left, text="Ayarlari Kaydet",
                   command=self.save_settings).grid(
            row=8, column=0, columnspan=2, pady=(10, 0))

        # Sag: Test
        right = ttk.LabelFrame(main, text="AI Test", padding=10)
        right.pack(side='right', fill='both', expand=True, padx=(6, 0))

        ttk.Label(right, text="Test sorusu yazin:").pack(anchor='w')
        self.test_input = scrolledtext.ScrolledText(
            right, wrap='word', height=4, font=('Helvetica', 11))
        self.test_input.pack(fill='x', pady=4)

        ttk.Button(right, text="Test Et",
                   command=self.test_response).pack(anchor='w', pady=4)

        ttk.Label(right, text="Sonuc:").pack(anchor='w', pady=(8, 0))
        self.test_output = scrolledtext.ScrolledText(
            right, wrap='word', height=12, font=('Helvetica', 11))
        self.test_output.pack(fill='both', expand=True, pady=4)

    def save_settings(self):
        try:
            gemini_config['enabled'] = self.enabled_var.get()
            gemini_config['auto_send'] = self.autosend_var.get()
            gemini_config['model'] = self.model_var.get()
            gemini_config['temperature'] = float(self.temp_var.get())
            gemini_config['max_tokens'] = int(self.maxtok_var.get())
            gemini_config['confidence_threshold'] = float(self.conf_var.get())
            gemini_config['fuzzy_threshold'] = float(self.fuzzy_var.get())
            gemini_config['system_prompt'] = self.prompt_text.get(
                '1.0', 'end').strip()
            save_gemini_config()
            self.app._set_status("AI ayarlari kaydedildi")
        except ValueError as e:
            messagebox.showerror("Hata", f"Gecersiz deger: {e}")

    def test_response(self):
        question = self.test_input.get('1.0', 'end').strip()
        if not question:
            messagebox.showwarning("Uyari", "Bir soru yazin.")
            return

        self.test_output.delete('1.0', 'end')
        self.test_output.insert('1.0', "Yanit uretiliyor...\n")
        self.app.update_idletasks()

        def _run():
            results = []

            cat = categorize_question(question)
            cat_info = QUESTION_CATEGORIES.get(cat, {})
            results.append(
                f"[KATEGORI] {cat_info.get('icon', '')} "
                f"{cat_info.get('label', cat)}")

            kw = exact_keyword_match(question)
            if kw:
                results.append(f"[ANAHTAR KELIME] ESLESME: {kw[:120]}")
            else:
                results.append("[ANAHTAR KELIME] Eslesme yok")

            fz, score = fuzzy_keyword_match(question)
            if fz:
                results.append(
                    f"[BULANIK] ESLESME (skor: {score:.0%}): {fz[:120]}")
            else:
                results.append("[BULANIK] Eslesme yok")

            suggestions = get_quick_suggestions(question, 3)
            if suggestions:
                sg_lines = ["[HIZLI ONERILER]"]
                for sq, sa in suggestions:
                    sg_lines.append(
                        f"  Soru: {sq[:60]}\n  Yanit: {sa[:100]}")
                results.append('\n'.join(sg_lines))

            relevant = find_relevant_reviews(question, '', max_reviews=3)
            if relevant:
                rev_lines = ["[ILGILI YORUMLAR]"]
                for prod, rev, sc in relevant:
                    rev_lines.append(
                        f"  {prod[:40]} | {rev.get('user', '')}: "
                        f"\"{rev.get('comment', '')[:100]}\" "
                        f"({rev.get('rate', 0)}/5)")
                results.append('\n'.join(rev_lines))
            else:
                results.append("[ILGILI YORUMLAR] Eslesen yorum yok")

            if not MISSING_GEMINI and gemini_config.get('enabled'):
                ai, conf = generate_gemini_response(question)
                if ai:
                    results.append(
                        f"[GEMINI AI] (guven: {conf:.0%}):\n{ai}")
                else:
                    results.append("[GEMINI AI] Yanit uretilemedi")
            else:
                results.append("[GEMINI AI] Devre disi")

            sep = '\n' + '-' * 50 + '\n'
            output = sep.join(results)
            self.app.after(0, lambda: self._display_result(output))

        threading.Thread(target=_run, daemon=True).start()

    def _display_result(self, text):
        self.test_output.delete('1.0', 'end')
        self.test_output.insert('1.0', text)
