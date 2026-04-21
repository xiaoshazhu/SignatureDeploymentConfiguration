# 飞书插件部署诊断与后端配置方案 (v1.1)

## 1. 现状：当前 Release 包的配置分析

经查阅您提供的 `release/v2_feishu_upload` 目录：

### 前端 (dist 目录)
*   **请求地址**: 它是以相对路径 `/api` 打包的。
*   **当前行为**: 插件在飞书内运行时，请求地址变成了 `https://ext.baseopendev.com/api/config/set-token`。
*   **结果**: 飞书静态服务器拦截请求，返回 `412 Precondition Failed`。

### 后端 (backend_code 目录)
*   **配置情况**: `.env` 文件中 `HOST_URL` 被设置为 `https://frp2.yiknet.com/`。
*   **跨域情况**: `main.py` 只允许 `*.feishu.cn`。
*   **结果**: 即使前端地址写对了，目前的配置也会导致 `ext.baseopendev.com` (开发域名) 或 `feishuapp.cn` (生产域名) 的跨域请求被拦截。

---

## 2. 后端连接配置指南

要实现前端（静态页）与后端（Python 业务）的成功连接，请按以下步骤操作：

### 步骤 A：准备后端服务器
1.  **获取域名**: 您需要一个支持 HTTPS 的域名（如 `https://api.yourdomain.com`）。
2.  **运行环境**: 确保 Python 后端已启动并监听 `3000` 端口（或通过 Gunicorn 转发）。
3.  **开放权限**: 确保该服务器的防火墙已放行对应端口。

### 步骤 B：修改前端打包配置 (关键)
您需要修改 `vue-template-main/.env.production` 文件：
```bash
# 原来是: VITE_API_BASE=/api
# 修改为您的真实后端地址 (必须是 https)
VITE_API_BASE=https://api.yourdomain.com/api

# 前端连接地址 (用于生成二维码)
VITE_FRONTEND_HOST=https://ext.baseopendev.com
```

### 步骤 C：修改后端白名单配置
修改 `BaseOpenSDK-Python-Playground/main.py` 中的跨域 origins，允许飞书的各种运行环境：
```python
# 增加飞书开发和生产环境的域名
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://localhost:5173", 
            "https://*.feishu.cn", 
            "https://*.baseopendev.com",  # 开发/测试环境
            "https://*.feishuapp.cn"      # 生产发布环境
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    }
})
```

---

## 3. 如何为交付打包

当您准备好交付新版本给飞书开发人员时，建议按以下流程：

### 1. 重新打包前端
```bash
cd vue-template-main
npm run build
```
这会生成新的 `dist` 目录。**注意：** 因为 VITE_API_BASE 现在是绝对路径，这个 `dist` 里的 JS 会直接向您的服务器发请求。

### 2. 交付物结构清单
您可以提供一个压缩包，包含以下内容：
*   `dist/` ----> **发给飞书人员**，请他们上传到插件托管平台（静态空间）。
*   `backend_code/` ----> **由您自己部署**在您的独立服务器上。

---

## 4. 为什么“30次内容没加载”？

因为前端一启动就会请求 `/api/quota/status`。
*   **本地开发时**: Vite 做了代理，请求被转到了 `localhost:3000`。
*   **发布后**: 请求由于是相对路径，变成了请求飞书的静态服务器，飞书服务器返回了 412/404，前端收不到数据，所以默认显示为 0。

---

## 5. 待沟通事项

*   [ ] **后端域名**: 您是否有已经配好 HTTPS 的域名用于运行后端？
*   [ ] **白名单**: 如果您能在飞书后台找到发布的正式域名（通常在“H5应用”配置里可以查到），请告诉我，以便精确锁定白名单。

**在您确认上述信息后，我可以一键为您完成这些配置的修改。**

---

## 🚀 宝塔 HTML 项目部署指南

由于前端是静态文件，后端是 Python 服务，您需要在宝塔中进行以下操作：

### 1. 创建站点
*   在宝塔面板点击 **“网站”** -> **“添加站点”**。
*   域名输入：`sign-pri.anhuishuzhi.com`。
*   备注：随意（如“电子签名插件前端”）。
*   根目录：宝塔会自动生成。
*   PHP版本：选择 **“纯静态”**。

### 2. 上传前端文件
*   构建完成后的文件位于本地项目的 `vue-template-main/dist` 目录下。
*   将 `dist` 目录内的**所有内容**（包含 `assets` 文件夹和 `index.html` 等）上传到您刚才创建站点的根目录中。

### 3. 配置反向代理 (极其重要)
由于前端代码中 API 地址是 `https://sign-pri.anhuishuzhi.com/api`，您需要让 Nginx 把 `/api` 的请求转发给后端的 Python 程序：
*   在网站列表找到该站点，点击 **“设置”** -> **“反向代理”** -> **“添加反向代理”**。
*   代理名称：`feishu-api`。
*   目标 URL：`http://127.0.0.1:3001` (假设您的 Python 后端在 3001 端口)。
*   发送域名：`$host`。
*   **注意**：在“代理目录”中填入 `/api`。

### 4. 开启 SSL (HTTPS)
*   点击 **“设置”** -> **“SSL”**。
*   申请或填入您的证书。飞书环境强制要求 HTTPS。

---

## 🏗️ 交付物存档

*   **前端打包结果**: [vue-template-main/dist/](file:///Users/wangxun/Desktop/demo/26xm/feishu-signature-plugin/vue-template-main/dist/)
*   **后端代码目录**: [BaseOpenSDK-Python-Playground/](file:///Users/wangxun/Desktop/demo/26xm/feishu-signature-plugin/BaseOpenSDK-Python-Playground/) (部署至宝塔 Python 项目管理器)

