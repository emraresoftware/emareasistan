"""
ui.tab_templates — Tab: Yanit Sablonlari
==========================================
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from config import QUESTION_CATEGORIES, BRAND, COLORS
from core.data import response_templates, save_templates


class TemplatesTab:
    """Yanit Sablonlari sekmesi."""

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self._build()

    def _build(self):
        top = ttk.Frame(self.parent)
        top.pack(fill='x', padx=8, pady=6)

        ttk.Label(top, text="Hizli yanit sablonlari — "
                  "{{degisken}} ifadeleri degistirilebilir",
                  style='Muted.TLabel').pack(side='left')
        ttk.Button(top, text="Yeni Sablon",
                   command=self.add_template).pack(side='right')

        paned = ttk.PanedWindow(self.parent, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        left_frame = ttk.LabelFrame(paned, text="Sablonlar", padding=4)
        paned.add(left_frame, weight=1)

        self.listbox = tk.Listbox(
            left_frame, font=('Helvetica', 11), selectmode='browse')
        self.listbox.pack(fill='both', expand=True)
        self.listbox.bind('<<ListboxSelect>>', self._on_select)

        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill='x', pady=(4, 0))
        ttk.Button(btn_frame, text="Duzenle",
                   command=self.edit_template).pack(side='left')
        ttk.Button(btn_frame, text="Sil",
                   command=self.delete_template).pack(
            side='left', padx=(4, 0))

        right_frame = ttk.LabelFrame(paned, text="Sablon Onizleme", padding=8)
        paned.add(right_frame, weight=2)

        self.preview = scrolledtext.ScrolledText(
            right_frame, wrap='word', font=('Helvetica', 11), state='disabled')
        self.preview.pack(fill='both', expand=True)

        info_frame = ttk.Frame(right_frame)
        info_frame.pack(fill='x', pady=(4, 0))
        self.info_var = tk.StringVar()
        ttk.Label(info_frame, textvariable=self.info_var,
                  style='Muted.TLabel').pack(side='left')

    def refresh_list(self):
        if not hasattr(self, 'listbox'):
            return
        self.listbox.delete(0, 'end')
        for t in response_templates:
            cat = t.get('category', '')
            cat_info = QUESTION_CATEGORIES.get(cat, {})
            icon = cat_info.get('icon', '')
            self.listbox.insert('end', f"{icon} {t['name']}")

    def _on_select(self, event=None):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(response_templates):
            t = response_templates[idx]
            self.preview.configure(state='normal')
            self.preview.delete('1.0', 'end')
            self.preview.insert('1.0', t['text'])
            self.preview.configure(state='disabled')
            vars_str = ', '.join(
                f'{{{{{v}}}}}' for v in t.get('variables', []))
            cat_info = QUESTION_CATEGORIES.get(t.get('category', ''), {})
            self.info_var.set(
                f"Kategori: {cat_info.get('label', t.get('category', 'Genel'))} | "
                f"Degiskenler: {vars_str or 'Yok'}")

    def add_template(self):
        win = tk.Toplevel(self.app)
        win.title("Yeni Sablon")
        win.geometry("600x450")
        win.transient(self.app)
        win.grab_set()

        ttk.Label(win, text="Sablon Adi:").pack(anchor='w', padx=10, pady=(10, 2))
        name_var = tk.StringVar()
        ttk.Entry(win, textvariable=name_var, width=40).pack(anchor='w', padx=10)

        ttk.Label(win, text="Kategori:").pack(anchor='w', padx=10, pady=(8, 2))
        cat_var = tk.StringVar(value='diger')
        ttk.Combobox(win, textvariable=cat_var,
                     values=list(QUESTION_CATEGORIES.keys()),
                     width=20, state='readonly').pack(anchor='w', padx=10)

        ttk.Label(win, text="Sablon Metni ({{degisken}} kullanin):").pack(
            anchor='w', padx=10, pady=(8, 2))
        text_widget = scrolledtext.ScrolledText(
            win, wrap='word', height=10, font=('Helvetica', 11))
        text_widget.pack(fill='both', expand=True, padx=10)

        ttk.Label(win, text="Degiskenler (virgul ile):").pack(
            anchor='w', padx=10, pady=(8, 2))
        vars_var = tk.StringVar()
        ttk.Entry(win, textvariable=vars_var, width=40).pack(anchor='w', padx=10)

        def save():
            name = name_var.get().strip()
            text = text_widget.get('1.0', 'end').strip()
            if not name or not text:
                messagebox.showerror("Hata", "Ad ve metin zorunludur.", parent=win)
                return
            variables = [v.strip() for v in vars_var.get().split(',') if v.strip()]
            response_templates.append({
                'name': name, 'text': text,
                'variables': variables, 'category': cat_var.get()})
            save_templates()
            self.refresh_list()
            self.app._set_status(f"Sablon eklendi: {name}")
            win.destroy()

        btn = ttk.Frame(win)
        btn.pack(fill='x', padx=10, pady=10)
        ttk.Button(btn, text="Kaydet", command=save).pack(side='right')
        ttk.Button(btn, text="Iptal", command=win.destroy).pack(
            side='right', padx=(0, 6))

    def edit_template(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showwarning("Uyari", "Bir sablon secin.")
            return
        idx = sel[0]
        t = response_templates[idx]

        win = tk.Toplevel(self.app)
        win.title(f"Sablon Duzenle — {t['name']}")
        win.geometry("600x450")
        win.transient(self.app)
        win.grab_set()

        ttk.Label(win, text="Sablon Adi:").pack(anchor='w', padx=10, pady=(10, 2))
        name_var = tk.StringVar(value=t['name'])
        ttk.Entry(win, textvariable=name_var, width=40).pack(anchor='w', padx=10)

        ttk.Label(win, text="Kategori:").pack(anchor='w', padx=10, pady=(8, 2))
        cat_var = tk.StringVar(value=t.get('category', 'diger'))
        ttk.Combobox(win, textvariable=cat_var,
                     values=list(QUESTION_CATEGORIES.keys()),
                     width=20, state='readonly').pack(anchor='w', padx=10)

        ttk.Label(win, text="Sablon Metni:").pack(
            anchor='w', padx=10, pady=(8, 2))
        text_widget = scrolledtext.ScrolledText(
            win, wrap='word', height=10, font=('Helvetica', 11))
        text_widget.pack(fill='both', expand=True, padx=10)
        text_widget.insert('1.0', t['text'])

        ttk.Label(win, text="Degiskenler:").pack(
            anchor='w', padx=10, pady=(8, 2))
        vars_var = tk.StringVar(value=', '.join(t.get('variables', [])))
        ttk.Entry(win, textvariable=vars_var, width=40).pack(anchor='w', padx=10)

        def save():
            name = name_var.get().strip()
            text = text_widget.get('1.0', 'end').strip()
            if not name or not text:
                messagebox.showerror("Hata", "Ad ve metin zorunludur.", parent=win)
                return
            variables = [v.strip() for v in vars_var.get().split(',') if v.strip()]
            response_templates[idx] = {
                'name': name, 'text': text,
                'variables': variables, 'category': cat_var.get()}
            save_templates()
            self.refresh_list()
            self.app._set_status(f"Sablon guncellendi: {name}")
            win.destroy()

        btn = ttk.Frame(win)
        btn.pack(fill='x', padx=10, pady=10)
        ttk.Button(btn, text="Kaydet", command=save).pack(side='right')
        ttk.Button(btn, text="Iptal", command=win.destroy).pack(
            side='right', padx=(0, 6))

    def delete_template(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showwarning("Uyari", "Bir sablon secin.")
            return
        idx = sel[0]
        name = response_templates[idx]['name']
        if messagebox.askyesno("Sil", f"'{name}' sablonunu silmek istiyor musunuz?"):
            response_templates.pop(idx)
            save_templates()
            self.refresh_list()
            self.preview.configure(state='normal')
            self.preview.delete('1.0', 'end')
            self.preview.configure(state='disabled')
            self.app._set_status(f"Sablon silindi: {name}")
