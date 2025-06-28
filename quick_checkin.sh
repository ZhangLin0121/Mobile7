#!/bin/bash

# E-Mobile 7 一次性打卡快速脚本
# 用于帮助同事临时打卡

echo ""
echo "🚀 E-Mobile 7 一次性打卡助手"
echo "=================================================="
echo "💡 帮助同事临时打卡，无需配置到服务器"
echo "📍 打卡地点: 武汉光谷（自动定位）"
echo "=================================================="

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 需要Python3环境，请先安装Python3"
    exit 1
fi

# 检查依赖
python3 -c "import requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 正在安装requests库..."
    pip3 install requests --user
fi

echo ""
echo "🎯 开始一次性打卡..."
python3 one_time_checkin.py

echo ""
echo "👋 打卡助手结束"