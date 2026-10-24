# Virtual Webcam Hub (Always-On Camera Relay)

Un servicio ligero para Linux que mantiene una **cámara virtual siempre activa** (`/dev/video0`) para navegadores y aplicaciones (WhatsApp Web, Discord, Google Meet, Zoom), conmutando en caliente y automáticamente a la transmisión de **DroidCam** cuando abres la app en tu teléfono (iOS / Android).

---

## 🌟 Características

- **Always-On Real**: `/dev/video0` está 100% activo las 24 horas entregando fotogramas continuos. WhatsApp y Discord reconocen la cámara de inmediato sin requerir recargar la página.
- **Standby con 0.0% de CPU**: Mientras el teléfono está inactivo, inyecta un fotograma precalculado en formato raw YU12 (barras de prueba de TV SMPTE) directamente al kernel sin usar FFmpeg en tiempo de ejecución.
- **0.0% de impacto en la batería del teléfono**: El PC nunca sondea activamente al teléfono; el teléfono solo notifica al PC al abrir y cerrar la app mediante un webhook HTTP local.
- **Fallback Automático (Watchdog)**: Si se corta la conexión o se apaga la app en el teléfono, la cámara virtual regresa sola al modo Standby sin congelar la llamada.

---

## 📋 Requisitos

- Linux con soporte V4L2 y el módulo `v4l2loopback` instalado:
  ```bash
  # Arch Linux
  sudo pacman -S v4l2loopback-dkms droidcam ffmpeg python
  ```
- DroidCam instalado en tu teléfono móvil.

---

## 🚀 Instalación y Configuración

### 1. Clonar el repositorio
```bash
git clone https://github.com/Zezenta/virtual-webcam.git
cd virtual-webcam
```

### 2. Configurar las variables de entorno
Copia la plantilla `.env.example` a `.env`:
```bash
cp .env.example .env
```

Edita `.env` con la configuración de tu red local:
```ini
# IP local de tu teléfono móvil
PHONE_IP=192.168.0.100

# Puerto de DroidCam (por defecto 4747)
PHONE_PORT=4747

# Puerto local del webhook en la PC (por defecto 8899)
PORT=8899

# Dispositivo virtual v4l2
DEV=/dev/video0
```

### 3. Configurar tu Firewall (UFW)
Permite que únicamente tu teléfono se comunique con el puerto del webhook:
```bash
sudo ufw allow from <TU_PHONE_IP> to any port 8899 proto tcp
```

---

## 📱 Configuración en el Teléfono

### En iPhone (Vía app Shortcuts / Atajos)
Crea 2 automatizaciones en la app **Shortcuts** -> pestaña **Automation**:

1. **Al abrir DroidCam:**
   - Evento: `When "DroidCam" is opened`
   - Configuración: `Run Immediately`, `Notify When Run: OFF`
   - Acción: `Get Contents of URL` -> `http://<IP_DE_TU_PC>:8899/start`

2. **Al cerrar DroidCam:**
   - Evento: `When "DroidCam" is closed`
   - Configuración: `Run Immediately`, `Notify When Run: OFF`
   - Acción: `Get Contents of URL` -> `http://<IP_DE_TU_PC>:8899/stop`

---

## ⚙️ Iniciar como Servicio Systemd de Usuario

Crea el archivo de servicio en `~/.config/systemd/user/virtual-webcam.service`:

```ini
[Unit]
Description=Virtual Webcam Always-On Hub with Webhook
After=graphical-session.target pipewire.service

[Service]
Type=simple
ExecStart=%h/Desktop/Coding/virtual-webcam/server_webhook.py
Restart=always
RestartSec=2

[Install]
WantedBy=default.target
```

Habilita y arranca el servicio:
```bash
systemctl --user daemon-reload
systemctl --user enable --now virtual-webcam.service
```

---

## 📄 Licencia

MIT
