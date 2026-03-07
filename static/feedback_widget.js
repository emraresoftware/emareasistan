/**
 * Emare Geri Bildirim Widget — Universal v1.0
 * Her projede çalışır. API_URL'i projeye göre ayarlayın.
 * Kullanım: <script src="/static/feedback_widget.js" data-api="/api/feedback"></script>
 */
(function () {
  'use strict';

  const API_URL = document.currentScript?.getAttribute('data-api') || '/api/feedback';
  const CSRF_META = document.querySelector('meta[name="csrf-token"]');
  const CSRF_TOKEN = CSRF_META ? CSRF_META.getAttribute('content') : '';

  // ── CSS ──────────────────────────────────────────────────────────────
  const CSS = `
#em-fb-btn {
  position: fixed; bottom: 24px; right: 24px; z-index: 99998;
  width: 52px; height: 52px; border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #9333ea);
  border: none; cursor: pointer; box-shadow: 0 4px 20px rgba(99,102,241,.45);
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; transition: transform .2s, box-shadow .2s;
}
#em-fb-btn:hover { transform: scale(1.1); box-shadow: 0 6px 28px rgba(99,102,241,.6); }
#em-fb-btn .em-fb-badge {
  position: absolute; top: -4px; right: -4px;
  background: #ef4444; color: #fff; font-size: 10px; font-weight: 700;
  width: 18px; height: 18px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  display: none;
}
#em-fb-panel {
  position: fixed; bottom: 88px; right: 24px; z-index: 99999;
  width: 340px; max-height: 520px;
  background: #0f1020; border: 1px solid rgba(99,102,241,.25);
  border-radius: 18px; overflow: hidden;
  box-shadow: 0 20px 60px rgba(0,0,0,.5);
  display: none; flex-direction: column;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  animation: em-fb-slide .22s ease;
}
@keyframes em-fb-slide {
  from { opacity: 0; transform: translateY(16px) scale(.97); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
#em-fb-panel.open { display: flex; }
.em-fb-header {
  padding: 16px 18px 12px;
  border-bottom: 1px solid rgba(255,255,255,.06);
  display: flex; align-items: center; justify-content: space-between;
}
.em-fb-header h3 { font-size: 14px; font-weight: 700; color: #f1f5f9; margin: 0; }
.em-fb-header span { font-size: 11px; color: #64748b; }
.em-fb-close { background: none; border: none; color: #475569; cursor: pointer; font-size: 18px; padding: 0; line-height: 1; }
.em-fb-close:hover { color: #f1f5f9; }
.em-fb-tabs {
  display: flex; border-bottom: 1px solid rgba(255,255,255,.06);
}
.em-fb-tab {
  flex: 1; padding: 10px; font-size: 12px; font-weight: 600;
  background: none; border: none; color: #64748b; cursor: pointer;
  border-bottom: 2px solid transparent; transition: all .15s;
}
.em-fb-tab.active { color: #818cf8; border-bottom-color: #6366f1; }
.em-fb-tab:hover { color: #a5b4fc; }
.em-fb-body { padding: 16px; overflow-y: auto; flex: 1; }
.em-fb-cats {
  display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 14px;
}
.em-fb-cat {
  padding: 8px 10px; border-radius: 10px; border: 1px solid rgba(255,255,255,.08);
  background: rgba(255,255,255,.03); color: #94a3b8; font-size: 12px;
  cursor: pointer; transition: all .15s; text-align: center;
}
.em-fb-cat:hover { border-color: rgba(99,102,241,.4); color: #c7d2fe; }
.em-fb-cat.sel { background: rgba(99,102,241,.15); border-color: #6366f1; color: #a5b4fc; }
.em-fb-cat span { display: block; font-size: 18px; margin-bottom: 3px; }
.em-fb-pris { display: flex; gap: 6px; margin-bottom: 14px; }
.em-fb-pri {
  flex: 1; padding: 5px 4px; border-radius: 8px; border: 1px solid rgba(255,255,255,.08);
  background: rgba(255,255,255,.03); color: #94a3b8; font-size: 11px;
  cursor: pointer; transition: all .15s; text-align: center;
}
.em-fb-pri.sel { background: rgba(99,102,241,.15); border-color: #6366f1; color: #a5b4fc; }
.em-fb-pri:hover { border-color: rgba(99,102,241,.4); }
textarea.em-fb-txt {
  width: 100%; min-height: 90px; resize: none;
  background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.1);
  border-radius: 10px; color: #e2e8f0; font-size: 13px; padding: 10px 12px;
  font-family: inherit; outline: none; transition: border-color .15s;
  box-sizing: border-box;
}
textarea.em-fb-txt:focus { border-color: rgba(99,102,241,.5); }
textarea.em-fb-txt::placeholder { color: #475569; }
.em-fb-footer { padding: 12px 16px 16px; border-top: 1px solid rgba(255,255,255,.06); }
.em-fb-send {
  width: 100%; padding: 10px; border-radius: 10px; border: none;
  background: linear-gradient(135deg, #6366f1, #9333ea);
  color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;
  transition: opacity .15s;
}
.em-fb-send:hover { opacity: .9; }
.em-fb-send:disabled { opacity: .5; cursor: not-allowed; }
.em-fb-success {
  text-align: center; padding: 24px 16px; display: none;
}
.em-fb-success .em-fb-check { font-size: 40px; margin-bottom: 10px; }
.em-fb-success p { color: #94a3b8; font-size: 13px; margin: 0; }
.em-fb-success h4 { color: #f1f5f9; font-size: 15px; margin: 4px 0 8px; }
.em-fb-hist { list-style: none; padding: 0; margin: 0; }
.em-fb-hist li {
  padding: 12px; border-radius: 10px; background: rgba(255,255,255,.03);
  border: 1px solid rgba(255,255,255,.07); margin-bottom: 8px;
}
.em-fb-hist li .em-fb-hcat {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 999px;
  margin-bottom: 6px;
}
.em-fb-hist li p { font-size: 12px; color: #94a3b8; margin: 0 0 6px; }
.em-fb-hist li .em-fb-status {
  font-size: 10px; font-weight: 600; padding: 2px 7px; border-radius: 999px;
}
.em-fb-hist li .em-fb-reply {
  margin-top: 8px; padding: 8px 10px; border-left: 3px solid #6366f1;
  background: rgba(99,102,241,.07); border-radius: 0 6px 6px 0;
  font-size: 11px; color: #94a3b8;
}
.em-fb-empty { text-align: center; padding: 30px 0; color: #475569; font-size: 13px; }
  `;

  // ── DOM ──────────────────────────────────────────────────────────────
  function inject() {
    const style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);

    // Buton
    const btn = document.createElement('button');
    btn.id = 'em-fb-btn';
    btn.innerHTML = '<span>💬</span><span class="em-fb-badge" id="em-fb-badge">●</span>';
    btn.title = 'Geri Bildirim';
    document.body.appendChild(btn);

    // Panel
    const panel = document.createElement('div');
    panel.id = 'em-fb-panel';
    panel.innerHTML = `
      <div class="em-fb-header">
        <div><h3>💬 Geri Bildirim</h3><span>Görüşleriniz bizim için değerli</span></div>
        <button class="em-fb-close" id="em-fb-close">✕</button>
      </div>
      <div class="em-fb-tabs">
        <button class="em-fb-tab active" data-tab="yeni">Yeni Bildirim</button>
        <button class="em-fb-tab" data-tab="gecmis">Geçmişim</button>
      </div>
      <div id="em-fb-tab-yeni" class="em-fb-body">
        <div class="em-fb-cats">
          <button class="em-fb-cat sel" data-cat="bug"><span>🐛</span>Hata</button>
          <button class="em-fb-cat" data-cat="suggestion"><span>💡</span>Öneri</button>
          <button class="em-fb-cat" data-cat="question"><span>❓</span>Soru</button>
          <button class="em-fb-cat" data-cat="other"><span>💬</span>Diğer</button>
        </div>
        <div class="em-fb-pris">
          <button class="em-fb-pri" data-pri="low">Düşük</button>
          <button class="em-fb-pri sel" data-pri="normal">Normal</button>
          <button class="em-fb-pri" data-pri="high">Yüksek</button>
          <button class="em-fb-pri" data-pri="critical">Kritik</button>
        </div>
        <textarea class="em-fb-txt" id="em-fb-msg" placeholder="Mesajınızı yazın... (min 3 karakter)" maxlength="2000"></textarea>
        <div class="em-fb-success" id="em-fb-success">
          <div class="em-fb-check">✅</div>
          <h4>Teşekkür ederiz!</h4>
          <p>Geri bildiriminiz iletildi.<br>En kısa sürede inceleneceğiz.</p>
        </div>
      </div>
      <div id="em-fb-tab-gecmis" class="em-fb-body" style="display:none;">
        <ul class="em-fb-hist" id="em-fb-hist-list"></ul>
      </div>
      <div class="em-fb-footer" id="em-fb-footer">
        <button class="em-fb-send" id="em-fb-send">Gönder →</button>
      </div>
    `;
    document.body.appendChild(panel);

    // State
    let selCat = 'bug';
    let selPri = 'normal';
    let open = false;

    function togglePanel() {
      open = !open;
      panel.classList.toggle('open', open);
      if (open && panel.querySelector('[data-tab="gecmis"]').classList.contains('active')) loadHistory();
    }

    btn.addEventListener('click', togglePanel);
    document.getElementById('em-fb-close').addEventListener('click', togglePanel);

    // Kategori seçimi
    panel.querySelectorAll('.em-fb-cat').forEach(b => {
      b.addEventListener('click', () => {
        panel.querySelectorAll('.em-fb-cat').forEach(x => x.classList.remove('sel'));
        b.classList.add('sel');
        selCat = b.dataset.cat;
      });
    });

    // Öncelik seçimi
    panel.querySelectorAll('.em-fb-pri').forEach(b => {
      b.addEventListener('click', () => {
        panel.querySelectorAll('.em-fb-pri').forEach(x => x.classList.remove('sel'));
        b.classList.add('sel');
        selPri = b.dataset.pri;
      });
    });

    // Tab geçişi
    panel.querySelectorAll('.em-fb-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        panel.querySelectorAll('.em-fb-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const which = tab.dataset.tab;
        document.getElementById('em-fb-tab-yeni').style.display = which === 'yeni' ? '' : 'none';
        document.getElementById('em-fb-tab-gecmis').style.display = which === 'gecmis' ? '' : 'none';
        document.getElementById('em-fb-footer').style.display = which === 'yeni' ? '' : 'none';
        if (which === 'gecmis') loadHistory();
      });
    });

    // Gönder
    document.getElementById('em-fb-send').addEventListener('click', async () => {
      const msg = document.getElementById('em-fb-msg').value.trim();
      if (msg.length < 3) { document.getElementById('em-fb-msg').focus(); return; }
      const sendBtn = document.getElementById('em-fb-send');
      sendBtn.disabled = true;
      sendBtn.textContent = 'Gönderiliyor...';

      const headers = { 'Content-Type': 'application/json' };
      if (CSRF_TOKEN) headers['X-CSRFToken'] = CSRF_TOKEN;

      try {
        const res = await fetch(API_URL, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            message: msg,
            category: selCat,
            priority: selPri,
            page_url: location.href,
          }),
        });
        const data = await res.json();
        if (data.success !== false) {
          document.getElementById('em-fb-msg').value = '';
          document.getElementById('em-fb-success').style.display = 'block';
          setTimeout(() => {
            document.getElementById('em-fb-success').style.display = 'none';
          }, 3000);
        }
      } catch (e) { console.error('Feedback error:', e); }

      sendBtn.disabled = false;
      sendBtn.textContent = 'Gönder →';
    });

    // Geçmiş yükle
    async function loadHistory() {
      const list = document.getElementById('em-fb-hist-list');
      list.innerHTML = '<div class="em-fb-empty">Yükleniyor...</div>';
      const STATUS_COLORS = {
        open: 'background:rgba(251,191,36,.15);color:#fbbf24',
        in_progress: 'background:rgba(96,165,250,.15);color:#60a5fa',
        resolved: 'background:rgba(74,222,128,.15);color:#4ade80',
        closed: 'background:rgba(148,163,184,.15);color:#94a3b8',
      };
      const STATUS_LABELS = { open: 'Açık', in_progress: 'İnceleniyor', resolved: 'Çözüldü', closed: 'Kapatıldı' };
      const CAT_COLORS = {
        bug: 'background:rgba(248,113,113,.15);color:#f87171',
        suggestion: 'background:rgba(96,165,250,.15);color:#60a5fa',
        question: 'background:rgba(167,139,250,.15);color:#a78bfa',
        other: 'background:rgba(148,163,184,.15);color:#94a3b8',
      };
      try {
        const res = await fetch(API_URL + '/my');
        const data = await res.json();
        const items = data.messages || data.feedbacks || [];
        if (!items.length) { list.innerHTML = '<div class="em-fb-empty">Henüz geri bildiriminiz yok</div>'; return; }
        list.innerHTML = items.map(f => `
          <li>
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
              <span class="em-fb-hcat" style="${CAT_COLORS[f.category] || ''}">${f.category_label || f.category}</span>
              <span class="em-fb-status" style="${STATUS_COLORS[f.status] || ''}">${STATUS_LABELS[f.status] || f.status}</span>
            </div>
            <p>${f.message}</p>
            <small style="color:#475569;font-size:11px">${f.created_at || ''}</small>
            ${f.admin_reply ? `<div class="em-fb-reply">💬 ${f.admin_reply}${f.replied_at ? '<br><small style="color:#475569">' + f.replied_at + '</small>' : ''}</div>` : ''}
          </li>
        `).join('');
      } catch (e) {
        list.innerHTML = '<div class="em-fb-empty">Geçmiş yüklenemedi</div>';
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inject);
  } else {
    inject();
  }
})();
