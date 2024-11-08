# channel_management.py
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
import logging
from typing import Optional

from telethon import TelegramClient

# 定义会话状态
CHOOSING_CHANNEL_TYPE = 0
CHOOSING_ADD_METHOD = 1
WAITING_FOR_FORWARD = 2
WAITING_FOR_MANUAL_INPUT = 3
WAITING_FOR_PROMPT = 4
WAITING_FOR_FORWARD_CHANNEL = 5
SELECTING_CHANNEL = 6
EDITING_PROMPT = 7

class ChannelManagement:
    def __init__(self, db, config,client):
        self.db = db
        self.config = config
        self.client:TelegramClient = client

    async def start_edit_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the channel editing process"""
        query = update.callback_query
        await query.answer()

        # Get list of monitor channels
        monitor_channels = self.db.get_channels_by_type('MONITOR')
        if not monitor_channels:
            await query.message.edit_text(
                "No monitor channels available to edit.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Back", callback_data="channel_management")
                ]])
            )
            return ConversationHandler.END

        # Create keyboard with channel options
        keyboard = []
        for channel in monitor_channels:
            keyboard.append([InlineKeyboardButton(
                channel['channel_name'],
                callback_data=f"select_{channel['channel_id']}"
            )])
        keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])

        await query.message.edit_text(
            "Select a channel to edit:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return SELECTING_CHANNEL

    async def handle_channel_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle channel selection for editing"""
        query = update.callback_query
        await query.answer()

        channel_id = int(query.data.split('_')[1])
        channel_info = self.db.get_channel_info(channel_id)
        
        if not channel_info:
            await query.message.edit_text("Channel not found.")
            return ConversationHandler.END

        context.user_data['edit_channel'] = channel_info

        await query.message.edit_text(
            f"Editing channel: {channel_info['channel_name']}\n"
            f"Current prompt:\n{channel_info['prompt']}\n\n"
            "Please enter the new prompt:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Cancel", callback_data="cancel")
            ]])
        )

        return EDITING_PROMPT

    async def handle_edit_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the new prompt input"""
        message = update.message
        channel_info = context.user_data.get('edit_channel')
        
        if not channel_info:
            await message.reply_text("Error: Channel information lost. Please start over.")
            return ConversationHandler.END

        new_prompt = message.text
        success = self.db.update_channel_prompt(channel_info['channel_id'], new_prompt)

        if success:
            await message.reply_text(
                f"✅ Channel prompt updated successfully!\n\n"
                f"Channel: {channel_info['channel_name']}\n"
                f"New prompt: {new_prompt}"
            )
        else:
            await message.reply_text("❌ Failed to update channel prompt.")

        context.user_data.clear()
        return ConversationHandler.END

    async def cancel_edit_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel the channel editing process"""
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            await query.message.edit_text("❌ Channel editing cancelled.")
        else:
            await update.message.reply_text("❌ Channel editing cancelled.")

        context.user_data.clear()
        return ConversationHandler.END

    async def show_channel_management(self, message, is_new_message: bool = True):
        """显示频道管理菜单
        
        Args:
            message: Telegram message 对象
            is_new_message: 是否是新消息，用于区分是发送新消息还是编辑现有消息
        """
        keyboard = [
            [
                InlineKeyboardButton("添加频道", callback_data="add_channel"),
                InlineKeyboardButton("删除频道", callback_data="remove_channel")
            ],
            [
                InlineKeyboardButton("频道列表", callback_data="list_channels"),
                InlineKeyboardButton("编辑频道", callback_data="edit_channel")
            ],
            [
                InlineKeyboardButton("查看配对", callback_data="view_pairs"),
                InlineKeyboardButton("返回主菜单", callback_data="main_menu")
            ]
        ]

        menu_text = (
            "频道管理\n\n"
            "• 添加监控或转发频道\n"
            "• 删除现有频道\n"
            "• 查看和管理频道配对\n"
            "• 编辑频道设置"
        )

        try:
            if is_new_message:
                # 处理 /channels 命令 - 发送新消息
                await message.reply_text(
                    menu_text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                # 处理回调查询 - 编辑现有消息
                await message.edit_text(
                    menu_text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        except Exception as e:
            error_msg = "发送新消息" if is_new_message else "编辑消息"
            logging.error(f"Error {error_msg} in show_channel_management: {e}")
            if is_new_message:
                await message.reply_text("显示频道管理菜单时发生错误")
            else:
                await message.edit_text("显示频道管理菜单时发生错误")

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理频道管理相关的回调"""
        query = update.callback_query
        data = query.data
        
        try:
            if data == "add_channel":
                await self.start_add_channel(update, context)
            elif data == "remove_channel":
                await self.show_remove_channel_options(query.message)
            elif data == "list_channels":
                await self.show_channel_list(query.message)
            elif data == "edit_channel":
                await self.start_edit_channel(update, context)
            elif data == "view_pairs":
                await self.view_channel_pairs(query.message)
            elif data == "manage_pairs":
                await self.handle_manage_pairs(update, context)
            elif data == "main_menu":
                # 调用主菜单显示
                await context.bot.callback_query_handler(query)
            else:
                await self._handle_specific_channel_action(query, data)
            
        except Exception as e:
            logging.error(f"Error in channel_management handle_callback_query: {e}")
            await query.answer("处理请求时发生错误")

    async def _handle_specific_channel_action(self, query: CallbackQuery, data: str):
        """处理特定的频道操作"""
        try:
            if data.startswith("remove_"):
                channel_id = int(data.split("_")[1])
                success = self.db.remove_channel(channel_id)
                if success:
                    await query.message.edit_text(
                        "频道已成功删除",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("返回", callback_data="list_channels")
                        ]])
                    )
                else:
                    await query.message.edit_text("删除频道失败")
            elif data.startswith("pair_"):
                await self.handle_channel_pairing(query)
            elif data.startswith("select_"):
                await self.handle_channel_selection(query)
            else:
                await query.answer("未知操作")
        except Exception as e:
            logging.error(f"Error handling specific channel action: {e}")
            await query.answer("处理频道操作时发生错误")

    async def show_remove_channel_options(self, message):
        """显示可删除的频道列表"""
        monitor_channels = self.db.get_channels_by_type('MONITOR')
        forward_channels = self.db.get_channels_by_type('FORWARD') 
        
        if not monitor_channels and not forward_channels:
            await message.edit_text(
                "当前没有监控的频道。",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("返回", callback_data="channel_management")
                ]])
            )
            return

        keyboard = []
        if monitor_channels:
            keyboard.append([InlineKeyboardButton("-- 监控频道 --", callback_data="dummy")])
            for channel in monitor_channels:
                keyboard.append([InlineKeyboardButton(
                    f"🔍 {channel['channel_name']}",
                    callback_data=f"remove_{channel['channel_id']}"
                )])

        if forward_channels:
            keyboard.append([InlineKeyboardButton("-- 转发频道 --", callback_data="dummy")])
            for channel in forward_channels:
                keyboard.append([InlineKeyboardButton(
                    f"📢 {channel['channel_name']}",
                    callback_data=f"remove_{channel['channel_id']}"
                )])

        keyboard.append([InlineKeyboardButton("返回", callback_data="channel_management")])
        
        await message.edit_text(
            "选择要删除的频道:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def show_channel_list(self, message):
        """显示所有频道列表"""
        monitor_channels = self.db.get_channels_by_type('MONITOR')
        forward_channels = self.db.get_channels_by_type('FORWARD')
        
        text = "📋 频道列表\n\n"
        
        if monitor_channels:
            text += "🔍 监控频道:\n"
            for idx, channel in enumerate(monitor_channels, 1):
                text += f"{idx}. {channel['channel_name']}\n"
                text += f"   用户名: @{channel['channel_username'] or 'Private'}\n"
                text += f"   状态: {'🟢 活跃' if channel['is_active'] else '🔴 未活跃'}\n\n"
        
        if forward_channels:
            text += "\n📢 转发频道:\n"
            for idx, channel in enumerate(forward_channels, 1):
                text += f"{idx}. {channel['channel_name']}\n"
                text += f"   用户名: @{channel['channel_username'] or 'Private'}\n"
                text += f"   状态: {'🟢 活跃' if channel['is_active'] else '🔴 未活跃'}\n\n"
        
        if not monitor_channels and not forward_channels:
            text += "未配置任何频道。"
        
        await message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("返回", callback_data="channel_management")
            ]])
        )

    async def view_channel_pairs(self, message):
        """显示频道配对信息"""
        pairs = self.db.get_channel_pairs()
        
        if not pairs:
            await message.edit_text(
                "未配置频道配对。",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("返回", callback_data="channel_management")
                ]])
            )
            return

        text = "📱 频道配对\n\n"
        current_monitor = None
        
        for pair in pairs:
            if current_monitor != pair['monitor_channel_id']:
                text += f"\n🔍 监控: {pair['monitor_name']}\n"
                text += "连接到:\n"
                current_monitor = pair['monitor_channel_id']
            text += f"└─ 📢 {pair['forward_name']}\n"

        keyboard = [
            [InlineKeyboardButton("管理配对", callback_data="manage_pairs")],
            [InlineKeyboardButton("返回", callback_data="channel_management")]
        ]
        
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def handle_manage_pairs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理配对管理"""
        query = update.callback_query
        await query.answer()

        monitor_channels = self.db.get_channels_by_type('MONITOR')
        if not monitor_channels:
            await query.message.edit_text(
                "没有可用的监控频道来创建配对。",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("返回", callback_data="channel_management")
                ]])
            )
            return

        keyboard = [[
            InlineKeyboardButton(
                f"{channel['channel_name']}",
                callback_data=f"pair_monitor_{channel['channel_id']}"
            )
        ] for channel in monitor_channels]
        
        keyboard.append([InlineKeyboardButton("返回", callback_data="channel_management")])

        await query.message.edit_text(
            "选择要配对的监控频道:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


    async def start_add_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the add channel process"""
        query = update.callback_query
        await query.answer()
        
        keyboard = [
            [
                InlineKeyboardButton("Monitor Channel", callback_data="type_monitor"),
                InlineKeyboardButton("Forward Channel", callback_data="type_forward")
            ],
            [InlineKeyboardButton("Cancel", callback_data="cancel")]
        ]
        
        await query.message.edit_text(
            "What type of channel would you like to add?\n\n"
            "• Monitor Channel: Channel to monitor for trading signals\n"
            "• Forward Channel: Channel to forward processed signals",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return CHOOSING_CHANNEL_TYPE

    async def handle_channel_type_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理频道类型选择"""
        try:
            query = update.callback_query
            await query.answer()

            channel_type = query.data.split('_')[1].upper()
            context.user_data['channel_type'] = channel_type

            keyboard = [
                [
                    InlineKeyboardButton("转发消息", callback_data="method_forward"),
                    InlineKeyboardButton("手动输入ID", callback_data="method_manual")
                ],
                [InlineKeyboardButton("取消", callback_data="cancel")]
            ]

            channel_type_name = "监控" if channel_type == "MONITOR" else "转发"
            await query.message.edit_text(
                f"请选择添加{channel_type_name}频道的方式:\n\n"
                "• 转发消息: 从目标频道转发任意一条消息\n"
                "• 手动输入ID: 手动输入频道的数字ID",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

            return CHOOSING_ADD_METHOD  # 返回正确的状态常量

        except Exception as e:
            logging.error(f"Error handling channel type choice: {e}")
            await query.message.edit_text("处理选择时出错，请重试")
            return ConversationHandler.END

    def get_handlers(self):
        """返回所有处理器"""
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('add', self.start_add_channel),
                CallbackQueryHandler(self.start_add_channel, pattern='^add_channel$')
            ],
            states={
                CHOOSING_CHANNEL_TYPE: [
                    CallbackQueryHandler(self.handle_channel_type_choice, pattern='^type_')
                ],
                CHOOSING_ADD_METHOD: [
                    CallbackQueryHandler(self.handle_add_method, pattern='^method_')
                ],
                WAITING_FOR_FORWARD: [
                    MessageHandler(filters.FORWARDED & ~filters.COMMAND, self.handle_forwarded_channel),
                    CallbackQueryHandler(self.cancel_add_channel, pattern='^cancel$')
                ],
                WAITING_FOR_MANUAL_INPUT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_manual_input),
                    CallbackQueryHandler(self.cancel_add_channel, pattern='^cancel$')
                ],
                WAITING_FOR_PROMPT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_prompt_input),
                    CallbackQueryHandler(self.cancel_add_channel, pattern='^cancel$')
                ],
                WAITING_FOR_FORWARD_CHANNEL: [
                    CallbackQueryHandler(self.handle_forward_channel_selection, pattern='^pair_'),
                    CallbackQueryHandler(self.cancel_add_channel, pattern='^cancel$')
                ]
            },
            fallbacks=[
                CommandHandler('cancel', self.cancel_add_channel),
                CallbackQueryHandler(self.cancel_add_channel, pattern='^cancel$')
            ],
            name="add_channel",
            persistent=False
        )
        return [conv_handler]

    async def handle_add_method(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理添加方法选择"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "method_forward":
            await query.message.edit_text(
                "请从要监控的频道转发一条消息。\n\n"
                "提示: 你可以点击消息，然后选择'Forward'来转发。\n\n"
                "输入 /cancel 取消操作。",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("取消", callback_data="cancel")
                ]])
            )
            return WAITING_FOR_FORWARD
            
        elif query.data == "method_manual":
            await query.message.edit_text(
                "请输入频道ID。\n\n"
                "提示: 频道ID是一串数字，可以通过将机器人添加到频道后转发消息来获取。\n\n"
                "输入 /cancel 取消操作。",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("取消", callback_data="cancel")
                ]])
            )
            return WAITING_FOR_MANUAL_INPUT
    async def handle_manual_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理手动输入的Channel ID"""
        try:
            message = update.message
            input_text = message.text.strip()

            try:
                # 处理输入的ID
                if input_text.startswith('-'):
                    channel_id = int(input_text)
                else:
                    # 如果输入不是负数格式，尝试添加-100前缀
                    if input_text.startswith('100'):
                        channel_id = -int(input_text)
                    else:
                        channel_id = -int(f"100{input_text}")

                # 使用 Telethon client 获取频道信息
                try:
                    chat = await self.client.get_entity(channel_id)
                    channel_info = {
                        'id': chat.id,
                        'title': getattr(chat, 'title', None) or getattr(chat, 'first_name', 'Unknown'),
                        'username': getattr(chat, 'username', None)
                    }
                    
                    logging.info(f"Retrieved channel info via Telethon: {channel_info}")
                    context.user_data['channel_info'] = channel_info

                    if context.user_data.get('channel_type') == 'MONITOR':
                        await message.reply_text(
                            f"✅ 频道信息获取成功!\n\n"
                            f"名称: {channel_info['title']}\n"
                            f"ID: {channel_info['id']}\n"
                            f"用户名: @{channel_info['username'] or 'N/A'}\n\n"
                            f"请输入用于分析消息的prompt:\n"
                            f"(这是一个用于分析频道消息的GPT提示词)",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("取消", callback_data="cancel")
                            ]])
                        )
                        return WAITING_FOR_PROMPT
                    else:
                        monitor_channels = self.db.get_channels_by_type('MONITOR')
                        if not monitor_channels:
                            await message.reply_text(
                                "❌ 没有可用的监控频道。请先添加一个监控频道。"
                            )
                            return ConversationHandler.END

                        keyboard = []
                        for channel in monitor_channels:
                            keyboard.append([InlineKeyboardButton(
                                channel['channel_name'],
                                callback_data=f"pair_{channel['channel_id']}"
                            )])
                        keyboard.append([InlineKeyboardButton("取消", callback_data="cancel")])

                        await message.reply_text(
                            f"选择要与 {channel_info['title']} 配对的监控频道:",
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                        return WAITING_FOR_FORWARD_CHANNEL

                except (ValueError, TypeError) as e:
                    logging.error(f"Error getting channel info via Telethon: {e}")
                    await message.reply_text(
                        "❌ 无法找到此频道。请确认:\n\n"
                        "1. ID输入正确\n"
                        "2. 频道是公开的或Bot已加入\n"
                        "3. 格式正确 (-100开头的完整ID)\n\n"
                        "请重新输入正确的频道ID:"
                    )
                    return WAITING_FOR_MANUAL_INPUT

            except ValueError:
                await message.reply_text(
                    "❌ 无效的频道ID格式。\n"
                    "请输入正确的数字ID，例如:\n"
                    "• -1001234567890\n"
                    "• 1234567890\n\n"
                    "提示：可以从频道设置中获取ID"
                )
                return WAITING_FOR_MANUAL_INPUT

        except Exception as e:
            logging.error(f"Error in handle_manual_input: {e}")
            await message.reply_text(
                "❌ 处理输入时发生错误，请重试"
            )
            return WAITING_FOR_MANUAL_INPUT

    async def handle_forwarded_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理转发的消息"""
        try:
            message = update.message
            
            # 获取转发来源的chat_id
            chat_id = None
            if message.forward_from_chat:
                chat_id = message.forward_from_chat.id
            elif message.forward_from:
                chat_id = message.forward_from.id
            
            if not chat_id:
                await message.reply_text(
                    "❌ 请转发一条来自目标频道的消息。",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("取消", callback_data="cancel")
                    ]])
                )
                return WAITING_FOR_FORWARD

            try:
                # 使用 Telethon client 获取频道信息
                chat = await self.client.get_entity(chat_id)
                channel_info = {
                    'id': chat.id,
                    'title': getattr(chat, 'title', None) or getattr(chat, 'first_name', 'Unknown'),
                    'username': getattr(chat, 'username', None)
                }
                
                logging.info(f"Retrieved forwarded channel info: {channel_info}")
                context.user_data['channel_info'] = channel_info

                if context.user_data.get('channel_type') == 'MONITOR':
                    await message.reply_text(
                        f"✅ 频道信息获取成功!\n\n"
                        f"名称: {channel_info['title']}\n"
                        f"ID: {channel_info['id']}\n"
                        f"用户名: @{channel_info['username'] or 'N/A'}\n\n"
                        f"请输入用于分析消息的prompt:\n"
                        f"(这是一个用于分析频道消息的GPT提示词)",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("取消", callback_data="cancel")
                        ]])
                    )
                    return WAITING_FOR_PROMPT
                else:
                    monitor_channels = self.db.get_channels_by_type('MONITOR')
                    if not monitor_channels:
                        await message.reply_text(
                            "❌ 没有可用的监控频道。请先添加一个监控频道。"
                        )
                        return ConversationHandler.END

                    keyboard = []
                    for channel in monitor_channels:
                        keyboard.append([InlineKeyboardButton(
                            channel['channel_name'],
                            callback_data=f"pair_{channel['channel_id']}"
                        )])
                    keyboard.append([InlineKeyboardButton("取消", callback_data="cancel")])

                    await message.reply_text(
                        f"选择要与 {channel_info['title']} 配对的监控频道:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    return WAITING_FOR_FORWARD_CHANNEL

            except Exception as e:
                logging.error(f"Error getting forwarded channel info: {e}")
                await message.reply_text(
                    "❌ 无法获取频道信息。请确保:\n"
                    "1. 转发的是频道消息\n"
                    "2. 频道是公开的或Bot已加入\n"
                    "请重新转发一条消息:"
                )
                return WAITING_FOR_FORWARD

        except Exception as e:
            logging.error(f"Error handling forwarded channel: {e}")
            await message.reply_text(
                "❌ 处理转发消息时出错，请重试"
            )
            return WAITING_FOR_FORWARD
    async def handle_prompt_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理prompt输入"""
        try:
            message = update.message
            channel_info = context.user_data.get('channel_info')
            if not channel_info:
                await message.reply_text("❌ 频道信息丢失，请重新开始")
                return ConversationHandler.END

            prompt = message.text
            
            # 使用原始channel_id添加频道
            success = self.db.add_channel(
                channel_id=channel_info['id'],  # 使用原始ID
                channel_name=channel_info['title'],
                channel_username=channel_info['username'],
                channel_type='MONITOR',
                prompt=prompt
            )
            
            if success:
                await message.reply_text(
                    f"✅ 监控频道添加成功!\n\n"
                    f"名称: {channel_info['title']}\n"
                    f"ID: {channel_info['id']}\n"  # 显示完整ID
                    f"Prompt: {prompt}"
                )
            else:
                await message.reply_text("❌ 添加频道失败")
            
            context.user_data.clear()
            return ConversationHandler.END

        except Exception as e:
            logging.error(f"Error handling prompt input: {e}")
            await message.reply_text("添加频道时发生错误")
            return ConversationHandler.END


    async def handle_forward_channel_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理转发频道的选择"""
        query = update.callback_query
        await query.answer()
        
        try:
            monitor_channel_id = int(query.data.split('_')[1])
            channel_info = context.user_data.get('channel_info')
            
            if not channel_info:
                await query.message.edit_text("❌ 频道信息丢失，请重新开始")
                return ConversationHandler.END
            
            # 添加转发频道
            success = self.db.add_channel(
                channel_id=channel_info['id'],
                channel_name=channel_info['title'],
                channel_username=channel_info['username'],
                channel_type='FORWARD'
            )
            
            if success:
                # 创建频道配对
                pair_success = self.db.add_channel_pair(
                    monitor_channel_id=monitor_channel_id,
                    forward_channel_id=channel_info['id']
                )
                
                if pair_success:
                    await query.message.edit_text(
                        f"✅ 转发频道添加成功并完成配对!\n\n"
                        f"名称: {channel_info['title']}\n"
                        f"ID: {channel_info['id']}\n"
                        f"配对监控频道ID: {monitor_channel_id}"
                    )
                else:
                    await query.message.edit_text("❌ 创建频道配对失败")
            else:
                await query.message.edit_text("❌ 添加转发频道失败")
            
            context.user_data.clear()
            return ConversationHandler.END
            
        except Exception as e:
            logging.error(f"Error handling forward channel selection: {e}")
            await query.message.edit_text(
                "❌ 处理频道选择时发生错误"
            )
            return ConversationHandler.END
    async def show_remove_channel_options(self, message):
        """Show list of channels that can be removed"""
        monitor_channels = self.db.get_channels_by_type('MONITOR')
        forward_channels = self.db.get_channels_by_type('FORWARD')
        
        if not monitor_channels and not forward_channels:
            await message.edit_text(
                "No channels are currently being monitored.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Back", callback_data="channel_management")
                ]])
            )
            return

        keyboard = []
        if monitor_channels:
            keyboard.append([InlineKeyboardButton("-- Monitor Channels --", callback_data="dummy")])
            for channel in monitor_channels:
                keyboard.append([InlineKeyboardButton(
                    f"🔍 {channel['channel_name']}",
                    callback_data=f"remove_{channel['channel_id']}"
                )])

        if forward_channels:
            keyboard.append([InlineKeyboardButton("-- Forward Channels --", callback_data="dummy")])
            for channel in forward_channels:
                keyboard.append([InlineKeyboardButton(
                    f"📢 {channel['channel_name']}",
                    callback_data=f"remove_{channel['channel_id']}"
                )])

        keyboard.append([InlineKeyboardButton("Back", callback_data="channel_management")])
        
        await message.edit_text(
            "Select a channel to remove:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def show_channel_list(self, message):
        """Display list of all channels"""
        monitor_channels = self.db.get_channels_by_type('MONITOR')
        forward_channels = self.db.get_channels_by_type('FORWARD')
        
        text = "📋 Channel List\n\n"
        
        if monitor_channels:
            text += "🔍 Monitor Channels:\n"
            for idx, channel in enumerate(monitor_channels, 1):
                text += f"{idx}. {channel['channel_name']}\n"
                text += f"   Username: @{channel['channel_username'] or 'Private'}\n"
                text += f"   Status: {'🟢 Active' if channel['is_active'] else '🔴 Inactive'}\n\n"
        
        if forward_channels:
            text += "\n📢 Forward Channels:\n"
            for idx, channel in enumerate(forward_channels, 1):
                text += f"{idx}. {channel['channel_name']}\n"
                text += f"   Username: @{channel['channel_username'] or 'Private'}\n"
                text += f"   Status: {'🟢 Active' if channel['is_active'] else '🔴 Inactive'}\n\n"
        
        if not monitor_channels and not forward_channels:
            text += "No channels configured."
        
        await message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Back", callback_data="channel_management")
            ]])
        )


    async def cancel_add_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel channel addition process"""
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            await query.message.edit_text("❌ Channel addition cancelled.")
        else:
            await update.message.reply_text("❌ Channel addition cancelled.")
        
        context.user_data.clear()
        return ConversationHandler.END