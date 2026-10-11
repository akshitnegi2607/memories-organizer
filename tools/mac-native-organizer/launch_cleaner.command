#!/bin/bash
# 1-Click Launcher for Memories Vault Cleaner
echo "=================================================="
echo " 📸 Launching Memories Cleaner..."
echo "=================================================="

# Check if SSD is mounted
if [ ! -d "/Volumes/DIVAKSHSSD/Organized_Memories" ]; then
    echo "⚠️ SSD Not Found! Please plug in your DIVAKSHSSD and try again."
    read -p "Press Enter to exit..."
    exit 1
fi

cd "/Users/Divyakshit/Documents/Jay/Antigravity/MemoryApp"
/opt/anaconda3/bin/python3 tools/mac-native-organizer/cleaner_server.py
