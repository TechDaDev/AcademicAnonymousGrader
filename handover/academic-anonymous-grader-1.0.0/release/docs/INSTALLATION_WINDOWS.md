# Windows Installation Guide

## Prerequisites

- Windows 10/11, 64-bit
- Docker Desktop 4.x+
- PowerShell 5.1+
- 4 GB free disk space
- Administrator access (for Docker Desktop installation)

## Step 1: Install Docker Desktop

1. Download Docker Desktop from [docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)
2. Run the installer and follow the prompts
3. Start Docker Desktop and wait for the engine to become ready
4. Keep **WSL 2 backend** selected (default)
5. Restart your computer if prompted

## Step 2: Verify Docker

Open PowerShell and run:

```powershell
docker version --format "{{.Server.Version}}"
```

You should see a version number (e.g., `29.5.3`).

## Step 3: Run the Installer

Navigate to the repository root and run:

```powershell
.\deployment\windows\install.ps1
```

The installer will:

1. Verify Docker Desktop is running
2. Run preflight checks (OS, disk space, port, files)
3. Create a secure `.env` with fresh encryption keys
4. Build the versioned Docker image
5. Create persistent Docker volumes
6. Start the application container
7. Wait for the health check to pass
8. Prompt for the first Administrator account
9. Run post-install validation
10. Display the application URL

### First Administrator Account

During installation, you will be prompted to create the first Administrator:

```
Username: [enter your admin username]
Password: [enter password — characters are not echoed]
Confirm:  [re-enter password]
```

**Important:** The password is not displayed on screen. Choose a strong password and store it securely.

## Step 4: Access the Application

Open your browser to: [http://localhost:8501](http://localhost:8501)

Login with the Administrator credentials you just created.

## Step 5: Verify Installation

Run the status check:

```powershell
.\deployment\windows\status.ps1
```

Or inside the container:

```powershell
docker compose exec app python -m scripts.health_check
```

## Repeated Installation

Running the installer again on the same machine is safe:

- Existing `.env` is detected and preserved (no key regeneration)
- Existing Administrator account is detected and not duplicated
- Existing volumes are reused
- Seeds are idempotent (departments, stages, terms not duplicated)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Docker not found | Install Docker Desktop and restart PowerShell |
| Port 8501 in use | Stop the other application or change `APP_HOST_PORT` in `.env` |
| Container not healthy | Run `docker compose logs --no-color` to inspect |
| Health check fails | Run `docker compose exec app python -m scripts.health_check` |

See [TROUBLESHOOTING_DEPLOYMENT.md](TROUBLESHOOTING_DEPLOYMENT.md) for more.
