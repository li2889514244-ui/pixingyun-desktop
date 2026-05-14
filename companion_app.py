"""
披星云桌面伴侣 v2.1 — 带 UI 界面，一键扫码
用法: python companion_app.py
"""
import asyncio, json, os, threading, time, uuid, base64
from pathlib import Path
from queue import Queue, Empty
from flask import Flask, request, jsonify, Response, make_response

app = Flask(__name__)
BASE_DIR = Path(__file__).parent.resolve()

# ── 平台配置 ──────────────────────────────────────────────────
PLATFORMS = {
    'douyin':   {'name':'抖音','url':'https://creator.douyin.com/','key':'DOUYIN'},
    'xiaohongshu': {'name':'小红书','url':'https://creator.xiaohongshu.com/','key':'XIAOHONGSHU'},
    'kuaishou': {'name':'快手','url':'https://cp.kuaishou.com/','key':'KUAISHOU'},
    'tencent':  {'name':'视频号','url':'https://channels.weixin.qq.com/','key':'WECHAT_VIDEO'},
}

# ── HTML UI ──────────────────────────────────────────────────
UI_HTML = r'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>披星云桌面伴侣</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#f0f2f5;color:#333;min-height:100vh}
.header{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:20px 32px;display:flex;align-items:center;gap:16px}
.header h1{font-size:22px;font-weight:600}
.dot{width:10px;height:10px;border-radius:50%;background:#4caf50;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.main{max-width:960px;margin:24px auto;padding:0 16px;display:grid;grid-template-columns:1fr 1fr;gap:20px}
.card{background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 12px rgba(0,0,0,.08)}
.card h2{font-size:16px;margin-bottom:16px;color:#555;border-bottom:2px solid #667eea;padding-bottom:8px}
.platforms{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.pbtn{border:2px solid #e8e8e8;border-radius:10px;padding:20px 12px;text-align:center;cursor:pointer;transition:.2s;background:#fafafa}
.pbtn:hover{border-color:#667eea;background:#f0f0ff;transform:translateY(-2px)}
.pbtn.active{border-color:#667eea;background:#eef0ff;box-shadow:0 0 0 3px rgba(102,126,234,.2)}
.pbtn .icon{font-size:32px;margin-bottom:8px}
.pbtn .name{font-size:14px;font-weight:600}
.pbtn .hint{font-size:11px;color:#999;margin-top:4px}
.scan-area{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:300px;text-align:center}
.scan-area img.qr{max-width:220px;border-radius:8px;border:2px solid #eee;margin-bottom:16px}
.scan-area .tip{color:#666;font-size:14px;margin-bottom:12px}
.scan-area .waiting{color:#999;font-size:13px}
.scan-area .success{color:#4caf50;font-size:48px;margin-bottom:8px}
.scan-area .error{color:#f44336;font-size:14px;margin-top:8px}
.status-bar{max-width:960px;margin:20px auto;background:#fff;border-radius:12px;padding:16px 24px;box-shadow:0 2px 12px rgba(0,0,0,.08);display:flex;align-items:center;gap:12px}
.status-bar .ind{width:12px;height:12px;border-radius:50%}
.status-bar .ind.on{background:#4caf50}.status-bar .ind.off{background:#f44336}
.spinner{border:3px solid #e8e8e8;border-top:3px solid #667eea;border-radius:50%;width:40px;height:40px;animation:spin 1s linear infinite;margin:16px auto}
@keyframes spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}}
.progress{width:100%;height:6px;background:#e8e8e8;border-radius:3px;margin:12px 0;overflow:hidden}
.progress .fill{height:100%;background:#667eea;border-radius:3px;transition:width .5s}
.btn{background:#667eea;color:#fff;border:none;padding:10px 24px;border-radius:8px;font-size:14px;cursor:pointer;margin-top:12px}
.btn:hover{background:#5a6fd6}
.step{display:flex;align-items:center;gap:8px;padding:8px 0;color:#666;font-size:13px}
.step .num{width:24px;height:24px;border-radius:50%;background:#667eea;color:#fff;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0}
</style></head><body>
<div class="header"><div class="dot"></div><h1>披星云桌面伴侣</h1><span style="opacity:.7;font-size:13px" v-if="siteConnected">已连接网站</span></div>

<div class="main">
  <div class="card">
    <h2>选择平台</h2>
    <div class="platforms">
      <div class="pbtn" v-for="p in platforms" :key="p.id" :class="{active:selected===p.id}" @click="selectPlatform(p.id)">
        <div class="icon">{{p.icon}}</div><div class="name">{{p.name}}</div><div class="hint">{{p.hint}}</div>
      </div>
    </div>
  </div>
  <div class="card">
    <h2>{{ selectedPlatform ? selectedPlatform.name + ' - 扫码登录' : '请从 MatrixFlow 网站发起绑定' }}</h2>
    <div class="scan-area">
      <template v-if="status==='idle'">
        <div style="color:#999;font-size:15px;line-height:1.8">
          <div class="step"><span class="num">1</span> 打开 MatrixFlow 网站登录</div>
          <div class="step"><span class="num">2</span> 点击"添加账号"</div>
          <div class="step"><span class="num">3</span> 网站会自动连接桌面伴侣</div>
          <div class="step"><span class="num">4</span> 选择平台 → 弹出 Chrome → 扫码</div>
        </div>
      </template>
      <div v-if="status==='loading'"><div class="spinner"></div><p class="waiting">正在启动浏览器...</p></div>
      <div v-if="status==='browser'"><p style="color:#4caf50;font-size:18px;margin-bottom:8px">浏览器已打开</p><p class="tip">请在 Chrome 窗口中扫码登录</p><div class="spinner"></div><p class="waiting">等待登录完成...</p><div class="progress"><div class="fill" :style="{width:progress+'%'}"></div></div></div>
      <div v-if="status==='scan'"><img class="qr" :src="qrUrl" v-if="qrUrl"><p class="tip">用手机扫描上方二维码</p></div>
      <div v-if="status==='uploading'"><div class="spinner"></div><p class="waiting">登录成功！正在上传 Cookie...</p></div>
      <div v-if="status==='done'"><div class="success">&#10003;</div><p style="color:#4caf50;font-size:16px">绑定成功！</p><p style="color:#999;margin:8px 0">刷新 MatrixFlow 网页即可看到新账号</p></div>
      <div v-if="status==='error'"><div class="error">{{ errorMsg }}</div><button class="btn" @click="reset">重试</button></div>
    </div>
  </div>
</div>

<div class="status-bar">
  <div class="ind" :class="siteConnected?'on':'off'"></div>
  <span>{{ siteConnected ? '已连接到 MatrixFlow 网站' : '等待网站连接... (在 MatrixFlow 网页中点击"添加账号")' }}</span>
  <span style="margin-left:auto;color:#999;font-size:12px">v2.1</span>
</div>

<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
<script>
const {createApp}=Vue
createApp({data(){return{
  platforms:[{id:'douyin',name:'抖音',icon:'🎵',hint:'扫码登录'},{id:'xiaohongshu',name:'小红书',icon:'📕',hint:'扫码登录'},{id:'kuaishou',name:'快手',icon:'🎬',hint:'扫码登录'},{id:'tencent',name:'视频号',icon:'📺',hint:'微信扫码'}],
  selected:'',status:'idle',qrUrl:'',errorMsg:'',siteConnected:false,evtSource:null,progress:0,timer:null,platformFromUrl:'',tokenFromUrl:'',apiFromUrl:''
}},computed:{selectedPlatform(){return this.platforms.find(p=>p.id===this.selected)}},
methods:{
  selectPlatform(id){
    if(this.status==='loading'||this.status==='browser'||this.status==='uploading')return
    this.selected=id;this.errorMsg=''
    const token=this.tokenFromUrl||this.getParam('token')
    const apiUrl=this.apiFromUrl||this.getParam('api')||'https://ddddkiii.com/api/v1'
    if(!token){this.errorMsg='请先从 MatrixFlow 网页的"添加账号"发起绑定（需要登录）';this.status='error';return}
    this.startScan(token,apiUrl)
  },
  getParam(k){return new URLSearchParams(location.search).get(k)},
  startScan(token,apiUrl){
    this.status='loading';this.progress=0
    this.timer=setInterval(()=>{if(this.progress<90)this.progress+=1},400)
    const url=`/api/scan-bind/start?platform=${this.selected}&token=${encodeURIComponent(token)}&api_url=${encodeURIComponent(apiUrl)}`
    this.evtSource=new EventSource(url)
    this.evtSource.onmessage=e=>{
      try{const d=JSON.parse(e.data)
        if(d.type==='qr_code'){this.status='scan';this.qrUrl=d.data}
        else if(d.type==='browser'){this.status='browser';this.progress=50}
        else if(d.type==='status'){if(d.data.includes('上传'))this.status='uploading'}
        else if(d.type==='success'){this.status='done';this.progress=100;clearInterval(this.timer);this.evtSource.close()}
        else if(d.type==='error'){this.status='error';this.errorMsg=d.data;clearInterval(this.timer);this.evtSource.close()}
      }catch(ex){}
    }
    this.evtSource.onerror=()=>{if(this.status!=='done'){this.status='error';this.errorMsg='连接中断，请重试';clearInterval(this.timer)}}
  },
  reset(){this.evtSource?.close();clearInterval(this.timer);this.status='idle';this.qrUrl='';this.errorMsg='';this.selected='';this.progress=0}
},
mounted(){
  this.platformFromUrl=this.getParam('platform')
  this.tokenFromUrl=this.getParam('token')
  this.apiFromUrl=this.getParam('api')
  if(this.platformFromUrl&&this.tokenFromUrl){this.selectPlatform(this.platformFromUrl)}
  setInterval(async()=>{try{const r=await fetch('/health');if(r.ok)this.siteConnected=true}catch{this.siteConnected=false}},3000)
}}).mount('body')
</script></body></html>'''

# ── Routes ────────────────────────────────────────────────────
@app.route('/')
def index():
    resp = make_response(UI_HTML)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp

@app.route('/health')
def health():
    resp = make_response(jsonify({'status':'ok','platforms':list(PLATFORMS.keys())}))
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

@app.route('/api/scan-bind/start')
def scan_bind_start():
    platform = request.args.get('platform', 'douyin')
    token = request.args.get('token', '')
    api_url = request.args.get('api_url', '')

    if not token or not api_url:
        return jsonify({'code':400,'msg':'缺少参数'}), 400
    if platform not in PLATFORMS:
        return jsonify({'code':400,'msg':f'不支持的平台: {platform}'}), 400

    info = PLATFORMS[platform]
    queue: Queue = Queue()

    def login_worker():
        async def _run():
            try:
                from playwright.async_api import async_playwright
                async with async_playwright() as pw:
                    browser = await pw.chromium.launch(
                        headless=False,
                        args=['--disable-blink-features=AutomationControlled','--lang=zh-CN','--start-maximized']
                    )
                    context = await browser.new_context(
                        viewport={'width':1280,'height':800},
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    )
                    page = await context.new_page()

                    queue.put(json.dumps({'type':'browser','data':'浏览器已打开'}))

                    # 打开平台登录页
                    await page.goto(info['url'], wait_until='domcontentloaded', timeout=30000)
                    await page.wait_for_timeout(5000)

                    # 尝试截图作为二维码
                    try:
                        screenshot = await page.screenshot(type='png')
                        b64 = base64.b64encode(screenshot).decode()
                        queue.put(json.dumps({'type':'qr_code','data':f'data:image/png;base64,{b64}'}))
                    except:
                        pass

                    queue.put(json.dumps({'type':'status','data':'请在弹出的 Chrome 窗口中扫码登录，等待中...'}))

                    original_url = page.url

                    # 等待登录完成（URL变化或Cookie出现，最多等5分钟）
                    logged_in = False
                    for i in range(300):
                        await page.wait_for_timeout(1000)
                        try:
                            # 检查URL是否变化（登录成功通常会跳转）
                            current_url = page.url
                            if current_url != original_url and 'login' not in current_url.lower():
                                logged_in = True
                                break
                            # 或者检查 Cookie 是否出现
                            cookies = await context.cookies()
                            if len(cookies) > 3:  # 多于初始的几个 cookie
                                logged_in = True
                                break
                        except:
                            pass

                    if not logged_in:
                        # 超时——仍然尝试获取 cookie
                        pass

                    queue.put(json.dumps({'type':'status','data':'正在提取 Cookie...'}))

                    # 提取所有 Cookies
                    cookies = await context.cookies()
                    cookie_str = '; '.join(f"{c['name']}={c['value']}" for c in cookies)

                    if not cookie_str:
                        queue.put(json.dumps({'type':'error','data':'未能获取到 Cookie，请在 Chrome 窗口中确认已登录'}))
                        await browser.close()
                        return

                    # 上传到云端
                    import requests
                    resp = requests.post(
                        f"{api_url.rstrip('/')}/accounts",
                        json={
                            'platform': info['key'],
                            'platformUserId': f"scan_{int(time.time())}",
                            'nickname': info['name'],
                            'cookies': cookie_str,
                        },
                        headers={'Authorization': f'Bearer {token}','Content-Type': 'application/json'},
                        timeout=30,
                    )
                    data = resp.json()
                    if data.get('code') == 0:
                        queue.put(json.dumps({'type':'success','data':{'platform':platform,'cookies_count':len(cookies)}}))
                    else:
                        queue.put(json.dumps({'type':'error','data':f"上传失败: {data.get('message','未知错误')}"}))

                    await browser.close()
            except Exception as e:
                queue.put(json.dumps({'type':'error','data':f'浏览器异常: {str(e)[:200]}'}))

        asyncio.run(_run())

    def sse_stream():
        t = threading.Thread(target=login_worker, daemon=True)
        t.start()

        while t.is_alive() or not queue.empty():
            try:
                msg = queue.get(timeout=0.5)
            except Empty:
                continue

            if isinstance(msg, str):
                try:
                    # 检查是不是JSON
                    d = json.loads(msg)
                    yield f"data: {json.dumps(d)}\n\n"
                except:
                    yield f"data: {json.dumps({'type':'status','data':str(msg)})}\n\n"
            elif isinstance(msg, dict):
                yield f"data: {json.dumps(msg)}\n\n"

    return Response(sse_stream(), mimetype='text/event-stream',
                    headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no',
                             'Access-Control-Allow-Origin':'*'})

# ── Main ──────────────────────────────────────────────────────
if __name__ == '__main__':
    print('=' * 50)
    print('  披星云桌面伴侣 v2.1')
    print('  http://localhost:5409')
    print(f'  平台: {" | ".join(p["name"] for p in PLATFORMS.values())}')
    print('=' * 50)
    app.run(host='127.0.0.1', port=5409, debug=False)
