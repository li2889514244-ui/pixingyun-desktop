// 披星云桌面伴侣 v1.2
const express = require('express');
const { chromium } = require('playwright');
const https = require('https');
const { exec } = require('child_process');

const PORT = 3456;
const API_HOST = 'ddddkiii.com';

const app = express();
app.use(express.json());

// === API 代理：Node.js 直连后端，绕过浏览器代理 ===
app.all('/api/proxy/*', async (req, res) => {
  const apiPath = req.path.replace('/api/proxy', '');
  const opts = {
    hostname: API_HOST, path: '/api/v1' + apiPath, method: req.method,
    headers: {
      'Content-Type': 'application/json',
      ...(req.headers.authorization ? { 'Authorization': req.headers.authorization } : {})
    },
    timeout: 15000,
    rejectUnauthorized: false,
  };
  const apiReq = https.request(opts, (apiRes) => {
    let d = '';
    apiRes.on('data', c => d += c);
    apiRes.on('end', () => {
      try { res.json(JSON.parse(d)); } catch(e) { res.status(502).json({ error: 'Invalid response' }); }
    });
  });
  apiReq.on('error', () => res.status(502).json({ error: 'API unreachable' }));
  apiReq.on('timeout', () => { apiReq.destroy(); res.status(504).json({ error: 'Timeout' }); });
  if (req.body && Object.keys(req.body).length > 0) apiReq.write(JSON.stringify(req.body));
  apiReq.end();
});

app.use(express.static(__dirname));

// === 浏览器自动化 ===
const sessions = {};
let browser = null;

app.post('/api/login', async (req, res) => {
  const { platform, token } = req.body;
  const sid = Math.random().toString(36).slice(2, 10);
  const configs = {
    douyin: { name: '抖音', url: 'https://creator.douyin.com' },
    xiaohongshu: { name: '小红书', url: 'https://creator.xiaohongshu.com' },
    kuaishou: { name: '快手', url: 'https://cp.kuaishou.com' },
    bilibili: { name: 'B站', url: 'https://member.bilibili.com' },
    weibo: { name: '微博', url: 'https://weibo.com' },
  };
  const cfg = configs[platform];
  if (!cfg) return res.status(400).json({ error: '不支持' });

  sessions[sid] = { platform, status: 'launching', name: cfg.name };
  res.json({ session_id: sid, status: 'launching', platform: cfg.name });

  try {
    if (!browser?.isConnected()) browser = await chromium.launch({ headless: false, args: ['--no-sandbox'] });
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'zh-CN' });
    const page = await ctx.newPage();
    await page.goto(cfg.url, { waitUntil: 'networkidle', timeout: 30000 });
    sessions[sid] = { ...sessions[sid], status: 'scanning', page, context: ctx, token };
  } catch(e) { sessions[sid].status = 'error'; sessions[sid].error = e.message; }
});

app.get('/api/login/status/:sid', async (req, res) => {
  const s = sessions[req.params.sid];
  if (!s) return res.json({ status: 'not_found' });
  if (s.status === 'done') return res.json({ status: 'done', account: s.account });
  if (s.status === 'error') return res.json({ status: 'error', error: s.error });
  if (s.page) {
    try {
      const cookies = await s.page.context().cookies();
      if (cookies.filter(c => c.name && c.value?.length > 5).length >= 3) {
        s.status = 'done'; s.account = { platform: s.platform, name: s.name };
        await s.page.close().catch(()=>{}); delete s.page;
        await s.context.close().catch(()=>{}); delete s.context;
        return res.json({ status: 'done', account: s.account });
      }
    } catch(e) {}
  }
  res.json({ status: s.status, name: s.name });
});

app.get('/health', (req, res) => res.json({ status: 'ok' }));

app.listen(PORT, () => {
  console.log('披星云桌面伴侣已启动 http://localhost:' + PORT);
  exec('start http://localhost:' + PORT);
});
process.on('SIGINT', async () => { if (browser) await browser.close().catch(()=>{}); process.exit(); });
