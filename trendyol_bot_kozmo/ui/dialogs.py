"""
ui.dialogs — Ortak Duzenleme Diyalogu
=======================================
"""

import tkinter as tk
from tkinter import ttk, scrolledtext

from config import BRAND, COLORS


def open_edit_dialog(parent, title, initial_text, on_save, on_cancel):
    """
    Ortak duzenleme penceresi ac.
    parent  : Ana pencere (App)
    on_save : callback(text, win)
    on_cancel: callback(win)
    """
    win = tk.Toplevel(parent)
    win.title(title)
    W, H = 680, 380
    parent.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (W // 2)
    y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (H // 2)
    win.geometry(f"{W}x{H}+{x}+{y}")
    win.resizable(True, True)
    win.transient(parent)
    win.grab_set()
    win.focus_set()

    t = parent.theme if hasattr(parent, 'theme') else {}
    bg = t.get('bg', COLORS['white'])
    fg = t.get('fg', COLORS['gray_800'])
    f = parent.fonts if hasattr(parent, 'fonts') else {}
    body_font = f.get('body', ('Helvetica', 12))

    win.configure(bg=bg)

    win.rowconfigure(0, weight=1)
    win.columnconfigure(0, weight=1)

    body = tk.Frame(win, bg=bg)
    body.grid(row=0, column=0, sticky='nsew', padx=16, pady=(14, 8))
    body.rowconfigure(0, weight=1)
    body.columnconfigure(0, weight=1)

    txt = scrolledtext.ScrolledText(
        body, wrap='word', font=body_font,
        bg=t.get('input_bg', COLORS['white']),
        fg=fg,
        insertbackground=t.get('accent', BRAND[500]),
        selectbackground=t.get('accent', BRAND[500]),
        selectforeground=COLORS['white'],
        relief='flat',
        borderwidth=1,
        highlightbackground=t.get('input_border', BRAND[200]),
        highlightthickness=1,
        highlightcolor=t.get('accent', BRAND[500]))
    txt.grid(row=0, column=0, sticky='nsew')
    txt.insert('1.0', initial_text)

    btnbar = tk.Frame(win, bg=bg)
    btnbar.grid(row=1, column=0, sticky='e', padx=16, pady=(0, 14))

    def _save(*_):
        val = txt.get('1.0', 'end').strip()
        on_save(val, win)

    def _cancel(*_):
        on_cancel(win)

    ttk.Button(btnbar, text="Kaydet", command=_save).pack(
        side='right', padx=(6, 0))
    ttk.Button(btnbar, text="Iptal", command=_cancel).pack(side='right')

    win.bind('<Control-s>', _save)
    win.bind('<Escape>', lambda e: win.destroy())
    txt.focus_set()
    return win
