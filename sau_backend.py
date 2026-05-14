"""
MatrixFlow Local Scan-Bind Server
本地扫码服务 — 对接云端 MatrixFlow ERP (Cloudflare Pages + NestJS ECS)

用法:
  pip install -r requirements.txt
  playwright install chromium
  python sau_backend.py          # → http://localhost:5409

前端连接:
  GET /api/scan-bind/start?platform=douyin&token=JWT&api_url=https://...
  → SSE 流: qr_code → uploading → success → 完成

为什么本地跑:
  Playwright 在用户电脑上启动 Chrome（真实IP），避免平台检测到阿里云数据中心IP封号。
"""

import asyncio
import json
import os
import sqlite3
import sys
import threading
import time
import uuid
from pathlib import Path
from queue import Queue, Empty

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from conf import BASE_DIR
from myUtils.login import douyin_cookie_gen, get_tencent_cookie, get_ks_cookie, xiaohongshu_cookie_gen

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = Flask(__name__)
CORS(app, origins=[
    'https://jujuju-28b.pages.dev',
    'https://ddddkiii.com',
    'https://www.ddddkiii.com',
    'http://localhost:5173',
    'http://localhost:3000',
    'http://127.0.0.1:5409',
])

app.config['MAX_CONTENT_LENGTH'] = 160 * 1024 * 1024

# ---------------------------------------------------------------------------
# Platform registry
# ---------------------------------------------------------------------------
PLATFORM_TYPE = {
    'douyin': 3, 'xiaohongshu': 1, 'kuaishou': 4, 'tencent': 2,
}
PLATFORM_API = {
    'douyin': 'DOUYIN', 'xiaohongshu': 'XIAOHONGSHU', 'kuaishou': 'KUAISHOU', 'tencent': 'WECHAT_VIDEO',
}
PLATFORM_CN = {
    'douyin': '抖音', 'xiaohongshu': '小红书', 'kuaishou': '快手', 'tencent': '视频号',
}
LOGIN_FN = {
    3: douyin_cookie_gen, 1: xiaohongshu_cookie_gen, 4: get_ks_cookie, 2: get_tencent_cookie,
}

# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------
def read_cookie_file(path: str) -> dict:
    """从 Playwright storage_state JSON 中提取 cookies 字符串"""
    try:
        with open(path) as f:
            data = json.load(f)
        cookies = data.get('cookies', [])
        cookie_str = '; '.join(f"{c['name']}={c['value']}" for c in cookies)
        return {'cookies': cookie_str, 'count': len(cookies)}
    except Exception as e:
        return {'cookies': '', 'count': 0, 'error': str(e)}


def find_latest_cookie() -> str | None:
    """在 cookiesFile/ 下找最近创建的 .json"""
    d = Path(BASE_DIR / 'cookiesFile')
    if not d.exists():
        return None
    files = sorted(d.glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)
    return str(files[0]) if files else None

# ---------------------------------------------------------------------------
# SSE endpoint — 核心：扫码 → 提取Cookie → 上传云端
# ---------------------------------------------------------------------------
@app.route('/api/scan-bind/start')
def scan_bind_start():
    platform = request.args.get('platform', 'douyin')
    token    = request.args.get('token', '')
    api_url  = request.args.get('api_url', '')

    if platform not in PLATFORM_TYPE:
        return jsonify({'code': 400, 'msg': f'不支持的平台: {platform}'}), 400
    if not token or not api_url:
        return jsonify({'code': 400, 'msg': '缺少 token 或 api_url'}), 400

    queue: Queue = Queue()

    def login_worker():
        """在独立线程中跑异步 Playwright 登录，通过 queue 与主线程通信"""
        type_num = PLATFORM_TYPE[platform]
        fn = LOGIN_FN.get(type_num)
        if not fn:
            queue.put({'type': 'error', 'data': '平台登录函数未实现'})
            return

        username = f"{platform}_{uuid.uuid4().hex[:6]}"

        async def _run():
            await fn(username, queue)

        try:
            asyncio.run(_run())
        except Exception as e:
            queue.put({'type': 'error', 'data': f'本地浏览器异常: {e}'})

        # 异步登录完成后，检查结果
        # 注意: login.py 往 queue 里放的是原始字符串 (qr_url / "200" / "500")
        # 我们需要在 worker 里监听 queue 并做后处理

    def _forward_raw():
        """把 login.py 的原始字符串转换成标准 JSON SSE 事件，并在成功时上传"""
        login_thread = threading.Thread(target=login_worker, daemon=True)
        login_thread.start()

        import requests as req

        while login_thread.is_alive() or not queue.empty():
            try:
                msg = queue.get(timeout=0.5)
            except Empty:
                continue

            # login.py 塞的是原始字符串：QR URL / "200" / "500"
            if isinstance(msg, str):
                if msg.startswith('http'):
                    # 二维码 URL
                    yield f"data: {json.dumps({'type': 'qr_code', 'data': msg})}\n\n"
                elif msg == '200':
                    yield f"data: {json.dumps({'type': 'status', 'data': '扫码成功，正在上传 Cookie...'})}\n\n"
                    # 找 Cookie 文件
                    cookie_path = find_latest_cookie()
                    if not cookie_path:
                        yield f"data: {json.dumps({'type': 'error', 'data': 'Cookie 文件未找到'})}\n\n"
                        return
                    info = read_cookie_file(cookie_path)
                    if not info['cookies']:
                        yield f"data: {json.dumps({'type': 'error', 'data': 'Cookie 解析失败: ' + info.get('error', '')})}\n\n"
                        return
                    # 上传云端
                    try:
                        resp = req.post(
                            f"{api_url.rstrip('/')}/accounts",
                            json={
                                'platform': PLATFORM_API[platform],
                                'platformUserId': f"scan_{int(time.time())}",
                                'nickname': PLATFORM_CN[platform],
                                'cookies': info['cookies'],
                            },
                            headers={
                                'Authorization': f'Bearer {token}',
                                'Content-Type': 'application/json',
                            },
                            timeout=20,
                        )
                        data = resp.json()
                        yield f"data: {json.dumps({'type': 'success', 'data': {'nestjs': data, 'platform': platform, 'nickname': PLATFORM_CN[platform]}})}\n\n"
                    except Exception as e:
                        yield f"data: {json.dumps({'type': 'error', 'data': f'上传云端失败: {e}'})}\n\n"
                    return
                elif msg == '500':
                    yield f"data: {json.dumps({'type': 'error', 'data': '扫码登录失败或超时（3分钟）'})}\n\n"
                    return
                else:
                    yield f"data: {json.dumps({'type': 'status', 'data': msg})}\n\n"
            elif isinstance(msg, dict):
                yield f"data: {json.dumps(msg)}\n\n"

        # Worker 退出了但没收到 200/500 → 异常退出
        if login_thread.is_alive() is False:
            yield f"data: {json.dumps({'type': 'error', 'data': '登录流程异常终止'})}\n\n"

    return Response(_forward_raw(), mimetype='text/event-stream',
                    headers={
                        'Cache-Control': 'no-cache',
                        'X-Accel-Buffering': 'no',
                        'Access-Control-Allow-Origin': '*',
                    })

# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------
@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'platforms': list(PLATFORM_TYPE.keys())})

# ---------------------------------------------------------------------------
# 保留旧端点向后兼容
# ---------------------------------------------------------------------------
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"code": 400, "msg": "No file"}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({"code": 400, "msg": "No filename"}), 400
    uid = uuid.uuid1()
    p = Path(BASE_DIR / "videoFile" / f"{uid}_{file.filename}")
    file.save(p)
    return jsonify({"code": 200, "msg": "ok", "data": f"{uid}_{file.filename}"})


@app.route('/api/login/stream/<int:type>/<id>')
def login_stream_legacy(type, id):
    """旧 SSE 端点（兼容 sau_frontend）"""
    q = Queue()
    fn = LOGIN_FN.get(type)
    if not fn:
        return jsonify({'code': 400, 'msg': 'unknown platform type'}), 400

    def _run():
        asyncio.run(fn(id, q))

    threading.Thread(target=_run, daemon=True).start()

    def _stream():
        while True:
            try:
                msg = q.get(timeout=0.3)
                yield f"data: {msg}\n\n"
            except Empty:
                continue
    return Response(_stream(), mimetype='text/event-stream')


if __name__ == '__main__':
    print(f'[MatrixFlow ScanBind] http://localhost:5409')
    print(f'  支持平台: {", ".join(PLATFORM_CN.values())}')
    app.run(host='127.0.0.1', port=5409, debug=False)
