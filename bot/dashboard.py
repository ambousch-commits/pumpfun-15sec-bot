import csv,io,json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HTML='''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Pump.fun 15sec Bot</title><style>body{font-family:system-ui;background:#0b1020;color:#edf2ff;max-width:1200px;margin:auto;padding:24px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card{background:#121a2d;border:1px solid #283653;border-radius:14px;padding:16px}.muted{color:#8f9bb5}.good{color:#55d187}.bad{color:#ff6477}.status{font-weight:700}.warn{color:#ffd166}table{width:100%;border-collapse:collapse;margin-top:18px}th,td{padding:10px;border-bottom:1px solid #283653;text-align:left;font-size:13px}@media(max-width:800px){.grid{grid-template-columns:repeat(2,1fr)}table{min-width:850px;display:block;overflow:auto}}</style></head><body><h1>Pump.fun 15sec Bot</h1><p class="muted">Pump.fun only · $1,200–$2,500 liquidity · 0.05 SOL · auto-sell at 15s · PAPER</p><p><span id="status" class="status">Starting…</span> · <span id="detail" class="muted"></span></p><p><a href="/api/trades.csv">Export trades CSV</a> · <a href="/api/events.csv">Export events CSV</a></p><div class="grid" id="cards"></div><table><thead><tr><th>Token</th><th>Entry</th><th>Exit</th><th>P&L %</th><th>P&L SOL</th><th>Reason</th></tr></thead><tbody id="trades"></tbody></table><script>const f=(v,d=6)=>Number(v||0).toLocaleString(undefined,{maximumFractionDigits:d});async function r(){try{const x=await fetch('/api/stats',{cache:'no-store'});const s=await x.json();const st=document.getElementById('status');st.textContent='BOT '+String(s.status?.state||'unknown').toUpperCase();st.className='status '+(s.status?.state==='running'?'good':(s.status?.state==='error'?'bad':'warn'));document.getElementById('detail').textContent=s.status?.detail||'';const age=s.status?.updated_at?Math.max(0,Math.floor(Date.now()/1000-s.status.updated_at)):null;document.getElementById('detail').textContent+=(age!==null?' · heartbeat '+age+'s ago':'');const cards=[['Closed trades',s.trades],['Wins',s.wins],['Win rate',s.win_rate+'%'],['P&L SOL',f(s.pnl_sol)],['Avg P&L %',f(s.avg_pnl_pct,3)],['Open',s.open_trades],['Entry size','0.05 SOL'],['Hold','15 sec']];document.getElementById('cards').innerHTML=cards.map(c=>`<div class="card"><div class="muted">${c[0]}</div><h2>${c[1]}</h2></div>`).join('');document.getElementById('trades').innerHTML=(s.recent||[]).map(t=>`<tr><td>${t.symbol||''}</td><td>${new Date(t.entry_time*1000).toLocaleString()}</td><td>${t.exit_time?new Date(t.exit_time*1000).toLocaleString():'open'}</td><td class="${Number(t.pnl_pct)>=0?'good':'bad'}">${Number(t.pnl_pct||0).toFixed(3)}%</td><td class="${Number(t.pnl_sol)>=0?'good':'bad'}">${Number(t.pnl_sol||0).toFixed(6)}</td><td>${t.exit_reason||''}</td></tr>`).join('')}catch(e){document.getElementById('status').textContent='DASHBOARD ERROR';document.getElementById('status').className='status bad';}}r();setInterval(r,3000)</script></body></html>'''

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args): return
 def j(self,o):
  b=json.dumps(o).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
 def do_GET(self):
  p=urlparse(self.path).path
  db=self.server.db
  if p=='/':
   b=HTML.encode();self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(b);return
  if p=='/health':
   self.j({'ok':True,'status':db.get_status()});return
  if p=='/api/stats':
   c=db.conn; total=int(c.execute('SELECT COUNT(*) FROM trades').fetchone()[0]); closed=int(c.execute('SELECT COUNT(*) FROM trades WHERE exit_time IS NOT NULL').fetchone()[0]); open_n=total-closed; wins=int(c.execute('SELECT COUNT(*) FROM trades WHERE pnl_sol>0 AND exit_time IS NOT NULL').fetchone()[0]); pnl=float(c.execute('SELECT COALESCE(SUM(pnl_sol),0) FROM trades WHERE exit_time IS NOT NULL').fetchone()[0]); avg=float(c.execute('SELECT COALESCE(AVG(pnl_pct),0) FROM trades WHERE exit_time IS NOT NULL').fetchone()[0]); recent=[dict(r) for r in c.execute('SELECT symbol,entry_time,exit_time,pnl_pct,pnl_sol,exit_reason FROM trades ORDER BY entry_time DESC LIMIT 25').fetchall()]; self.j({'trades':closed,'wins':wins,'win_rate':round(wins/closed*100,2) if closed else 0,'pnl_sol':round(pnl,8),'avg_pnl_pct':round(avg,4),'open_trades':open_n,'recent':recent,'status':db.get_status()});return
  if p in ('/api/trades.csv','/api/events.csv'):
   if p.endswith('trades.csv'):
    rows=db.conn.execute('SELECT * FROM trades ORDER BY entry_time ASC').fetchall();name='pumpfun-15sec-trades.csv'
   else:
    rows=db.conn.execute('SELECT * FROM events ORDER BY ts ASC').fetchall();name='pumpfun-15sec-events.csv'
   out=io.StringIO();w=csv.writer(out);w.writerow(rows[0].keys() if rows else []);w.writerows([tuple(r) for r in rows]);b=out.getvalue().encode();self.send_response(200);self.send_header('Content-Type','text/csv');self.send_header('Content-Disposition',f'attachment; filename="{name}"');self.end_headers();self.wfile.write(b);return
  self.send_response(404);self.end_headers()

def serve(db,host='0.0.0.0',port=8080):
 s=ThreadingHTTPServer((host,port),Handler);s.db=db;s.serve_forever()
