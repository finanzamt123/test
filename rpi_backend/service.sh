#!/usr/bin/env bash
set -e
sudo apt-get update && sudo apt-get install -y python3-pip python3-venv git
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cat <<'EOF' | sudo tee /etc/systemd/system/hydroponics.service
[Unit]
Description=Hydroponic Flask backend
After=network.target

[Service]
WorkingDirectory=%h/hydroponics/rpi_backend
ExecStart=%h/hydroponics/rpi_backend/venv/bin/python app.py
Restart=always
User=%i

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable hydroponics.service --now
