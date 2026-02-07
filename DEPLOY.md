# WFM Pro - AWS Deployment Guide

This guide details how to deploy the Wizard Football Organization (WFM Pro) application to AWS using Docker Compose.

## 1. Prerequisites (AWS Server)
- **Instance**: launch an EC2 instance (Ubuntu 22.04 LTS recommended). t3.medium or larger is recommended for Playwright/AI tasks.
- **Security Group**: Open ports `80` (HTTP), `443` (HTTPS), and `22` (SSH).
- **Docker**: Install Docker and Docker Compose on the server.
  ```bash
  sudo apt-get update
  sudo apt-get install -y docker.io docker-compose
  sudo usermod -aG docker $USER
  # Log out and log back in
  ```

## 2. Project Setup
Clone your repository to the server:
```bash
git clone https://github.com/YOUR_GITHUB_USER/web_scraper_0.git
cd web_scraper_0/web_app
```

## 3. Environment Configuration
Create the production environment file `.env.prod`. **Do not commit this file to GitHub.**
```bash
nano .env.prod
```
Paste the following (update with your actual secure keys):
```ini
DEBUG=False
SECRET_KEY=long_random_secret_string_here
ALLOWED_HOSTS=wfm-pro.com,www.wfm-pro.com,localhost,127.0.0.1
DATABASE_URL=postgres://wfm:wfm_secret@db:5432/wfm_prod
GEMINI_API_KEY=AIzaSyDNcfzMNd69cUOCEOtzDURqNGob0q5cGzI
```

## 4. Build and Run
Build the Docker images and start the services:
```bash
docker-compose -f docker-compose.yml up -d --build
```

Check the status:
```bash
docker-compose ps
docker-compose logs -f
```

## 5. SSL Certificate (HTTPS)
The `docker-compose.yml` includes a `certbot` service. Currently, it is configured for `staging` (testing).

1. **Verify HTTP**: Ensure `http://wfm-pro.com` works.
2. **Production Certs**:
   - Edit `docker-compose.yml`:
     - Change `--staging` to `--force-renewal` (or remove staging flag).
     - Remove `--dry-run` if present.
   - Edit `nginx/nginx.conf` to enable SSL (uncomment SSL sections if added, or use a separate ssl config).
   *Recommended*: For the first run, use the provided setup to issue certs, then update Nginx to use them.

   **Standard Certbot Command (One-off):**
   ```bash
   docker-compose run --rm certbot certonly --webroot --webroot-path /var/www/html -d wfm-pro.com -d www.wfm-pro.com
   ```
   
   **Update Nginx for SSL**:
   After obtaining certs, update `nginx/nginx.conf` to listen on 443 and point to:
   `/etc/letsencrypt/live/wfm-pro.com/fullchain.pem`
   `/etc/letsencrypt/live/wfm-pro.com/privkey.pem`

## 6. Updates
To deploy updates:
```bash
git pull
docker-compose up -d --build
```
