#!/bin/bash

# Xianyu Scraper 快速安装脚本

set -e

echo "🚀 开始安装 Xianyu Scraper..."

# 检查 Python 版本
echo "📋 检查 Python 版本..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python 版本: $python_version"

# 安装依赖
echo "📦 安装 Python 依赖..."
pip3 install -r requirements.txt

# 安装 Playwright 浏览器
echo "🌐 安装 Playwright 浏览器..."
playwright install chromium

# 创建必要的目录
echo "📁 创建目录..."
mkdir -p session
mkdir -p data

# 检查配置文件
if [ ! -f "config.json" ]; then
    echo "⚙️  创建配置文件..."
    cp config.example.json config.json
    echo "⚠️  请编辑 config.json 填入你的 API 配置（如需使用 AI 功能）"
fi

echo ""
echo "✅ 安装完成！"
echo ""
echo "📖 快速开始："
echo "  1. 登录: python3 main.py login"
echo "  2. 搜索: python3 main.py search \"关键词\""
echo "  3. Web界面: uvicorn server:app --reload"
echo ""
echo "📚 更多信息请查看 README.md"
