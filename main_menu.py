from telegram import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update
)
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import logging
from typing import Dict, Any

from config import Config

class MainMenuManager:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.db = bot_instance.db
        self.config:Config = bot_instance.config
        self.exchange_manager = bot_instance.exchange_manager

    @property
    def main_menu_keyboard(self):
        """创建主菜单键盘"""
        return ReplyKeyboardMarkup([
            [KeyboardButton("💰 交易"), KeyboardButton("📊 统计")],
            [KeyboardButton("📈 持仓"), KeyboardButton("⚙️ 设置")],
            [KeyboardButton("📺 频道"), KeyboardButton("❓ 帮助")]
        ], resize_keyboard=True)

    async def setup_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """设置主菜单"""
        if not self.bot.is_authorized(update.effective_user.id):
            await update.message.reply_text("未经授权的访问")
            return

        network_indicator = "🏮 测试网" if self.config.trading.use_testnet else "🔵 主网"
        await update.message.reply_text(
            f"{network_indicator} 交易机器人已启动\n\n"
            "请使用底部菜单选择功能:",
            reply_markup=self.main_menu_keyboard
        )

    async def handle_menu_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理菜单选择"""
        if not self.bot.is_authorized(update.effective_user.id):
            return

        message_text = update.message.text
        network_indicator = "🏮 测试网" if self.config.trading.use_testnet else "🔵 主网"

        try:
            if message_text == "💰 交易":
                keyboard = [
                    [
                        InlineKeyboardButton("创建订单", callback_data="create_order"),
                        InlineKeyboardButton("订单历史", callback_data="order_history")
                    ],
                    [
                        InlineKeyboardButton("活动订单", callback_data="active_orders"),
                        InlineKeyboardButton("风险设置", callback_data="risk_settings")
                    ]
                ]
                await update.message.reply_text(
                    f"{network_indicator} 交易管理\n\n"
                    "请选择操作:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

            elif message_text == "📊 统计":
                stats = await self.bot.generate_statistics()
                stats_text = (
                    f"{network_indicator} 交易统计\n\n"
                    f"📈 今日收益: {stats['daily_pnl']:.2f} USDT\n"
                    f"📊 本周收益: {stats['weekly_pnl']:.2f} USDT\n"
                    f"📈 本月收益: {stats['monthly_pnl']:.2f} USDT\n\n"
                    f"🎯 总交易次数: {stats['total_trades']}\n"
                    f"✅ 成功交易: {stats['winning_trades']}\n"
                    f"❌ 失败交易: {stats['losing_trades']}\n"
                    f"📊 胜率: {stats['win_rate']:.1f}%"
                )
                await update.message.reply_text(stats_text)

            elif message_text == "📈 持仓":
                keyboard = [
                    [
                        InlineKeyboardButton("查看持仓", callback_data="view_positions"),
                        InlineKeyboardButton("修改持仓", callback_data="modify_position")
                    ],
                    [
                        InlineKeyboardButton("一键平仓", callback_data="close_all_positions"),
                        InlineKeyboardButton("持仓分析", callback_data="position_analysis")
                    ]
                ]
                await update.message.reply_text(
                    f"{network_indicator} 持仓管理\n\n"
                    "请选择操作:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

            elif message_text == "⚙️ 设置":
                keyboard = [
                    [
                        InlineKeyboardButton("交易设置", callback_data="trade_settings"),
                        InlineKeyboardButton("API设置", callback_data="api_settings")
                    ],
                    [
                        InlineKeyboardButton("通知设置", callback_data="notification_settings"),
                        InlineKeyboardButton("其他设置", callback_data="other_settings")
                    ]
                ]
                await update.message.reply_text(
                    f"{network_indicator} 系统设置\n\n"
                    "请选择设置项:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

            elif message_text == "📺 频道":
                keyboard = [
                    [
                        InlineKeyboardButton("添加频道", callback_data="add_channel"),
                        InlineKeyboardButton("删除频道", callback_data="remove_channel")
                    ],
                    [
                        InlineKeyboardButton("频道列表", callback_data="list_channels"),
                        InlineKeyboardButton("编辑频道", callback_data="edit_channel")
                    ]
                ]
                await update.message.reply_text(
                    f"{network_indicator} 频道管理\n\n"
                    "请选择操作:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

            elif message_text == "❓ 帮助":
                help_text = (
                    f"{network_indicator} 帮助信息\n\n"
                    "🤖 基本功能:\n"
                    "• 💰 交易 - 管理交易订单\n"
                    "• 📊 统计 - 查看交易统计\n"
                    "• 📈 持仓 - 管理当前持仓\n"
                    "• ⚙️ 设置 - 系统设置\n"
                    "• 📺 频道 - 管理信号频道\n\n"
                    "📱 常用命令:\n"
                    "/start - 启动机器人\n"
                    "/stats - 查看统计\n"
                    "/balance - 查看余额\n"
                    "/help - 显示帮助"
                )
                await update.message.reply_text(help_text)

        except Exception as e:
            logging.error(f"Error handling menu selection: {e}")
            await update.message.reply_text("处理请求时发生错误")