"""密码加密与校验(只使用 Python 标准库,无需额外依赖)"""
import hashlib
import os


def hash_password(password: str) -> str:
    """给密码加盐后做哈希,返回 "盐$哈希" 字符串,数据库里只存这个结果"""
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    """校验输入的密码和数据库里存的哈希是否一致"""
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()
    return check == digest
