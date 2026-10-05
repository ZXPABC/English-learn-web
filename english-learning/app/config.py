"""全局配置"""
import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SQLite 数据库文件路径(首次启动自动生成,无需安装数据库)
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'english.db')}"

# 会话签名密钥:用于管理员登录状态的加密 Cookie(已换成随机字符串)
SECRET_KEY = "2f757c987e1c073fa489eaffda61798383fabda4b70f5d65bd3ef4527012e019"
