#!/bin/bash
# ==============================================================================
# ElderAlpha Trading Helper AI - 1-Click 24/7 Cloud Deployment Script
# Supports: Ubuntu 20.04/22.04/24.04, Debian 11/12
# Works on: DigitalOcean Droplets, Hetzner Cloud, AWS EC2/Lightsail, Linode
# ==============================================================================

set -e

echo "=========================================================="
echo "  Deploying ElderAlpha AI Trading Helper 24/7 Service    "
echo "=========================================================="

# 1. Update system packages
echo "[1/5] Updating system packages..."
sudo apt-get update -y
sudo apt-get install -y curl git ufw

# 2. Install Docker & Docker Compose if missing
if ! command -v docker &> /dev/null; then
    echo "[2/5] Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
else
    echo "[2/5] Docker is already installed."
fi

# 3. Create persistent directories
echo "[3/5] Setting up persistent model and database directories..."
mkdir -p models data
touch calibrations.json trading_journal.db

# 4. Open firewall port 8000
echo "[4/5] Configuring firewall for port 8000..."
sudo ufw allow 8000/tcp || true

# 5. Build and launch 24/7 Docker Container
echo "[5/5] Building and starting 24/7 daemon container..."
sudo docker compose down || true
sudo docker compose build
sudo docker compose up -d

echo ""
echo "=========================================================="
echo "  SUCCESS! ElderAlpha AI is now running 24x7 in the cloud!"
echo "  - Access Web Dashboard at: http://YOUR_SERVER_IP:8000"
echo "  - Autonomous Learning Engine: Running continuously in background"
echo "  - View live logs with: sudo docker compose logs -f"
echo "=========================================================="
