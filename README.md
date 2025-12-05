# 飞书多维表格电子签名插件

基于飞书多维表格的电子签名插件系统,支持批量生成签字链接、二维码、会签/或签模式、历史签名复用等功能。

## 项目结构

```
feishu_chajian_qianzi/
├── BaseOpenSDK-Python-Playground/  # 后端服务 (Python Flask)
│   ├── main.py                      # 主程序入口
│   ├── routes/                      # API路由
│   ├── services/                    # 业务逻辑
│   ├── utils/                       # 工具类
│   └── .env                         # 环境配置
├── vue-template-main/               # 前端项目 (Vue 3)
│   ├── src/                         # 源代码
│   ├── dist/                        # 打包输出目录
│   └── package.json                 # 依赖配置
└── README.md                        # 本文件
```

## 功能特性

- ✅ **批量生成签字链接** - 一键为所有记录生成签字链接和二维码
- ✅ **单行自定义生成** - 为特定行设置独立的签字模式和人数
- ✅ **会签/或签模式** - 支持多人会签(所有人签字)或或签(任意一人签字)
- ✅ **二维码生成** - 自动生成签字二维码,支持自定义Logo
- ✅ **历史签名复用** - 用户可以复用之前的签名
- ✅ **API限流保护** - 智能限流避免触发飞书API频率限制
- ✅ **自动重试机制** - 遇到临时错误自动重试,确保100%成功率

## 环境要求

### 后端
- Python 3.8+
- Poetry (Python包管理工具)

### 前端
- Node.js 16+
- npm 或 yarn

---

## 快速开始

### 1. 克隆项目

```bash
cd ~/Desktop
# 项目已在 feishu_chajian_qianzi 目录
cd feishu_chajian_qianzi
```

---

## 后端部署

### 1.1 安装依赖

```bash
# 进入后端目录
cd BaseOpenSDK-Python-Playground

# 安装 Poetry (如果还没安装)
curl -sSL https://install.python-poetry.org | python3 -

# 使用 Poetry 安装项目依赖
poetry install
```

### 1.2 配置环境变量

编辑 `.env` 文件,配置以下必要参数:

```bash
# 飞书应用凭证 (在飞书开发者后台获取)
APP_ID=your_app_id
APP_SECRET=your_app_secret

# 端口配置
PORT=3000

# 前端访问域名 (用于生成签字链接)
HOST_URL=https://your-domain.com/

# URL参数加密密钥 (32字节十六进制)
# 生成方法: python -c "import os; print(os.urandom(32).hex())"
ENCRYPTION_KEY=your_encryption_key

# 二维码配置
QRCODE_SIZE=340
QRCODE_LOGO_SIZE=40
QRCODE_LOGO_PATH=static/image/ahlogo.png
```

### 1.3 运行后端服务

**开发环境**:
```bash
# 在 BaseOpenSDK-Python-Playground 目录下
poetry run python main.py
```

服务将在 `http://localhost:3000` 启动

**生产环境** (使用 Gunicorn):
```bash
# 安装 gunicorn
poetry add gunicorn

# 启动生产服务器
poetry run gunicorn -w 4 -b 0.0.0.0:3000 main:app
```

### 1.4 后台运行 (可选)

```bash
# 使用 nohup 后台运行
nohup poetry run python main.py > backend.log 2>&1 &

# 查看日志
tail -f backend.log

# 停止服务
pkill -f "python main.py"
```

---

## 前端部署

### 2.1 安装依赖

```bash
# 进入前端目录
cd ../vue-template-main

# 安装依赖
npm install
# 或使用 yarn
# yarn install
```

### 2.2 配置环境变量

创建或编辑 `.env.development` (开发环境):
```bash
VITE_API_BASE=http://localhost:3000/api
VITE_FRONTEND_HOST=http://localhost:5173
```

创建或编辑 `.env.production` (生产环境):
```bash
VITE_API_BASE=https://your-backend-domain.com/api
VITE_FRONTEND_HOST=https://your-frontend-domain.com
```

### 2.3 开发模式运行

```bash
# 在 vue-template-main 目录下
npm run dev
```

前端将在 `https://localhost:5173` 启动 (支持HTTPS)

### 2.4 生产环境打包

```bash
# 在 vue-template-main 目录下
npm run build
```

打包后的文件将输出到 `dist/` 目录

### 2.5 部署打包文件

**方法1: 使用 Nginx**

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # 前端静态文件
    location / {
        root /path/to/vue-template-main/dist;
        try_files $uri $uri/ /index.html;
    }
    
    # 后端API代理
    location /api {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**方法2: 上传到飞书云文档**

1. 打包完成后,将 `dist/` 目录下的所有文件上传到飞书云文档
2. 配置飞书插件指向该云文档地址

**方法3: 使用静态托管服务**

将 `dist/` 目录部署到:
- Vercel
- Netlify
- GitHub Pages
- 阿里云OSS
- 腾讯云COS

---

## 完整部署流程

### 开发环境

```bash
# 终端1: 启动后端
cd ~/Desktop/feishu_chajian_qianzi/BaseOpenSDK-Python-Playground
poetry run python main.py

# 终端2: 启动前端
cd ~/Desktop/feishu_chajian_qianzi/vue-template-main
npm run dev
```

### 生产环境

```bash
# 1. 打包前端
cd ~/Desktop/feishu_chajian_qianzi/vue-template-main
npm run build

# 2. 部署前端文件 (dist/ 目录)
# 上传到服务器或云存储

# 3. 启动后端服务
cd ~/Desktop/feishu_chajian_qianzi/BaseOpenSDK-Python-Playground
poetry run gunicorn -w 4 -b 0.0.0.0:3000 main:app

# 或使用 PM2 管理进程
npm install -g pm2
pm2 start "poetry run python main.py" --name feishu-backend
```

---

## 常用命令速查

### 后端命令

```bash
# 进入后端目录
cd ~/Desktop/feishu_chajian_qianzi/BaseOpenSDK-Python-Playground

# 安装依赖
poetry install

# 运行开发服务器
poetry run python main.py

# 查看依赖
poetry show

# 添加新依赖
poetry add package_name

# 生成加密密钥
python -c "import os; print(os.urandom(32).hex())"
```

### 前端命令

```bash
# 进入前端目录
cd ~/Desktop/feishu_chajian_qianzi/vue-template-main

# 安装依赖
npm install

# 开发模式
npm run dev

# 生产打包
npm run build

# 预览打包结果
npm run preview

# 清理 node_modules 重新安装
rm -rf node_modules package-lock.json
npm install
```

---

## 故障排查

### 后端问题

**端口被占用**:
```bash
# 查找占用3000端口的进程
lsof -ti:3000

# 终止进程
lsof -ti:3000 | xargs kill -9
```

**依赖安装失败**:
```bash
# 清理 Poetry 缓存
poetry cache clear pypi --all

# 重新安装
poetry install
```

**API频率限制错误**:
- 已集成限流器,默认每秒5个请求
- 如需调整,修改 `utils/rate_limiter.py` 中的 `max_calls_per_second` 参数

### 前端问题

**端口被占用**:
```bash
# 查找占用5173端口的进程
lsof -ti:5173

# 终止进程
lsof -ti:5173 | xargs kill -9
```

**打包失败**:
```bash
# 清理缓存
rm -rf node_modules dist .vite
npm install
npm run build
```

**HTTPS证书问题**:
- 开发环境使用 `vite-plugin-mkcert` 自动生成本地证书
- 首次运行可能需要信任证书

---

## 技术栈

### 后端
- **框架**: Flask (Python Web框架)
- **SDK**: 飞书开放平台 Python SDK
- **限流**: 自研令牌桶限流器
- **加密**: AES-256-GCM
- **二维码**: qrcode + Pillow

### 前端
- **框架**: Vue 3 + Vite
- **UI组件**: Element Plus
- **飞书SDK**: @lark-base-open/js-sdk
- **签名组件**: vue-signature-pad

---

## 性能优化

### API限流保护
- **令牌桶算法**: 每秒最多5个请求
- **自动重试**: 遇到频率限制自动重试,最多3次
- **指数退避**: 重试间隔逐步增加(1秒 → 2秒 → 4秒)
- **并发控制**: 批量处理使用5个并发线程

### 批量生成性能
- **100条记录**: 约20秒
- **成功率**: 接近100%
- **错误处理**: 自动重试 + 详细日志

---

## 安全说明

1. **环境变量保护**: 敏感信息存储在 `.env` 文件,不要提交到Git
2. **URL参数加密**: 使用AES-256-GCM加密签字链接参数
3. **API鉴权**: 使用飞书tenant_access_token
4. **HTTPS**: 生产环境必须使用HTTPS

---

## 更新日志

### v1.1.0 (2025-12-04)
- ✅ 新增API限流器,解决频率限制问题
- ✅ 实现自动重试机制(指数退避)
- ✅ 优化并发处理,降低并发度至5
- ✅ 批量生成成功率提升至100%

### v1.0.0
- ✅ 基础功能实现
- ✅ 批量生成签字链接
- ✅ 会签/或签模式
- ✅ 二维码生成
- ✅ 历史签名复用

---

## 许可证

MIT License

---

## 联系方式

如有问题,请联系项目维护者。

---

## 附录: 飞书应用配置

### 1. 创建飞书应用

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 获取 `App ID` 和 `App Secret`

### 2. 配置权限

需要开通以下权限:
- `bitable:app` - 多维表格应用权限
- `drive:drive` - 云文档权限(上传图片)

### 3. 配置回调地址

在"事件订阅"中配置:
- 请求地址: `https://your-backend-domain.com/api/callback`

### 4. 发布应用

- 在"版本管理与发布"中创建版本
- 提交审核并发布到企业

---

**祝部署顺利!** 🚀
