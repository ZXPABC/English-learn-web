# 云服务器部署方案

把"轻松学英语"部署到云服务器,让任何人通过网址访问。

## 一、总体架构

```
你的电脑(开发环境)                     云服务器(生产环境)
                        上传代码
                    ───────────────>    nginx(对外 80/443 端口)
                                            │ 转发请求
                                            ▼
浏览器(用户)  ──────访问──────>     uvicorn(FastAPI,127.0.0.1:8000)
                                            │
                                            ├─ english.db(SQLite 数据库)
                                            └─ app/data/(词库 JSON)
```

- **nginx**:接客的门面,负责对外提供 80(HTTP)/ 443(HTTPS)端口,把请求转给后端
- **uvicorn + systemd**:网站本体,开机自启、崩溃自动重启
- **SQLite**:数据就是服务器上一个文件,本项目规模完全够用,不需要单独装数据库

## 二、准备:买什么、花多少钱

| 项目 | 说明 | 参考价格 |
|---|---|---|
| 云服务器 | 腾讯云/阿里云"轻量应用服务器" 2核2G 足够,系统选 **Ubuntu 22.04 或 24.04** | 新用户/学生价约 ¥50~100/年 |
| 域名(可选) | .com 约 ¥60/年,.cn 更便宜 | ¥30~80/年 |
| 备案(用域名才需要) | 国内服务器绑域名必须 ICP 备案,免费,但流程要 1~2 周 | 免费 |
| HTTPS 证书 | Let's Encrypt 免费证书,自动续期 | 免费 |

**备案是关键**:国内服务器,**用域名访问就必须备案**。想最快跑起来,可以先用"服务器 IP"直接访问(不绑域名,不用备案),以后再买域名备案升级。

## 三、上线前必须做的两件事(安全!)

### 1. 换掉密钥 SECRET_KEY

当前 [config.py](../app/config.py) 里是开发用的固定密钥,上线前必须换成随机字符串:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

把输出的字符串粘贴到 `app/config.py` 的 `SECRET_KEY`。

### 2. 换掉默认管理员密码

默认密码 `admin123` 不能留着。改法:编辑 [seed.py](../app/seed.py) 里的 `admin123` 为你自己的密码,然后**删除 `english.db`** 重新启动(注意:这会把本地已有的数据重置,如果数据重要先备份)。

## 四、上传代码到服务器

三种方式任选(推荐第一种):

1. **git**:在 Gitee/GitHub 建一个私有仓库,push 上去,服务器上 `git clone` 拉下来。以后每次更新 `git pull` 就行
2. **压缩包**:把项目打成 zip 上传到服务器,`unzip` 解压
3. **scp 命令**:`scp -r english-learning root@服务器IP:/opt/`

代码放到服务器的 `/opt/english-learning`。

## 五、在服务器上部署

前提:改好 `deploy/nginx.conf` 里的 `server_name`(填域名或服务器 IP)。

### 方式 A:一键脚本(推荐)

```bash
cd /opt/english-learning
bash deploy/deploy.sh
```

脚本自动完成:装 Python 和 nginx → 建虚拟环境装依赖 → 配开机自启 → 配 nginx 转发。

### 方式 B:手动执行(想看懂每一步用这个)

```bash
# 1. 装系统软件
apt update && apt install -y python3 python3-venv python3-pip nginx

# 2. 建虚拟环境装依赖(服务器 Python 需 3.10 以上)
cd /opt/english-learning
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. 注册开机自启服务
cp deploy/english-learning.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now english-learning

# 4. 配置 nginx 并启动
cp deploy/nginx.conf /etc/nginx/sites-available/english-learning
ln -sf /etc/nginx/sites-available/english-learning /etc/nginx/sites-enabled/english-learning
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

## 六、云控制台放行端口

登录云厂商控制台 → 找到"防火墙 / 安全组"→ 放行:

| 端口 | 用途 | 建议 |
|---|---|---|
| 80 | HTTP | 对所有人开放 |
| 443 | HTTPS | 对所有人开放(配置 HTTPS 后) |
| 22 | SSH 登录 | 只对你的 IP 开放,更安全 |

## 七、配置 HTTPS(有域名之后)

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d 你的域名
```

按提示填邮箱即可,证书会自动配置和续期,以后不用管。

## 八、日常维护

```bash
systemctl restart english-learning     # 更新代码后重启
journalctl -u english-learning -f      # 实时看日志(排错用)
systemctl status english-learning      # 看运行状态
```

- 更新代码:上传新代码后执行重启命令
- 备份数据:定期把服务器上的 `english.db` 下载回本地
- 学习进度在用户自己浏览器里(localStorage),和服务器数据无关

## 九、安全清单

- [ ] `app/config.py` 的 SECRET_KEY 已换成随机字符串
- [ ] 默认管理员密码已修改
- [ ] 只开放 80 / 443 / 22 端口
- [ ] 有域名后已开启 HTTPS

## 十、其他可选方案

- **宝塔面板**:图形化操作,不熟 Linux 命令的同学友好;装面板后在"网站 + Supervisor"里配 uvicorn
- **Docker**:适合熟练以后,第一次部署不推荐,增加学习成本
- **PythonAnywhere / Render 等免费平台**:免费但不稳定,国内访问速度差,且对 FastAPI 支持有限,不建议作为正式方案
