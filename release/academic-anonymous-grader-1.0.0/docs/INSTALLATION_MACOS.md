# macOS Installation Guide

## Prerequisites

- macOS 13 (Ventura) or later
- Apple Silicon (M1/M2/M3) or Intel
- Docker Desktop for Mac 4.x+
- 4 GB free disk space

## Step 1: Install Docker Desktop

Download from [docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/) and install.

## Step 2: Run the Installer

The Linux shell scripts are compatible with macOS:

```bash
cd /path/to/AcademicAnonymousGrader
./deployment/linux/install.sh
```

## Step 3: Access

Open [http://localhost:8501](http://localhost:8501).

## Notes

- The `.sh` scripts in `deployment/linux/` work on macOS without changes.
- Docker Desktop for Mac is required (Docker Engine is not available natively on macOS).
- File permissions: `.env` should be readable only by your user (`chmod 600 .env`).

## Troubleshooting

See [TROUBLESHOOTING_DEPLOYMENT.md](TROUBLESHOOTING_DEPLOYMENT.md).
