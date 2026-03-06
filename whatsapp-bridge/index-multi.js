/**
 * Emare Asistan WhatsApp Bridge - Çoklu Hesap Desteği
 * Her bağlantı ayrı Client, Admin istediği kadar oluşturup kullanıcıya atayabilir
 */
const path = require('path');
try {
  require('dotenv').config({ path: path.join(__dirname, '.env') });
  require('dotenv').config({ path: path.join(__dirname, '..', '.env') });
} catch (e) { /* dotenv yoksa devam */ }
const http = require('http');
const { Client, LocalAuth, MessageMedia, Location } = require('whatsapp-web.js');
const QRCode = require('qrcode');
const axios = require('axios');

const { execSync } = require('child_process');

const fs = require('fs');

const API_URL = process.env.ASISTAN_API_URL || 'http://localhost:8000';
const API_TIMEOUT = parseInt(process.env.ASISTAN_API_TIMEOUT_MS || '120000', 10); // 120 sn
const QR_PORT = parseInt(process.env.QR_PORT || '3100', 10);
const MAX_QR_ATTEMPTS = 15; // ~5 dakika sonra QR üretmeyi durdur (bellek koruma)
const CHROME_MAX_HEAP_MB = 512; // Chrome JS heap limiti
const MAX_RECONNECT_ATTEMPTS = 3; // Bağlantı kopunca max yeniden deneme
const LAZY_LOADING = process.env.LAZY_LOADING !== 'false'; // Kayıtlı oturumu olmayan bağlantıları başlatma
const MAX_CONCURRENT_CHROME = parseInt(process.env.MAX_CONCURRENT_CHROME || '3', 10); // Aynı anda max Chrome sayısı

// Docker ortamında sistem Chromium'u kullan
const CHROMIUM_PATH = process.env.PUPPETEER_EXECUTABLE_PATH || process.env.CHROME_PATH || null;

// connection_id -> { client, qr, status, phone, name, fallbackPhone, qrAttempts, reconnectAttempts }
const connections = new Map();

// Orphan Chrome süreçlerini temizle
function killOrphanChromeProcesses() {
  try {
    const result = execSync('pgrep -f "chrome.*whatsapp" || true', { encoding: 'utf8' }).trim();
    if (result) {
      console.log('[Chrome] Orphan süreçler temizleniyor:', result.split('\n').length, 'adet');
      execSync('pkill -f "chrome.*whatsapp" || true');
    }
  } catch (e) { /* ignore */ }
}

// Bellek kullanımını logla
function logMemoryUsage() {
  const mem = process.memoryUsage();
  const rss = Math.round(mem.rss / 1024 / 1024);
  const heap = Math.round(mem.heapUsed / 1024 / 1024);
  console.log(`[Bellek] Node RSS: ${rss}MB, Heap: ${heap}MB`);
}

function getConnectionsFile() {
  return path.join(__dirname, 'connections.json');
}

async function loadConnectionsFromAPI() {
  try {
    const r = await axios.get(`${API_URL}/api/bridge/connections`, { timeout: 5000 });
    const list = r.data || [];
    if (list.length === 0) {
      console.warn('API boş bağlantı listesi döndü, varsayılan kullanılıyor');
      return [{ id: 'default', name: 'Ana Hesap', auth_path: 'default' }];
    }
    return list;
  } catch (e) {
    console.warn('Python API\'den bağlantılar alınamadı, varsayılan kullanılıyor:', e.message);
    return [{ id: 'default', name: 'Ana Hesap', auth_path: 'default' }];
  }
}

async function fetchImageAsMedia(url) {
  try {
    return await MessageMedia.fromUrl(url, { unsafeMime: true });
  } catch (e) {
    const resp = await axios.get(url, { responseType: 'arraybuffer', timeout: 30000 });
    const base64 = Buffer.from(resp.data).toString('base64');
    const contentType = resp.headers['content-type'] || 'image/jpeg';
    return new MessageMedia(contentType, base64);
  }
}

function collectBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try { resolve(body ? JSON.parse(body) : {}); } catch (e) { resolve({}); }
    });
    req.on('error', reject);
  });
}

// Startup'ta Chrome lock dosyalarını temizle (container restart sonrası kalan locklar)
function cleanChromeLocks() {
  const authBaseDir = process.env.AUTH_BASE_DIR || __dirname;
  try {
    const entries = fs.readdirSync(authBaseDir).filter(e => e.startsWith('.wwebjs_auth'));
    let cleaned = 0;
    for (const entry of entries) {
      const sessionDir = path.join(authBaseDir, entry, 'session');
      if (fs.existsSync(sessionDir)) {
        for (const f of ['SingletonLock', 'SingletonSocket', 'SingletonCookie']) {
          const lockFile = path.join(sessionDir, f);
          try { fs.unlinkSync(lockFile); cleaned++; } catch (e) { /* yok veya silinemedi */ }
        }
      }
    }
    if (cleaned > 0) console.log(`[Startup] ${cleaned} Chrome lock dosyası temizlendi`);
  } catch (e) { /* ignore */ }
}

// Auth verisi var mı kontrol et (session kayıtlı mı?)
function hasAuthSession(authPath) {
  const suffix = (authPath === 'default' ? '' : '_' + authPath);
  const authBaseDir = process.env.AUTH_BASE_DIR || __dirname;
  const authDir = path.join(authBaseDir, '.wwebjs_auth' + suffix);
  try {
    if (fs.existsSync(authDir)) {
      const files = fs.readdirSync(authDir);
      return files.length > 0;
    }
  } catch (e) { /* ignore */ }
  return false;
}

async function createClient(connId, name, authPath, fallbackPhone = null) {
  const suffix = (authPath === 'default' ? '' : '_' + authPath);
  // AUTH_BASE_DIR: Docker'da mount edilen dizin (host auth verileri burada)
  const authBaseDir = process.env.AUTH_BASE_DIR || __dirname;
  const dataPath = path.join(authBaseDir, '.wwebjs_auth' + suffix);

  const puppeteerConfig = {
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--disable-software-rasterizer',
      '--disable-extensions',
      '--no-first-run',
      '--disable-background-networking',
      '--disable-default-apps',
      '--disable-sync',
      '--metrics-recording-only',
      '--mute-audio',
      // Chrome bellek limitleri - çökme koruması
      `--js-flags=--max-old-space-size=${CHROME_MAX_HEAP_MB}`,
      '--renderer-process-limit=2',
      '--disable-features=TranslateUI,BlinkGenPropertyTrees',
      '--disable-ipc-flooding-protection',
      '--disable-renderer-backgrounding',
      '--disable-backgrounding-occluded-windows',
      '--disable-component-update',
      '--memory-pressure-off',
    ]
  };
  // Docker'da sistem Chromium'u kullan
  if (CHROMIUM_PATH) {
    puppeteerConfig.executablePath = CHROMIUM_PATH;
    console.log(`[${connId}] Chromium: ${CHROMIUM_PATH}`);
  }

  const client = new Client({
    authStrategy: new LocalAuth({ dataPath }),
    puppeteer: puppeteerConfig
  });

  let conn = { client, qr: null, status: 'disconnected', phone: null, widSerialized: null, name, fallbackPhone, qrAttempts: 0, reconnectAttempts: 0 };
  connections.set(connId, conn);

  client.on('qr', (qr) => {
    conn.qrAttempts++;
    if (conn.qrAttempts > MAX_QR_ATTEMPTS) {
      console.warn(`[${connId}] QR limiti aşıldı (${conn.qrAttempts}/${MAX_QR_ATTEMPTS}). Chrome bellek koruması: client durduruluyor.`);
      conn.status = 'qr_timeout';
      conn.qr = null;
      // Client'ı kapat, Chrome'u serbest bırak
      client.destroy().catch(e => console.error(`[${connId}] Destroy hatası:`, e.message));
      logMemoryUsage();
      return;
    }
    conn.qr = qr;
    conn.status = 'qr_pending';
    console.log(`[${connId}] QR hazır (deneme ${conn.qrAttempts}/${MAX_QR_ATTEMPTS})`);
  });

  client.on('ready', async () => {
    conn.qr = null;
    conn.qrAttempts = 0; // QR sayacını sıfırla
    conn.reconnectAttempts = 0; // Yeniden bağlanma sayacını sıfırla
    conn.status = 'connected';
    try {
      const info = await client.info;
      conn.phone = info?.wid?.user || null;
      conn.widSerialized = info?.wid?._serialized || null;
    } catch (e) { /* ignore */ }

    // Bot'un LID'ini al (yeni WhatsApp format - @lid mention tespiti için)
    try {
      const lidInfo = await client.pupPage.evaluate(() => {
        try {
          // Yöntem 1: Store.Me.attributes.lid
          const Store = window.Store || {};
          if (Store.Me && Store.Me.attributes && Store.Me.attributes.lid) {
            const lid = Store.Me.attributes.lid;
            return lid._serialized || String(lid);
          }
          // Yöntem 2: ContactModel getMaybeMeContact
          const me = Store.Contact && typeof Store.Contact.getMaybeMeContact === 'function'
            ? Store.Contact.getMaybeMeContact() : null;
          if (me && me.lid) return me.lid._serialized || String(me.lid);
          // Yöntem 3: Conn model
          if (Store.Conn && Store.Conn.attributes && Store.Conn.attributes.lid) {
            return Store.Conn.attributes.lid._serialized || String(Store.Conn.attributes.lid);
          }
          return null;
        } catch(e) { return null; }
      });
      if (lidInfo) {
        conn.lidSerialized = lidInfo;
        conn.lidUser = lidInfo.split('@')[0];
      }
    } catch (e) { /* ignore */ }

    console.log(`[${connId}] Bağlandı (phone=${conn.phone}, wid=${conn.widSerialized}, lid=${conn.lidSerialized || 'bilinmiyor'})`);
    logMemoryUsage();

    // ── Catch-up: bağlantı yokken gelen okunmamış mesajları tara ──
    try {
      const chats = await client.getChats();
      let unreadCount = 0;
      const catchupWindowSec = 1800; // Son 30 dakika
      const nowSec = Date.now() / 1000;
      for (const chat of chats) {
        // Grup sohbetlerini catch-up'tan hariç tut (sadece DM)
        if (chat.id?._serialized?.endsWith('@g.us')) continue;
        if (chat.unreadCount > 0) {
          try {
            const msgs = await chat.fetchMessages({ limit: Math.min(chat.unreadCount, 20) });
            for (const msg of msgs) {
              if (!msg.fromMe && msg.timestamp > (nowSec - catchupWindowSec)) {
                unreadCount++;
                // Doğrudan API'ye gönder (mesaj kuyruğu yerine sıralı işle)
                const msgText = (msg.body || '').trim();
                if (!msgText) continue;
                try {
                  const payload = {
                    from: msg.from,
                    text: msgText,
                    connection_id: connId,
                  };
                  const response = await axios.post(
                    `${API_URL}/api/whatsapp/process`,
                    payload,
                    { timeout: API_TIMEOUT }
                  );
                  const { text: replyText } = response.data || {};
                  if (replyText && replyText.trim()) {
                    await msg.reply(replyText.trim());
                    console.log(`[${connId}] Geçmiş mesaj yanıtlandı: ${msg.from} → ${replyText.substring(0, 50)}...`);
                  }
                } catch (apiErr) {
                  console.error(`[${connId}] Geçmiş mesaj API hatası:`, apiErr.message);
                }
              }
            }
          } catch (fetchErr) {
            console.error(`[${connId}] Chat mesaj çekme hatası:`, fetchErr.message);
          }
        }
      }
      if (unreadCount > 0) {
        console.log(`[${connId}] 📬 ${unreadCount} okunmamış mesaj işlendi (catch-up)`);
      }
    } catch (err) {
      console.error(`[${connId}] Okunmamış mesaj tarama hatası:`, err.message);
    }
  });

  client.on('auth_failure', (m) => {
    console.error(`[${connId}] Auth hatası:`, m);
    conn.status = 'auth_failed';
    // Auth hatası durumunda Chrome'u kapat
    client.destroy().catch(e => console.error(`[${connId}] Auth destroy hatası:`, e.message));
  });

  client.on('disconnected', async (reason) => {
    conn.status = 'disconnected';
    conn.qr = null;
    conn.phone = null;
    conn.reconnectAttempts++;
    const reasonStr = (reason && typeof reason === 'string') ? reason : (reason ? String(reason) : 'bilinmiyor');
    console.log(`[${connId}] Bağlantı kesildi. Sebep: ${reasonStr} (deneme ${conn.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
    logMemoryUsage();

    // Max deneme aşıldıysa duraksla
    if (conn.reconnectAttempts > MAX_RECONNECT_ATTEMPTS) {
      console.warn(`[${connId}] Max yeniden bağlanma denemesi aşıldı. 5 dakika bekleniyor...`);
      // Önce Chrome'u temizle
      try { await client.destroy(); } catch (e) { /* ignore */ }
      setTimeout(async () => {
        conn.reconnectAttempts = 0;
        conn.qrAttempts = 0;
        console.log(`[${connId}] Bekleme süresi doldu, tekrar deniyor...`);
        try {
          await client.initialize();
        } catch (e) {
          console.error(`[${connId}] Yeniden başlatma hatası:`, e.message);
        }
      }, 300000); // 5 dakika bekle
      return;
    }

    const delayMs = reasonStr.includes('CONNECTION_LOST') ? 15000 : 5000;
    setTimeout(async () => {
      try {
        conn.qrAttempts = 0; // QR sayacını sıfırla
        await client.initialize();
      } catch (e) {
        console.error(`[${connId}] Yeniden başlatma hatası:`, e.message);
      }
    }, delayMs);
  });

  client.on('message', async (message) => {
    if (message.fromMe) return;

    // Grup mesajı tespiti - birden fazla JID formatını kontrol et
    const fromJid = message.from || '';
    const remoteJid = (message.id && message.id.remote) || '';
    const isGroup = fromJid.endsWith('@g.us') || remoteJid.endsWith('@g.us');
    let groupName = null;
    let sender = null;

    // Debug: Her mesajın kaynağını logla
    if (isGroup || message.author) {
      console.log(`[${connId}] 📩 from=${fromJid} remote=${remoteJid} author=${message.author || 'N/A'} isGroup=${isGroup}`);
    }

    if (isGroup) {
      try {
        const chat = await message.getChat();
        groupName = (chat.name || '').trim();
        sender = (message.author || '').replace('@c.us', '').replace('@s.whatsapp.net', '').replace(/@lid$/, '');
      } catch (e) {
        console.error(`[${connId}] Grup bilgisi alınamadı:`, e.message);
        return;
      }

      // Gruplarda SADECE WhatsApp'ın resmi @mention özelliği veya mesajda @emareasistan geçtiğinde yanıt ver
      // NOT: "emareasistan" kelimesi @ olmadan geçiyorsa tetiklemez (yanlış pozitif önleme)
      const msgBody = (message.body || '').toLowerCase();
      const textMention = msgBody.includes('@emareasistan') || msgBody.includes('@emare asistan');

      // whatsapp-web.js: mentionedIds botun kendi numarasını içeriyorsa mention edilmiş demektir
      // NOT: Yeni WhatsApp hesapları LID formatı kullanır (144784102580253@lid), telefon numarasıyla eşleşmez!
      let botMentioned = false;
      try {
        const mentions = message.mentionedIds || [];
        const botPhone = conn.phone || '';
        const botWid = conn.widSerialized || '';
        const botLidUser = botWid.includes('@lid') ? botWid.split('@')[0] : '';

        if (mentions.length > 0) {
          console.log(`[${connId}] 🔍 mentionedIds:`, JSON.stringify(mentions.map(m => m._serialized || m)));
          botMentioned = mentions.some(mid => {
            const midStr = (mid._serialized || String(mid)).toString();
            const midUser = midStr.split('@')[0];
            // 1. Telefon numarası eşleşmesi (@c.us format)
            if (botPhone && (midUser === botPhone || midStr.includes(botPhone))) return true;
            // 2. Tam WID eşleşmesi
            if (botWid && midStr === botWid) return true;
            // 3. Bilinen LID eşleşmesi (pupPage'den alındıysa)
            if (conn.lidSerialized && midStr === conn.lidSerialized) return true;
            if (conn.lidUser && midUser === conn.lidUser) return true;
            return false;
          });

          // Fallback: LID bilinmiyorsa ve sadece @lid formatlı mention varsa bot'a aittir
          // (Yeni WhatsApp format - grup için @c.us yerine @lid kullanılır)
          if (!botMentioned && !conn.lidSerialized) {
            const hasLidMention = mentions.some(mid => {
              const midStr = (mid._serialized || String(mid)).toString();
              return midStr.endsWith('@lid');
            });
            if (hasLidMention) {
              botMentioned = true;
              // LID'i öğren ve kaydet (kendini öğrenen sistem)
              const lidMention = mentions.find(mid => {
                const s = (mid._serialized || String(mid)).toString();
                return s.endsWith('@lid');
              });
              if (lidMention) {
                conn.lidSerialized = lidMention._serialized || String(lidMention);
                conn.lidUser = conn.lidSerialized.split('@')[0];
                console.log(`[${connId}] 💡 Bot LID öğrenildi: ${conn.lidSerialized}`);
              }
            }
          }
        }

        // Ek: body'de @{phone} veya @{lidUser} var mı? (mentionedIds boş gelse bile)
        if (!botMentioned) {
          if (botPhone && msgBody.includes('@' + botPhone)) botMentioned = true;
          if (!botMentioned && botLidUser && msgBody.includes('@' + botLidUser)) botMentioned = true;
          if (!botMentioned && conn.lidUser && msgBody.includes('@' + conn.lidUser)) botMentioned = true;
        }
      } catch (e) { /* ignore */ }

      if (!textMention && !botMentioned) {
        // Mention yoksa sessiz kal - debug log
        const preview = (message.body || '').substring(0, 40);
        console.log(`[${connId}] 🔇 Grup mesajı ignore: "${groupName}" - "${preview}" (mention yok)`);
        return;
      }
      console.log(`[${connId}] 👥 Grup mention: "${groupName}" - ${sender} (text:${textMention}, botMention:${botMentioned})`);
    }

    let text = (message.body || '').trim();
    // Grup mesajında mention etiketlerini mesaj metninden temizle
    if (isGroup) {
      // @numara formatını temizle (WhatsApp mention: @905xx...)
      text = text.replace(/@\d{10,15}/g, '').trim();
      // @emareasistan / @emare asistan metin formatını temizle
      text = text.replace(/@emareasistan/gi, '').replace(/@emare\s*asistan/gi, '').trim();
      // İsimlendirme ile mention temizle (ör: @Emare Asistan)
      text = text.replace(/@emare\s*/gi, '').trim();
      if (!text) text = 'merhaba'; // Sadece mention yazıldıysa varsayılan mesaj
    }
    console.log(`[${connId}] Mesaj alındı:`, text ? text.substring(0, 50) + (text.length > 50 ? '...' : '') : '(medya)');
    let audioBase64 = null;
    let audioMimetype = null;
    let imageBase64 = null;
    let imageMimetype = null;

    // Resim - Vision AI ürün eşleştirme için
    if (message.type === 'image' || (message.hasMedia && (message.type === 'image' || message.type === 'sticker'))) {
      try {
        const media = await message.downloadMedia();
        if (media && media.data && (media.mimetype || '').startsWith('image/')) {
          imageBase64 = media.data;
          imageMimetype = media.mimetype || 'image/jpeg';
        }
      } catch (e) {
        console.error(`[${connId}] Resim indirilemedi:`, e.message);
      }
    }

    // Sesli mesaj (PTT) - indir ve API'ye gönder
    if ((!text || !text.trim()) && !imageBase64 && (message.type === 'ptt' || (message.hasMedia && message.type === 'audio'))) {
      try {
        const media = await message.downloadMedia();
        if (media && media.data) {
          audioBase64 = media.data;
          audioMimetype = media.mimetype || 'audio/ogg';
        }
      } catch (e) {
        console.error(`[${connId}] Sesli mesaj indirilemedi:`, e.message);
        return;
      }
    }
    if (!text && !audioBase64 && !imageBase64) return;

    const chat = await message.getChat();
    const fromNumber = message.from;
    let repliedToCaption = null;
    if (message.hasQuotedMsg) {
      const quoted = await message.getQuotedMessage();
      repliedToCaption = (quoted.caption || quoted.body || '').trim() || null;
    }

    try {
      const payload = {
        from: fromNumber,
        text: text || '',
        replied_to_caption: repliedToCaption,
        connection_id: connId,
        is_group: isGroup,
        group_name: groupName,
        sender: sender,
      };
      if (audioBase64) {
        payload.audio_base64 = audioBase64;
        payload.audio_mimetype = audioMimetype;
      }
      if (imageBase64) {
        payload.image_base64 = imageBase64;
        payload.image_mimetype = imageMimetype;
      }
      const response = await axios.post(
        `${API_URL}/api/whatsapp/process`,
        payload,
        { timeout: API_TIMEOUT }
      );

      const { text: replyText, images = [], videos = [], location, audio_base64, audio_mimetype } = response.data;
      if (replyText) console.log(`[${connId}] Yanıt gönderildi (${replyText.length} karakter)`);
      let sent = false;
      if (audio_base64 && audio_mimetype) {
        try {
          const media = new MessageMedia(audio_mimetype || 'audio/mpeg', audio_base64, 'yanit.mp3');
          await message.reply(media);
          sent = true;
        } catch (err) {
          console.error(`[${connId}] Sesli yanıt gönderilemedi:`, err.message);
        }
      }
      if (!sent && replyText && replyText.trim()) {
        await message.reply(replyText.trim());
        sent = true;
      }
      if (location) {
        try {
          const loc = new Location(location.lat, location.lng, { name: location.name || 'Firma', address: location.address || '' });
          await chat.sendMessage(loc);
          sent = true;
        } catch (err) { console.error('Konum gönderilemedi:', err.message); }
      }
      for (const img of images) {
        try {
          const media = await MessageMedia.fromUrl(img.url, { unsafeMime: true });
          await chat.sendMessage(media, { caption: img.caption || '' });
          sent = true;
        } catch (err) { console.error('Resim gönderilemedi:', err.message); }
      }
      for (const vid of videos) {
        try {
          const media = await MessageMedia.fromUrl(vid.url, { unsafeMime: true });
          await chat.sendMessage(media, { caption: vid.caption || '' });
          sent = true;
        } catch (err) { console.error('Video gönderilemedi:', err.message); }
      }
      if (!sent && (location || images.length || videos.length)) sent = true;
      if (!sent) {
        const fallbackPhone = (conn?.fallbackPhone || process.env.FALLBACK_PHONE || '').trim();
        if (fallbackPhone) {
          await message.reply(`Mesajınız alındı. En kısa sürede dönüş yapacağız. Acil durumda ${fallbackPhone} numarasından ulaşabilirsiniz.`);
        } else {
          await message.reply('Mesajınız alındı. En kısa sürede dönüş yapacağız.');
        }
      }
    } catch (err) {
      console.error(`[${connId}] API hatası:`, err.message, err.code || '', err.response?.status || '');
      const fallbackPhone = (conn?.fallbackPhone || process.env.FALLBACK_PHONE || '').trim();
      if (fallbackPhone) {
        await message.reply(`Üzgünüz, şu an yanıt veremiyoruz. ${fallbackPhone} numarasından bize ulaşabilirsiniz.`);
      } else {
        await message.reply('Üzgünüz, şu an yanıt veremiyoruz. Lütfen birazdan tekrar deneyin.');
      }
    }
  });

  // initialize'ı fire-and-forget yap (bloklama)
  client.initialize().catch(e => {
    console.error(`[${connId}] Chrome başlatma hatası:`, e.message);
  });
  return client;
}

async function initConnections() {
  const list = await loadConnectionsFromAPI();
  
  // fallback_phone doluysa öncelikli sırala (aktif olma ihtimali yüksek)
  const sorted = [...list].sort((a, b) => {
    const aPhone = (a.fallback_phone || '').replace(/\D/g, '');
    const bPhone = (b.fallback_phone || '').replace(/\D/g, '');
    if (aPhone && !bPhone) return -1;
    if (!aPhone && bPhone) return 1;
    return 0;
  });
  
  let started = 0, skipped = 0;
  for (const c of sorted) {
    const id = String(c.id);
    if (!connections.has(id)) {
      const authPath = c.auth_path || id;
      
      // Max eşzamanlı Chrome limiti: daha fazla Chrome başlatma
      if (started >= MAX_CONCURRENT_CHROME) {
        connections.set(id, {
          client: null, qr: null, status: 'idle',
          phone: null, name: c.name || id,
          fallbackPhone: c.fallback_phone || null,
          qrAttempts: 0, reconnectAttempts: 0,
          authPath: authPath
        });
        skipped++;
        console.log(`[${id}] ⏸️  Chrome limiti (${MAX_CONCURRENT_CHROME}), idle`);
        continue;
      }
      
      // LAZY LOADING: Kaydedilmiş auth oturumu yoksa Chrome başlatma
      if (LAZY_LOADING && !hasAuthSession(authPath)) {
        connections.set(id, {
          client: null, qr: null, status: 'idle',
          phone: null, name: c.name || id,
          fallbackPhone: c.fallback_phone || null,
          qrAttempts: 0, reconnectAttempts: 0,
          authPath: authPath
        });
        skipped++;
        console.log(`[${id}] ⏸️  Auth oturumu yok, idle (Chrome başlatılmadı)`);
        continue;
      }
      try {
        await createClient(id, c.name || id, authPath, c.fallback_phone || null);
        started++;
        // Chrome'lar arası 3 saniye bekle (resource spike önleme)
        if (started > 0) await new Promise(r => setTimeout(r, 3000));
      } catch (e) {
        console.error(`[${id}] Başlatılamadı:`, e.message);
      }
    }
  }
  console.log(`[Başlatma] ${started} bağlantı başlatıldı, ${skipped} idle (toplam: ${sorted.length})`);
}

async function reloadConnections() {
  const list = await loadConnectionsFromAPI();
  for (const c of list) {
    const id = String(c.id);
    const existing = connections.get(id);
    if (existing) {
      existing.fallbackPhone = c.fallback_phone || null;
    } else {
      try {
        await createClient(id, c.name || id, c.auth_path || id, c.fallback_phone || null);
        console.log(`[${id}] Yeni bağlantı eklendi`);
      } catch (e) {
        console.error(`[${id}] Başlatılamadı:`, e.message);
      }
    }
  }
}

function getClientForSend(connectionId) {
  if (connectionId) {
    const c = connections.get(String(connectionId));
    if (c?.status === 'connected') return c.client;
  }
  for (const [id, c] of connections) {
    if (c.status === 'connected') return c.client;
  }
  return null;
}

const server = http.createServer(async (req, res) => {
  res.setHeader('Content-Type', 'application/json; charset=utf-8');

  if (req.method === 'GET' && req.url === '/api/connections') {
    const list = [];
    for (const [id, c] of connections) {
      list.push({ id, name: c.name, status: c.status, phone: c.phone });
    }
    res.statusCode = 200;
    res.end(JSON.stringify(list));
    return;
  }

  if (req.method === 'POST' && req.url === '/api/reload') {
    try {
      await reloadConnections();
      res.statusCode = 200;
      res.end(JSON.stringify({ ok: true }));
    } catch (e) {
      res.statusCode = 500;
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }

  // Belirli bir bağlantıyı yeniden başlat (QR timeout veya idle durumundan)
  if (req.method === 'POST' && /^\/api\/connections\/([^/]+)\/restart$/.test(req.url)) {
    const m = req.url.match(/^\/api\/connections\/([^/]+)\/restart$/);
    const connId = m[1];
    const conn = connections.get(connId);
    if (!conn) {
      res.statusCode = 404;
      res.end(JSON.stringify({ error: 'Bağlantı bulunamadı' }));
      return;
    }
    try {
      console.log(`[${connId}] Manuel yeniden başlatma istendi (durum: ${conn.status})`);
      // idle durumundaki bağlantı için sıfırdan Chrome başlat
      if (conn.status === 'idle' && !conn.client) {
        const authPath = conn.authPath || connId;
        await createClient(connId, conn.name, authPath, conn.fallbackPhone);
        res.statusCode = 200;
        res.end(JSON.stringify({ ok: true, message: 'Chrome başlatılıyor, QR bekleniyor' }));
      } else {
        try { await conn.client.destroy(); } catch (e) { /* ignore */ }
        conn.qrAttempts = 0;
        conn.reconnectAttempts = 0;
        conn.status = 'disconnected';
        await conn.client.initialize();
        res.statusCode = 200;
        res.end(JSON.stringify({ ok: true, message: 'Yeniden başlatılıyor' }));
      }
    } catch (e) {
      res.statusCode = 500;
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }

  if (req.method === 'GET' && req.url === '/api/status') {
    const client = getClientForSend();
    res.statusCode = 200;
    res.end(JSON.stringify({ connected: !!client }));
    return;
  }

  if (req.method === 'GET' && /^\/api\/connections\/([^/]+)\/qr$/.test(req.url)) {
    const m = req.url.match(/^\/api\/connections\/([^/]+)\/qr$/);
    let conn = connections.get(m[1]);
    if (!conn) {
      try {
        await reloadConnections();
        conn = connections.get(m[1]);
      } catch (e) {
        console.error('QR isteği sırasında reload hatası:', e.message);
      }
    }
    if (!conn || !conn.qr) {
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.statusCode = 200;
      const msg = !conn
        ? 'Bu bağlantı henüz bridge\'de yok. Bridge yeniden yükleniyor...'
        : 'QR hazırlanıyor. Yeni hesap veya kopan bağlantı için 10-15 sn sürebilir.';
      res.end(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>WhatsApp QR</title></head><body style="font-family:sans-serif;text-align:center;padding:40px;background:#f8fafc;">
        <h1>⏳ ${!conn ? 'Bağlantı yükleniyor' : 'QR hazırlanıyor'}...</h1>
        <p style="color:#64748b;">${msg}</p>
        <p style="font-size:0.9rem;color:#94a3b8;">Sayfa 4 sn'de yenilenecek.</p>
        <script>setTimeout(()=>location.reload(),4000)</script>
      </body></html>`);
      return;
    }
    try {
      const qrDataUrl = await QRCode.toDataURL(conn.qr, { width: 280, margin: 2 });
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.end(`<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WhatsApp QR</title><style>
        body{margin:0;padding:12px;font-family:sans-serif;text-align:center;box-sizing:border-box;}
        .qr-wrap{max-width:min(280px,90vw);margin:0 auto;}
        .qr-wrap img{width:100%;height:auto;display:block;border:6px solid #fff;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.12);}
        h1{font-size:1.1rem;margin:0 0 8px;}
        p{font-size:0.85rem;color:#666;margin:8px 0 0;}
      </style></head><body>
        <h1>📱 WhatsApp'a Bağlan</h1>
        <div class="qr-wrap"><img src="${qrDataUrl}" alt="QR"></div>
        <p>QR 60 sn'de yenilenir.</p>
        <script>setTimeout(()=>location.reload(),5000)</script>
      </body></html>`);
    } catch (e) {
      console.error(`[${m[1]}] QRCode.toDataURL hatası:`, e.message);
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.statusCode = 200;
      res.end(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>WhatsApp QR</title></head><body style="font-family:sans-serif;text-align:center;padding:40px;background:#fef2f2;">
        <h1>⚠️ QR oluşturulamadı</h1>
        <p style="color:#991b1b;">${e.message}</p>
        <p style="font-size:0.9rem;color:#94a3b8;">Sayfa 5 sn'de yenilenecek.</p>
        <script>setTimeout(()=>location.reload(),5000)</script>
      </body></html>`);
    }
    return;
  }

  if (req.method === 'POST' && req.url === '/send') {
    const client = getClientForSend();
    if (!client) {
      res.statusCode = 503;
      res.end(JSON.stringify({ error: 'WhatsApp bağlı değil' }));
      return;
    }
    try {
      const body = await collectBody(req);
      const connectionId = body.connection_id ? String(body.connection_id) : null;
      const sendClient = getClientForSend(connectionId) || client;

      let to = (body.to || '').toString().replace(/\s/g, '').replace(/^\+/, '');
      if (to.startsWith('0')) to = '90' + to.slice(1);
      to = to.replace(/\D/g, '');
      const text = (body.text || '').toString().trim();
      const imageUrl = (body.image_url || '').toString().trim();
      const imageUrls = Array.isArray(body.image_urls) ? body.image_urls.map(u => String(u).trim()).filter(Boolean) : [];
      const caption = (body.caption || '').toString().trim();

      if (!to) {
        res.statusCode = 400;
        res.end(JSON.stringify({ error: 'to gerekli' }));
        return;
      }
      if (!text && !imageUrl && !imageUrls.length) {
        res.statusCode = 400;
        res.end(JSON.stringify({ error: 'text veya image_url/image_urls gerekli' }));
        return;
      }

      const chatId = to.includes('@') ? to : to + '@c.us';
      const chat = await sendClient.getChatById(chatId);

      if (imageUrl || imageUrls.length) {
        const urls = imageUrl ? [imageUrl] : imageUrls;
        for (let i = 0; i < urls.length; i++) {
          const media = await fetchImageAsMedia(urls[i]);
          const cap = (i === 0 && caption) ? caption : '';
          await chat.sendMessage(media, cap ? { caption: cap } : {});
        }
      } else {
        await chat.sendMessage(text);
      }
      res.statusCode = 200;
      res.end(JSON.stringify({ ok: true }));
    } catch (err) {
      console.error('Gönderim hatası:', err.message);
      res.statusCode = 500;
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  if (req.url === '/' || req.url === '/qr') {
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    const client = getClientForSend();
    if (client) {
      res.end(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>Emare WhatsApp</title></head><body style="font-family:sans-serif;text-align:center;padding:40px;background:#e8f5e9;">
        <h1>✅ WhatsApp bağlı!</h1>
        <p><a href="/api/connections">Bağlantılar</a></p>
      </body></html>`);
      return;
    }
    const first = [...connections.values()][0];
    if (first?.qr) {
      try {
        const qrDataUrl = await QRCode.toDataURL(first.qr, { width: 280, margin: 2 });
        res.end(`<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WhatsApp QR</title><style>
          body{margin:0;padding:12px;font-family:sans-serif;text-align:center;}
          .qr-wrap{max-width:min(280px,90vw);margin:0 auto;}
          .qr-wrap img{width:100%;height:auto;border:6px solid #fff;border-radius:10px;}
        </style></head><body>
          <h1>📱 WhatsApp'a Bağlan</h1>
          <div class="qr-wrap"><img src="${qrDataUrl}" alt="QR"></div>
          <p><script>setTimeout(()=>location.reload(),5000)</script></p>
        </body></html>`);
      } catch (e) { res.end(`<h1>Hata</h1><p>${e.message}</p>`); }
    } else {
      res.end(`<!DOCTYPE html><html><body style="font-family:sans-serif;text-align:center;padding:40px;"><h1>⏳ Hazırlanıyor...</h1><script>setTimeout(()=>location.reload(),2000)</script></body></html>`);
    }
    return;
  }

  res.statusCode = 404;
  res.end('Not found');
});

// Periyodik bellek izleme (her 5 dakika)
setInterval(() => {
  logMemoryUsage();
  // Chrome süreç sayısını kontrol et
  try {
    const count = execSync('pgrep -c chrome || echo 0', { encoding: 'utf8' }).trim();
    console.log(`[Chrome] Aktif süreç sayısı: ${count}`);
    if (parseInt(count) > 10) {
      console.warn('[Chrome] Çok fazla süreç! Temizleme yapılacak...');
      // Bağlı olmayan client'ları destroy et
      for (const [id, c] of connections) {
        if (c.status === 'qr_timeout' || c.status === 'auth_failed') {
          console.log(`[${id}] Inactive client temizleniyor...`);
          c.client.destroy().catch(() => {});
        }
      }
    }
  } catch (e) { /* ignore */ }
}, 300000); // 5 dakika

// Graceful shutdown - Chrome süreçlerini temizle
process.on('SIGTERM', async () => {
  console.log('[Shutdown] SIGTERM alındı, Chrome temizleniyor...');
  for (const [id, c] of connections) {
    try { await c.client.destroy(); } catch (e) { /* ignore */ }
  }
  killOrphanChromeProcesses();
  process.exit(0);
});

process.on('SIGINT', async () => {
  console.log('[Shutdown] SIGINT alındı, Chrome temizleniyor...');
  for (const [id, c] of connections) {
    try { await c.client.destroy(); } catch (e) { /* ignore */ }
  }
  killOrphanChromeProcesses();
  process.exit(0);
});

async function main() {
  console.log(`[Başlatma] Chrome heap limiti: ${CHROME_MAX_HEAP_MB}MB, Max QR deneme: ${MAX_QR_ATTEMPTS}, Max reconnect: ${MAX_RECONNECT_ATTEMPTS}`);
  logMemoryUsage();
  cleanChromeLocks();
  await initConnections();
  server.listen(QR_PORT, '0.0.0.0', () => {
    console.log(`\n📱 http://0.0.0.0:${QR_PORT}\n`);
  });
}

main().catch(err => {
  console.error('Başlatma hatası:', err);
  killOrphanChromeProcesses();
  process.exit(1);
});
