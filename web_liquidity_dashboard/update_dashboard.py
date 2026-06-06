from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from data_fetch import fred, market, last, change, trend

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'us-liquidity' / 'index.html'


def card(k, v, n=''):
    return f"<div class='card'><b>{k}</b><div class='big'>{v}</div><small>{n}</small></div>"


def main():
    walcl, d1 = fred('WALCL', 8500000)
    tga, d2 = fred('WTREGEN', 650000)
    rrp, d3 = fred('RRPONTSYD', 1800)
    nfci, d4 = fred('NFCI', -0.25)
    sofr, d5 = fred('SOFR', 5.2)
    iorb, d6 = fred('IORB', 5.4)
    spy, m1 = market('SPY', 520)
    qqq, m2 = market('QQQ', 450)
    vix, m3 = market('^VIX', 18)
    btc, m4 = market('BTC-USD', 65000)

    liq = pd.concat({'WALCL': walcl, 'TGA': tga, 'RRP': rrp * 1000}, axis=1).dropna()
    liq['NET'] = liq['WALCL'] - liq['TGA'] - liq['RRP']
    net = liq['NET']
    net4, net13 = change(net, 4), change(net, 13)
    spy_s, spy_p, spy_ma = trend(spy)
    qqq_s, qqq_p, qqq_ma = trend(qqq)
    btc_s, btc_p, btc_ma = trend(btc)
    vix_p = last(vix.Close)
    nfci_p, nfci4 = last(nfci), change(nfci, 4)
    spread = last(sofr) - last(iorb)

    score = 50
    reasons = []
    checks = [(net4 > 0, 15, '净流动性4周上升', '净流动性4周下降'), (net13 > 0, 10, '净流动性13周改善', '净流动性13周走弱'), (spy_p >= spy_ma, 10, 'SPY强于50日线', 'SPY弱于50日线'), (qqq_p >= qqq_ma, 10, 'QQQ强于50日线', 'QQQ弱于50日线'), (nfci4 < 0, 10, 'NFCI下降', 'NFCI上升'), (btc_p >= btc_ma, 5, 'BTC强于50日线', 'BTC弱于50日线')]
    for ok, pts, good, bad in checks:
        score += pts if ok else -pts
        reasons.append(good if ok else bad)
    if vix_p < 20:
        score += 5; reasons.append('VIX低于20')
    elif vix_p > 30:
        score -= 15; reasons.append('VIX高于30')
    else:
        score -= 5; reasons.append('VIX高于20')
    if spread < .05:
        score += 5; reasons.append('SOFR-IORB压力不明显')
    elif spread > .15:
        score -= 10; reasons.append('SOFR-IORB扩大')
    score = int(max(0, min(100, score)))
    light, bias, color = ('🟢','Bullish / 偏多','#16a34a') if score >= 70 else (('🟡','Neutral / 中性','#f59e0b') if score >= 40 else ('🔴','Bearish / 偏空','#dc2626'))

    fig = make_subplots(specs=[[{'secondary_y': True}]])
    fig.add_trace(go.Scatter(x=net.index, y=net/1000000, name='Net Liquidity, $tn'), secondary_y=False)
    fig.add_trace(go.Scatter(x=spy.index, y=spy.Close, name='SPY'), secondary_y=True)
    fig.update_layout(template='plotly_white', height=540, title='Net Liquidity vs SPY')
    chart = fig.to_html(full_html=False, include_plotlyjs='cdn')
    mode = 'Demo Mode' if any([d1,d2,d3,d4,d5,d6,m1,m2,m3,m4]) else 'Live Mode'
    cards = ''.join([card('综合评分', f'{score}/100', bias), card('红黄绿灯', light, '70以上偏多；40-70中性；40以下偏空'), card('净流动性4周变化', f'{net4/1000:,.0f} 十亿美元'), card('SPY趋势', spy_s, f'{spy_p:.2f} / 50MA {spy_ma:.2f}'), card('QQQ趋势', qqq_s, f'{qqq_p:.2f} / 50MA {qqq_ma:.2f}'), card('VIX', f'{vix_p:.2f}'), card('NFCI', f'{nfci_p:.2f}', f'4周变化 {nfci4:.2f}'), card('BTC趋势', btc_s, f'{btc_p:,.0f} / 50MA {btc_ma:,.0f}')])
    lis = ''.join(f'<li>{r}</li>' for r in reasons)
    gen = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    css = "body{margin:0;background:#f5f7fb;font-family:Arial,'Microsoft YaHei',sans-serif;color:#111827}.wrap{max-width:1280px;margin:auto;padding:28px}.hero{background:linear-gradient(135deg,#0f172a,#1e3a8a);color:white;padding:28px;border-radius:22px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-top:18px}.card,.panel{background:white;border-radius:18px;padding:18px;box-shadow:0 10px 28px #0001}.big{font-size:28px;font-weight:800;margin:8px 0}.panel{margin-top:18px}.tag{display:inline-block;background:#e2e8f0;color:#0f172a;border-radius:999px;padding:6px 10px;margin-right:8px;margin-top:10px}"
    html = f"<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta http-equiv='refresh' content='1800'><title>美股流动性看板</title><style>{css}</style></head><body><div class='wrap'><div class='hero'><h1>美股流动性看板</h1><p>网页自动更新：GitHub Actions定时生成；浏览器每30分钟刷新。</p><span class='tag'>{gen}</span><span class='tag'>{mode}</span></div><div class='grid'>{cards}</div><div class='panel' style='border-left:8px solid {color}'><h2>SPX/SPY 未来1-4周倾向：{bias}</h2><ul>{lis}</ul></div><div class='panel'>{chart}</div><p>净流动性 = WALCL - WTREGEN - RRPONTSYD。仅用于趋势监控。</p></div></body></html>"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding='utf-8')
    print('wrote', OUT)

if __name__ == '__main__':
    main()
