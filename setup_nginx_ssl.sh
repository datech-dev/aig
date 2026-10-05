#!/bin/bash
set -e

DOMAIN="zetagirl.zetalink.cloud"
EMAIL="admin@zetalink.cloud"

echo "=== Installing Nginx and Certbot for Hostinger DNS SSL ==="
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx

echo "=== Configuring Nginx Proxy for $DOMAIN ==="
cat << 'EOF' | sudo tee /etc/nginx/sites-available/zetagirl
server {
    listen 80;
    server_name zetagirl.zetalink.cloud;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/zetagirl /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default || true
sudo nginx -t
sudo systemctl reload nginx

echo "=== Obtaining Free SSL Certificate via Certbot ==="
sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m $EMAIL --redirect || true

echo "=== SSL Setup Complete for $DOMAIN ==="
