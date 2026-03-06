"""
ui.tab_pending — Tab: Bekleyen Sorular
========================================
"""

import re
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from config import QUESTION_CATEGORIES, BRAND, COLORS
from core.data import (
    pending_questions, save_pending, add_log_entry,
    automated_responses, save_responses, normalize_key_text,
    response_templates,
)
from api.trendyol import answer_question
from ui.dialogs import open_edit_dialog


class PendingTab:
    """Bekleyen Sorular sekmesi."""

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self._build()

    def _build(self):
        top = ttk.Frame(self.parent)
        top.pack(fill='x', padx=8, pady=6)

        ttk.Label(
            top,
            text="AI tarafindan uretilen veya eslesme bulunamayan yanitlar",
            style='Muted.TLabel').pack(side='left')
        ttk.Button(top, text="Yenile",
                   command=self.refresh_list).pack(side='right')
        ttk.Button(top, text="Tamamlananlari Temizle",
                   command=self.clear_completed).pack(side='right', padx=(0, 6))

        # Kategori filtresi
        filter_frame = ttk.Frame(self.parent)
        filter_frame.pack(fill='x', padx=8, pady=(0, 4))
        ttk.Label(filter_frame, text="Kategori:").pack(side='left')
        self.cat_var = tk.StringVar(value='Tumu')
        cat_values = ['Tumu'] + [
            c['label'] for c in QUESTION_CATEGORIES.values()]
        ttk.Combobox(
            filter_frame, textvariable=self.cat_var,
            values=cat_values, width=20, state='readonly'
        ).pack(side='left', padx=4)
        ttk.Button(filter_frame, text="Filtrele",
                   command=self.refresh_list).pack(side='left', padx=4)

        # Alt butonlar
        btn_frame = ttk.Frame(self.parent)
        btn_frame.pack(fill='x', padx=8, pady=(0, 8), side='bottom')
        ttk.Button(btn_frame, text="Onayla ve Gonder",
                   command=self.approve).pack(side='left')
        ttk.Button(btn_frame, text="Duzenle ve Gonder",
                   command=self.edit_and_send).pack(side='left', padx=(6, 0))
        ttk.Button(btn_frame, text="Reddet",
                   command=self.reject).pack(side='left', padx=(6, 0))
        ttk.Button(btn_frame, text="Sablondan Yanit",
                   command=self.reply_from_template).pack(
            side='left', padx=(6, 0))

        ttk.Separator(btn_frame, orient='vertical').pack(
            side='left', fill='y', padx=8)
        ttk.Button(btn_frame, text="Tumunu Onayla",
                   command=self.approve_all).pack(side='left')
        ttk.Button(btn_frame, text="Tumunu Reddet",
                   command=self.reject_all).pack(side='left', padx=(6, 0))
        ttk.Button(btn_frame, text="Yanit Olarak Kaydet",
                   command=self.save_as_response).pack(side='right')

        # Treeview
        columns = ('kategori', 'zaman', 'soru', 'oneri', 'guven', 'durum')
        tree_frame = ttk.Frame(self.parent)
        tree_frame.pack(fill='both', expand=True, padx=8, pady=(0, 4))

        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', height=20)
        self.tree.heading('kategori', text='Kategori')
        self.tree.heading('zaman', text='Zaman')
        self.tree.heading('soru', text='Soru')
        self.tree.heading('oneri', text='AI Onerisi')
        self.tree.heading('guven', text='Guven')
        self.tree.heading('durum', text='Durum')

        self.tree.column('kategori', width=100, minwidth=80)
        self.tree.column('zaman', width=120, minwidth=100)
        self.tree.column('soru', width=280, minwidth=200)
        self.tree.column('oneri', width=380, minwidth=200)
        self.tree.column('guven', width=60, minwidth=50)
        self.tree.column('durum', width=90, minwidth=70)

        p_scroll = ttk.Scrollbar(
            tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=p_scroll.set)
        self.tree.pack(fill='both', expand=True, side='left')
        p_scroll.pack(side='right', fill='y')

    # ─── Liste ───
    def refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        cat_filter = self.cat_var.get() if hasattr(self, 'cat_var') else 'Tumu'

        for i, p in enumerate(pending_questions):
            if p.get('status') in ('sent', 'rejected'):
                continue
            cat = p.get('category', 'diger')
            cat_info = QUESTION_CATEGORIES.get(cat, {})
            cat_label = cat_info.get('label', cat)
            if cat_filter != 'Tumu' and cat_label != cat_filter:
                continue

            ts = p.get('timestamp', '')[:16].replace('T', ' ')
            q = p.get('question', '')[:80]
            a = p.get('suggested_answer', '')[:80]
            c = f"{p.get('confidence', 0):.0%}"
            s = p.get('status', 'pending')
            status_map = {'pending': 'Bekliyor', 'no_match': 'Eslesmedi'}
            self.tree.insert(
                '', 'end', iid=str(i),
                values=(cat_label, ts, q, a, c, status_map.get(s, s)))

    def _get_selected_idx(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Uyari", "Bir soru secin.")
            return None
        return int(sel[0])

    # ─── Islemler ───
    def approve(self):
        idx = self._get_selected_idx()
        if idx is None:
            return
        p = pending_questions[idx]
        if not p.get('suggested_answer'):
            messagebox.showerror("Hata", "Bu soru icin AI onerisi yok.")
            return
        answer_text = p['suggested_answer']
        if '[KARA_LISTE_UYARI' in answer_text:
            answer_text = re.sub(
                r'\[KARA_LISTE_UYARI:[^\]]*\]\s*', '', answer_text).strip()
        if answer_question(p['question_id'], answer_text):
            p['status'] = 'sent'
            save_pending()
            add_log_entry(p['question_id'], p['question'],
                          answer_text, 'manual_approved')
            self.refresh_list()
            self.app.refresh_stats()
            self.app._set_status("Yanit onaylandi ve gonderildi")

    def edit_and_send(self):
        idx = self._get_selected_idx()
        if idx is None:
            return
        p = pending_questions[idx]

        def do_save(text, win):
            if not text.strip():
                messagebox.showerror("Hata", "Yanit bos olamaz.", parent=win)
                return
            if answer_question(p['question_id'], text.strip()):
                p['status'] = 'sent'
                p['suggested_answer'] = text.strip()
                save_pending()
                add_log_entry(p['question_id'], p['question'],
                              text.strip(), 'manual_edited')
                self.refresh_list()
                self.app.refresh_stats()
                self.app._set_status("Duzenlenmis yanit gonderildi")
                win.destroy()

        initial = p.get('suggested_answer', '')
        if '[KARA_LISTE_UYARI' in initial:
            initial = re.sub(
                r'\[KARA_LISTE_UYARI:[^\]]*\]\s*', '', initial).strip()

        open_edit_dialog(
            self.app, f"Yaniti Duzenle — {p['question'][:50]}...",
            initial, do_save, lambda w: w.destroy())

    def reject(self):
        idx = self._get_selected_idx()
        if idx is None:
            return
        pending_questions[idx]['status'] = 'rejected'
        save_pending()
        self.refresh_list()
        self.app._set_status("Soru reddedildi")

    def approve_all(self):
        active = [
            (i, p) for i, p in enumerate(pending_questions)
            if p.get('status') == 'pending'
            and p.get('suggested_answer')
            and '[KARA_LISTE_UYARI' not in p.get('suggested_answer', '')
        ]
        if not active:
            messagebox.showinfo("Bilgi", "Onaylanacak soru yok.")
            return
        if not messagebox.askyesno(
                "Toplu Onay",
                f"{len(active)} bekleyen soruyu onaylamak istediginize emin misiniz?"):
            return
        count = 0
        for i, p in active:
            if answer_question(p['question_id'], p['suggested_answer']):
                p['status'] = 'sent'
                add_log_entry(p['question_id'], p['question'],
                              p['suggested_answer'], 'manual_approved')
                count += 1
        save_pending()
        self.refresh_list()
        self.app.refresh_stats()
        self.app._set_status(f"{count} soru toplu onaylandi")

    def reject_all(self):
        active = [
            (i, p) for i, p in enumerate(pending_questions)
            if p.get('status') in ('pending', 'no_match')
        ]
        if not active:
            messagebox.showinfo("Bilgi", "Reddedilecek soru yok.")
            return
        if not messagebox.askyesno(
                "Toplu Reddet",
                f"{len(active)} bekleyen soruyu reddetmek istediginize emin misiniz?"):
            return
        for i, p in active:
            p['status'] = 'rejected'
        save_pending()
        self.refresh_list()
        self.app._set_status(f"{len(active)} soru toplu reddedildi")

    def reply_from_template(self):
        idx = self._get_selected_idx()
        if idx is None:
            return
        if not response_templates:
            messagebox.showinfo("Bilgi", "Henuz sablon tanimlanmamis.")
            return

        p = pending_questions[idx]
        win = tk.Toplevel(self.app)
        win.title("Sablondan Yanit")
        win.geometry("650x500")
        win.transient(self.app)
        win.grab_set()

        ttk.Label(win, text=f"Soru: {p.get('question', '')[:80]}...",
                  wraplength=600).pack(anchor='w', padx=10, pady=(10, 6))

        ttk.Label(win, text="Sablon Secin:").pack(anchor='w', padx=10)
        tmpl_var = tk.StringVar()
        template_names = [t['name'] for t in response_templates]
        tmpl_combo = ttk.Combobox(
            win, textvariable=tmpl_var,
            values=template_names, width=40, state='readonly')
        tmpl_combo.pack(anchor='w', padx=10, pady=4)

        ttk.Label(win, text="Onizleme / Duzenle:").pack(
            anchor='w', padx=10, pady=(8, 0))
        preview_text = scrolledtext.ScrolledText(
            win, wrap='word', height=12, font=('Helvetica', 11))
        preview_text.pack(fill='both', expand=True, padx=10, pady=4)

        def on_select(*_):
            name = tmpl_var.get()
            tmpl = next((t for t in response_templates
                         if t['name'] == name), None)
            if tmpl:
                preview_text.delete('1.0', 'end')
                preview_text.insert('1.0', tmpl['text'])

        tmpl_combo.bind('<<ComboboxSelected>>', on_select)

        def do_send():
            text = preview_text.get('1.0', 'end').strip()
            if not text:
                messagebox.showerror("Hata", "Yanit bos olamaz.", parent=win)
                return
            if answer_question(p['question_id'], text):
                p['status'] = 'sent'
                p['suggested_answer'] = text
                save_pending()
                add_log_entry(p['question_id'], p['question'],
                              text, 'template')
                self.refresh_list()
                self.app.refresh_stats()
                self.app._set_status("Sablondan yanit gonderildi")
                win.destroy()

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill='x', padx=10, pady=(0, 10))
        ttk.Button(btn_frame, text="Gonder", command=do_send).pack(side='right')
        ttk.Button(btn_frame, text="Iptal",
                   command=win.destroy).pack(side='right', padx=(0, 6))

    def save_as_response(self):
        idx = self._get_selected_idx()
        if idx is None:
            return
        p = pending_questions[idx]

        def do_save_key(key_text, win):
            key = normalize_key_text(key_text)
            if not key:
                messagebox.showerror(
                    "Hata", "En az bir anahtar kelime girin.", parent=win)
                return
            win.destroy()

            def do_save_answer(answer_text, w2):
                if not answer_text.strip():
                    messagebox.showerror("Hata", "Cevap bos olamaz.", parent=w2)
                    return
                automated_responses[key] = answer_text.strip()
                save_responses()
                self.app.responses_tab.reload_list()
                answer_question(p['question_id'], answer_text.strip())
                p['status'] = 'sent'
                save_pending()
                self.refresh_list()
                self.app.refresh_stats()
                self.app._set_status("Yeni yanit kurali kaydedildi ve gonderildi")
                w2.destroy()

            open_edit_dialog(
                self.app, "Cevap", p.get('suggested_answer', ''),
                do_save_answer, lambda w: w.destroy())

        words = re.findall(r'\w+', p.get('question', '').lower())
        suggested = ','.join(w for w in words if len(w) > 2)[:100]
        open_edit_dialog(
            self.app, "Anahtar Kelimeler (virgul ile)", suggested,
            do_save_key, lambda w: w.destroy())

    def clear_completed(self):
        global pending_questions
        from core import data as _d
        _d.pending_questions = [
            p for p in _d.pending_questions
            if p.get('status') not in ('sent', 'rejected')
        ]
        # Yerel referansi da guncelle
        pending_questions.clear()
        pending_questions.extend(_d.pending_questions)
        save_pending()
        self.refresh_list()
        self.app._set_status("Tamamlananlar temizlendi")
