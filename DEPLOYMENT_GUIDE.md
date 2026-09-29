# 24/7 Cloud Deployment & Continuous Training Guide
## ElderAlpha Trading Helper AI

This guide shows you how to host and run the **ElderAlpha Trading Helper AI** in the cloud 24/7, so it autonomously trains on market data, monitors setups, tracks news alerts, and streams live charts day and night without requiring your home PC or laptop to stay on.

---

## 1. Top Recommended 24/7 Cloud Hosts

| Provider | Recommended Tier | Price | Best For |
| :--- | :--- | :--- | :--- |
| **[Hetzner Cloud](https://www.hetzner.com/cloud)** *(Top Pick)* | **CX22** (2 vCPU, 4GB RAM, 40GB SSD) | **~€3.79/mo** | Highest CPU performance for machine learning at the lowest cost. |
| **[DigitalOcean](https://www.digitalocean.com)** | **Basic Droplet** (1-2 vCPU, 2GB RAM) | **$6 - $12/mo** | Beginner-friendly, instant 1-click Docker setup. |
| **[AWS Lightsail](https://aws.amazon.com/lightsail/)** | **Standard** (2 vCPU, 2GB RAM) | **$10/mo** | Reliable AWS infrastructure with fixed monthly pricing. |
| **[Railway.app](https://railway.app)** *(PaaS)* | **Hobby / Pro** | **~$5/mo** | Easiest setup: auto-deploys straight from your GitHub repository. |

> [!TIP]
> A server with **2 vCPUs and 2GB to 4GB of RAM** is ideal for continuous background machine learning (PyTorch CPU + Scikit-Learn Gradient Boosting) and live WebSocket streaming.

---

## 2. Deploying on a Cloud VPS (Hetzner / DigitalOcean / AWS)

### Step 1: Create your Cloud Server
1. Launch an **Ubuntu 22.04 LTS or 24.04 LTS** instance.
2. Connect to your server using SSH from your terminal or PowerShell:
   ```bash
   ssh root@YOUR_SERVER_IP
   ```

### Step 2: Upload Your Project Code & Trained Models

#### Option A: Transfer Files Directly via `scp` (From your Windows PC)
Open PowerShell in your Windows project folder (`tradinghelper`) and run:
```powershell
# Copy the whole project directory to your cloud server
scp -r * root@YOUR_SERVER_IP:/opt/tradinghelper/
```

#### Option B: Upload via GitHub
On your VPS:
```bash
git clone https://github.com/YOUR_USERNAME/tradinghelper.git /opt/tradinghelper
cd /opt/tradinghelper
```
*(If you have existing models on your PC, upload the `models/` folder and `calibrations.json` via SFTP or `scp` so you don't lose previous training progress)*:
```powershell
scp -r ./models root@YOUR_SERVER_IP:/opt/tradinghelper/
scp ./calibrations.json root@YOUR_SERVER_IP:/opt/tradinghelper/
scp ./trading_journal.db root@YOUR_SERVER_IP:/opt/tradinghelper/
```

---

### Step 3: Launch with Docker (Fastest, 1-Click)

On your server, run the automated deployment script:
```bash
cd /opt/tradinghelper
chmod +x deploy.sh
./deploy.sh
```

Or run Docker Compose manually:
```bash
sudo docker compose build
sudo docker compose up -d
```

That's it! The container is set to `restart: always`, meaning:
- If the server restarts, the trading bot restarts automatically.
- If the app crashes, Docker automatically restarts it in seconds.
- All trained models (`models/*.pkl`), calibrations (`calibrations.json`), and trades (`trading_journal.db`) are saved to mounted volumes so they are never lost.

---

## 3. Alternative: Running via Linux Systemd Service (No Docker)

If you prefer running directly in Python:
```bash
cd /opt/tradinghelper

# 1. Install Python virtual environment
sudo apt-get update && sudo apt-get install -y python3-venv python3-pip

# 2. Create virtualenv and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# 3. Setup Systemd Auto-Start Service
sudo cp systemd/tradinghelper.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable tradinghelper
sudo systemctl start tradinghelper

# Check live status
sudo systemctl status tradinghelper
```

---

## 4. Alternative: Deploying to Railway.app (Zero Server Admin)

1. Push your `tradinghelper` code to a private GitHub repository.
2. Go to [Railway.app](https://railway.app) and click **"New Project" $\rightarrow$ "Deploy from GitHub repo"**.
3. Select your repository. Railway will detect the `Dockerfile` automatically.
4. In Railway project settings:
   - Add a **Persistent Volume** mounted at `/app/models`.
   - Set environment variable `PORT = 8000`.
5. Click **Deploy**. Railway will provide a free public HTTPS domain (e.g. `https://tradinghelper.up.railway.app`).

---

## 5. How to Access Your Live Dashboard

Open your web browser and go to:
```
http://YOUR_SERVER_IP:8000
```

### Useful Server Commands:
- **View live logs & training updates:**
  ```bash
  sudo docker compose logs -f
  # or if using systemd:
  journalctl -u tradinghelper -f
  ```
- **Trigger background retrain of all assets:**
  ```bash
  curl -X POST http://127.0.0.1:8000/api/auto-trainer/train-now -H "Content-Type: application/json" -d '{"symbol":"ALL"}'
  ```
- **Stop service:**
  ```bash
  sudo docker compose down
  # or:
  sudo systemctl stop tradinghelper
  ```

---

## 6. Security Best Practices
- **Firewall:** Keep only ports 22 (SSH) and 8000 (Dashboard) open (`sudo ufw allow 22 && sudo ufw allow 8000 && sudo ufw enable`).
- **Free SSL / Custom Domain:** You can install **Caddy** (`sudo apt install caddy`) for automatic free HTTPS with Let's Encrypt:
  ```
  yourdomain.com {
      reverse_proxy localhost:8000
  }
  ```
