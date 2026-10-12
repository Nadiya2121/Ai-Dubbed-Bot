#!/bin/bash

echo "🚀 অটোমেটিক সেটআপ শুরু হচ্ছে..."

# ১. ৫১২ এমবি র‍্যামের জন্য ২ জিবি Swap তৈরি
if [ ! -f /swapfile ]; then
    echo "📦 ২ জিবি Swap মেমরি তৈরি করা হচ্ছে..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# ২. সিস্টেম আপডেট ও প্যাকেজ ইনস্টলেশন
echo "📦 FFmpeg এবং Python ইনস্টল করা হচ্ছে..."
apt-get update && apt-get install -y ffmpeg python3 python3-pip

# ৩. পাইথন লাইব্রেরি ইনস্টল
echo "📦 লাইব্রেরি ইনস্টল করা হচ্ছে..."
pip3 install -r requirements.txt

# ৪. সার্ভিস কনফিগারেশন (সার্ভার রিস্টার্ট নিলেও অটো চলবে)
CURRENT_DIR=$(pwd)
SERVICE_FILE="/etc/systemd/system/aidubbot.service"

echo "⚙️ ব্যাকগ্রাউন্ড সার্ভিস তৈরি করা হচ্ছে..."
bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=AI Video Dubbing Telegram Bot
After=network.target

[Service]
User=root
WorkingDirectory=$CURRENT_DIR
ExecStart=/usr/bin/python3 $CURRENT_DIR/bot.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable aidubbot
systemctl start aidubbot

echo "🎉 অভিনন্দন! বট সফলভাবে ব্যাকগ্রাউন্ডে চালু হয়ে গেছে।"
