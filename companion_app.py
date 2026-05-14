"""
披星云桌面伴侣 v2 — 带 UI 界面
用法: python companion_app.py
打开浏览器访问 http://localhost:5409
"""
import asyncio, json, os, threading, time, uuid
from pathlib import Path
from queue import Queue, Empty

from flask import Flask, request, jsonify, Response, render_template_string

app = Flask(__name__)

BASE_DIR = Path(__file__).parent.resolve()

# ── HTML UI ──────────────────────────────────────────────────
UI_HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>披星云桌面伴侣</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#f0f2f5;color:#333;min-height:100vh}
.header{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:20px 32px;display:flex;align-items:center;gap:16px}
.header h1{font-size:22px;font-weight:600;letter-spacing:2px}
.header .dot{width:10px;height:10px;border-radius:50%;background:#4caf50;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.main{max-width:960px;margin:24px auto;padding:0 16px;display:grid;grid-template-columns:1fr 1fr;gap:20px}
.card{background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 12px rgba(0,0,0,.08)}
.card h2{font-size:16px;margin-bottom:16px;color:#555;border-bottom:2px solid #667eea;padding-bottom:8px}
.platforms{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.platform-btn{border:2px solid #e8e8e8;border-radius:10px;padding:20px 12px;text-align:center;cursor:pointer;transition:all .2s;background:#fafafa}
.platform-btn:hover{border-color:#667eea;background:#f0f0ff;transform:translateY(-2px)}
.platform-btn.active{border-color:#667eea;background:#eef0ff;box-shadow:0 0 0 3px rgba(102,126,234,.2)}
.platform-btn .icon{font-size:32px;margin-bottom:8px}
.platform-btn .name{font-size:14px;font-weight:600}
.platform-btn .hint{font-size:11px;color:#999;margin-top:4px}
.scan-area{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:300px;text-align:center}
.scan-area img.qr{max-width:220px;border-radius:8px;border:2px solid #eee;margin-bottom:16px}
.scan-area .tip{color:#666;font-size:14px;margin-bottom:12px}
.scan-area .waiting{color:#999;font-size:13px}
.scan-area .success{color:#4caf50;font-size:48px;margin-bottom:8px}
.scan-area .error{color:#f44336;font-size:14px}
.status-bar{background:#fff;border-radius:12px;padding:16px 24px;box-shadow:0 2px 12px rgba(0,0,0,.08);margin-top:20px;display:flex;align-items:center;gap:12px}
.status-bar .indicator{width:12px;height:12px;border-radius:50%}
.status-bar .indicator.on{background:#4caf50}
.status-bar .indicator.off{background:#f44336}
.status-bar span{font-size:14px;color:#666}
.spinner{border:3px solid #e8e8e8;border-top:3px solid #667eea;border-radius:50%;width:40px;height:40px;animation:spin 1s linear infinite;margin:16px auto}
@keyframes spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}}
.progress{width:100%;height:6px;background:#e8e8e8;border-radius:3px;margin:12px 0;overflow:hidden}
.progress .fill{height:100%;background:#667eea;border-radius:3px;transition:width .3s}
</style>
</head>
<body>
<div class="header">
  <div class="dot"></div>
  <h1>披星云桌面伴侣</h1>
</div>

<div class="main">
  <div class="card">
    <h2>选择平台</h2>
    <div class="platforms">
      <div class="platform-btn" v-for="p in platforms" :key="p.id"
           :class="{active:selected===p.id}" @click="selectPlatform(p.id)">
        <div class="icon">{{p.icon}}</div>
        <div class="name">{{p.name}}</div>
        <div class="hint">{{p.hint}}</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>{{ selectedPlatform ? platforms.find(p=>p.id===selected)?.name+' - 扫码登录' : '请选择平台' }}</h2>
    <div class="scan-area">
      <div v-if="status==='idle'">👈 选择一个平台开始</div>
      <div v-if="status==='loading'"><div class="spinner"></div><p class="waiting">正在启动浏览器...</p></div>
      <div v-if="status==='scan'"><img class="qr" :src="qrUrl" v-if="qrUrl"><p class="tip">请用手机扫码</p><div v-if="!qrUrl"><div class="spinner"></div><p class="waiting">加载二维码...</p></div></div>
      <div v-if="status==='uploading'"><div class="spinner"></div><p class="waiting">扫码成功！正在上传 Cookie...</p><div class="progress"><div class="fill" style="width:80%"></div></div></div>
      <div v-if="status==='done'"><div class="success">&#10003;</div><p style="color:#4caf50;font-size:16px">绑定成功！</p><p style="color:#999;margin-top:8px">刷新 MatrixFlow 网页即可看到新账号</p><button @click="reset" style="margin-top:16px;background:#667eea;color:#fff;border:none;padding:10px 24px;border-radius:8px;font-size:14px;cursor:pointer">继续绑定</button></div>
      <div v-if="status==='error'"><div class="error">{{ errorMsg }}</div><button @click="reset" style="margin-top:12px;background:#667eea;color:#fff;border:none;padding:10px 24px;border-radius:8px;font-size:14px;cursor:pointer">重试</button></div>
    </div>
  </div>
</div>

<div class="status-bar" style="max-width:960px;margin:0 auto">
  <div class="indicator" :class="siteConnected?'on':'off'"></div>
  <span>{{ siteConnected ? '已连接到 MatrixFlow 网站' : '等待网站连接... (在 MatrixFlow 网页点击"添加账号")' }}</span>
</div>

<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
<script>
const {createApp} = Vue
createApp({
  data(){return{
    platforms:[
      {id:'douyin',name:'抖音',icon:'🎵',hint:'支持扫码登录'},
      {id:'xiaohongshu',name:'小红书',icon:'📕',hint:'支持扫码登录'},
      {id:'kuaishou',name:'快手',icon:'🎬',hint:'支持扫码登录'},
      {id:'tencent',name:'视频号',icon:'📺',hint:'需微信扫码'},
    ],
    selected:'',status:'idle',qrUrl:'',errorMsg:'',siteConnected:false,evtSource:null
  }},
  computed:{
    selectedPlatform(){return this.platforms.find(p=>p.id===this.selected)}
  },
  methods:{
    selectPlatform(id){
      if(this.status==='loading'||this.status==='scan'||this.status==='uploading')return
      this.selected=id;this.status='loading';this.errorMsg=''
      const token=this.getTokenFromUrl()
      const apiUrl=this.getApiUrl()
      if(!token||!apiUrl){this.errorMsg='请从 MatrixFlow 网页发起绑定';this.status='error';return}
      this.startScan(token,apiUrl)
    },
    getTokenFromUrl(){return new URLSearchParams(location.search).get('token')},
    getApiUrl(){return new URLSearchParams(location.search).get('api')||'https://ddddkiii.com/api/v1'},
    startScan(token,apiUrl){
      const url=`/api/scan-bind/start?platform=${this.selected}&token=${encodeURIComponent(token)}&api_url=${encodeURIComponent(apiUrl)}`
      this.evtSource=new EventSource(url)
      this.evtSource.onmessage=e=>{
        try{const d=JSON.parse(e.data)
          if(d.type==='qr_code'){this.status='scan';this.qrUrl=d.data}
          else if(d.type==='status'){this.status=d.data.includes('上传')?'uploading':'scan'}
          else if(d.type==='success'){this.status='done';this.evtSource.close()}
          else if(d.type==='error'){this.status='error';this.errorMsg=d.data;this.evtSource.close()}
        }catch(ex){}
      }
      this.evtSource.onerror=()=>{if(this.status!=='done'){this.status='error';this.errorMsg='连接本地服务失败'}}
    },
    reset(){this.evtSource?.close();this.status='idle';this.qrUrl='';this.errorMsg='';this.selected=''}
  },
  mounted(){
    // Check site connectivity every 3s
    setInterval(async()=>{
      try{const r=await fetch('/health');if(r.ok)this.siteConnected=true}catch{this.siteConnected=false}
    },3000)
  }
}).mount('body')
</script>
</body>
</html>'''

# ── Routes ────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template_string(UI_HTML)

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'platforms': ['douyin','xiaohongshu','kuaishou','tencent']})

@app.route('/api/scan-bind/start')
def scan_bind_start():
    platform = request.args.get('platform', 'douyin')
    token = request.args.get('token', '')
    api_url = request.args.get('api_url', '')

    if not token or not api_url:
        return jsonify({'code': 400, 'msg': '缺少 token 或 api_url'}), 400

    queue: Queue = Queue()

    def login_worker():
        """在独立线程中运行异步 Playwright 登录"""
        async def _run():
            try:
                from playwright.async_api import async_playwright
                async with async_playwright() as pw:
                    browser = await pw.chromium.launch(headless=False, args=[
                        '--disable-blink-features=AutomationControlled',
                        '--lang=zh-CN', '--start-maximized'
                    ])
                    context = await browser.new_context()
                    page = await context.new_page()

                    urls = {
                        'douyin': 'https://creator.douyin.com/',
                        'xiaohongshu': 'https://creator.xiaohongshu.com/',
                        'kuaishou': 'https://cp.kuaishou.com/',
                        'tencent': 'https://channels.weixin.qq.com/',
                    }
                    url = urls.get(platform, urls['douyin'])
                    await page.goto(url, wait_until='domcontentloaded')

                    # 等待二维码出现
                    await page.wait_for_timeout(3000)
                    qr_found = False
                    for selector in ['img[alt*="二维码"]', 'img[src*="qrcode"]', 'img[src*="qr"]', '.qrcode img', 'canvas']:
                        try:
                            img = await page.query_selector(selector)
                            if img:
                                src = await img.get_attribute('src')
                                if src:
                                    queue.put(src)
                                    qr_found = True
                                    break
                        except:
                            continue

                    if not qr_found:
                        # 截图作为二维码
                        try:
                            screenshot = await page.screenshot(type='png')
                            import base64
                            b64 = base64.b64encode(screenshot).decode()
                            queue.put(f'data:image/png;base64,{b64}')
                        except:
                            queue.put('no_qr')

                    # 等待登录（检测 URL 变化，最多等 3 分钟）
                    original_url = page.url
                    for _ in range(180):
                        await page.wait_for_timeout(1000)
                        try:
                            if page.url != original_url:
                                queue.put('200')
                                break
                        except:
                            pass
                    else:
                        queue.put('500')
                        await browser.close()
                        return

                    # 提取 Cookies
                    cookies = await context.cookies()
                    cookie_str = '; '.join(f"{c['name']}={c['value']}" for c in cookies)

                    # 上传到云端
                    import requests
                    resp = requests.post(
                        f"{api_url.rstrip('/')}/accounts",
                        json={
                            'platform': {'douyin':'DOUYIN','xiaohongshu':'XIAOHONGSHU','kuaishou':'KUAISHOU','tencent':'WECHAT_VIDEO'}[platform],
                            'platformUserId': f"scan_{int(time.time())}",
                            'nickname': {'douyin':'抖音','xiaohongshu':'小红书','kuaishou':'快手','tencent':'视频号'}[platform],
                            'cookies': cookie_str,
                        },
                        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
                        timeout=20,
                    )
                    data = resp.json()
                    queue.put(json.dumps({'type': 'success', 'data': {'platform': platform, 'cookies_count': len(cookies)}}))

                    await browser.close()
            except Exception as e:
                queue.put(json.dumps({'type': 'error', 'data': f'浏览器异常: {str(e)[:200]}'}))

        asyncio.run(_run())

    import requests as req

    def sse_stream():
        t = threading.Thread(target=login_worker, daemon=True)
        t.start()

        while t.is_alive() or not queue.empty():
            try:
                msg = queue.get(timeout=0.5)
            except Empty:
                continue

            if isinstance(msg, str):
                if msg.startswith('http') or msg.startswith('data:image'):
                    yield f"data: {json.dumps({'type': 'qr_code', 'data': msg})}\n\n"
                elif msg == '200':
                    yield f"data: {json.dumps({'type': 'status', 'data': '扫码成功，正在上传 Cookie...'})}\n\n"
                elif msg == '500':
                    yield f"data: {json.dumps({'type': 'error', 'data': '扫码超时（3分钟），请重试'})}\n\n"
                elif msg.startswith('{'):
                    yield f"data: {msg}\n\n"
                elif msg == 'no_qr':
                    yield f"data: {json.dumps({'type': 'error', 'data': '未找到二维码，请确认页面是否加载成功'})}\n\n"

        if not t.is_alive():
            yield f"data: {json.dumps({'type': 'error', 'data': '浏览器进程异常退出'})}\n\n"

    return Response(sse_stream(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no',
                             'Access-Control-Allow-Origin': '*'})

# ── Main ──────────────────────────────────────────────────────
if __name__ == '__main__':
    print('=' * 50)
    print('  披星云桌面伴侣 v2')
    print('  http://localhost:5409')
    print('  支持的平台: 抖音 | 小红书 | 快手 | 视频号')
    print('=' * 50)
    app.run(host='127.0.0.1', port=5409, debug=False)
