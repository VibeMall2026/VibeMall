#!/bin/bash

echo "🔄 Restarting VibeMall Services..."

# Restart Django application
sudo systemctl restart vibemall
echo "✅ VibeMall service restarted"

# Reload Nginx
sudo systemctl reload nginx
echo "✅ Nginx reloaded"

# Check service status
echo ""
echo "📊 Service Status:"
sudo systemctl is-active vibemall && echo "✅ VibeMall: Running" || echo "❌ VibeMall: Not running"
sudo systemctl is-active nginx && echo "✅ Nginx: Running" || echo "❌ Nginx: Not running"

echo ""
echo "🎉 Services restarted successfully!"
echo "🌐 Visit: https://vibemall.in/admin-panel/"
