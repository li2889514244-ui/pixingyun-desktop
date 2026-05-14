# 披星云桌面伴侣

MatrixFlow 本地扫码绑定工具 — 在你电脑上运行，用真实 IP 完成平台扫码登录，Cookie 自动同步云端。

## 支持的平台

抖音 / 小红书 / 快手 / 视频号

## 使用步骤

1. 下载本仓库 zip 并解压
2. 双击 **setup.bat**（首次自动安装 Python 依赖 + Chromium 浏览器，约 150MB，需几分钟）
3. 双击 **start.bat** 启动本地服务（http://localhost:5409）
4. 在 MatrixFlow 网页中点击"添加平台账号" → 选择平台
5. 弹出 Chrome 窗口 → 手机扫码登录
6. Cookie 自动上传，刷新网页即可见

## 工作原理

```
MatrixFlow 网页 ──SSE──→ localhost:5409 (Flask)
                           │
                           ├─ Playwright 启动 Chrome（你的真实 IP）
                           ├─ 打开平台登录页，获取二维码
                           ├─ 你手机扫码 → 检测登录成功
                           ├─ 提取 Cookie
                           └─ POST 上传到 MatrixFlow 云端
```

## 依赖

- Python 3.9+
- Playwright + Chromium
- Flask, requests
