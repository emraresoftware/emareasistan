"""
Partner Remote Deploy — admin sub-router
========================================
Akış:
1. Admin panelde IP, port, kullanıcı adı, şifre girilir.
2. Sunucuya ilk kez bağlanırken şifre ile SSH key yüklenir (paramiko).
3. Sonraki güncellemelerde anahtar kullanılır, şifre istenmez.
4. Deploy scripti arka planda çalışır; log ve durum panelden izlenir.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from pathlib import Path
import subprocess
import time
import os
import json
import logging

from .common import templates, check_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

ROOT = Path(__file__).resolve().parent.parent
DEPLOY_DIR = ROOT / "deploy"
KEYS_DIR = ROOT / "deploy_keys"


# ── helpers ──────────────────────────────────────────────────────

def _tenant_meta_path(tenant_slug: str) -> Path:
    """Her tenant için bağlantı bilgilerini saklayan JSON dosyası."""
    d = DEPLOY_DIR / tenant_slug
    d.mkdir(parents=True, exist_ok=True)
    return d / "connection.json"


def _save_meta(tenant_slug: str, meta: dict):
    p = _tenant_meta_path(tenant_slug)
    with open(p, "w") as f:
        json.dump(meta, f, indent=2)


def _load_meta(tenant_slug: str) -> dict | None:
    p = _tenant_meta_path(tenant_slug)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return None


def _generate_keypair(tenant_slug: str) -> tuple[Path, str]:
    """RSA 2048 keypair oluştur, private key'i diske yaz, (key_path, pub_text) döndür."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )

    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    key_path = KEYS_DIR / f"{tenant_slug}.pem"
    with open(key_path, "wb") as f:
        f.write(priv_bytes)
    os.chmod(key_path, 0o600)
    return key_path, pub_bytes.decode()


def _install_pubkey_via_paramiko(
    host: str, port: int, user: str, password: str, pub_text: str
) -> str | None:
    """Paramiko ile şifre kullanarak public key'i remote authorized_keys'e ekler.
    Başarılıysa None, hata varsa hata mesajı döner."""
    try:
        import paramiko
    except ImportError:
        return "paramiko yüklü değil — pip install paramiko"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=host, port=port, username=user, password=password, timeout=15)

        # mkdir -p ~/.ssh && chmod 700
        client.exec_command("mkdir -p ~/.ssh && chmod 700 ~/.ssh")

        # authorized_keys'e ekle (zaten varsa ekleme)
        sftp = client.open_sftp()
        auth_path = ".ssh/authorized_keys"
        try:
            with sftp.file(auth_path, "r") as af:
                existing = af.read().decode()
        except IOError:
            existing = ""

        if pub_text.strip() not in existing:
            with sftp.file(auth_path, "a") as af:
                af.write(pub_text.strip() + "\n")

        # izinler
        sftp.chmod(auth_path, 0o600)
        sftp.close()
        return None  # başarılı
    except Exception as e:
        return str(e)
    finally:
        client.close()


# ── routes ───────────────────────────────────────────────────────

@router.get("/partner/deploy", response_class=HTMLResponse)
async def partner_deploy_form(request: Request):
    """Partner uzak sunucu deploy formunu görüntüler."""
    if not check_admin(request):
        return RedirectResponse(url="/admin/login")
    return templates.TemplateResponse("partner_deploy.html", {"request": request})


@router.post("/partner/deploy", response_class=HTMLResponse)
async def partner_deploy_submit(
    request: Request,
    host: str = Form(...),
    user: str = Form(...),
    tenant_slug: str = Form(...),
    ssh_port: int = Form(22),
    ssh_password: str = Form(""),
    key_text: str = Form(""),
    key_file: UploadFile = File(None),
    api_port: int = Form(8000),
    bridge_port: int = Form(3100),
):
    """Uzak sunucuya tenant deploy işlemini başlatır.

    3 SSH kimlik doğrulama yöntemi desteklenir:
    - Şifre ile otomatik anahtar üretimi
    - PEM dosyası yükleme
    - Anahtar metni yapıştırma
    """
    if not check_admin(request):
        return RedirectResponse(url="/admin/login")

    deploy_dir = DEPLOY_DIR / tenant_slug
    deploy_dir.mkdir(parents=True, exist_ok=True)

    error_msg = None
    key_installed = False
    key_method = None  # "existing" | "uploaded" | "pasted" | "generated"

    # Daha önce bu tenant için key var mı?
    meta = _load_meta(tenant_slug)
    key_path = KEYS_DIR / f"{tenant_slug}.pem"

    if meta and key_path.exists():
        # Anahtar zaten var — şifre gerekmez, doğrudan deploy
        key_installed = True
        key_method = "existing"

    # Seçenek B: Dosya yüklendi mi?
    elif key_file and key_file.filename:
        KEYS_DIR.mkdir(parents=True, exist_ok=True)
        content = await key_file.read()
        if not content.strip():
            return templates.TemplateResponse(
                "partner_deploy.html",
                {"request": request, "error": "Yüklenen anahtar dosyası boş."},
            )
        with open(key_path, "wb") as f:
            f.write(content)
        os.chmod(key_path, 0o600)
        key_installed = True
        key_method = "uploaded"

    # Seçenek C: Metin yapıştırıldı mı?
    elif key_text and key_text.strip():
        KEYS_DIR.mkdir(parents=True, exist_ok=True)
        with open(key_path, "w") as f:
            f.write(key_text.strip() + "\n")
        os.chmod(key_path, 0o600)
        key_installed = True
        key_method = "pasted"

    # Seçenek A: Şifre ile otomatik anahtar üret ve yükle
    elif ssh_password:
        key_path, pub_text = _generate_keypair(tenant_slug)
        err = _install_pubkey_via_paramiko(host, ssh_port, user, ssh_password, pub_text)
        if err:
            return templates.TemplateResponse(
                "partner_deploy.html",
                {"request": request, "error": f"SSH key yüklenemedi: {err}"},
            )
        key_installed = True
        key_method = "generated"

    else:
        # Hiçbir yöntem seçilmemiş
        return templates.TemplateResponse(
            "partner_deploy.html",
            {"request": request, "error": "Lütfen şifre girin, anahtar dosyası yükleyin veya anahtar metni yapıştırın."},
        )

    # Deploy scriptini arka planda çalıştır
    script = str(ROOT / "scripts" / "remote_deploy_tenant.sh")
    cmd = [
        script,
        "--host", host,
        "--user", user,
        "--key", str(key_path),
        "--tenant", tenant_slug,
        "--api-port", str(api_port),
        "--bridge-port", str(bridge_port),
        "--ssh-port", str(ssh_port),
    ]

    log_file = deploy_dir / "remote_deploy_launch.log"
    with open(log_file, "ab") as lf:
        lf.write(f"\n{'='*60}\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Deploy başlatılıyor...\n{'='*60}\n".encode())
        p = subprocess.Popen(cmd, cwd=str(ROOT), stdout=lf, stderr=lf)
        (deploy_dir / "remote_deploy.pid").write_text(str(p.pid))

    # Meta güncelle (her deploy'da)
    _save_meta(tenant_slug, {
        "host": host,
        "user": user,
        "ssh_port": ssh_port,
        "api_port": api_port,
        "bridge_port": bridge_port,
        "key_file": str(key_path),
        "last_deploy": time.strftime("%Y-%m-%d %H:%M:%S"),
    })

    return templates.TemplateResponse(
        "partner_deploy.html",
        {
            "request": request,
            "started": True,
            "host": host,
            "tenant": tenant_slug,
            "pid": p.pid,
            "key_installed": key_installed,
            "key_method": key_method,
        },
    )


@router.get("/partner/deploy/log/{tenant_slug}")
async def partner_deploy_log(request: Request, tenant_slug: str, lines: int = 200):
    """Deploy log tail (JSON)."""
    if not check_admin(request):
        return RedirectResponse(url="/admin/login")
    log_file = DEPLOY_DIR / tenant_slug / "remote_deploy_launch.log"
    if not log_file.exists():
        return {"ok": False, "error": "Log bulunamadı"}
    text = log_file.read_text(errors="ignore")
    return {"ok": True, "log": text.splitlines()[-lines:]}


@router.get("/partner/deploy/status/{tenant_slug}")
async def partner_deploy_status(request: Request, tenant_slug: str):
    """Deploy süreç durumu (JSON)."""
    if not check_admin(request):
        return RedirectResponse(url="/admin/login")
    pid_file = DEPLOY_DIR / tenant_slug / "remote_deploy.pid"
    if not pid_file.exists():
        return {"running": False, "message": "Henüz deploy başlatılmamış"}
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
        return {"running": True, "pid": pid}
    except (ValueError, ProcessLookupError, PermissionError):
        return {"running": False, "message": "Süreç tamamlanmış"}


@router.get("/partner/servers", response_class=HTMLResponse)
async def partner_servers(request: Request):
    """Kayıtlı sunucuları listele."""
    if not check_admin(request):
        return RedirectResponse(url="/admin/login")
    servers = []
    if DEPLOY_DIR.exists():
        for d in sorted(DEPLOY_DIR.iterdir()):
            meta_file = d / "connection.json"
            if meta_file.exists():
                with open(meta_file) as f:
                    meta = json.load(f)
                meta["tenant_slug"] = d.name
                # key mevcut mu?
                meta["key_ok"] = (KEYS_DIR / f"{d.name}.pem").exists()
                servers.append(meta)
    return templates.TemplateResponse(
        "partner_deploy.html",
        {"request": request, "servers": servers},
    )
