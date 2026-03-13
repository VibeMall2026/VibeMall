# 🔧 VPS Deployment Troubleshooting Guide

## Current Issue: SSH Connection Timeout

The GitHub Actions deployment is failing with `dial tcp ***:22: i/o timeout`, indicating the runner cannot connect to your VPS.

## 🚨 IMMEDIATE ACTIONS REQUIRED

### 1. **Check VPS Accessibility**
```bash
# Test from your local machine
ping 187.124.98.177
telnet 187.124.98.177 22
```

### 2. **Connect to VPS Manually**
```bash
ssh root@187.124.98.177
```

### 3. **On VPS: Check SSH Service**
```bash
# Check SSH service status
sudo systemctl status ssh
sudo systemctl status sshd

# If SSH is not running, start it
sudo systemctl start ssh
sudo systemctl enable ssh

# Check if SSH is listening
sudo netstat -tlnp | grep :22
sudo ss -tlnp | grep :22
```

### 4. **Check Firewall Settings**
```bash
# Check UFW status
sudo ufw status

# If firewall is blocking SSH, allow it
sudo ufw allow ssh
sudo ufw allow 22

# Check iptables rules
sudo iptables -L
```

### 5. **Verify SSH Configuration**
```bash
# Check SSH config
sudo nano /etc/ssh/sshd_config

# Ensure these settings:
Port 22
PermitRootLogin yes
PubkeyAuthentication yes
PasswordAuthentication yes  # Temporarily enable for testing

# Restart SSH after changes
sudo systemctl restart ssh
```

### 6. **Test SSH Key Authentication**
```bash
# On VPS: Check authorized_keys
ls -la ~/.ssh/
cat ~/.ssh/authorized_keys

# Set proper permissions
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

### 7. **Regenerate SSH Keys (If Needed)**
```bash
# On VPS: Generate new key pair
ssh-keygen -t rsa -b 4096 -C "github-actions" -f ~/.ssh/github_actions

# Add public key to authorized_keys
cat ~/.ssh/github_actions.pub >> ~/.ssh/authorized_keys

# Copy private key for GitHub secrets
cat ~/.ssh/github_actions
```

## 🔍 COMMON CAUSES & SOLUTIONS

### **Cause 1: VPS is Down**
- **Solution**: Contact your VPS provider or restart the VPS

### **Cause 2: SSH Service Stopped**
- **Solution**: `sudo systemctl start ssh && sudo systemctl enable ssh`

### **Cause 3: Firewall Blocking**
- **Solution**: `sudo ufw allow ssh` or configure iptables

### **Cause 4: Wrong SSH Key**
- **Solution**: Regenerate keys and update GitHub secrets

### **Cause 5: SSH Config Issues**
- **Solution**: Check `/etc/ssh/sshd_config` and restart SSH

### **Cause 6: Network Issues**
- **Solution**: Check with VPS provider for network connectivity

## 📋 GITHUB SECRETS VERIFICATION

Make sure these secrets are correctly set in your GitHub repository:

1. **VPS_HOST**: `187.124.98.177`
2. **VPS_USERNAME**: `root` (or your SSH username)
3. **VPS_SSH_KEY**: Complete private key content (including headers)

```
-----BEGIN OPENSSH PRIVATE KEY-----
[key content]
-----END OPENSSH PRIVATE KEY-----
```

## 🚀 ALTERNATIVE DEPLOYMENT METHOD

If SSH issues persist, you can deploy manually:

```bash
# On your local machine
git push origin main

# On VPS manually
cd /var/www/vibemall
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations --merge
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart vibemall
sudo systemctl reload nginx
```

## 📞 NEXT STEPS

1. **Immediate**: Test VPS connectivity and SSH service
2. **Verify**: GitHub secrets are correct
3. **Test**: Manual SSH connection works
4. **Deploy**: Try GitHub Actions again or deploy manually
5. **Monitor**: Check deployment logs for success

## 🆘 IF ALL ELSE FAILS

Contact your VPS provider to ensure:
- VPS is running and accessible
- SSH service is enabled
- No network-level blocking
- Firewall allows SSH connections

Once connectivity is restored, the comprehensive features will auto-deploy successfully!