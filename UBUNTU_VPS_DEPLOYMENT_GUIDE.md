# Ubuntu VPS Deployment Guide

Aa guide VibeMall ne Ubuntu VPS par proper rite chalava mate chhe.
Aa ma 2 main goals cover thay chhe:

1. `502 Bad Gateway` problem fix karvi
2. `GitHub push -> VPS auto deploy` setup karvu

## 1. Current Setup Summary

Aa project ma nginx config already present chhe:

- `nginx_vibemall.conf`

Nginx backend ne aa Unix socket par expect kare chhe:

- `/run/vibemall.sock`

Etle `502 Bad Gateway` no common reason a hoy:

- Gunicorn service down hoy
- `/run/vibemall.sock` create na thay
- nginx ne socket access na male

## 2. Prerequisites

Tamara VPS par aa chijon hovi joiye:

- Ubuntu server
- Python virtualenv at `/var/www/vibemall/venv`
- Project folder at `/var/www/vibemall`
- Domain DNS already server taraf point thatu hoy
- nginx installed hoy
- systemd available hoy

## 3. Step 1: VPS ma Login

```bash
ssh your_user@your_server_ip
```

`your_user` ne tamara real VPS username thi replace karjo.

## 4. Step 2: Project Health Check

```bash
cd /var/www/vibemall
source venv/bin/activate
python manage.py check
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

Jo a commands error aape to pehla e error solve karo.

## 5. Step 3: Gunicorn systemd Service Create Karo

File create karo:

```bash
sudo nano /etc/systemd/system/vibemall.service
```

Aa content paste karo:

```ini
[Unit]
Description=VibeMall Gunicorn
After=network.target

[Service]
User=your_user
Group=www-data
WorkingDirectory=/var/www/vibemall
Environment="PATH=/var/www/vibemall/venv/bin"
ExecStartPre=/bin/rm -f /run/vibemall.sock
ExecStart=/var/www/vibemall/venv/bin/gunicorn --workers 3 --bind unix:/run/vibemall.sock --umask 007 VibeMall.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

Important:

- `your_user` ne tamara actual VPS username thi replace karjo
- `Group=www-data` thi nginx socket access kari shake
- `--umask 007` thi socket permissions workable rahe

## 6. Step 4: Gunicorn Service Start Karo

```bash
sudo systemctl daemon-reload
sudo systemctl enable vibemall
sudo systemctl start vibemall
sudo systemctl status vibemall --no-pager
```

Expected result:

- `active (running)`

## 7. Step 5: Nginx Config Apply Karo

Project no nginx config VPS ma copy karo:

```bash
sudo cp /var/www/vibemall/nginx_vibemall.conf /etc/nginx/sites-available/vibemall
sudo ln -sf /etc/nginx/sites-available/vibemall /etc/nginx/sites-enabled/vibemall
sudo nginx -t
sudo systemctl reload nginx
```

Jo `nginx -t` fail thay to error pehla fix karo.

## 8. Step 6: 502 Bad Gateway Troubleshooting

Jo site par `502 Bad Gateway` ave to aa commands chalavo:

```bash
sudo systemctl status vibemall --no-pager
sudo journalctl -u vibemall -n 50 --no-pager
sudo ls -l /run/vibemall.sock
sudo tail -n 50 /var/log/nginx/error.log
```

Most common fixes:

- Gunicorn restart karo
- stale socket remove karo
- nginx reload karo

Quick restart:

```bash
sudo rm -f /run/vibemall.sock
sudo systemctl restart vibemall
sudo systemctl reload nginx
```

## 9. Step 7: GitHub Auto Deploy Overview

Auto deploy no flow a rite hoy:

1. Tame `git push origin main` karo
2. GitHub Action run thay
3. Action SSH thi VPS ma login kare
4. VPS par latest code pull thay
5. Migrations, collectstatic ane service restart thay

Aa mate GitHub ne VPS ma SSH access joiye.

## 10. Step 8: Local Machine par SSH Key Generate Karo

Windows PowerShell ma:

```powershell
ssh-keygen -t ed25519 -C "vibemall-github-actions" -f "$env:USERPROFILE\.ssh\vibemall_actions"
```

Aa thi 2 files banse:

- private key: `C:\Users\ADMIN\.ssh\vibemall_actions`
- public key: `C:\Users\ADMIN\.ssh\vibemall_actions.pub`

Passphrase empty rakhi shako for automation use.

## 11. Step 9: Public Key VPS ma Add Karo

Local machine par public key joi lo:

```powershell
Get-Content "$env:USERPROFILE\.ssh\vibemall_actions.pub"
```

Aa output copy karo.

Pachi VPS ma:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
nano ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Public key `authorized_keys` ma paste karo.

## 12. Step 10: SSH Connection Test Karo

Windows PowerShell ma:

```powershell
ssh -i "$env:USERPROFILE\.ssh\vibemall_actions" your_user@your_server_ip
```

Jo login thai jay to GitHub Actions pan same key thi VPS ma login kari shakshe.

## 13. Step 11: GitHub Repository Secrets Add Karo

GitHub repo ma:

- `Settings`
- `Secrets and variables`
- `Actions`

Aa secrets add karo:

- `VPS_HOST`
- `VPS_USER`
- `VPS_PORT`
- `VPS_SSH_KEY`
- `VPS_APP_DIR`
- `VPS_VENV_DIR`
- `VPS_SERVICE_NAME`
- `VPS_BRANCH`

Recommended values:

- `VPS_HOST = your_server_ip`
- `VPS_USER = your_user`
- `VPS_PORT = 22`
- `VPS_APP_DIR = /var/www/vibemall`
- `VPS_VENV_DIR = /var/www/vibemall/venv`
- `VPS_SERVICE_NAME = vibemall`
- `VPS_BRANCH = main`

Private key paste karva:

```powershell
Get-Content "$env:USERPROFILE\.ssh\vibemall_actions" -Raw
```

Aa output ne `VPS_SSH_KEY` secret ma paste karo.

## 14. Step 12: VPS User ne Restart Permission Aapo

VPS ma:

```bash
sudo visudo
```

Aa line add karo:

```bash
your_user ALL=(ALL) NOPASSWD:/bin/systemctl restart vibemall,/bin/systemctl reload nginx
```

`your_user` ne actual server username thi replace karjo.

## 15. Step 13: Private GitHub Repo Access

Jo repo private hoy ane VPS par `git pull origin main` fail thay to VPS ne GitHub access joiye.

Easy rule:

- Jo VPS par manually `git pull origin main` already chale chhe, to aa step skip karo
- Jo na chale, to server par GitHub access fix karo

Aa mate 2 option chhe:

1. Deploy key
2. Personal access token

Best option:

- Deploy key

## 16. Step 14: GitHub Actions Workflow File

Repo ma `.github/workflows/deploy-vps.yml` create karo ane aa content mukho:

```yaml
name: Deploy To VPS

on:
  push:
    branches:
      - main

jobs:
  deploy:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest

    steps:
      - name: Deploy over SSH
        uses: appleboy/ssh-action@v1.2.0
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          port: ${{ secrets.VPS_PORT || 22 }}
          script_stop: true
          script: |
            cd "${{ secrets.VPS_APP_DIR }}"
            git pull origin "${{ secrets.VPS_BRANCH || 'main' }}"
            source "${{ secrets.VPS_VENV_DIR }}/bin/activate"
            python -m pip install -r requirements.txt
            python manage.py migrate --noinput
            python manage.py collectstatic --noinput
            sudo systemctl restart "${{ secrets.VPS_SERVICE_NAME || 'vibemall' }}"
            sudo systemctl reload nginx
```

## 17. Step 15: Test Auto Deploy

Local machine par:

```bash
git add .
git commit -m "setup vps auto deploy"
git push origin main
```

Pachi GitHub ma:

- `Actions` tab open karo
- latest workflow run check karo

Jo workflow pass thay to deployment successful.

## 18. Daily Usage

Aagal thi normal workflow:

```bash
git add .
git commit -m "your changes"
git push origin main
```

Bas. GitHub Action VPS ma latest code deploy kari de.

## 19. Emergency Commands

Jo site down thai jai to aa commands useful chhe:

```bash
sudo systemctl restart vibemall
sudo systemctl reload nginx
sudo systemctl status vibemall --no-pager
sudo journalctl -u vibemall -n 50 --no-pager
sudo tail -n 50 /var/log/nginx/error.log
```

## 20. Final Checklist

Aa badhu done hovun joiye:

- VPS ma project folder present chhe
- virtualenv ready chhe
- `python manage.py check` pass thay chhe
- `vibemall.service` created chhe
- `systemctl status vibemall` active chhe
- nginx config enabled chhe
- `nginx -t` pass thay chhe
- site open thay chhe
- GitHub secrets added chhe
- SSH key working chhe
- push pachi GitHub Action run thay chhe

## 21. If Something Fails

Pehla aa 3 outputs check karo:

```bash
sudo systemctl status vibemall --no-pager
sudo journalctl -u vibemall -n 50 --no-pager
sudo tail -n 50 /var/log/nginx/error.log
```

Aa tran outputs thi almost hamesha root cause mali jay chhe.
