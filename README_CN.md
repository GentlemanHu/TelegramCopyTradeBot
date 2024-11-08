# 🤖 TelegramCopyTradeBot

[English](README.md) | [中文](README_CN.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-Latest-blue.svg)](https://core.telegram.org/bots/api)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Maintainability](https://api.codeclimate.com/v1/badges/your-maintainability-key/maintainability)](https://codeclimate.com/github/GentlemanHu/TelegramCopyTradeBot/maintainability)
[![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/GentlemanHu/TelegramCopyTradeBot/issues)

基于 Telegram 的智能加密货币跟单交易机器人，支持多交易所操作、GPT 信号分析、自动执行交易等功能。

## ✨ 主要特性

- 🔄 多交易所支持 (币安、OKX)
- 📱 Telegram 机器人管理界面
- 🤖 GPT 驱动的信号分析
- 📊 自动监控交易信号
- 💰 智能交易执行
- 📈 动态止损和多级止盈
- ⚠️ 实时风险监控
- 📊 全面的交易统计

## 🚀 快速开始

### 环境要求

```bash
Python 3.9+
pip
Git
```

### 安装步骤

1. 克隆项目
```bash
git clone https://github.com/GentlemanHu/TelegramCopyTradeBot.git
cd TelegramCopyTradeBot
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
创建 `.env` 文件并填入以下配置：

```env
# Telegram 配置
TELEGRAM_TOKEN=你的机器人token
API_ID=你的API_ID
API_HASH=你的API_HASH
OWNER_ID=你的用户ID
PHONE_NUMBER=你的手机号
SESSION_NAME=my_session

# OpenAI 配置
OPENAI_API_KEY=你的OpenAI密钥
OPENAI_API_BASE_URL=你的OpenAI接口地址

# 交易所配置 - 主网
BINANCE_API_KEY=币安API密钥
BINANCE_API_SECRET=币安API密钥
OKX_API_KEY=OKX API密钥
OKX_API_SECRET=OKX API密钥
OKX_PASSPHRASE=OKX密码短语

# 交易所配置 - 测试网
BINANCE_TESTNET_API_KEY=币安测试网密钥
BINANCE_TESTNET_API_SECRET=币安测试网密钥
OKX_TESTNET_API_KEY=OKX测试网密钥
OKX_TESTNET_API_SECRET=OKX测试网密钥
OKX_TESTNET_PASSPHRASE=OKX测试网密码短语
```

### 启动机器人
```bash
python main.py
```

## 📱 命令列表

- `/start` - 初始化机器人
- `/help` - 显示帮助信息
- `/stats` - 查看交易统计
- `/balance` - 查看账户余额
- `/positions` - 查看当前持仓
- `/channels` - 管理监控频道
- `/settings` - 机器人设置

## 🔧 项目结构

```
TelegramCopyTradeBot/
├── main.py                # 主程序入口
├── config.py             # 配置管理
├── database.py           # 数据库操作
├── models.py             # 数据模型
├── trading_logic.py      # 交易逻辑
├── exchange_execution.py # 交易执行
├── message_processor.py  # 消息处理
├── channel_management.py # 频道管理
├── settings.py          # 设置管理
└── button_texts.py      # UI文本
```

## 💡 功能特色

### GPT 信号分析
- [x] 智能识别交易信号
- [ ] 风险评估和分析
- [ ] 自动生成交易建议

### 多级止盈系统
- [x] 支持多个止盈目标
- [ ] 自动按比例平仓
- [ ] 动态调整止盈位置

### 风险控制系统
- [ ] 实时监控持仓风险
- [ ] 自动风险预警
- [ ] 超限自动平仓

## 🤝 参与贡献

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

## 📜 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🎁 支持项目

<div align="center">

### 您的支持是项目发展的动力
  
<details>
<summary>点击展开赞赏方式 ❤️</summary>

<table>
  <tr>
    <th>数字货币</th>
    <th>钱包地址</th>
  </tr>
  <tr>
    <td><img src="https://img.shields.io/badge/比特币-000000?style=flat&logo=bitcoin&logoColor=white"/> BTC</td>
    <td><code>bc1p6qkthl9jqqgle7xh2savggcfz284953lw8xnyj4z67wswse0runscdyta5</code></td>
  </tr>
  <tr>
    <td><img src="https://img.shields.io/badge/泰达币-50AF95?style=flat&logo=tether&logoColor=white"/> USDT (TRC20)</td>
    <td><code>TY1A9McJd6wz1ZgfVHmLEoQGFJX27WSNoN</code></td>
  </tr>
  <tr>
    <td><img src="https://img.shields.io/badge/以太坊-3C3C3D?style=flat&logo=ethereum&logoColor=white"/> ETH</td>
    <td><code>0x5aa791a5fe03f823275d7240ebe887d35fdf0f3b</code></td>
  </tr>
</table>

</details>
</div>

---

⭐ 如果这个项目对你有帮助，欢迎点个星！
