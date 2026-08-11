# 飞书签字插件打包标准指南 (Packaging Guide)

为了确保插件更新时不覆盖企业现有的配置、授权码以及额度数据，请在打包时严格遵守以下标准。

## 1. 目录结构要求
打包后的压缩包（如 `feishu_plugin_vX.zip`）应包含以下核心内容：
- `dist/` : 经过 `npm run build` 编译后的前端静态资源。
- `backend_code/` : 后端 Python 源代码目录（由 `BaseOpenSDK-Python-Playground` 复制并重命名而来）。
- `package.json` : 项目元数据。
- `PACKAGING_GUIDE.md` : 本打包标准文件。

## 2. 排除清单 (EXCLUDE LIST)
在复制后端代码到 `backend_code/` 目录时，**严禁**包含以下文件/文件夹，以防覆盖生产环境数据：

### A. 数据库文件 (生产环境核心数据)
- `quota.db` : 包含租户额度、订单历史和支付状态。
- `data.db` : 缓存或其它持久化数据。

### B. 配置文件与私密信息
- `.env` : 包含 AppID, AppSecret, 微信支付私钥等敏感信息。
- `.personal_base_token` : 包含用户个人的多维表格授权码。
- `cert_pub.key`, `key_pub.key` : 加密公私钥。

### C. 运行缓存与日志
- `__pycache__/` : Python 编译缓存。
- `.venv/` : 本地虚拟环境目录。
- `*.log` : 所有日志文件（如 `backend.log`, `frontend.log` 等）。
- `backend.pid` : 运行进程 ID。

## 3. 打包命令参考 (Mac/Linux)
```bash
# 1. 构建前端
cd vue-template-main && npm run build && cd ..

# 2. 创建临时打包目录
mkdir -p feishu_plugin_v4

# 3. 复制前端资源
cp -r vue-template-main/dist feishu_plugin_v4/

# 4. 复制后端源码 (使用 rsync 排除敏感文件)
rsync -av --progress BaseOpenSDK-Python-Playground/ feishu_plugin_v4/backend_code \
--exclude='quota.db' \
--exclude='data.db' \
--exclude='.env' \
--exclude='.personal_base_token' \
--exclude='*.log' \
--exclude='__pycache__' \
--exclude='.venv' \
--exclude='backend.pid' \
--exclude='.DS_Store'

# 5. 复制标准文件
cp package.json feishu_plugin_v4/
cp PACKAGING_GUIDE.md feishu_plugin_v4/

# 6. 压缩
zip -r feishu_plugin_v4.zip feishu_plugin_v4
```

## 4. 交付标准
每次交付时，必须确保 `backend_code` 目录下仅包含源代码及必要的静态资源（如 `templates`, `static`），不包含任何 `.db` 或 `.env` 文件。
