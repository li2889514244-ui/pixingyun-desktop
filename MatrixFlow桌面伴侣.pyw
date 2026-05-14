"""
披星云桌面伴侣 v3.1 — Windows 桌面应用 + 网站联动
双击运行，自动检测网站连接
"""
import customtkinter as ctk
import threading, json, time, asyncio, base64, webbrowser, requests
from queue import Queue, Empty
from flask import Flask, request, jsonify, Response

# ── Flask 后台服务（供网站检测和通信） ─────────────────────────
flask_app = Flask(__name__)
API_URL = "https://ddddkiii.com/api/v1"
SITE_URL = "https://jujuju-28b.pages.dev"
SCAN_QUEUE = Queue()  # 全局消息队列，供 Flask 和 tkinter 通信
scan_sessions = {}

PLATFORM_INFO = {
    "douyin":       ("抖音", "DOUYIN", "https://creator.douyin.com/"),
    "xiaohongshu":  ("小红书", "XIAOHONGSHU", "https://creator.xiaohongshu.com/"),
    "kuaishou":     ("快手", "KUAISHOU", "https://cp.kuaishou.com/"),
    "tencent":      ("视频号", "WECHAT_VIDEO", "https://channels.weixin.qq.com/"),
}

PLATFORM_BUTTONS = [
    {"id": "douyin", "name": "抖 音", "color": "#111111", "icon": "🎵"},
    {"id": "xiaohongshu", "name": "小红书", "color": "#ff2442", "icon": "📕"},
    {"id": "kuaishou", "name": "快 手", "color": "#ff4906", "icon": "🎬"},
    {"id": "tencent", "name": "视频号", "color": "#07c160", "icon": "📺"},
]

@flask_app.route('/health')
def health():
    resp = jsonify({'status':'ok','platforms':list(PLATFORM_INFO.keys())})
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

@flask_app.route('/api/scan-bind/start')
def scan_bind_start():
    platform = request.args.get('platform', 'douyin')
    token = request.args.get('token', '')
    api_url = request.args.get('api_url', API_URL)

    if platform not in PLATFORM_INFO:
        return jsonify({'code':400,'msg':'unknown platform'}),400
    if not token:
        return jsonify({'code':400,'msg':'missing token'}),400

    SCAN_QUEUE.put({'action':'start','platform':platform,'token':token,'api_url':api_url})

    def sse_stream():
        yield f"data: {json.dumps({'type':'status','data':'已发送到桌面伴侣'})}\n\n"
        # 等待结果
        for i in range(600):
            time.sleep(0.5)
            try:
                msg = SCAN_QUEUE.get_nowait()
                if isinstance(msg, dict) and msg.get('action') in ('done','error'):
                    yield f"data: {json.dumps(msg)}\n\n"
                    return
            except Empty:
                pass
        yield f"data: {json.dumps({'type':'error','data':'timeout'})}\n\n"

    resp = Response(sse_stream(), mimetype='text/event-stream',
                    headers={'Cache-Control':'no-cache','Access-Control-Allow-Origin':'*'})
    return resp

def start_flask():
    from waitress import serve
    serve(flask_app, host='127.0.0.1', port=5409, _quiet=True)

# ── 桌面 UI ──────────────────────────────────────────────────
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class MatrixFlowApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("披星云桌面伴侣")
        self.geometry("460x600")
        self.resizable(False, False)
        self.scanning = False
        self.build_ui()
        self.check_website()

    def build_ui(self):
        # ── 顶栏 ──
        header = ctk.CTkFrame(self, fg_color="#667eea", corner_radius=0, height=90)
        header.pack(fill="x"); header.pack_propagate(False)
        ctk.CTkLabel(header, text="披星云", font=("Microsoft YaHei", 24, "bold"), text_color="white").pack(pady=(16,0))
        ctk.CTkLabel(header, text="桌面伴侣 v3.1 · 矩阵账号管理", font=("Microsoft YaHei", 10), text_color="#cccccc").pack()

        # ── 状态条 ──
        sf = ctk.CTkFrame(self, fg_color="transparent", height=32)
        sf.pack(fill="x", padx=20, pady=(12,0))
        self.status_dot = ctk.CTkLabel(sf, text="●", font=("",14), text_color="gray", width=16)
        self.status_dot.pack(side="left")
        self.status_lbl = ctk.CTkLabel(sf, text="检测中...", font=("Microsoft YaHei",11), text_color="gray")
        self.status_lbl.pack(side="left", padx=4)
        self.status_url = ctk.CTkLabel(sf, text="localhost:5409", font=("Microsoft YaHei",9), text_color="#bbb")
        self.status_url.pack(side="right")

        # ── 打开网站按钮 ──
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(fill="x", padx=20, pady=(10,0))
        ctk.CTkButton(bf, text="🌐  打开 MatrixFlow 网站", font=("Microsoft YaHei",13,"bold"),
                      height=44, fg_color="#667eea", hover_color="#5a6fd6",
                      command=lambda: webbrowser.open(SITE_URL)).pack(fill="x")

        # ── 平台选择 ──
        ctk.CTkLabel(self, text="选择平台开始绑定（需先在网站登录）", font=("Microsoft YaHei",10), text_color="#999").pack(pady=(14,6))
        pf = ctk.CTkFrame(self, fg_color="transparent")
        pf.pack(fill="x", padx=20)
        self.plat_btns = {}
        for i, p in enumerate(PLATFORM_BUTTONS):
            def handler(pid=p["id"]): self.start_scan(pid)
            btn = ctk.CTkButton(pf, text=f"{p['icon']}  {p['name']}", font=("Microsoft YaHei",13),
                                height=48, fg_color=p["color"], hover_color=self._dark(p["color"]),
                                command=handler)
            row, col = divmod(i, 2)
            btn.grid(row=row, column=col, padx=4, pady=4, sticky="ew")
            self.plat_btns[p["id"]] = btn
        pf.grid_columnconfigure(0, weight=1); pf.grid_columnconfigure(1, weight=1)

        # ── 消息区 ──
        self.msg_frame = ctk.CTkFrame(self, fg_color="#f5f7fa", corner_radius=8, height=120)
        self.msg_frame.pack(fill="x", padx=20, pady=(12,0))
        self.msg_frame.pack_propagate(False)
        self.msg_title = ctk.CTkLabel(self.msg_frame, text="👋 欢迎使用桌面伴侣", font=("Microsoft YaHei",13,"bold"), text_color="#333")
        self.msg_title.pack(pady=(24,4))
        self.msg_text = ctk.CTkLabel(self.msg_frame, text="点击上方按钮打开网站，登录后选择平台即可开始", font=("Microsoft YaHei",11), text_color="#999", wraplength=400)
        self.msg_text.pack()
        self.btn_row = None

        # ── 进度 ──
        self.progress = ctk.CTkProgressBar(self, width=420, height=6, progress_color="#667eea")
        self.progress.pack(pady=(10,0)); self.progress.set(0)

        # ── 底部 ──
        ctk.CTkLabel(self, text="扫码使用你电脑的真实IP，不触发平台风控", font=("Microsoft YaHei",9), text_color="#bbb").pack(pady=(8,10))

    def _dark(self, h): r,g,b=int(h[1:3],16),int(h[3:5],16),int(h[5:7],16); return f"#{max(0,r-40):02x}{max(0,g-40):02x}{max(0,b-40):02x}"

    # ── 网站检测 ──
    def check_website(self):
        def _chk():
            while True:
                try:
                    r = requests.get(f"{API_URL}/health", timeout=5)
                    ok = r.status_code == 200
                except: ok = False
                self.after(0, lambda o=ok: (
                    self.status_dot.configure(text="●",text_color="#4caf50"),
                    self.status_lbl.configure(text="网站已连接",text_color="#4caf50")
                ) if o else (
                    self.status_dot.configure(text="●",text_color="#f44336"),
                    self.status_lbl.configure(text="网站未连接",text_color="#f44336")
                ))
                time.sleep(5)
        threading.Thread(target=_chk, daemon=True).start()

    # ── 扫码 ──
    def start_scan(self, platform_id: str):
        if self.scanning:
            return
        self.scanning = True
        for b in self.plat_btns.values(): b.configure(state="disabled")
        self.progress.set(0)

        info = PLATFORM_INFO[platform_id]
        self._msg("🔄", "正在启动浏览器...", f"平台: {info[0]}\n即将弹出 Chrome 窗口，请稍候")

        def worker():
            try:
                async def _run():
                    from playwright.async_api import async_playwright
                    self.after(0, lambda: self.progress.set(0.1))
                    async with async_playwright() as pw:
                        browser = await pw.chromium.launch(headless=False, args=[
                            '--disable-blink-features=AutomationControlled','--lang=zh-CN','--start-maximized'])
                        ctx = await browser.new_context(viewport={'width':1280,'height':800},
                            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36')
                        page = await ctx.new_page()
                        self.after(0, lambda: self.progress.set(0.3))
                        self.after(0, lambda: self._show_confirm())
                        await page.goto(info[2], wait_until='domcontentloaded', timeout=30000)
                        await page.wait_for_timeout(5000)
                        self.after(0, lambda: self.progress.set(0.5))

                        # 等待用户确认
                        for i in range(600):
                            await page.wait_for_timeout(500)
                            try:
                                msg = SCAN_QUEUE.get_nowait()
                                if isinstance(msg, dict) and msg.get('action') == 'confirm':
                                    break
                            except Empty:
                                pass
                        else:
                            self.after(0, lambda: self._msg("⏰","超时","请重试"))
                            self.after(0, lambda: self._reset()); await browser.close(); return

                        self.after(0, lambda: self.progress.set(0.7))
                        self.after(0, lambda: self._msg("📤","正在提取 Cookie...",""))
                        cookies = await ctx.cookies()
                        ck_str = '; '.join(f"{c['name']}={c['value']}" for c in cookies)
                        if not ck_str:
                            self.after(0, lambda: self._msg("❌","未获取到Cookie","请在Chrome中确认已登录"))
                            self.after(0, lambda: self._reset()); await browser.close(); return

                        token = ""
                        # 尝试从 SCAN_QUEUE 获取 token
                        try: token = SCAN_QUEUE.get_nowait().get('token','')
                        except: pass

                        resp = requests.post(f"{API_URL}/accounts", json={
                            'platform':info[1], 'platformUserId':f"scan_{int(time.time())}",
                            'nickname':info[0], 'cookies':ck_str,
                        }, headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'}, timeout=30)
                        self.after(0, lambda: self.progress.set(1.0))
                        if resp.json().get('code')==0:
                            self.after(0, lambda: self._msg("✅",f"{info[0]}绑定成功！",f"Cookie数:{len(cookies)}\n刷新网站即可看到"))
                        else:
                            self.after(0, lambda: self._msg("❌","上传失败",resp.json().get('message','')))
                        await browser.close()
                asyncio.run(_run())
            except Exception as e:
                self.after(0, lambda: self._msg("❌","出错",str(e)[:200]))
            finally:
                self.after(0, lambda: self._reset())
        threading.Thread(target=worker, daemon=True).start()

    def _show_confirm(self):
        for w in self.msg_frame.winfo_children(): w.destroy()
        self.msg_title = ctk.CTkLabel(self.msg_frame, text="📱 请在 Chrome 窗口扫码", font=("Microsoft YaHei",13,"bold"), text_color="#333")
        self.msg_title.pack(pady=(12,4))
        self.msg_text = ctk.CTkLabel(self.msg_frame, text="扫码成功后点击下方按钮", font=("Microsoft YaHei",11), text_color="#666")
        self.msg_text.pack()
        row = ctk.CTkFrame(self.msg_frame, fg_color="transparent"); row.pack(pady=(6,8))
        ctk.CTkButton(row, text="✅ 已完成登录", font=("Microsoft YaHei",12,"bold"), fg_color="#4caf50",
                      hover_color="#388e3c", height=36, width=180,
                      command=lambda: SCAN_QUEUE.put({'action':'confirm'})).pack(side="left",padx=4)
        ctk.CTkButton(row, text="取消", font=("Microsoft YaHei",11), fg_color="#999",
                      hover_color="#777", height=36, width=70,
                      command=lambda: [self._reset()]).pack(side="left",padx=4)

    def _msg(self, icon, title, text):
        for w in self.msg_frame.winfo_children(): w.destroy()
        self.msg_title = ctk.CTkLabel(self.msg_frame, text=f"{icon} {title}", font=("Microsoft YaHei",13,"bold"), text_color="#333")
        self.msg_title.pack(pady=(20,4))
        if text:
            self.msg_text = ctk.CTkLabel(self.msg_frame, text=text, font=("Microsoft YaHei",11), text_color="#666", wraplength=400)
            self.msg_text.pack()

    def _reset(self):
        self.scanning = False
        for b in self.plat_btns.values(): b.configure(state="normal")
        self.progress.set(0)
        self._msg("👋","欢迎使用桌面伴侣","点击按钮打开网站，登录后选择平台即可")

# ── 启动 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    # 后台启动 Flask
    threading.Thread(target=start_flask, daemon=True).start()
    # 启动桌面 UI
    app = MatrixFlowApp()
    app.mainloop()
