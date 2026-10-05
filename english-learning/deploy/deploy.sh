#!/bin/bash
# 一键部署脚本:在全新的 Ubuntu/Debian 服务器上执行
#
# 用法(用 root 用户):
#   1. 先把代码放到 /opt/english-learning(git clone 或上传压缩包解压)
#   2. 先改好 deploy/nginx.conf 里的 server_name(域名或服务器 IP)
#   3. 执行:bash deploy/deploy.sh
set -e

APP_DIR=/opt/english-learning
cd "$APP_DIR"

echo "==> 1/5 安装系统软件(Python、nginx)..."
apt update -y
apt install -y python3 python3-venv python3-pip nginx

echo "==> 2/5 创建 Python 虚拟环境并安装依赖..."
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "==> 3/5 配置开机自启服务..."
cp deploy/english-learning.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now english-learning

echo "==> 4/5 配置 nginx 反向代理..."
cp deploy/nginx.conf /etc/nginx/sites-available/english-learning
ln -sf /etc/nginx/sites-available/english-learning /etc/nginx/sites-enabled/english-learning
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "==> 5/5 部署完成!"
systemctl status english-learning --no-pager || true
echo ""
echo "请检查:"
echo "  - 浏览器访问 http://服务器IP 是否能看到首页"
echo "  - app/config.py 的 SECRET_KEY 是否已改成随机字符串"
echo "  - 后台默认密码是否已修改(改 app/seed.py 后删除 english.db 重建)"
