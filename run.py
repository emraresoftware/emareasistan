#!/usr/bin/env python3
"""
Emare Asistan - Tek komutla tüm servisleri başlat
Python API (port 8000) + WhatsApp Bridge (port 3100)
"""
import os
import signal
import subprocess
import sys
import time

if __name__ == "__main__":
    root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root)

    # .env yükle - Bridge subprocess'e ASISTAN_API_URL vb. geçsin
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(root, ".env"))
    except ImportError:
        pass

    procs = []

    def cleanup(sig=None, frame=None):
        print("\n\nDurduruluyor...")
        for p in procs:
            try:
                p.terminate()
                p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print("=" * 50)
    print("Emare Asistan")
    print("=" * 50)
    print("1. Python API başlatılıyor (port 8000)...")
    p1 = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=root,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    procs.append(p1)
    time.sleep(2)
    if p1.poll() is not None:
        print("API başlatılamadı.")
        sys.exit(1)

    bridge_dir = os.path.join(root, "whatsapp-bridge")
    if not os.path.exists(os.path.join(bridge_dir, "node_modules")):
        print("   WhatsApp bridge bağımlılıkları yükleniyor (npm install)...")
        subprocess.run(["npm", "install"], cwd=bridge_dir, shell=(os.name == "nt"), check=True)
    print("2. WhatsApp Bridge başlatılıyor (port 3100)...")
    bridge_env = os.environ.copy()
    bridge_env.setdefault("ASISTAN_API_URL", "http://localhost:8000")
    p2 = subprocess.Popen(
        ["npm", "start"],
        cwd=bridge_dir,
        shell=(os.name == "nt"),
        stdout=sys.stdout,
        stderr=sys.stderr,
        env=bridge_env,
    )
    procs.append(p2)

    print()
    print("Hazır! Admin: http://localhost:8000/admin")
    print("WhatsApp QR: http://localhost:3100")
    print("Durdurmak için Ctrl+C")
    print("=" * 50)

    try:
        p1.wait()
    except KeyboardInterrupt:
        pass
    cleanup()
