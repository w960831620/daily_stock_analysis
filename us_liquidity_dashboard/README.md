# US Liquidity Dashboard

Streamlit 美股流动性看板，用于跟踪 FRED 与 Yahoo Finance 数据，计算 0-100 综合流动性评分，并输出红黄绿灯和未来 1-4 周 SPX/SPY 倾向。

## 安装方法

```bash
pip install -r requirements.txt
```

## 运行方法

```bash
streamlit run app.py
```

Windows 也可以双击 `start.bat`，脚本会自动安装依赖并启动看板。

## 功能说明

- Yahoo Finance 数据：`SPY`、`QQQ`、`^VIX`、`BTC-USD`
- FRED 数据：`WALCL`、`RRPONTSYD`、`SOFR`、`IORB`、`NFCI`
- 核心计算：`Net Liquidity = WALCL - RRPONTSYD`
- 0-100 综合流动性评分
- 红黄绿灯：
  - 70 以上：🟢 偏多
  - 40-70：🟡 中性
  - 40 以下：🔴 偏空
- SPY、QQQ、BTC 趋势判断
- VIX 状态判断
- Net Liquidity 与 SPY 双轴图
- 未来 1-4 周 SPX/SPY 倾向：Bullish / Neutral / Bearish，并展示原因

评分加分项包括：

- 净流动性 4 周上升
- SPY 高于 50MA
- QQQ 高于 50MA
- VIX 低于 20
- NFCI 下降
- SOFR-IORB 没有明显扩大

## Demo Mode

如果 FRED API、Yahoo Finance 或网络不可用，应用会自动进入 Demo Mode，使用模拟数据保持页面可启动和可演示，不会报错退出。

## Codex 云环境说明

Codex 云环境只负责验证应用可以安装、编译和启动，不作为长期公网托管服务。长期使用请部署到自己的服务器、Streamlit Community Cloud 或其他托管平台。
