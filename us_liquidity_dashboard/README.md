# US Liquidity Dashboard

美股流动性红黄绿灯看板，用来跟踪 **Fed资产负债表、TGA、RRP、银行准备金、NFCI、HY Spread、VIX、SPX/QQQ趋势**，并输出一个 0-100 的流动性评分和 SPX 短期走势判断。

> 用途：辅助判断美股风险环境和仓位节奏，不构成投资建议。

---

## 1. 功能

### 核心指标

- Fed Total Assets：美联储总资产
- TGA：美国财政部现金账户
- RRP：隔夜逆回购
- Bank Reserves：银行准备金
- SOFR - IORB：短端资金压力
- NFCI：芝加哥联储金融条件指数
- HY Spread：高收益债利差
- VIX：市场波动率
- SPX / QQQ / BTC：风险资产趋势确认

### 核心公式

```text
Net Liquidity = WALCL - WTREGEN - RRPONTSYD
```

即：

```text
净流动性 = 美联储总资产 - TGA - RRP
```

### 输出结果

- 🟢 Green：流动性/风险偏好偏多
- 🟡 Yellow：中性震荡，等待确认
- 🔴 Red：流动性/风险偏好偏空

并输出：

- Liquidity Score：0-100分
- SPX走势判断：Bullish / Neutral / Bearish
- 主要驱动原因
- Net Liquidity vs SPX 双轴图
- SPX 50MA / 200MA 趋势确认图
- 因子评分明细表

---

## 2. 安装

进入项目目录：

```bash
cd us_liquidity_dashboard
```

安装依赖：

```bash
pip install -r requirements.txt
```

如果 Windows 下 pip 不识别，用：

```bash
python -m pip install -r requirements.txt
```

---

## 3. 运行

```bash
streamlit run app.py
```

或：

```bash
python -m streamlit run app.py
```

浏览器会打开：

```text
http://localhost:8501
```

---

## 4. Windows 一键启动

双击：

```text
start.bat
```

这个脚本会自动安装依赖并启动看板。

---

## 5. 数据源

### FRED

使用 FRED 公开 CSV：

- WALCL
- WTREGEN
- RRPONTSYD
- RESBALNS
- SOFR
- IORB
- NFCI
- BAMLH0A0HYM2

### Yahoo Finance

通过 `yfinance` 获取：

- ^GSPC：SPX
- SPY
- QQQ
- ^VIX
- BTC-USD
- HYG
- TLT
- UUP

---

## 6. Demo Mode

如果 FRED 或 Yahoo Finance 暂时无法访问，程序会自动切换到 Demo Mode，用模拟数据保持页面可运行。

页面顶部会提示：

```text
当前为 Demo Mode
```

联网后刷新即可恢复真实数据。

---

## 7. 评分逻辑

模型不是机器学习黑箱，而是可解释的因子打分：

| 因子 | 方向 |
|---|---|
| 净流动性4周上升 | 加分 |
| 净流动性13周上升 | 加分 |
| 银行准备金上升 | 加分 |
| NFCI下降 | 加分 |
| HY Spread下降 | 加分 |
| SOFR-IORB下降 | 加分 |
| VIX下降或低位 | 加分 |
| SPX站上50MA/200MA | 加分 |
| QQQ站上50MA/200MA | 加分 |
| BTC站上50MA | 加分 |

### 分数区间

| 分数 | 状态 | 解读 |
|---:|---|---|
| 70-100 | 🟢 Green | 风险偏好偏多 |
| 45-70 | 🟡 Yellow | 中性震荡 |
| 0-45 | 🔴 Red | 防回撤 |

---

## 8. 后续可升级方向

可以继续加入：

- AAII散户情绪
- Put/Call Ratio
- MOVE指数
- PMI / ISM New Orders
- 铜金比
- BTC Dominance
- 美元指数 DXY
- 自动邮件/Telegram/微信提醒
- 每日定时生成市场日报

---

## 9. 风险提示

本项目只用于观察宏观流动性和风险资产环境。模型输出不等于投资建议，也不能保证预测准确。
