# models.py
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

@dataclass
class EntryZone:
    price: float
    percentage: float
    order_id: Optional[str] = None
    status: str = 'PENDING'  # PENDING, FILLED, CANCELLED

@dataclass
class TakeProfitLevel:
    price: float
    percentage: float
    order_id: Optional[str] = None
    is_hit: bool = False
    hit_time: Optional[datetime] = None

@dataclass
class TradingSignal:
    exchange: str
    symbol: str
    action: str  # OPEN_LONG, OPEN_SHORT, CLOSE
    entry_price: Optional[float] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    position_size: float = 50.0
    source_message: str = ""
    confidence: float = 0.0
    risk_level: str = "MEDIUM"
    timestamp: datetime = datetime.now()
    
    # 新增字段
    leverage: int = 50
    margin_mode: str = "cross"
    entry_zones: Optional[List[EntryZone]] = None
    take_profit_levels: Optional[List[TakeProfitLevel]] = None
    dynamic_sl: bool = False
    signal_id: Optional[int] = None
    additional_info: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换信号为字典格式"""
        base_dict = {
            'exchange': self.exchange,
            'symbol': self.symbol,
            'action': self.action,
            'position_size': self.position_size,
            'leverage': self.leverage,
            'margin_mode': self.margin_mode,
            'confidence': self.confidence,
            'risk_level': self.risk_level,
            'timestamp': self.timestamp.isoformat(),
            'source_message': self.source_message
        }
        
        # 添加可选字段
        if self.entry_price:
            base_dict['entry_price'] = self.entry_price
        if self.take_profit:
            base_dict['take_profit'] = self.take_profit
        if self.stop_loss:
            base_dict['stop_loss'] = self.stop_loss
        if self.additional_info:
            base_dict['additional_info'] = self.additional_info
            
        # 添加区间入场和多级止盈
        if self.entry_zones:
            base_dict['entry_zones'] = [
                {'price': ez.price, 'percentage': ez.percentage, 'status': ez.status}
                for ez in self.entry_zones
            ]
        if self.take_profit_levels:
            base_dict['take_profit_levels'] = [
                {
                    'price': tp.price,
                    'percentage': tp.percentage,
                    'is_hit': tp.is_hit,
                    'hit_time': tp.hit_time.isoformat() if tp.hit_time else None
                }
                for tp in self.take_profit_levels
            ]
            
        return base_dict

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'TradingSignal':
        """从字典创建TradingSignal对象"""
        # 处理基本字段
        signal_data = {k: v for k, v in data.items() 
                      if k not in ['entry_zones', 'take_profit_levels']}
        
        if 'timestamp' in signal_data:
            signal_data['timestamp'] = datetime.fromisoformat(signal_data['timestamp'])
            
        signal = TradingSignal(**signal_data)
        
        # 处理区间入场
        if 'entry_zones' in data and data['entry_zones']:
            signal.entry_zones = [
                EntryZone(**ez) for ez in data['entry_zones']
            ]
            
        # 处理多级止盈
        if 'take_profit_levels' in data and data['take_profit_levels']:
            signal.take_profit_levels = [
                TakeProfitLevel(
                    price=tp['price'],
                    percentage=tp['percentage'],
                    is_hit=tp.get('is_hit', False),
                    hit_time=datetime.fromisoformat(tp['hit_time']) if tp.get('hit_time') else None
                )
                for tp in data['take_profit_levels']
            ]
            
        return signal

    def calculate_risk_ratio(self) -> float:
        """计算风险收益比"""
        if self.action == 'OPEN_LONG':
            if self.take_profit_levels:
                highest_tp = max(tp.price for tp in self.take_profit_levels)
                reward = highest_tp - self.entry_price
            else:
                reward = self.take_profit - self.entry_price if self.take_profit else 0
            risk = self.entry_price - self.stop_loss if self.stop_loss else 0
        else:  # OPEN_SHORT
            if self.take_profit_levels:
                lowest_tp = min(tp.price for tp in self.take_profit_levels)
                reward = self.entry_price - lowest_tp
            else:
                reward = self.entry_price - self.take_profit if self.take_profit else 0
            risk = self.stop_loss - self.entry_price if self.stop_loss else 0
        
        return abs(reward / risk) if risk != 0 else 0

    def is_valid(self) -> bool:
        """验证信号是否有效"""
        if not all([self.exchange, self.symbol, self.action]):
            return False
            
        if not self.entry_zones and not self.entry_price:
            return False
            
        if self.action not in ['OPEN_LONG', 'OPEN_SHORT', 'CLOSE']:
            return False
            
        return True

@dataclass
class OrderResult:
    """订单结果"""
    success: bool
    order_id: Optional[str] = None
    error_message: Optional[str] = None
    executed_price: Optional[float] = None
    executed_amount: Optional[float] = None
    extra_info: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'success': self.success,
            'order_id': self.order_id,
            'error_message': self.error_message,
            'executed_price': self.executed_price,
            'executed_amount': self.executed_amount,
            'extra_info': self.extra_info
        }
        
@dataclass
class ChannelMessage:
    channel_id: int
    message_id: int
    text: str
    timestamp: datetime
    channel_title: str
    channel_username: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'channel_id': self.channel_id,
            'message_id': self.message_id,
            'text': self.text,
            'timestamp': self.timestamp.isoformat(),
            'channel_title': self.channel_title,
            'channel_username': self.channel_username
        }