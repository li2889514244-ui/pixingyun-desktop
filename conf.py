from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
XHS_SERVER = "http://127.0.0.1:11901"
LOCAL_CHROME_PATH = ""  # 让 Playwright 用自己的 Chromium，不碰用户个人 Chrome
LOCAL_CHROME_HEADLESS = False  # 有头模式：弹出浏览器窗口，用户直接看到二维码扫码
DEBUG_MODE = True
