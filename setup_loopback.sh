#!/bin/bash
# Script to configure and load v4l2loopback virtual camera on Ubuntu 24.04

set -e

echo "=== Configuring v4l2loopback Virtual Camera for Webcam Controller ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run this script with sudo: sudo ./setup_loopback.sh"
  exit 1
fi

# Ensure v4l2loopback-dkms is installed
if ! dpkg -s v4l2loopback-dkms >/dev/null 2>&1; then
    echo "Installing v4l2loopback-dkms..."
    apt-get update && apt-get install -y v4l2loopback-dkms v4l-utils
fi

# Remove existing module if loaded without parameters
if lsmod | grep -q v4l2loopback; then
    echo "Unloading existing v4l2loopback module..."
    modprobe -r v4l2loopback || true
fi

# Create modprobe configuration
echo "Writing /etc/modprobe.d/v4l2loopback.conf..."
cat <<EOF > /etc/modprobe.d/v4l2loopback.conf
options v4l2loopback devices=1 video_nr=10 card_label="Webcam Controller Virtual Cam" exclusive_caps=1
EOF

# Create autoload configuration
echo "Writing /etc/modules-load.d/v4l2loopback.conf..."
cat <<EOF > /etc/modules-load.d/v4l2loopback.conf
v4l2loopback
EOF

# Load module now
echo "Loading v4l2loopback module..."
modprobe v4l2loopback devices=1 video_nr=10 card_label="Webcam Controller Virtual Cam" exclusive_caps=1

# Check device node
if [ -e /dev/video10 ]; then
    chmod 666 /dev/video10
    echo "✅ Success! /dev/video10 is ready and configured as 'Webcam Controller Virtual Cam'."
else
    echo "⚠️ /dev/video10 was not created automatically. Listing available video devices:"
    ls -l /dev/video*
fi

echo "Done! You can now use the Virtual Camera feature in Webcam Controller for MS Teams, Zoom, and Meet."
