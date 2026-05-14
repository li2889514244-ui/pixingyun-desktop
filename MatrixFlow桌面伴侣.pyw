"""
披星云桌面伴侣 v3.2 — 一键绑定，扫码即自动上传
"""
import customtkinter as ctk
import threading, json, time, asyncio, requests, webbrowser
from queue import Queue, Empty
from flask import Flask, request, jsonify

# ── 全局状态 ──
API_URL = "https://ddddkiii.com/api/v1"
SITE_URL = "https://jujuju-28b.pages.dev"
SCAN_Q = Queue()  # tkinter <-> Flask 通信

PLATFORM_INFO = {
    "douyin":       ("抖音",   "DOUYIN",        "https://creator.douyin.com/"),
    "xiaohongshu":  ("小红书", "XIAOHONGSHU",   "https://creator.xiaohongshu.com/"),
    "kuaishou":     ("快手",   "KUAISHOU",      "https://cp.kuaishou.com/"),
    "tencent":      ("视频号", "WECHAT_VIDEO",  "https://channels.weixin.qq.com/"),
}

PLATFORM_BTNS = [
    {"id":"douyin","name":"抖 音","color":"#111111","icon":"🎵"},
    {"id":"xiaohongshu","name":"小红书","color":"#ff2442","icon":"📕"},
    {"id":"kuaishou","name":"快 手","color":"#ff4906","icon":"🎬"},
    {"id":"tencent","name":"视频号","color":"#07c160","icon":"📺"},
]

# ── Flask 后台 ───────────────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route('/health')
def health():
    r = jsonify({'status':'ok','platforms':list(PLATFORM_INFO.keys())})
    r.headers['Access-Control-Allow-Origin'] = '*'
    return r

@flask_app.route('/api/scan-bind/start')
def scan_bind_start():
    platform = request.args.get('platform','douyin')
    token = request.args.get('token','')
    api_url = request.args.get('api_url', API_URL)
    if platform not in PLATFORM_INFO: return jsonify({'code':400}),400
    if not token: return jsonify({'code':400,'msg':'需要登录'}),400

    # 发送到 tkinter 主线程处理
    SCAN_Q.put({'action':'start','platform':platform,'token':token,'api_url':api_url})
    return jsonify({'code':0,'msg':'已发送到桌面伴侣'})

def flask_thread():
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
        self.current_token = ""
        self.build_ui()
        self._check_site()
        self._poll_queue()  # 轮询 Flask 发来的请求

    def build_ui(self):
        h = ctk.CTkFrame(self, fg_color="#667eea", corner_radius=0, height=90)
        h.pack(fill="x"); h.pack_propagate(False)
        ctk.CTkLabel(h, text="披星云", font=("Microsoft YaHei",24,"bold"), text_color="white").pack(pady=(16,0))
        ctk.CTkLabel(h, text="桌面伴侣 v3.2 · 自动联动", font=("Microsoft YaHei",10), text_color="#ccc").pack()

        sf = ctk.CTkFrame(self, fg_color="transparent", height=30)
        sf.pack(fill="x", padx=20, pady=(10,0))
        self.sdot = ctk.CTkLabel(sf, text="●", font=("",14), text_color="gray", width=16)
        self.sdot.pack(side="left")
        self.slbl = ctk.CTkLabel(sf, text="检测中...", font=("Microsoft YaHei",11), text_color="gray")
        self.slbl.pack(side="left", padx=4)

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(fill="x", padx=20, pady=(8,0))
        ctk.CTkButton(bf, text="🌐  打开 MatrixFlow 网站", font=("Microsoft YaHei",13,"bold"),
                      height=44, fg_color="#667eea", hover_color="#5a6fd6",
                      command=lambda: webbrowser.open(SITE_URL)).pack(fill="x")

        ctk.CTkLabel(self, text="或选择平台开始（需先在网站登录）", font=("Microsoft YaHei",10), text_color="#999").pack(pady=(12,4))
        pf = ctk.CTkFrame(self, fg_color="transparent"); pf.pack(fill="x", padx=20)
        self.pbtns = {}
        for i,p in enumerate(PLATFORM_BTNS):
            btn = ctk.CTkButton(pf, text=f"{p['icon']}  {p['name']}", font=("Microsoft YaHei",13),
                                height=48, fg_color=p["color"], hover_color=self._dk(p["color"]),
                                command=lambda pid=p["id"]: self._manual_scan(pid))
            r,c = divmod(i,2); btn.grid(row=r, column=c, padx=4, pady=4, sticky="ew")
            self.pbtns[p["id"]] = btn
        pf.grid_columnconfigure(0,weight=1); pf.grid_columnconfigure(1,weight=1)

        self.mf = ctk.CTkFrame(self, fg_color="#f5f7fa", corner_radius=8, height=140)
        self.mf.pack(fill="x", padx=20, pady=(12,0)); self.mf.pack_propagate(False)
        self.mt = ctk.CTkLabel(self.mf, text="👋 欢迎使用桌面伴侣", font=("Microsoft YaHei",13,"bold"), text_color="#333")
        self.mt.pack(pady=(28,4))
        self.mb = ctk.CTkLabel(self.mf, text="登录网站后点击\"添加账号\"，桌面伴侣会自动响应", font=("Microsoft YaHei",11), text_color="#999", wraplength=400)
        self.mb.pack()

        self.prog = ctk.CTkProgressBar(self, width=420, height=6, progress_color="#667eea")
        self.prog.pack(pady=(10,0)); self.prog.set(0)
        ctk.CTkLabel(self, text="扫码用真实IP，不触发平台风控", font=("Microsoft YaHei",9), text_color="#bbb").pack(pady=(8,10))

    def _dk(self,h):
        h = h.lstrip('#')
        if len(h) == 3: h = h[0]*2 + h[1]*2 + h[2]*2
        r,g,b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        return f"#{max(0,r-40):02x}{max(0,g-40):02x}{max(0,b-40):02x}"

    # ── 轮询 Flask 请求 ──
    def _poll_queue(self):
        """每 500ms 检查是否有来自网站的扫描请求"""
        try:
            msg = SCAN_Q.get_nowait()
            if isinstance(msg, dict) and msg.get('action') == 'start':
                self.current_token = msg.get('token','')
                self._do_scan(msg['platform'], msg['token'], msg.get('api_url', API_URL))
        except Empty:
            pass
        self.after(500, self._poll_queue)

    # ── 手动点击平台按钮（引导用户通过网站发起） ──
    def _manual_scan(self, pid):
        if self.scanning: return
        info = PLATFORM_INFO[pid]
        self._msg("ℹ️",f"请通过网站发起绑定",
                  f"1. 打开 MatrixFlow 网站并登录\n2. 点击\"添加账号\" → 选择{info[0]}\n3. 网站会自动触发桌面伴侣弹出 Chrome")

    # ── 网站检测 ──
    def _check_site(self):
        def _c():
            while True:
                try: ok = requests.get(f"{API_URL}/health",timeout=5).status_code==200
                except: ok = False
                self.after(0, lambda o=ok: (self.sdot.configure(text="●",text_color="#4caf50"), self.slbl.configure(text="网站已连接",text_color="#4caf50")) if o
                           else (self.sdot.configure(text="●",text_color="#f44336"), self.slbl.configure(text="网站未连接",text_color="#f44336")))
                time.sleep(5)
        threading.Thread(target=_c, daemon=True).start()

    # ── 执行扫码 ──
    def _do_scan(self, platform_id, token, api_url):
        if self.scanning: return
        self.scanning = True
        for b in self.pbtns.values(): b.configure(state="disabled")
        self.prog.set(0)
        info = PLATFORM_INFO[platform_id]
        self._msg("🔄","正在启动浏览器...",f"平台: {info[0]}")

        def worker():
            try:
                async def _run():
                    from playwright.async_api import async_playwright
                    self.after(0, lambda: self.prog.set(0.1))
                    async with async_playwright() as pw:
                        browser = await pw.chromium.launch(headless=False, args=[
                            '--disable-blink-features=AutomationControlled','--lang=zh-CN','--start-maximized'])
                        ctx = await browser.new_context(viewport={'width':1280,'height':800},
                            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36')
                        page = await ctx.new_page()
                        self.after(0, lambda: self.prog.set(0.3))
                        self.after(0, self._show_confirm_ui)
                        await page.goto(info[2], wait_until='domcontentloaded', timeout=30000)
                        await page.wait_for_timeout(5000)
                        self.after(0, lambda: self.prog.set(0.5))

                        # 等用户确认（最多5分钟）
                        for _ in range(600):
                            await page.wait_for_timeout(500)
                            try:
                                m = SCAN_Q.get_nowait()
                                if isinstance(m,dict) and m.get('action')=='confirm': break
                            except Empty: pass
                        else:
                            self.after(0, lambda: self._msg("⏰","超时","请重试"))
                            self.after(0, self._reset); await browser.close(); return

                        self.after(0, lambda: self.prog.set(0.7))
                        self.after(0, lambda: self._msg("📤","提取Cookie并上传...",""))
                        cookies = await ctx.cookies()
                        ck = '; '.join(f"{c['name']}={c['value']}" for c in cookies)
                        if not ck:
                            self.after(0, lambda: self._msg("❌","未获取到Cookie","请在Chrome中确认已登录后重试"))
                            self.after(0, self._reset); await browser.close(); return

                        # 上传到服务器
                        resp = requests.post(f"{api_url.rstrip('/')}/accounts", json={
                            'platform': info[1], 'platformUserId': f"scan_{int(time.time())}",
                            'nickname': info[0], 'cookies': ck,
                        }, headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'}, timeout=30)

                        self.after(0, lambda: self.prog.set(1.0))
                        data = resp.json()
                        if data.get('code') == 0:
                            self.after(0, lambda: self._msg("✅",f"{info[0]} 绑定成功！",f"Cookie数量: {len(cookies)}\n刷新网站即可查看账号"))
                        else:
                            self.after(0, lambda: self._msg("❌","上传失败", data.get('message','未知错误')))
                        await browser.close()
                asyncio.run(_run())
            except Exception as e:
                self.after(0, lambda: self._msg("❌","出错", str(e)[:200]))
            finally:
                self.after(0, self._reset)
        threading.Thread(target=worker, daemon=True).start()

    def _show_confirm_ui(self):
        for w in self.mf.winfo_children(): w.destroy()
        self.mt = ctk.CTkLabel(self.mf, text="📱 请在 Chrome 窗口扫码", font=("Microsoft YaHei",13,"bold"), text_color="#333")
        self.mt.pack(pady=(12,4))
        self.mb = ctk.CTkLabel(self.mf, text="扫码成功后点击下方按钮", font=("Microsoft YaHei",11), text_color="#666")
        self.mb.pack()
        row = ctk.CTkFrame(self.mf, fg_color="transparent"); row.pack(pady=(8,8))
        ctk.CTkButton(row, text="✅ 已完成登录，提取 Cookie", font=("Microsoft YaHei",12,"bold"),
                      fg_color="#4caf50", hover_color="#388e3c", height=36, width=200,
                      command=lambda: SCAN_Q.put({'action':'confirm'})).pack(side="left",padx=4)
        ctk.CTkButton(row, text="取消", font=("Microsoft YaHei",11), fg_color="#999",
                      hover_color="#777", height=36, width=70,
                      command=lambda: self._reset()).pack(side="left",padx=4)

    def _msg(self, icon, title, text):
        for w in self.mf.winfo_children(): w.destroy()
        self.mt = ctk.CTkLabel(self.mf, text=f"{icon}  {title}", font=("Microsoft YaHei",13,"bold"), text_color="#333")
        self.mt.pack(pady=(24,4))
        if text:
            self.mb = ctk.CTkLabel(self.mf, text=text, font=("Microsoft YaHei",11), text_color="#666", wraplength=400)
            self.mb.pack()

    def _reset(self):
        self.scanning = False
        for b in self.pbtns.values(): b.configure(state="normal")
        self.prog.set(0)
        self._msg("👋","欢迎使用桌面伴侣","登录网站后点击\"添加账号\"，桌面伴侣会自动响应")

# ── 启动 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=flask_thread, daemon=True).start()
    app = MatrixFlowApp()
    app.mainloop()
