// 披星云桌面伴侣 v1.1
const express = require('express');
const { chromium } = require('playwright');
const https = require('https');
const { exec } = require('child_process');

const PORT = 3456;
const API_HOSTS = ['ddddkiii.com', '8.134.218.39'];
let activeHost = API_HOSTS[0];

const app = express();
app.use(express.json());
app.use(express.static(__dirname));

const sessions = {};
let browser = null;

// ========== Tools ==========

function apiRequest(method, path, body, token) {
  return new Promise((resolve) => {
    const tryHost = (idx) => {
      if (idx >= API_HOSTS.length) return resolve(null);
      const host = API_HOSTS[idx];
      const url = new URL('https://' + host + '/api/v1' + path);
      const opts = {
        hostname: url.hostname, path: url.pathname + url.search, method,
        headers: { 'Content-Type': 'application/json', ...(token ? { 'Authorization': 'Bearer ' + token } : {}) },
        timeout: 10000,
      };
      const req = https.request(opts, (res) => {
        let d = '';
        res.on('data', c => d += c);
        res.on('end', () => {
          try { resolve(JSON.parse(d)); } catch(e) { tryHost(idx + 1); }
        });
      });
      req.on('error', () => tryHost(idx + 1));
      req.on('timeout', () => { req.destroy(); tryHost(idx + 1); });
      if (body) req.write(JSON.stringify(body));
      req.end();
    };
    tryHost(0);
  });
}

// ========== API ==========

app.post('/api/login', async (req, res) => {
  const { platform, token } = req.body;
  if (!platform) return res.status(400).json({ error: '请选择平台' });

  const sid = Math.random().toString(36).slice(2, 10);
  const platformConfig = {
    douyin: { name: '抖音', url: 'https://creator.douyin.com' },
    xiaohongshu: { name: '小红书', url: 'https://creator.xiaohongshu.com' },
    kuaishou: { name: '快手', url: 'https://cp.kuaishou.com' },
    bilibili: { name: 'B站', url: 'https://member.bilibili.com' },
    weibo: { name: '微博', url: 'https://weibo.com' },
  };
  const config = platformConfig[platform];
  if (!config) return res.status(400).json({ error: '不支持的平台' });

  sessions[sid] = { platform, status: 'launching', name: config.name };

  (async () => {
    try {
      if (!browser || !browser.isConnected()) {
        browser = await chromium.launch({ headless: false, args: ['--no-sandbox'] });
      }
      const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'zh-CN' });
      const page = await context.newPage();
      await page.goto(config.url, { waitUntil: 'networkidle', timeout: 30000 });
      sessions[sid] = { ...sessions[sid], status: 'scanning', page, context, token };
      console.log(`[${sid}] ${config.name} 登录页已打开`);
    } catch(e) {
      sessions[sid] = { ...sessions[sid], status: 'error', error: e.message };
    }
  })();

  res.json({ session_id: sid, status: 'launching', platform: config.name });
});

app.get('/api/login/status/:sid', async (req, res) => {
  const s = sessions[req.params.sid];
  if (!s) return res.json({ status: 'not_found' });
  if (s.status === 'error') return res.json({ status: 'error', error: s.error });
  if (s.status === 'done') return res.json({ status: 'done', account: s.account });
  
  if (s.page) {
    try {
      const cookies = await s.page.context().cookies();
      const meaningful = cookies.filter(c => c.name && c.value?.length > 5);
      if (meaningful.length >= 3) {
        const result = await apiRequest('POST', '/accounts', {
          platform: s.platform.toUpperCase(),
          platformUserId: s.name + '_' + Date.now().toString(36),
          nickname: s.name + '账号',
          cookies: JSON.stringify(meaningful),
        }, s.token);
        
        s.status = 'done';
        s.account = { platform: s.platform, name: s.name };
        if (s.page) { await s.page.close().catch(()=>{}); delete s.page; }
        if (s.context) { await s.context.close().catch(()=>{}); delete s.context; }
        return res.json({ status: 'done', account: s.account });
      }
    } catch(e) {}
  }
  res.json({ status: s.status, name: s.name });
});

app.get('/health', (req, res) => res.json({ status: 'ok' }));

// ========== Start ==========
app.listen(PORT, () => {
  console.log('\n披星云桌面伴侣已启动');
  console.log('浏览器打开 http://localhost:' + PORT + '\n');
  exec('start http://localhost:' + PORT);
});

process.on('SIGINT', async () => {
  if (browser) await browser.close().catch(()=>{});
  process.exit();
});
