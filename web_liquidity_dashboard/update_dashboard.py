from pathlib import Path
from datetime import datetime
out = Path(__file__).resolve().parents[1] / 'docs' / 'us-liquidity' / 'index.html'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text('<html><body><h1>美股流动性看板</h1><p>updated '+datetime.utcnow().isoformat()+'</p></body></html>', encoding='utf-8')
print(out)
