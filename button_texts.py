# button_texts.py

class ButtonText:
    """按钮文本统一配置"""
    
    # 主菜单
    CHANNEL_MANAGEMENT = "频道管理"
    TRADE_MANAGEMENT = "交易管理"
    POSITION_OVERVIEW = "持仓概览"
    ACCOUNT_STATS = "账户统计"
    SETTINGS = "设置"
    HELP = "帮助"
    BACK_MAIN = "返回主菜单"
    
    # 频道管理
    ADD_CHANNEL = "添加频道"
    REMOVE_CHANNEL = "删除频道"
    CHANNEL_LIST = "频道列表"
    EDIT_CHANNEL = "编辑频道"
    VIEW_PAIRS = "查看配对"
    MANAGE_PAIRS = "管理配对"
    
    # 交易管理
    VIEW_POSITIONS = "查看持仓"
    CLOSE_POSITION = "平仓"
    MODIFY_POSITION = "修改持仓"
    ORDER_HISTORY = "订单历史"
    MODIFY_TP_SL = "修改止盈止损"
    MODIFY_TP = "修改止盈"
    MODIFY_SL = "修改止损"
    
    # 订单操作
    EXECUTE_TRADE = "执行交易"
    CONFIRM_CLOSE = "确认平仓"
    IGNORE_SIGNAL = "忽略信号"
    VIEW_ANALYSIS = "查看分析"
    CANCEL = "取消"
    
    # 设置
    RISK_SETTINGS = "风险管理"
    AUTO_TRADE_SETTINGS = "自动交易"
    NOTIFICATION_SETTINGS = "通知设置"
    API_SETTINGS = "API设置"
    
    # 状态标签
    STATUS_ACTIVE = "🟢 活跃"
    STATUS_INACTIVE = "🔴 未活跃"
    
    # 方向标签
    DIRECTION_LONG = "🟢 多头"
    DIRECTION_SHORT = "🔴 空头"
    DIRECTION_CLOSE = "⚪️ 平仓"

    # 测试网标签
    TESTNET_INDICATOR = "🏮 测试网"
    MAINNET_INDICATOR = "🔵 主网"