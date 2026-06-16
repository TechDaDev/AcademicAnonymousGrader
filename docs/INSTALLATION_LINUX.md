# Linux Installation Guide

## Prerequisites

- Linux x86_64 (Ubuntu 22.04+, Debian 12+, Fedora 38+, or equivalent)
- Docker Engine 24.0+
- Docker Compose plugin v2.20+
- Python 3.12+ (for setup scripts)
- 4 GB free disk space

## Step 1: Install Docker

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install docker.io docker-compose-v2
sudo systemctl enable --now docker
```

### Fedora

```bash
sudo dnf install docker docker-compose
sudo systemctl enable --now docker
```

### Verify

```bash
docker version --format '{{.Server.Version}}'
docker compose version --short
```

## Step 2: Add Your User to the Docker Group

```bash
sudo usermod -aG docker $USER
```

Log out and back in, or run `newgrp docker`.

## Step 3: Run the Installer

```bash
cd /path/to/AcademicAnonymousGrader
./deployment/linux/install.sh
```

The installer automates the same steps as the Windows version.

## Step 4: Access

Open [http://localhost:8501](http://localhost:8501) in your browser.

## Daily Operations

```bash
./deployment/linux/start.sh      # Start the application
./deployment/linux/stop.sh       # Stop the application
./deployment/linux/status.sh     # Check status
./deployment/linux/backup.sh     # Create a backup
```

## Troubleshooting

See [TROUBLESHOOTING_DEPLOYMENT.md](TROUBLESHOOTING_DEPLOYMENT.md).
