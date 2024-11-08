import logging
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    CallbackQuery
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters
)

from config import Config


class SettingsManager:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.db = bot_instance.db
        self.config:Config = bot_instance.config

    async def handle_settings_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理设置相关的回调"""
        query = update.callback_query
        await query.answer()
        data = query.data
        
        try:
            if data == "risk_settings":
                await self.show_risk_settings(query.message)
            elif data == "auto_trade_settings":
                await self.show_auto_trade_settings(query.message)
            elif data == "notification_settings":
                await self.show_notification_settings(query.message)
            elif data == "api_settings":
                await self.show_api_settings(query.message)
            elif data.startswith("save_"):
                await self.handle_settings_save(query, data)
            else:
                await query.answer("功能开发中...")

        except Exception as e:
            logging.error(f"Error in settings callback: {e}")
            await query.answer("处理设置时发生错误")

    async def show_risk_settings(self, message):
        """显示风险管理设置"""
        keyboard = [
            [
                InlineKeyboardButton("最大持仓", callback_data="risk_position_limit"),
                InlineKeyboardButton("杠杆限制", callback_data="risk_leverage_limit")
            ],
            [
                InlineKeyboardButton("止损设置", callback_data="risk_stop_loss"),
                InlineKeyboardButton("风险系数", callback_data="risk_factor")
            ],
            [InlineKeyboardButton("返回", callback_data="settings")]
        ]
        
        text = (
            "⚠️ 风险管理设置\n\n"
            f"当前设置:\n"
            f"• 最大持仓: {self.config.trading.max_position_size} USDT\n"
            f"• 最大杠杆: {self.config.trading.max_leverage}X\n"
            f"• 启用动态止损: {'是' if self.config.trading.enable_dynamic_sl else '否'}\n"
            f"• 最大回撤限制: {self.config.trading.max_drawdown_percentage}%"
        )
        
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def show_auto_trade_settings(self, message):
        """显示自动交易设置"""
        keyboard = [
            [
                InlineKeyboardButton("开启自动交易", callback_data="auto_trade_on"),
                InlineKeyboardButton("关闭自动交易", callback_data="auto_trade_off")
            ],
            [
                InlineKeyboardButton("交易策略", callback_data="trade_strategy"),
                InlineKeyboardButton("订单设置", callback_data="order_settings")
            ],
            [InlineKeyboardButton("返回", callback_data="settings")]
        ]
        
        text = (
            "⚙️ 自动交易设置\n\n"
            f"当前状态:\n"
            f"• 自动交易: {'开启' if self.config.trading.auto_trade_enabled else '关闭'}\n"
            f"• 默认仓位: {self.config.trading.default_position_size} USDT\n"
            f"• 默认杠杆: {self.config.trading.default_leverage}X\n"
            f"• 每日最大交易次数: {self.config.trading.max_daily_trades}"
        )
        
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def show_notification_settings(self, message):
        """显示通知设置"""
        keyboard = [
            [
                InlineKeyboardButton("交易通知", callback_data="trade_notifications"),
                InlineKeyboardButton("风险预警", callback_data="risk_notifications")
            ],
            [
                InlineKeyboardButton("定时报告", callback_data="scheduled_reports"),
                InlineKeyboardButton("消息过滤", callback_data="message_filters")
            ],
            [InlineKeyboardButton("返回", callback_data="settings")]
        ]
        
        text = "🔔 通知设置\n\n选择要配置的通知类型:"
        
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def show_api_settings(self, message):
        """显示API设置"""
        keyboard = [
            [
                InlineKeyboardButton("Binance API", callback_data="binance_api"),
                InlineKeyboardButton("OKX API", callback_data="okx_api")
            ],
            [
                InlineKeyboardButton("测试网设置", callback_data="testnet_settings"),
                InlineKeyboardButton("检查连接", callback_data="check_connection")
            ],
            [InlineKeyboardButton("返回", callback_data="settings")]
        ]
        
        # 检查API配置状态
        binance_status = "✅" if self.config.exchange.binance_api_key else "❌"
        okx_status = "✅" if self.config.exchange.okx_api_key else "❌"
        
        text = (
            "🔑 API 设置\n\n"
            f"当前状态:\n"
            f"• Binance API: {binance_status}\n"
            f"• OKX API: {okx_status}\n"
            f"• 运行环境: {'测试网' if self.config.trading.use_testnet else '主网'}"
        )
        
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def handle_settings_save(self, query: CallbackQuery, data: str):
        """处理设置保存"""
        setting_type = data.replace("save_", "")
        try:
            # 处理不同类型的设置保存
            if setting_type == "risk":
                await self._save_risk_settings(query)
            elif setting_type == "auto_trade":
                await self._save_auto_trade_settings(query)
            elif setting_type == "notification":
                await self._save_notification_settings(query)
            elif setting_type == "api":
                await self._save_api_settings(query)
                
            await query.answer("设置已保存")
            
        except Exception as e:
            logging.error(f"Error saving settings: {e}")
            await query.answer("保存设置时发生错误")
            
            
            

class StatisticsManager:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.db = bot_instance.db
        
    async def handle_stats_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理统计相关的回调"""
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data == "detailed_stats":
                await self.show_detailed_stats(query.message)
            elif query.data == "export_stats":
                await self.export_statistics(query.message)
            else:
                await query.answer("未知操作")
                
        except Exception as e:
            logging.error(f"Error in stats callback: {e}")
            await query.answer("处理统计数据时发生错误")

    async def show_detailed_stats(self, message):
        """显示详细统计"""
        try:
            stats = await self.bot.generate_statistics()
            trades = self.db.get_recent_trades(30)  # 获取最近30天的交易
            
            text = (
                "📊 详细统计分析\n\n"
                f"🔸 交易统计\n"
                f"总交易次数: {stats['total_trades']}\n"
                f"成功交易: {stats['winning_trades']}\n"
                f"失败交易: {stats['losing_trades']}\n"
                f"胜率: {stats['win_rate']:.1f}%\n\n"
                
                f"🔸 收益分析\n"
                f"总收益: {stats.get('total_pnl', 0):.2f} USDT\n"
                f"平均收益: {stats.get('avg_pnl', 0):.2f} USDT\n"
                f"最大单笔盈利: {stats.get('max_profit', 0):.2f} USDT\n"
                f"最大单笔亏损: {stats.get('max_loss', 0):.2f} USDT\n\n"
                
                f"🔸 风险指标\n"
                f"资金回撤: {stats.get('max_drawdown', 0):.2f}%\n"
                f"夏普比率: {stats.get('sharpe_ratio', 0):.2f}\n"
                f"收益风险比: {stats.get('profit_factor', 0):.2f}\n"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("导出数据", callback_data="export_stats"),
                    InlineKeyboardButton("返回", callback_data="stats")
                ]
            ]
            
            await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            
        except Exception as e:
            logging.error(f"Error showing detailed stats: {e}")
            await message.edit_text("生成详细统计时发生错误")

    async def export_statistics(self, message):
        """导出统计数据"""
        try:
            # 生成CSV文件
            trades = self.db.get_recent_trades(30)
            if not trades:
                await message.edit_text("没有可导出的交易数据")
                return
                
            csv_data = "日期,交易对,方向,入场价,出场价,数量,盈亏\n"
            for trade in trades:
                csv_data += (
                    f"{trade['close_time']},{trade['symbol']},"
                    f"{trade['side']},{trade['entry_price']},"
                    f"{trade['exit_price']},{trade['size']},"
                    f"{trade['pnl']}\n"
                )
                
            # 发送CSV文件
            await message.reply_document(
                document=csv_data.encode(),
                filename="trading_statistics.csv",
                caption="交易统计数据导出"
            )
            
            await message.edit_text(
                "统计数据已导出",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("返回", callback_data="stats")
                ]])
            )
            
        except Exception as e:
            logging.error(f"Error exporting stats: {e}")
            await message.edit_text("导出统计数据时发生错误")
            
            
            
            
