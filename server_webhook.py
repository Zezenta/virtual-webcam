#!/usr/bin/env python3
"""
server_webhook.py - Receptor webhook con auto-detección dinámica de IP
- Standby en 0.0% CPU inyectando el fotograma YUV a /dev/video0.
- Auto-detecta la IP del iPhone directamente desde la petición HTTP /start.
- Cero desincronización por cambios de DHCP del router.
"""

import http.server
import subprocess
import os
import signal
import sys
import threading
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

env_file = os.path.join(SCRIPT_DIR, ".env")
if os.path.exists(env_file):
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

PORT = int(os.environ.get("PORT", 8899))
DEFAULT_PHONE_IP = os.environ.get("PHONE_IP", "192.168.0.101")
PHONE_PORT = os.environ.get("PHONE_PORT", "4747")
DEV = os.environ.get("DEV", "/dev/video0")
YUV_FRAME = os.path.join(SCRIPT_DIR, "standby_frame.yuv")

current_mode = "none"
active_phone_ip = DEFAULT_PHONE_IP
droidcam_proc = None
standby_stop_flag = False
standby_thread = None
lock = threading.Lock()

if not os.path.exists(YUV_FRAME):
    smpte_png = os.path.join(SCRIPT_DIR, "smpte_tv_720p.png")
    subprocess.run([
        "ffmpeg", "-i", smpte_png, "-s", "640x480", "-pix_fmt", "yuv420p",
        YUV_FRAME, "-y"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

with open(YUV_FRAME, "rb") as f:
    RAW_FRAME_DATA = f.read()

def standby_worker():
    global standby_stop_flag
    try:
        with open(DEV, "wb") as dev:
            while not standby_stop_flag:
                dev.write(RAW_FRAME_DATA)
                dev.flush()
                time.sleep(0.066)
    except Exception:
        pass

def stop_all_locked():
    global droidcam_proc, standby_stop_flag, standby_thread
    if standby_thread and standby_thread.is_alive():
        standby_stop_flag = True
        standby_thread.join(timeout=0.5)
        standby_thread = None

    if droidcam_proc and droidcam_proc.poll() is None:
        try:
            droidcam_proc.terminate()
            droidcam_proc.wait(timeout=0.4)
        except Exception:
            try:
                droidcam_proc.kill()
                droidcam_proc.wait(timeout=0.2)
            except Exception:
                pass
        droidcam_proc = None

def watchdog_droidcam(proc):
    global current_mode
    proc.wait()
    with lock:
        if droidcam_proc == proc and current_mode == "droidcam":
            print("[AUTO-FALLBACK] DroidCam desconectado. Restaurando barras de TV (Standby)...", flush=True)
            do_start_standby_locked()

def do_start_standby_locked():
    global current_mode, standby_stop_flag, standby_thread
    stop_all_locked()
    time.sleep(0.1)
    standby_stop_flag = False
    standby_thread = threading.Thread(target=standby_worker, daemon=True)
    standby_thread.start()
    current_mode = "standby"
    print("[ESTADO] 📺 Standby activo (Barras de TV - 0% CPU)", flush=True)

def do_start_droidcam_locked(target_ip):
    global current_mode, droidcam_proc, active_phone_ip
    active_phone_ip = target_ip
    stop_all_locked()
    time.sleep(0.2)
    cmd = ["droidcam-cli", "-v", active_phone_ip, PHONE_PORT]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    droidcam_proc = proc
    current_mode = "droidcam"
    print(f"[ESTADO] 🟢 Teléfono conectado dinámicamente desde {active_phone_ip}", flush=True)
    threading.Thread(target=watchdog_droidcam, args=(proc,), daemon=True).start()

class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def send_quick_ack(self):
        body = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
            self.wfile.flush()
        except Exception:
            pass

    def do_GET(self):
        # Auto-detectar la IP real de quien hace la llamada HTTP
        client_ip = self.client_address[0]
        
        if self.path == "/start":
            self.send_quick_ack()
            with lock:
                do_start_droidcam_locked(client_ip)
        elif self.path == "/stop":
            self.send_quick_ack()
            with lock:
                do_start_standby_locked()
        elif self.path == "/ping":
            self.send_quick_ack()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

def handle_sigterm(signum, frame):
    with lock:
        stop_all_locked()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigterm)
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    with lock:
        do_start_standby_locked()
    
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), WebhookHandler)
    print(f"[INFO] Webhook server escuchando en puerto {PORT} con IP dinámica...", flush=True)
    try:
        server.serve_forever()
    finally:
        with lock:
            stop_all_locked()
