/**
 * Emare Asistan WhatsApp Bridge - QR ile giriş (tek hesap)
 * 
 * Kullanım:
 *   1. python main.py  (Python API çalışıyor olmalı)
 *   2. npm run start:single  veya  node index.js
 *   3. Tarayıcıda http://localhost:3100 açın, QR kodu telefonla tarayın
 */
const path = require('path');
try {
  require('dotenv').config({ path: path.join(__dirname, '.env') });
  require('dotenv').config({ path: path.join(__dirname, '..', '.env') });
} catch (e) { /* dotenv yoksa devam */ }
const http = require('http');
const { Client, LocalAuth, MessageMedia, Location } = require('whatsapp-web.js');
const qrcodeTerminal = require('qrcode-terminal');
const QRCode = require('qrcode');
const axios = require('axios');

const API_URL = process.env.ASISTAN_API_URL || 'http://localhost:8000';
const API_TIMEOUT = parseInt(process.env.ASISTAN_API_TIMEOUT_MS || '120000', 10);
const QR_PORT = parseInt(process.env.QR_PORT || '3100', 10);

let currentQR = null;
let isConnected = false;
let isReconnecting = false;

// ── Mesaj Kuyruğu — bağlantı koptuğunda veya API erişilemediğinde mesajları sakla ──
const pendingMessages = [];  // { message, timestamp, retries }
const MAX_QUEUE_SIZE = 1000;
const MAX_RETRIES = 5;
const RETRY_BASE_DELAY = 2000; // ms, exponential backoff

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: './.wwebjs_auth' }),
  puppeteer: {
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
    ]
  }
});

// Resim URL'den indir - fromUrl CORS hatası verirse axios ile dene
async function fetchImageAsMedia(url) {
  try {
    return await MessageMedia.fromUrl(url, { unsafeMime: true });
  } catch (e) {
    console.warn('MessageMedia.fromUrl başarısız, axios ile deneniyor:', e.message);
    const resp = await axios.get(url, { responseType: 'arraybuffer', timeout: 30000 });
    const base64 = Buffer.from(resp.data).toString('base64');
    const contentType = resp.headers['content-type'] || 'image/jpeg';
    return new MessageMedia(contentType, base64);
  }
}

// Body toplama yardımcısı
function collectBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (e) {
        resolve({});
      }
    });
    req.on('error', reject);
  });
}

// QR web sunucusu + Temsilci mesaj gönderme endpoint - tarayıcıda http://localhost:3100 açın
const server = http.createServer(async (req, res) => {
  res.setHeader('Content-Type', 'application/json; charset=utf-8');

  if (req.method === 'GET' && req.url === '/api/status') {
    res.statusCode = 200;
    res.end(JSON.stringify({ connected: isConnected }));
    return;
  }

  // POST /send - Temsilci panelinden mesaj gönderme
  if (req.method === 'POST' && req.url === '/send') {
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    if (!isConnected) {
      res.statusCode = 503;
      res.end(JSON.stringify({ error: 'WhatsApp bağlı değil' }));
      return;
    }
    try {
      const body = await collectBody(req);
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
      const chat = await client.getChatById(chatId);
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
      console.error('Temsilci mesaj gönderimi:', err.message);
      res.statusCode = 500;
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  if (req.url === '/' || req.url === '/qr') {
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    if (isConnected) {
      res.end(`
        <!DOCTYPE html>
        <html><head><meta charset="utf-8"><title>Emare WhatsApp</title></head>
        <body style="font-family:sans-serif;text-align:center;padding:40px;background:#e8f5e9;">
          <h1>✅ WhatsApp bağlı!</h1>
          <p>Emare Asistan hazır.</p>
        </body></html>
      `);
      return;
    }
    if (currentQR) {
      try {
        const qrDataUrl = await QRCode.toDataURL(currentQR, { width: 320, margin: 2 });
        res.end(`
          <!DOCTYPE html>
          <html><head><meta charset="utf-8"><title>WhatsApp QR - Emare Asistan</title></head>
          <body style="font-family:sans-serif;text-align:center;padding:40px;background:#f5f5f5;">
            <h1>📱 WhatsApp'a Bağlan</h1>
            <p>Bu QR kodu telefonunuzla tarayın:<br>WhatsApp > Ayarlar > Bağlı Cihazlar > Cihaz Bağla</p>
            <img src="${qrDataUrl}" alt="QR Code" style="border:8px solid white;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.15);">
            <p style="color:#666;">QR kod 60 saniyede yenilenir. Sayfa otomatik yenilenecek.</p>
            <script>setTimeout(()=>location.reload(),5000)</script>
          </body></html>
        `);
      } catch (e) {
        res.end(`<h1>Hata</h1><p>${e.message}</p>`);
      }
    } else {
      res.end(`
        <!DOCTYPE html>
        <html><head><meta charset="utf-8"><title>Emare WhatsApp</title></head>
        <body style="font-family:sans-serif;text-align:center;padding:40px;">
          <h1>⏳ QR hazırlanıyor...</h1>
          <p>Birkaç saniye bekleyin, sayfa otomatik yenilenecek.</p>
          <script>setTimeout(()=>location.reload(),2000)</script>
        </body></html>
      `);
    }
  } else {
    res.statusCode = 404;
    res.end('Not found');
  }
});

server.listen(QR_PORT, () => {
  console.log(`\n📱 Tarayıcıda açın: http://localhost:${QR_PORT}\n`);
  console.log('   WhatsApp > Ayarlar > Bağlı Cihazlar > Cihaz Bağla\n');
});

// QR kodu hem terminalde hem web için güncelle
client.on('qr', (qr) => {
  currentQR = qr;
  isConnected = false;
  console.log('\n📱 QR kod hazır. Tarayıcıda http://localhost:' + QR_PORT + ' açın\n');
  qrcodeTerminal.generate(qr, { small: true });
});

client.on('ready', async () => {
  currentQR = null;
  isConnected = true;
  isReconnecting = false;
  console.log('\n✅ WhatsApp\'a bağlandı! Emare Asistan hazır.\n');

  // ── Catch-up: bağlantı yokken gelen okunmamış mesajları tara ──
  try {
    const chats = await client.getChats();
    let unreadCount = 0;
    for (const chat of chats) {
      if (chat.unreadCount > 0) {
        const msgs = await chat.fetchMessages({ limit: chat.unreadCount });
        for (const msg of msgs) {
          if (!msg.fromMe && msg.timestamp > (Date.now() / 1000 - 300)) {
            // Son 5 dakika içindeki okunmamış mesajlar
            unreadCount++;
            pendingMessages.push({ message: msg, timestamp: Date.now(), retries: 0 });
          }
        }
      }
    }
    if (unreadCount > 0) {
      console.log(`📬 ${unreadCount} okunmamış mesaj kuyruğa alındı — işleniyor...`);
      drainQueue();
    }
  } catch (err) {
    console.error('Okunmamış mesaj tarama hatası:', err.message);
  }

  // Bekleyen kuyrukta mesaj varsa işle
  if (pendingMessages.length > 0) {
    console.log(`📤 Kuyrukta ${pendingMessages.length} bekleyen mesaj var — işleniyor...`);
    drainQueue();
  }
});

client.on('authenticated', () => {
  console.log('🔐 Kimlik doğrulandı, oturum açılıyor...\n');
});

client.on('disconnected', (reason) => {
  console.log('⚠️ Bağlantı kesildi:', reason);
  isConnected = false;
  currentQR = null;

  if (isReconnecting) return; // zaten yeniden bağlanıyor
  isReconnecting = true;

  // Hızlı yeniden bağlanma — 2sn
  console.log('🔄 2 saniye sonra yeniden bağlanılacak...');
  setTimeout(async () => {
    try {
      console.log('🔄 Yeniden başlatılıyor (client.initialize)...');
      await client.initialize();
    } catch (err) {
      console.error('❌ Yeniden başlatma hatası:', err.message);
      console.log('💀 Process çıkıyor — supervisor yeniden başlatacak.');
      process.exit(1);
    } finally {
      isReconnecting = false;
    }
  }, 2_000);
});

// Bağlantı durumu değişikliklerini izle
client.on('change_state', (state) => {
  console.log(`📡 WhatsApp durum değişti: ${state}`);
  if (state === 'CONFLICT' || state === 'UNLAUNCHED' || state === 'UNPAIRED') {
    console.warn('⚠️ Oturum çakışması veya eşleşme kaybı:', state);
  }
});

// Auth hatası — session bozulmuşsa temizle ve yeniden QR iste
client.on('auth_failure', (msg) => {
  console.error('❌ Giriş hatası:', msg);
  isConnected = false;
  currentQR = null;

  console.log('🧹 Auth hatası — 5 saniye sonra yeniden başlatılacak...');
  setTimeout(async () => {
    try {
      await client.initialize();
    } catch (err) {
      console.error('❌ Auth sonrası yeniden başlatma hatası:', err.message);
      process.exit(1);
    }
  }, 5_000);
});

// ── API'ye mesaj gönder (retry ile) ─────────────────────────
async function sendToAPI(payload, retries = 3) {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const response = await axios.post(
        `${API_URL}/api/whatsapp/process`,
        payload,
        { timeout: API_TIMEOUT }
      );
      return response.data;
    } catch (err) {
      const isLast = attempt === retries;
      const isRetryable = err.code === 'ECONNREFUSED' || err.code === 'ECONNRESET' ||
                          err.code === 'ETIMEDOUT' || (err.response && err.response.status >= 500);
      if (isRetryable && !isLast) {
        const delay = RETRY_BASE_DELAY * Math.pow(2, attempt - 1); // exponential backoff
        console.warn(`⏳ API retry ${attempt}/${retries} — ${delay}ms sonra tekrar...`);
        await new Promise(r => setTimeout(r, delay));
      } else {
        throw err;
      }
    }
  }
}

// ── Mesaj işleme (tek mesaj) ────────────────────────────────
async function processMessage(message) {
  if (message.fromMe) return;
  let text = (message.body || '').trim();
  let audioBase64 = null;
  let audioMimetype = null;
  let imageBase64 = null;
  let imageMimetype = null;

  // Sesli mesaj (PTT)
  if (!text && (message.type === 'ptt' || (message.hasMedia && message.type === 'audio'))) {
    try {
      const media = await message.downloadMedia();
      if (media && media.data) {
        audioBase64 = media.data;
        audioMimetype = media.mimetype || 'audio/ogg';
      }
    } catch (e) {
      console.error('Sesli mesaj indirilemedi:', e.message);
    }
  }
  // Resim
  if (!text && message.hasMedia && (message.type === 'image' || (message._data && message._data.type === 'image'))) {
    try {
      const media = await message.downloadMedia();
      if (media && media.data && (media.mimetype || '').startsWith('image/')) {
        imageBase64 = media.data;
        imageMimetype = media.mimetype || 'image/jpeg';
      }
    } catch (e) {
      console.error('Resim indirilemedi:', e.message);
    }
  }

  if (!text && !audioBase64 && !imageBase64) return;
  console.log('Mesaj alındı:', text ? text.substring(0, 50) + (text.length > 50 ? '...' : '') : '[sesli/resim]');

  const fromNumber = message.from;

  let repliedToCaption = null;
  try {
    if (message.hasQuotedMsg) {
      const quoted = await message.getQuotedMessage();
      const cap = (quoted.caption || quoted.body || (quoted._data && quoted._data.caption) || '').trim();
      repliedToCaption = cap || null;
    }
  } catch (e) { /* quoted msg erişilemeyebilir */ }

  const payload = { from: fromNumber, text: text || '', replied_to_caption: repliedToCaption };
  if (audioBase64) {
    payload.audio_base64 = audioBase64;
    payload.audio_mimetype = audioMimetype;
  }
  if (imageBase64) {
    payload.image_base64 = imageBase64;
    payload.image_mimetype = imageMimetype;
  }

  try {
    const data = await sendToAPI(payload);

    const { text: replyText, images = [], videos = [], location, audio_base64: respAudio, audio_mimetype: respAudioMime } = data;
    const chat = await message.getChat();

    let sent = false;
    if (respAudio && respAudioMime) {
      try {
        const media = new MessageMedia(respAudioMime || 'audio/mpeg', respAudio, 'yanit.mp3');
        await message.reply(media);
        sent = true;
      } catch (err) {
        console.error('Sesli yanıt gönderilemedi:', err.message);
      }
    }
    if (!sent && replyText && replyText.trim()) {
      await message.reply(replyText.trim());
      sent = true;
    }
    if (!sent && !images.length && !videos.length && !location) {
      console.warn('API boş yanıt döndü. AI anahtarı veya limit kontrol edin.');
      const fallback = process.env.FALLBACK_PHONE
        ? `Üzgünüz, şu an yanıt oluşturamadık. Lütfen ${process.env.FALLBACK_PHONE} numarasından bize ulaşın.`
        : 'Üzgünüz, şu an yanıt oluşturamadık. Lütfen daha sonra tekrar deneyin.';
      await message.reply(fallback);
    }

    if (location) {
      try {
        const loc = new Location(location.lat, location.lng, {
          name: location.name || 'Firma',
          address: location.address || ''
        });
        await chat.sendMessage(loc);
      } catch (err) {
        console.error('Konum gönderilemedi:', err.message);
      }
    }
    for (const img of images) {
      try {
        const media = await MessageMedia.fromUrl(img.url, { unsafeMime: true });
        await chat.sendMessage(media, { caption: img.caption || '' });
      } catch (err) {
        console.error('Resim gönderilemedi:', img.url?.substring(0, 50) || img.name, err.message);
      }
    }
    for (const vid of videos) {
      try {
        const media = await MessageMedia.fromUrl(vid.url, { unsafeMime: true });
        await chat.sendMessage(media, { caption: vid.caption || '' });
      } catch (err) {
        console.error('Video gönderilemedi:', err.message);
      }
    }
  } catch (err) {
    const errMsg = err.response?.data?.detail || err.message;
    const status = err.response?.status;
    console.error('API hatası (tüm retry başarısız):', status || err.code, errMsg);

    // Kuyruğa al — daha sonra tekrar denenecek
    if (pendingMessages.length < MAX_QUEUE_SIZE) {
      pendingMessages.push({ message, timestamp: Date.now(), retries: 0 });
      console.log(`📥 Mesaj kuyruğa alındı (kuyruk: ${pendingMessages.length})`);
    } else {
      console.error('⚠️ Kuyruk dolu — mesaj atılıyor');
    }

    // Kullanıcıya bilgi ver
    try {
      await message.reply('Mesajınız alındı, kısa süre içinde yanıtlanacaktır. Teşekkürler.');
    } catch (e) { /* bağlantı yoksa reply de başarısız olabilir */ }
  }
}

// ── Kuyruk işleme ───────────────────────────────────────────
let isDraining = false;

async function drainQueue() {
  if (isDraining || !isConnected || pendingMessages.length === 0) return;
  isDraining = true;
  console.log(`📤 Kuyruk işleniyor (${pendingMessages.length} mesaj)...`);

  while (pendingMessages.length > 0 && isConnected) {
    const item = pendingMessages[0];

    // Çok eski mesajlar (10dk+) atla
    if (Date.now() - item.timestamp > 10 * 60 * 1000) {
      pendingMessages.shift();
      console.log('⏭️ Eski mesaj atlandı (10dk+)');
      continue;
    }

    // Max retry aşıldıysa atla
    if (item.retries >= MAX_RETRIES) {
      pendingMessages.shift();
      console.log('⏭️ Max retry aşıldı, mesaj atlandı');
      continue;
    }

    try {
      await processMessage(item.message);
      pendingMessages.shift(); // başarılı — kuyruktan çıkar
    } catch (err) {
      item.retries++;
      console.warn(`⚠️ Kuyruk retry ${item.retries}/${MAX_RETRIES}: ${err.message}`);
      // Biraz bekle, sonra tekrar dene
      await new Promise(r => setTimeout(r, RETRY_BASE_DELAY * item.retries));
      if (item.retries >= MAX_RETRIES) {
        pendingMessages.shift();
        console.error('❌ Mesaj işlenemedi, atılıyor');
      }
    }
  }

  isDraining = false;
  if (pendingMessages.length > 0) {
    console.log(`📋 Kuyrukta hâlâ ${pendingMessages.length} mesaj kaldı`);
  } else {
    console.log('✅ Kuyruk tamamen işlendi');
  }
}

// Periyodik kuyruk kontrolü (her 5sn)
setInterval(() => {
  if (isConnected && pendingMessages.length > 0 && !isDraining) {
    drainQueue();
  }
}, 5_000);

// Gelen mesajları işle
client.on('message', async (message) => {
  await processMessage(message);
});

client.initialize().catch((err) => {
  console.error('Başlatma hatası:', err);
  process.exit(1);
});

// ── Heartbeat: periyodik bağlantı kontrolü ──────────────────
const HEARTBEAT_INTERVAL = parseInt(process.env.WA_HEARTBEAT_SEC || '30', 10) * 1000;
let heartbeatFails = 0;
const MAX_HEARTBEAT_FAILS = 3;

setInterval(async () => {
  if (!isConnected) return; // henüz bağlı değilse kontrol etme
  try {
    const state = await client.getState();
    if (state === 'CONNECTED') {
      heartbeatFails = 0;
    } else {
      heartbeatFails++;
      console.warn(`💓 Heartbeat: durum ${state} (fail ${heartbeatFails}/${MAX_HEARTBEAT_FAILS})`);
      if (heartbeatFails >= MAX_HEARTBEAT_FAILS) {
        console.error('💀 Heartbeat limiti aşıldı — yeniden başlatılıyor...');
        heartbeatFails = 0;
        isConnected = false;
        try {
          await client.destroy();
        } catch (e) { /* ignore */ }
        setTimeout(() => client.initialize().catch(() => process.exit(1)), 5000);
      }
    }
  } catch (err) {
    heartbeatFails++;
    console.warn(`💓 Heartbeat hatası: ${err.message} (fail ${heartbeatFails}/${MAX_HEARTBEAT_FAILS})`);
    if (heartbeatFails >= MAX_HEARTBEAT_FAILS) {
      console.error('💀 Heartbeat limiti aşıldı — process çıkıyor, supervisor yeniden başlatacak.');
      process.exit(1);
    }
  }
}, HEARTBEAT_INTERVAL);

// ── Process crash guard ─────────────────────────────────────
process.on('uncaughtException', (err) => {
  console.error('🔥 Uncaught Exception:', err);
  // Loglayıp devam et — kritikse process.exit(1) çağır
});

process.on('unhandledRejection', (reason) => {
  console.error('🔥 Unhandled Rejection:', reason);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('🛑 SIGTERM alındı — kapatılıyor...');
  try { await client.destroy(); } catch (e) { /* ignore */ }
  server.close(() => process.exit(0));
});

process.on('SIGINT', async () => {
  console.log('🛑 SIGINT alındı — kapatılıyor...');
  try { await client.destroy(); } catch (e) { /* ignore */ }
  server.close(() => process.exit(0));
});
