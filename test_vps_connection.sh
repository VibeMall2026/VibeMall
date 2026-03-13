#!/bin/bash

# Simple VPS connectivity test script
echo "🔍 Testing VPS Connection..."
echo "=========================="

VPS_IP="187.124.98.177"
VPS_USER="root"

echo "📡 Testing ping to VPS..."
if ping -c 3 $VPS_IP; then
    echo "✅ VPS is reachable via ping"
else
    echo "❌ VPS is not reachable via ping"
    exit 1
fi

echo ""
echo "🔌 Testing SSH port..."
if nc -z -v $VPS_IP 22 2>&1; then
    echo "✅ SSH port 22 is open"
else
    echo "❌ SSH port 22 is not accessible"
    exit 1
fi

echo ""
echo "🔑 Testing SSH connection..."
echo "Note: This will prompt for password/key authentication"
ssh -o ConnectTimeout=10 -o BatchMode=yes $VPS_USER@$VPS_IP "echo '✅ SSH connection successful'; hostname; date" || {
    echo "❌ SSH connection failed"
    echo "🔍 Trying with verbose output..."
    ssh -v -o ConnectTimeout=10 $VPS_USER@$VPS_IP "echo 'Connected'" 2>&1 | head -20
}

echo ""
echo "🎯 Connection test completed!"