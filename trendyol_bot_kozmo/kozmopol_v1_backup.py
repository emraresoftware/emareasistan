import tkinter as tk
from tkinter import messagebox
import requests
from requests.auth import HTTPBasicAuth
import time
import threading
import json
import os
from dotenv import load_dotenv
from datetime import datetime

# === Ortam Değişkenleri ===
load_dotenv()
supplier_id = os.getenv('SUPPLIER_ID')
api_key = os.getenv('API_KEY')
api_secret_key = os.getenv('API_SECRET_KEY')

# Pencere her durumda açılsın diye hata FIRLATMIYORUZ
MISSING_CREDS = not (supplier_id and api_key and api_secret_key)
if MISSING_CREDS:
    print("[UYARI] .env içinde SUPPLIER_ID / API_KEY / API_SECRET_KEY eksik. UI açılacak; API devre dışı.")

# === API Ayarları ===
base_url = f"https://apigw.trendyol.com/integration/qna/sellers/{supplier_id}" if supplier_id else ""
headers = {"User-Agent": f"{supplier_id or 'N/A'} - SelfIntegration", "Content-Type": "application/json"}

# === Veri Deposu ===
responses_file = 'automated_responses.json'
automated_responses = {}  # {('hangi','kargo'): 'cevap', ...}

out_of_service_message = (
    "Merhaba, şu anda mesai saatleri dışındayız, "
    "Sorunuzun karşılığı ürün sayfasında bulunan Soru-Cevap veya Değerlendirmeler sayfasında bulunuyor olabilir, "
    "incelemenizi tavsiye edebiliriz veya Pazartesi-Cuma 10:00-17:00 arasında sorar iseniz yardımcı olabiliriz. Saygılar"
)

# === Yardımcılar (normalize & persist) ===
def normalize_key_text(key_text: str):
    return tuple(w.strip().lower() for w in key_text.split(',') if w.strip())

def normalize_key_tuple(key_tuple):
    return tuple(w.strip().lower() for w in key_tuple if str(w).strip())

def normalize_dict(d: dict):
    norm = {}
    for k, v in d.items():
        nk = normalize_key_tuple(k) if isinstance(k, (tuple, list)) else normalize_key_text(str(k))
        if nk:
            norm[nk] = v
    return norm

def load_responses():
    """JSON'dan oku ve sözlüğü yerinde güncelle."""
    if os.path.exists(responses_file) and os.path.getsize(responses_file) > 0:
        try:
            with open(responses_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
                loaded = {}
                for key_str, value in data.items():
                    nk = normalize_key_text(key_str)
                    if nk:
                        loaded[nk] = value
                automated_responses.clear()
                automated_responses.update(loaded)
        except json.JSONDecodeError:
            print("Error decoding JSON from file.")
            automated_responses.clear()
    else:
        automated_responses.clear()

def save_responses():
    """Sözlüğü JSON'a yaz (anahtarlar 'a,b,c' formatında)."""
    data = {','.join(k): v for k, v in automated_responses.items()}
    with open(responses_file, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

# === Zamanlama ===
def is_out_of_service_hours():
    current_time = datetime.now().time()
    start_time = datetime.strptime("18:00", "%H:%M").time()
    end_time = datetime.strptime("08:30", "%H:%M").time()
    return datetime.now().weekday() >= 5 or current_time >= start_time or current_time < end_time

# === API ===
def get_customer_questions():
    if MISSING_CREDS:
        return None
    url = f"{base_url}/questions/filter?status=WAITING_FOR_ANSWER"
    response = requests.get(url, headers=headers, auth=HTTPBasicAuth(api_key, api_secret_key))
    if response.status_code == 200:
        try:
            return response.json()
        except ValueError:
            print("JSON çözümleme hatası: Yanıt verisi bir JSON formatında değil.")
            return None
    else:
        print("İstek başarısız oldu:", response.status_code, response.text)
        return None

def answer_question(question_id, answer):
    if MISSING_CREDS:
        print(f"[Simülasyon] Yanıt (ID={question_id}): {answer[:60]}...")
        return
    url = f"{base_url}/questions/{question_id}/answers"
    payload = {"text": answer}
    response = requests.post(url, headers=headers, auth=HTTPBasicAuth(api_key, api_secret_key), json=payload)
    if response.status_code == 200:
        print(f"Soru {question_id} için yanıt gönderildi.")
    else:
        try:
            print(f"Yanıt gönderme başarısız oldu: {response.status_code}", response.json())
        except Exception:
            print(f"Yanıt gönderme başarısız oldu: {response.status_code}", response.text)

def check_and_answer_questions():
    """Arka planda soruları kontrol eden thread."""
    answered_questions = set()
    while True:
        try:
            questions = get_customer_questions()
            if questions is None:
                time.sleep(300)
            elif 'content' not in questions or questions['content'] is None:
                print("Soruların içerik anahtarı bulunamadı veya içerik boş:", questions)
                time.sleep(300)
            elif len(questions['content']) == 0:
                print("Yanıtlanacak yeni soru bulunamadı.")
                time.sleep(300)
            else:
                for question in questions['content']:
                    qid = question.get('id')
                    qtext = (question.get('text') or '').lower()
                    print(f"Çekilen Soru: {qtext}")
                    if qid and qid not in answered_questions:
                        response_given = False
                        # AND mantığı: tuple'daki tüm kelimeler geçmeli
                        for search_words, response_text in list(automated_responses.items()):
                            if all(word in qtext for word in search_words):
                                answer_question(qid, response_text)
                                response_given = True
                                break
                        if not response_given:
                            if is_out_of_service_hours() and globals().get('app') and getattr(app, 'out_of_office_var', None) and app.out_of_office_var.get():
                                answer_question(qid, out_of_service_message)
                            else:
                                print(f"Soruya otomatik yanıt verilemedi: {qtext}")
                        answered_questions.add(qid)
                time.sleep(300)
        except Exception as e:
            print("[Thread Hatası]", e)
            time.sleep(300)

# === UI ===
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Trendyol Otomatik Cevap Sistemi")
        self.geometry("1024x768")   # ana ekran
        self.resizable(False, False)

        self.out_of_office_var = tk.BooleanVar(value=True)
        self.selected_key = None
        self.status_var = tk.StringVar(value="Hazır")

        # Üst bilgi ve (varsa) uyarı
        top = tk.Frame(self); top.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(top, text="Soru : anahtar(lar) • Cevap : metin  —  Tıklayıp düzenleyin", fg="#666").pack(anchor="w")

        if MISSING_CREDS:
            warn = tk.Label(self, text="API DEVRE DIŞI: .env kimlik bilgileri eksik. UI çalışıyor; otomatik cevap gönderilmez.",
                            fg="white", bg="#d9534f")
            warn.pack(fill="x", padx=10, pady=(0,6))

        cb = tk.Checkbutton(self, text="Ofis Saatleri dışında otomatik cevabı aktif et",
                            variable=self.out_of_office_var)
        cb.pack(anchor="w", padx=10, pady=(0, 8))

        # Eylem butonları (Yenile düğmesi KALDIRILDI)
        actions = tk.Frame(self); actions.pack(fill="x", padx=10, pady=(0, 6))
        tk.Button(actions, text="Yeni Ekle", command=self.add_new).pack(side="left")
        tk.Button(actions, text="Seçiliyi Sil", fg="#b00000",
                  command=self.delete_selected).pack(side="left", padx=(6,0))

        # Kaydırılabilir liste alanı
        container = tk.Frame(self); container.pack(fill="both", expand=True, padx=10, pady=8)
        self.canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        self.scroll_y = tk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.list_frame = tk.Frame(self.canvas)
        self.list_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll_y.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll_y.pack(side="right", fill="y")

        # Durum çubuğu
        status = tk.Frame(self, bd=1, relief="sunken")
        status.pack(fill="x", side="bottom")
        tk.Label(status, textvariable=self.status_var, anchor="w").pack(fill="x", padx=8)

        self.reload_list()

    # --- Ortak edit penceresi (600x300, sağ-altta Sil & Kaydet) ---
    def _open_edit_dialog(self, title, initial_text, on_save, on_delete):
        win = tk.Toplevel(self)
        win.title(title)
        # Boyut + merkez
        W, H = 600, 300
        self.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (W // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (H // 2)
        win.geometry(f"{W}x{H}+{x}+{y}")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        win.focus_set()

        # GRID düzeni
        win.rowconfigure(0, weight=1)
        win.columnconfigure(0, weight=1)

        body = tk.Frame(win)
        body.grid(row=0, column=0, sticky="nsew", padx=12, pady=(10, 6))
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        txt = tk.Text(body, wrap="word")
        txt.grid(row=0, column=0, sticky="nsew")
        txt.insert("1.0", initial_text)

        btnbar = tk.Frame(win); btnbar.grid(row=1, column=0, sticky="e", padx=12, pady=(0, 10))

        def _save_and_close(*_):
            val = txt.get("1.0", "end").strip()
            on_save(val, win)

        def _delete_and_close(*_):
            on_delete(win)

        btn_delete = tk.Button(btnbar, text="Sil", fg="#b00000", command=_delete_and_close)
        btn_save = tk.Button(btnbar, text="Kaydet", command=_save_and_close)
        btn_delete.pack(side="right", padx=(6,0))
        btn_save.pack(side="right")

        # Kısayollar
        win.bind("<Control-s>", _save_and_close)
        win.bind("<Escape>", lambda e: win.destroy())
        win.bind("<Delete>", _delete_and_close)
        txt.focus_set()
        return win

    # === Listeyi yeniden çiz (Soru : / Cevap :) ===
    def reload_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()

        normalized = normalize_dict(automated_responses)
        automated_responses.clear()
        automated_responses.update(normalized)

        items = sorted([(k, v) for k, v in automated_responses.items()],
                       key=lambda kv: ", ".join(kv[0]))

        if not items:
            tk.Label(self.list_frame, text="(Kayıt yok)", fg="#888").pack(anchor="w", pady=6)
            self.selected_key = None
            return

        for key_tuple, resp in items:
            block = tk.Frame(self.list_frame, bd=1, relief="solid", bg="#f6f6f6")
            block.pack(fill="x", pady=6, padx=0)
            block.grid_columnconfigure(1, weight=1)

            soru_text = ', '.join([s.strip() for s in key_tuple])

            # Soru : <değer>
            lbl_soru_k = tk.Label(block, text="Soru :", fg="#b00000",
                                  font=("Segoe UI", 10, "bold"), bg="#f6f6f6")
            lbl_soru_v = tk.Label(block, text=soru_text, fg="#b00000",
                                  font=("Segoe UI", 11), bg="#f6f6f6")

            # Cevap : <değer> (cevap kalın değil)
            lbl_cevap_k = tk.Label(block, text="Cevap :", font=("Segoe UI", 10, "bold"), bg="#f6f6f6")
            lbl_cevap_v = tk.Label(block, text=resp, fg="#000000",
                                   font=("Segoe UI", 11), justify="left",
                                   wraplength=940, bg="#f6f6f6")

            # Izgara yerleşimi
            lbl_soru_k.grid(row=0, column=0, sticky="nw", padx=(8,4),  pady=(6,2))
            lbl_soru_v.grid(row=0, column=1, sticky="nw", padx=(0,8),  pady=(6,2))
            lbl_cevap_k.grid(row=1, column=0, sticky="nw", padx=(8,4),  pady=(0,8))
            lbl_cevap_v.grid(row=1, column=1, sticky="w",  padx=(0,8),  pady=(0,8))

            # Tıklanıp düzenlenebilir
            for lab, handler in ((lbl_soru_v, self.edit_question), (lbl_cevap_v, self.edit_answer),
                                 (lbl_soru_k, self.edit_question), (lbl_cevap_k, self.edit_answer)):
                lab.configure(cursor="hand2", takefocus=True)
                lab.bind("<Button-1>", lambda e, k=key_tuple, h=handler: h(k))

            # Silmek için seç
            block.bind("<Button-1>", lambda e, k=key_tuple: self.set_selected(k))
            for lab in (lbl_soru_k, lbl_soru_v, lbl_cevap_k, lbl_cevap_v):
                lab.bind("<Button-1>", lambda e, k=key_tuple: self.set_selected(k), add="+")

    def set_selected(self, key_tuple):
        self.selected_key = key_tuple

    def _persist_and_refresh(self, status_msg="Kaydedildi"):
        save_responses()
        load_responses()
        self.reload_list()
        self._set_status(status_msg)

    def _set_status(self, text):
        self.status_var.set(f"{text} • {datetime.now().strftime('%H:%M:%S')}")

    # === Soru düzenle ===
    def edit_question(self, key_tuple):
        old_q = ', '.join(list(key_tuple))

        def do_save(new_text, win):
            new_key = normalize_key_text(new_text)
            if not new_key:
                messagebox.showerror("Hata", "En az bir anahtar kelime girin.", parent=win)
                return
            resp = automated_responses.get(key_tuple, "")
            if key_tuple in automated_responses:
                del automated_responses[key_tuple]
            automated_responses[new_key] = resp
            self._persist_and_refresh("Soru güncellendi")
            win.destroy()

        def do_delete(win):
            if messagebox.askyesno("Sil", "Bu kaydı silmek istiyor musunuz?", parent=win):
                if key_tuple in automated_responses:
                    del automated_responses[key_tuple]
                self._persist_and_refresh("Kayıt silindi")
                win.destroy()

        self._open_edit_dialog("Soru Düzenle (anahtar kelimeler)", old_q, do_save, do_delete)

    # === Cevap düzenle ===
    def edit_answer(self, key_tuple):
        old_a = automated_responses.get(key_tuple, "")

        def do_save(new_text, win):
            if not new_text:
                messagebox.showerror("Hata", "Cevap metni boş olamaz.", parent=win)
                return
            automated_responses[key_tuple] = new_text
            self._persist_and_refresh("Cevap güncellendi")
            win.destroy()

        def do_delete(win):
            if messagebox.askyesno("Sil", "Bu kaydı silmek istiyor musunuz?", parent=win):
                if key_tuple in automated_responses:
                    del automated_responses[key_tuple]
                self._persist_and_refresh("Kayıt silindi")
                win.destroy()

        self._open_edit_dialog("Cevap Düzenle", old_a, do_save, do_delete)

    # === Yeni kayıt ekle ===
    def add_new(self):
        # önce soru
        def do_save_soru(new_text, win):
            key = normalize_key_text(new_text)
            if not key:
                messagebox.showerror("Hata", "En az bir anahtar kelime girin.", parent=win)
                return
            win.destroy()

            # sonra cevap
            def do_save_cevap(a_text, w2):
                if not a_text:
                    messagebox.showerror("Hata", "Cevap metni boş olamaz.", parent=w2)
                    return
                automated_responses[key] = a_text
                self._persist_and_refresh("Yeni kayıt eklendi")
                w2.destroy()

            def do_delete_cevap(w2):
                w2.destroy()

            self._open_edit_dialog("Cevap Ekle", "", do_save_cevap, do_delete_cevap)

        def do_delete_soru(win):
            win.destroy()

        self._open_edit_dialog("Soru Ekle (anahtar kelimeler, virgülle)", "", do_save_soru, do_delete_soru)

    def delete_selected(self):
        if not self.selected_key:
            messagebox.showwarning("Uyarı", "Silmek için listeden bir kayıt tıklayın.")
            return
        if messagebox.askyesno("Sil", "Bu kaydı silmek istediğinize emin misiniz?"):
            if self.selected_key in automated_responses:
                del automated_responses[self.selected_key]
            self._persist_and_refresh("Kayıt silindi")
            self.selected_key = None

# === Çalıştırma ===
if __name__ == "__main__":
    load_responses()
    app = App()  # UI önce oluşturulsun
    # Kimlik bilgileri TAM ise arka plan thread'i başlat
    if not MISSING_CREDS:
        question_thread = threading.Thread(target=check_and_answer_questions, daemon=True)
        question_thread.start()
    else:
        print("[Bilgi] Kimlik bilgileri eksik olduğu için otomatik cevap thread'i başlatılmadı.")
    app.mainloop()
