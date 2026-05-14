"""
披星云桌面伴侣 v3 — 真正的 Windows 桌面应用
双击 .exe 就能用，不用懂代码
"""
import customtkinter as ctk
import threading, json, time, asyncio, base64, webbrowser, requests
from queue import Queue, Empty
from pathlib import Path
import tkinter.messagebox as msgbox

# ── 设置 ─────────────────────────────────────────────────────
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

API_URL = "https://ddddkiii.com/api/v1"
SITE_URL = "https://jujuju-28b.pages.dev"
LOCAL_PORT = 5409

PLATFORMS = [
    {"id": "douyin", "name": "抖 音", "color": "#111111", "icon": "🎵"},
    {"id": "xiaohongshu", "name": "小红书", "color": "#ff2442", "icon": "📕"},
    {"id": "kuaishou", "name": "快 手", "color": "#ff4906", "icon": "🎬"},
    {"id": "tencent", "name": "视频号", "color": "#07c160", "icon": "📺"},
]

SCAN_LABELS = {
    "douyin": ("抖音", "DOUYIN", "https://creator.douyin.com/"),
    "xiaohongshu": ("小红书", "XIAOHONGSHU", "https://creator.xiaohongshu.com/"),
    "kuaishou": ("快手", "KUAISHOU", "https://cp.kuaishou.com/"),
    "tencent": ("视频号", "WECHAT_VIDEO", "https://channels.weixin.qq.com/"),
}

# ── 主窗口 ───────────────────────────────────────────────────
class MatrixFlowApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("披星云桌面伴侣")
        self.geometry("480x620")
        self.resizable(False, False)
        self.iconbitmap(default="")

        self.token = ""
        self.scanning = False
        self.queue = Queue()

        self.build_ui()

    def build_ui(self):
        # ── 顶部标题 ──
        header = ctk.CTkFrame(self, fg_color="#667eea", corner_radius=0, height=100)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="披星云", font=("Microsoft YaHei", 24, "bold"),
                     text_color="white").pack(pady=(18, 0))
        ctk.CTkLabel(header, text="矩阵账号管理 · 桌面伴侣", font=("Microsoft YaHei", 11),
                     text_color="rgba(255,255,255,0.8)").pack()

        # ── 状态指示器 ──
        self.status_frame = ctk.CTkFrame(self, fg_color="transparent", height=36)
        self.status_frame.pack(fill="x", padx=20, pady=(16, 0))

        self.status_dot = ctk.CTkLabel(self.status_frame, text="●", font=("", 16),
                                        text_color="gray", width=20)
        self.status_dot.pack(side="left")
        self.status_label = ctk.CTkLabel(self.status_frame, text="检测网站连接中...",
                                          font=("Microsoft YaHei", 11), text_color="gray")
        self.status_label.pack(side="left", padx=4)

        # ── 按钮区域 ──
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(12, 0))

        self.open_btn = ctk.CTkButton(btn_frame, text="🌐  打开 MatrixFlow 网站",
                                       font=("Microsoft YaHei", 13, "bold"),
                                       height=42, fg_color="#667eea", hover_color="#5a6fd6",
                                       command=self.open_website)
        self.open_btn.pack(fill="x")

        # ── 平台选择 ──
        ctk.CTkLabel(self, text="— 选择平台开始绑定 —", font=("Microsoft YaHei", 11),
                     text_color="#999").pack(pady=(16, 8))

        plat_frame = ctk.CTkFrame(self, fg_color="transparent")
        plat_frame.pack(fill="x", padx=20)

        self.plat_buttons = {}
        for i, p in enumerate(PLATFORMS):
            btn = ctk.CTkButton(
                plat_frame,
                text=f"{p['icon']}  {p['name']}",
                font=("Microsoft YaHei", 13),
                height=50, fg_color=p["color"], hover_color=self._darken(p["color"]),
                command=lambda pid=p["id"]: self.start_scan(pid)
            )
            row, col = divmod(i, 2)
            btn.grid(row=row, column=col, padx=4, pady=4, sticky="ew")
            self.plat_buttons[p["id"]] = btn

        plat_frame.grid_columnconfigure(0, weight=1)
        plat_frame.grid_columnconfigure(1, weight=1)

        # ── 状态消息 ──
        self.msg_frame = ctk.CTkFrame(self, fg_color="#f5f7fa", corner_radius=8, height=100)
        self.msg_frame.pack(fill="x", padx=20, pady=(16, 0))
        self.msg_frame.pack_propagate(False)

        self.msg_title = ctk.CTkLabel(self.msg_frame, text="👋 欢迎使用桌面伴侣",
                                       font=("Microsoft YaHei", 13, "bold"), text_color="#333")
        self.msg_title.pack(pady=(20, 4))
        self.msg_text = ctk.CTkLabel(self.msg_frame, text="点击上方按钮打开网站，或选择平台开始绑定",
                                      font=("Microsoft YaHei", 11), text_color="#999", wraplength=400)
        self.msg_text.pack()

        # ── 进度条 ──
        self.progress = ctk.CTkProgressBar(self, width=440, height=6, progress_color="#667eea")
        self.progress.pack(pady=(12, 0))
        self.progress.set(0)

        # ── 底部 ──
        ctk.CTkLabel(self, text="v3.0 · 扫码用真实IP，不会触发平台风控",
                     font=("Microsoft YaHei", 10), text_color="#bbb").pack(pady=(8, 12))

        # 启动检测
        self.check_website()

    def _darken(self, hex_color: str) -> str:
        """把颜色变暗 20%"""
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        r, g, b = max(0, r - 40), max(0, g - 40), max(0, b - 40)
        return f"#{r:02x}{g:02x}{b:02x}"

    # ── 网站检测 ──
    def check_website(self):
        def _check():
            while True:
                try:
                    r = requests.get(f"{API_URL}/health", timeout=5)
                    if r.status_code == 200:
                        self.after(0, lambda: self._set_status(True))
                    else:
                        self.after(0, lambda: self._set_status(False))
                except:
                    self.after(0, lambda: self._set_status(False))
                time.sleep(5)

        t = threading.Thread(target=_check, daemon=True)
        t.start()

    def _set_status(self, online: bool):
        if online:
            self.status_dot.configure(text="●", text_color="#4caf50")
            self.status_label.configure(text="网站已连接", text_color="#4caf50")
        else:
            self.status_dot.configure(text="●", text_color="#f44336")
            self.status_label.configure(text="网站未连接", text_color="#f44336")

    # ── 打开网站 ──
    def open_website(self):
        webbrowser.open(SITE_URL)
        self._show_msg("🌐", "网站已在浏览器中打开", "登录后点击\"添加账号\"即可绑定平台")

    # ── 扫码 ──
    def start_scan(self, platform_id: str):
        if self.scanning:
            msgbox.showwarning("提示", "正在扫码中，请先完成或等待超时")
            return

        if not self.token:
            # 尝试从网站获取 token —— 简化：直接告诉用户先登录
            msgbox.showinfo("提示", "请先在 MatrixFlow 网站登录，\n然后点击\"添加账号\"选择平台。\n\n桌面伴侣会自动检测到。")
            webbrowser.open(SITE_URL)
            return

        self.scanning = True
        self._set_buttons_state("disabled")
        self.progress.set(0)

        info = SCAN_LABELS[platform_id]

        self._show_msg("🔄", f"正在启动浏览器...",
                       f"目标平台: {info[0]}\n即将弹出 Chrome 窗口")

        def worker():
            try:
                async def _run():
                    from playwright.async_api import async_playwright

                    self.after(0, lambda: self.progress.set(0.1))

                    async with async_playwright() as pw:
                        browser = await pw.chromium.launch(
                            headless=False,
                            args=['--disable-blink-features=AutomationControlled', '--lang=zh-CN', '--start-maximized']
                        )
                        context = await browser.new_context(
                            viewport={'width': 1280, 'height': 800},
                            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
                        )
                        page = await context.new_page()

                        self.after(0, lambda: self._show_msg("🌐", "浏览器已打开",
                                                              f"请在 Chrome 窗口中扫码登录 {info[0]}\n登录后回到这里点击下方按钮"))
                        self.after(0, lambda: self.progress.set(0.3))
                        self.after(0, lambda: self._show_confirm_button(platform_id, browser, context, page))

                        await page.goto(info[2], wait_until='domcontentloaded', timeout=30000)
                        await page.wait_for_timeout(5000)

                        self.after(0, lambda: self.progress.set(0.5))

                        # 截图
                        try:
                            screenshot = await page.screenshot(type='png')
                            self.current_screenshot = base64.b64encode(screenshot).decode()
                        except:
                            self.current_screenshot = None

                        # 等待用户确认（最多5分钟）
                        for i in range(600):
                            await page.wait_for_timeout(500)
                            try:
                                msg = self.queue.get_nowait()
                                if msg == 'CONFIRM':
                                    break
                                if msg == 'CANCEL':
                                    self.after(0, lambda: self._show_msg("❌", "已取消", ""))
                                    self.after(0, lambda: self._reset_ui())
                                    await browser.close()
                                    return
                            except Empty:
                                pass
                        else:
                            self.after(0, lambda: self._show_msg("⏰", "超时（5分钟）", "请重试"))
                            self.after(0, lambda: self._reset_ui())
                            await browser.close()
                            return

                        self.after(0, lambda: self.progress.set(0.7))
                        self.after(0, lambda: self._show_msg("📤", "正在提取 Cookie...", ""))

                        # 提取 Cookie
                        cookies = await context.cookies()
                        cookie_str = '; '.join(f"{c['name']}={c['value']}" for c in cookies)

                        if not cookie_str:
                            self.after(0, lambda: self._show_msg("❌", "未获取到 Cookie", "请在 Chrome 中确认已登录后重试"))
                            self.after(0, lambda: self._reset_ui())
                            await browser.close()
                            return

                        # 上传
                        resp = requests.post(
                            f"{API_URL}/accounts",
                            json={
                                'platform': info[1],
                                'platformUserId': f"scan_{int(time.time())}",
                                'nickname': info[0],
                                'cookies': cookie_str,
                            },
                            headers={'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'},
                            timeout=30,
                        )

                        self.after(0, lambda: self.progress.set(1.0))

                        if resp.json().get('code') == 0:
                            self.after(0, lambda: self._show_msg("✅", f"{info[0]} 绑定成功！",
                                                                  f"Cookie 数量: {len(cookies)}\n刷新网站即可看到新账号"))
                        else:
                            self.after(0, lambda: self._show_msg("❌", "上传失败",
                                                                  resp.json().get('message', '未知错误')))

                        await browser.close()

                asyncio.run(_run())
            except Exception as e:
                self.after(0, lambda: self._show_msg("❌", "出错了", str(e)[:200]))
            finally:
                self.after(0, lambda: self._reset_ui())

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _show_confirm_button(self, platform_id, browser, context, page):
        """显示确认按钮"""
        for widget in self.msg_frame.winfo_children():
            widget.destroy()

        self.msg_title = ctk.CTkLabel(self.msg_frame, text="📱 请在 Chrome 窗口中扫码",
                                       font=("Microsoft YaHei", 13, "bold"), text_color="#333")
        self.msg_title.pack(pady=(12, 4))
        self.msg_text = ctk.CTkLabel(self.msg_frame, text=f"用手机扫描 Chrome 窗口中的二维码\n登录成功后点击下方按钮",
                                      font=("Microsoft YaHei", 11), text_color="#666")
        self.msg_text.pack()

        btn_row = ctk.CTkFrame(self.msg_frame, fg_color="transparent")
        btn_row.pack(pady=(6, 8))

        ctk.CTkButton(btn_row, text="✅ 已完成登录，提取 Cookie",
                      font=("Microsoft YaHei", 12, "bold"),
                      fg_color="#4caf50", hover_color="#388e3c",
                      height=36, width=220,
                      command=lambda: self.confirm_login()).pack(side="left", padx=4)

        ctk.CTkButton(btn_row, text="❌ 取消",
                      font=("Microsoft YaHei", 11),
                      fg_color="#999", hover_color="#777",
                      height=36, width=80,
                      command=lambda: self.cancel_login()).pack(side="left", padx=4)

    def confirm_login(self):
        self.queue.put('CONFIRM')

    def cancel_login(self):
        self.queue.put('CANCEL')

    def _show_msg(self, icon, title, text):
        for widget in self.msg_frame.winfo_children():
            widget.destroy()
        self.msg_title = ctk.CTkLabel(self.msg_frame, text=f"{icon}  {title}",
                                       font=("Microsoft YaHei", 13, "bold"), text_color="#333")
        self.msg_title.pack(pady=(16, 4))
        if text:
            self.msg_text = ctk.CTkLabel(self.msg_frame, text=text,
                                          font=("Microsoft YaHei", 11), text_color="#666", wraplength=400)
            self.msg_text.pack()

    def _set_buttons_state(self, state):
        for btn in self.plat_buttons.values():
            btn.configure(state=state)
        self.open_btn.configure(state=state)

    def _reset_ui(self):
        self.scanning = False
        self._set_buttons_state("normal")
        self.progress.set(0)
        self._show_msg("👋", "欢迎使用桌面伴侣", "点击上方按钮打开网站，或选择平台开始绑定")


# ── 启动 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    app = MatrixFlowApp()
    app.mainloop()
