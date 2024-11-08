# trading_logic.py
from typing import Optional, Dict, Any, List, Tuple
import logging
import re
import json
from datetime import datetime, timedelta
import time
from openai import OpenAI
from math import isclose
import numpy as np
import pandas as pd

from models import TradingSignal, EntryZone, TakeProfitLevel

class TradingLogic:
    def __init__(self, openai_key: str,openai_base_url:str):
        self.openai_client = OpenAI(api_key=openai_key)
        self.openai_client.base_url = openai_base_url
        self.default_prompt = """
你是一个交易信号分析器。请分析输入的消息并提取交易信号信息。
如果找到有效的交易信号，请返回包含以下字段的JSON：

{
    "exchange": "string (BINANCE或OKX)",
    "symbol": "string (如BTCUSDT)",
    "action": "string (OPEN_LONG, OPEN_SHORT, 或 CLOSE)",
    "entry_price": float或array (可以是单个价格或价格区间),
    "take_profit_levels": [
        {"price": float, "percentage": float}
    ],
    "stop_loss": float,
    "position_size": float,
    "leverage": integer,
    "margin_mode": "string (cross或isolated)",
    "confidence": float (0-1),
    "risk_level": "string (LOW, MEDIUM, HIGH)"
}

特别说明：
1. 如果是区间入场，将入场价格设置为数组
2. 多个止盈目标时，设置不同的percentage表示每个目标平仓的仓位比例
3. 如果没有指定止损，需要基于风险控制计算一个合理的止损价格
4. 保证risk:reward比率至少为1:1.5

如果无法提取有效信号，返回null。
"""

    def _validate_json_data(self, data: Dict[str, Any]) -> bool:
        """验证JSON数据的有效性"""
        try:
            # 验证必要字段
            required_fields = ['exchange', 'symbol', 'action']
            for field in required_fields:
                if field not in data:
                    logging.error(f"Missing required field: {field}")
                    return False

            # 验证交易所
            if data['exchange'] not in ['BINANCE', 'OKX']:
                logging.error(f"Invalid exchange: {data['exchange']}")
                return False

            # 验证交易对
            if not isinstance(data['symbol'], str) or not data['symbol']:
                logging.error("Invalid symbol")
                return False

            # 验证操作类型
            if data['action'] not in ['OPEN_LONG', 'OPEN_SHORT', 'CLOSE']:
                logging.error(f"Invalid action: {data['action']}")
                return False

            # 验证入场区间或价格
            if 'entry_zones' in data:
                if not isinstance(data['entry_zones'], list):
                    logging.error("entry_zones must be a list")
                    return False
                for zone in data['entry_zones']:
                    if not all(k in zone for k in ['price', 'percentage']):
                        logging.error("Invalid entry zone format")
                        return False

            # 验证止盈目标
            if 'take_profit_levels' in data:
                if not isinstance(data['take_profit_levels'], list):
                    logging.error("take_profit_levels must be a list")
                    return False
                for tp in data['take_profit_levels']:
                    if not all(k in tp for k in ['price', 'percentage']):
                        logging.error("Invalid take profit level format")
                        return False

            # 验证数值字段
            numeric_fields = {
                'position_size': 50.0,
                'leverage': 10,
                'confidence': 0.8
            }
            for field, default in numeric_fields.items():
                if field in data:
                    try:
                        float(data[field])
                    except (TypeError, ValueError):
                        logging.error(f"Invalid {field} value")
                        return False

            return True

        except Exception as e:
            logging.error(f"Error validating JSON data: {e}")
            return False

    def _normalize_numbers(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """规范化数值字段"""
        try:
            normalized = data.copy()

            # 处理入场区间
            if 'entry_zones' in normalized and isinstance(normalized['entry_zones'], list):
                for zone in normalized['entry_zones']:
                    zone['price'] = float(zone['price'])
                    zone['percentage'] = float(zone['percentage'])

            # 处理止盈目标
            if 'take_profit_levels' in normalized and isinstance(normalized['take_profit_levels'], list):
                for tp in normalized['take_profit_levels']:
                    tp['price'] = float(tp['price'])
                    tp['percentage'] = float(tp['percentage'])

            # 处理其他数值字段
            numeric_fields = ['stop_loss', 'position_size', 'leverage', 'confidence']
            for field in numeric_fields:
                if field in normalized:
                    try:
                        if field == 'leverage':
                            normalized[field] = int(float(normalized[field]))
                        else:
                            normalized[field] = float(normalized[field])
                    except (TypeError, ValueError):
                        logging.warning(f"Could not convert {field} to number, removing field")
                        normalized.pop(field)

            return normalized

        except Exception as e:
            logging.error(f"Error normalizing numbers: {e}")
            return data
        
    def _convert_to_trading_signal(self, data: Dict[str, Any]) -> Optional[TradingSignal]:
        """将字典转换为TradingSignal对象"""
        try:
            logging.info("Converting dictionary to TradingSignal")
            logging.info(f"Input data:\n{'-'*40}\n{json.dumps(data, indent=2)}\n{'-'*40}")

            # 验证必要字段
            required_fields = ['exchange', 'symbol', 'action']
            for field in required_fields:
                if field not in data:
                    logging.error(f"Missing required field: {field}")
                    return None

            # 处理入场价格/区间
            entry_price = None
            entry_zones = []
            
            # 检查是否有区间入场
            if 'entry_zones' in data and isinstance(data['entry_zones'], list) and data['entry_zones']:
                for zone_data in data['entry_zones']:
                    try:
                        zone = EntryZone(
                            price=float(zone_data['price']),
                            percentage=float(zone_data['percentage'])
                        )
                        entry_zones.append(zone)
                    except (KeyError, ValueError) as e:
                        logging.error(f"Error creating entry zone: {e}")
                        continue
                logging.info(f"Created {len(entry_zones)} entry zones")
            # 检查是否有单一入场价格
            elif 'entry_price' in data and data['entry_price'] is not None:
                try:
                    entry_price = float(data['entry_price'])
                    logging.info(f"Using single entry price: {entry_price}")
                except (TypeError, ValueError) as e:
                    logging.error(f"Error converting entry price: {e}")
                    return None

            # 如果既没有入场区间也没有入场价格，返回None
            if not entry_zones and entry_price is None:
                logging.error("No valid entry price or zones found")
                return None

            # 处理止盈目标
            take_profit_levels = []
            # 检查 take_profit_levels 或 take_profit 字段
            tp_data = data.get('take_profit_levels', data.get('take_profit', []))
            if isinstance(tp_data, list):
                for tp_item in tp_data:
                    try:
                        tp = TakeProfitLevel(
                            price=float(tp_item['price']),
                            percentage=float(tp_item['percentage'])
                        )
                        take_profit_levels.append(tp)
                    except (KeyError, ValueError) as e:
                        logging.error(f"Error creating take profit level: {e}")
                        continue
            
            if take_profit_levels:
                logging.info(f"Created {len(take_profit_levels)} take profit levels")
                # 确保止盈百分比总和为1
                total_percentage = sum(tp.percentage for tp in take_profit_levels)
                if not isclose(total_percentage, 1.0, rel_tol=1e-5):
                    logging.warning(f"Take profit percentages sum to {total_percentage}, normalizing...")
                    for tp in take_profit_levels:
                        tp.percentage = tp.percentage / total_percentage

            # 获取止损价格
            stop_loss = None
            if 'stop_loss' in data:
                try:
                    stop_loss = float(data['stop_loss'])
                except (TypeError, ValueError):
                    logging.error("Invalid stop loss value")

            # 创建信号对象
            try:
                signal = TradingSignal(
                    exchange=data['exchange'],
                    symbol=data['symbol'],
                    action=data['action'],
                    entry_price=entry_price,  # 可以是None
                    entry_zones=entry_zones if entry_zones else None,  # 可以是None
                    take_profit_levels=take_profit_levels if take_profit_levels else None,
                    stop_loss=stop_loss,
                    position_size=float(data.get('position_size', 50.0)),
                    leverage=int(data.get('leverage', 10)),
                    margin_mode=data.get('margin_mode', 'cross'),
                    confidence=float(data.get('confidence', 0.8)),
                    risk_level=data.get('risk_level', 'MEDIUM'),
                    source_message="",
                    additional_info={}
                )
                
                logging.info("Successfully created TradingSignal object")
                logging.info(f"Signal details:\n{'-'*40}")
                logging.info(f"Exchange: {signal.exchange}")
                logging.info(f"Symbol: {signal.symbol}")
                logging.info(f"Action: {signal.action}")
                
                if entry_zones:
                    logging.info("Entry Zones:")
                    for i, zone in enumerate(entry_zones, 1):
                        logging.info(f"  Zone {i}: Price={zone.price}, Percentage={zone.percentage:.2%}")
                elif entry_price:
                    logging.info(f"Entry Price: {entry_price}")
                
                if take_profit_levels:
                    logging.info("Take Profit Levels:")
                    for i, tp in enumerate(take_profit_levels, 1):
                        logging.info(f"  TP {i}: Price={tp.price}, Percentage={tp.percentage:.2%}")
                
                logging.info(f"Stop Loss: {signal.stop_loss}")
                logging.info(f"Leverage: {signal.leverage}x")
                logging.info(f"Position Size: {signal.position_size} USDT")
                logging.info(f"{'-'*40}")

                # 验证信号有效性
                is_valid = signal.is_valid()
                if not is_valid:
                    logging.error("Signal validation failed")
                    logging.error("Missing essential components:")
                    if not signal.entry_zones and signal.entry_price is None:
                        logging.error("- No entry price or zones")
                    if not signal.take_profit_levels:
                        logging.error("- No take profit levels")
                    if not signal.stop_loss:
                        logging.error("- No stop loss")
                    return None

                return signal

            except Exception as e:
                logging.error(f"Error creating TradingSignal object: {e}")
                import traceback
                logging.error(f"Traceback:\n{traceback.format_exc()}")
                return None

        except Exception as e:
            logging.error(f"Error converting to trading signal: {e}")
            import traceback
            logging.error(f"Traceback:\n{traceback.format_exc()}")
            return None

    def _preprocess_message(self, message: str) -> str:
        """预处理消息文本"""
        try:
            logging.info("Preprocessing message")
            
            # 移除表情符号和特殊字符
            cleaned = re.sub(r'[^\w\s.,#@$%+-:()]', ' ', message)
            
            # 标准化价格格式
            cleaned = cleaned.replace(',', '')
            cleaned = re.sub(r'(\d+\.?\d*)k', lambda m: str(float(m.group(1))*1000), cleaned)
            
            # 统一符号
            cleaned = cleaned.replace('$', '')
            cleaned = cleaned.upper()
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            
            logging.info(f"Preprocessed message:\n{'-'*40}\n{cleaned}\n{'-'*40}")
            return cleaned
            
        except Exception as e:
            logging.error(f"Error preprocessing message: {e}")
            return message

    def process_message(self, message: str, custom_prompt: Optional[str] = None) -> Optional[TradingSignal]:
        """处理消息并提取交易信号"""
        try:
            prompt = custom_prompt if custom_prompt else self.default_prompt
            
            logging.info(f"Original message:\n{'-'*40}\n{message}\n{'-'*40}")
            
            cleaned_message = self._preprocess_message(message)
            
            logging.info(f"Using prompt:\n{'-'*40}\n{prompt}\n{'-'*40}")
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": cleaned_message}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            response_text = response.choices[0].message.content
            logging.info(f"GPT response:\n{'-'*40}\n{response_text}\n{'-'*40}")
            
            signal_dict = self._parse_response(response_text)
            if signal_dict:
                logging.info(f"Parsed signal dictionary:\n{'-'*40}\n{json.dumps(signal_dict, indent=2)}\n{'-'*40}")
                
                if self._validate_json_data(signal_dict):
                    normalized_dict = self._normalize_numbers(signal_dict)
                    signal = self._convert_to_trading_signal(normalized_dict)
                    
                    if signal and signal.is_valid():
                        risk_ratio_valid = True#self._validate_risk_ratio(signal)
                        logging.info(f"Risk ratio validation: {risk_ratio_valid}")
                        if risk_ratio_valid:
                            return signal
                        else:
                            logging.error("Risk ratio validation failed")
                    else:
                        logging.error("Signal validation failed")
                else:
                    logging.error("JSON data validation failed")
            else:
                logging.error("Failed to parse GPT response")

            return None
            
        except Exception as e:
            logging.error(f"Error processing message: {e}")
            import traceback
            logging.error(f"Traceback:\n{traceback.format_exc()}")
            return None

    def _parse_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """解析GPT响应"""
        try:
            # 记录开始解析
            logging.info("Starting to parse GPT response")
            
            # 清除注释
            cleaned_text = ""
            for line in response_text.split('\n'):
                # 移除单行注释
                line = re.sub(r'//.*$', '', line)
                # 移除含有注释的部分
                line = re.sub(r'/\*.*?\*/', '', line)
                if line.strip():
                    cleaned_text += line + "\n"
                    
            # 提取JSON部分
            json_match = re.search(r'{.*}', cleaned_text, re.DOTALL)
            if not json_match:
                logging.warning("No JSON found in response")
                return None
                    
            json_str = json_match.group()
            logging.info(f"Extracted JSON string:\n{'-'*40}\n{json_str}\n{'-'*40}")
            
            # 解析JSON
            parsed_data = json.loads(json_str)
            logging.info(f"Successfully parsed JSON:\n{'-'*40}\n{json.dumps(parsed_data, indent=2)}\n{'-'*40}")
            
            # 验证必要字段
            required_fields = ['exchange', 'symbol', 'action']
            missing_fields = [field for field in required_fields if field not in parsed_data]
            if missing_fields:
                logging.warning(f"Missing required fields: {missing_fields}")
                return None
            
            return parsed_data
                
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error: {e}")
            logging.error(f"Problematic text:\n{response_text}")
            return None
        except Exception as e:
            logging.error(f"Error parsing GPT response: {e}")
            return None


    def _validate_and_complete_signal(self, signal: TradingSignal) -> Optional[TradingSignal]:
        """验证并补充信号信息"""
        try:
            # 验证基本字段
            if not all([signal.exchange, signal.symbol, signal.action]):
                return None
            
            # 确保有入场价格或区间
            if not signal.entry_price and not signal.entry_zones:
                return None
            
            # 验证动作类型
            if signal.action not in ['OPEN_LONG', 'OPEN_SHORT', 'CLOSE']:
                return None
            
            # 如果没有止损，计算默认止损
            if not signal.stop_loss and signal.action != 'CLOSE':
                signal.stop_loss = self._calculate_default_stop_loss(signal)
            
            # 如果没有止盈等级，设置默认止盈
            if not signal.take_profit_levels and signal.action != 'CLOSE':
                signal.take_profit_levels = self._calculate_default_take_profits(signal)
            
            # 验证风险比率
            if not self._validate_risk_ratio(signal):
                logging.warning(f"Invalid risk ratio for signal: {signal.symbol}")
                return None
            
            return signal
            
        except Exception as e:
            logging.error(f"Error validating signal: {e}")
            return None

    def _calculate_default_stop_loss(self, signal: TradingSignal) -> float:
        """计算默认止损价格"""
        try:
            entry_price = signal.entry_price
            if not entry_price and signal.entry_zones:
                # 使用区间入场的中间价格
                prices = [zone.price for zone in signal.entry_zones]
                entry_price = sum(prices) / len(prices)
            
            # 默认使用2%的止损距离
            stop_distance = entry_price * 0.02
            
            if signal.action == 'OPEN_LONG':
                return entry_price - stop_distance
            else:  # OPEN_SHORT
                return entry_price + stop_distance
                
        except Exception as e:
            logging.error(f"Error calculating default stop loss: {e}")
            return 0

    def _calculate_default_take_profits(self, signal: TradingSignal) -> List[TakeProfitLevel]:
        """计算默认止盈等级"""
        try:
            entry_price = signal.entry_price
            if not entry_price and signal.entry_zones:
                prices = [zone.price for zone in signal.entry_zones]
                entry_price = sum(prices) / len(prices)
            
            # 计算止损距离
            stop_distance = abs(entry_price - signal.stop_loss)
            
            # 设置三个止盈目标，分别是2R、3R和4R
            multipliers = [2, 3, 4]  # R倍数
            percentages = [0.4, 0.3, 0.3]  # 每个目标的仓位比例
            
            tp_levels = []
            for mult, pct in zip(multipliers, percentages):
                if signal.action == 'OPEN_LONG':
                    price = entry_price + (stop_distance * mult)
                else:  # OPEN_SHORT
                    price = entry_price - (stop_distance * mult)
                tp_levels.append(TakeProfitLevel(price, pct))
            
            return tp_levels
            
        except Exception as e:
            logging.error(f"Error calculating default take profits: {e}")
            return []

    def _validate_risk_ratio(self, signal: TradingSignal) -> bool:
        """验证风险收益比"""
        try:
            if signal.action == 'CLOSE':
                return True
            
            entry_price = signal.entry_price
            if not entry_price and signal.entry_zones:
                prices = [zone.price for zone in signal.entry_zones]
                entry_price = sum(prices) / len(prices)
            
            if not signal.stop_loss or not signal.take_profit_levels:
                return False
            
            # 计算回报
            if signal.action == 'OPEN_LONG':
                highest_tp = max(tp.price for tp in signal.take_profit_levels)
                reward = highest_tp - entry_price
                risk = entry_price - signal.stop_loss
            else:  # OPEN_SHORT
                lowest_tp = min(tp.price for tp in signal.take_profit_levels)
                reward = entry_price - lowest_tp
                risk = signal.stop_loss - entry_price
            
            # 要求至少1:1.5的风险收益比
            return (reward / risk) >= 1.5 if risk > 0 else False
            
        except Exception as e:
            logging.error(f"Error validating risk ratio: {e}")
            return False

    async def generate_analysis(self, signal: TradingSignal) -> Dict[str, Any]:
        """生成交易分析"""
        try:
            # TODO: 获取市场数据并进行技术分析
            analysis = {
                'trend': self._analyze_trend(signal),
                'support_resistance': self._find_support_resistance(signal),
                'volatility': self._analyze_volatility(signal),
                'risk_level': self._assess_risk_level(signal),
                'recommendation': self._generate_recommendation(signal)
            }
            
            return analysis
            
        except Exception as e:
            logging.error(f"Error generating analysis: {e}")
            return {}

    def _analyze_trend(self, signal: TradingSignal) -> Dict[str, Any]:
        """分析市场趋势"""
        # TODO: 实现实际的趋势分析
        return {
            'short_term': 'BULLISH',
            'medium_term': 'NEUTRAL',
            'long_term': 'BEARISH'
        }

    def _find_support_resistance(self, signal: TradingSignal) -> Dict[str, Any]:
        """寻找支撑阻力位"""
        # TODO: 实现支撑阻力位分析
        return {
            'support_levels': [40000, 39000, 38000],
            'resistance_levels': [42000, 43000, 44000]
        }

    def _analyze_volatility(self, signal: TradingSignal) -> Dict[str, Any]:
        """分析波动性"""
        # TODO: 实现波动性分析
        return {
            'current_volatility': 'HIGH',
            'volatility_trend': 'INCREASING',
            'risk_factor': 0.8
        }

    def _assess_risk_level(self, signal: TradingSignal) -> str:
        """评估风险等级"""
        try:
            # 计算风险分数
            risk_score = 0
            
            # 基于杠杆的风险
            if signal.leverage > 20:
                risk_score += 3
            elif signal.leverage > 10:
                risk_score += 2
            elif signal.leverage > 5:
                risk_score += 1
            
            # 基于止损距离的风险
            entry_price = signal.entry_price
            if not entry_price and signal.entry_zones:
                prices = [zone.price for zone in signal.entry_zones]
                entry_price = sum(prices) / len(prices)
            
            stop_distance = abs(entry_price - signal.stop_loss) / entry_price * 100
            if stop_distance < 1:
                risk_score += 3
            elif stop_distance < 2:
                risk_score += 2
            elif stop_distance < 3:
                risk_score += 1
            
            # 基于风险收益比的风险
            rr_ratio = self.calculate_risk_reward_ratio(signal)
            if rr_ratio < 1.5:
                risk_score += 3
            elif rr_ratio < 2:
                risk_score += 2
            elif rr_ratio < 2.5:
                risk_score += 1
            
            # 返回风险等级
            if risk_score >= 7:
                return 'HIGH'
            elif risk_score >= 4:
                return 'MEDIUM'
            else:
                return 'LOW'
                
        except Exception as e:
            logging.error(f"Error assessing risk level: {e}")
            return 'MEDIUM'

    def calculate_risk_reward_ratio(self, signal: TradingSignal) -> float:
        """计算风险收益比"""
        try:
            entry_price = signal.entry_price
            if not entry_price and signal.entry_zones:
                prices = [zone.price for zone in signal.entry_zones]
                entry_price = sum(prices) / len(prices)
            
            if signal.action == 'OPEN_LONG':
                if signal.take_profit_levels:
                    highest_tp = max(tp.price for tp in signal.take_profit_levels)
                    reward = highest_tp - entry_price
                else:
                    reward = signal.take_profit - entry_price
                risk = entry_price - signal.stop_loss
            else:
                if signal.take_profit_levels:
                    lowest_tp = min(tp.price for tp in signal.take_profit_levels)
                    reward = entry_price - lowest_tp
                else:
                    reward = entry_price - signal.take_profit
                risk = signal.stop_loss - entry_price
            
            return reward / risk if risk > 0 else 0
            
        except Exception as e:
            logging.error(f"Error calculating risk reward ratio: {e}")
            return 0

    def _generate_recommendation(self, signal: TradingSignal) -> str:
        """生成交易建议"""
        try:
            risk_level = self._assess_risk_level(signal)
            rr_ratio = self.calculate_risk_reward_ratio(signal)
            
            if risk_level == 'HIGH':
                return "🔴 高风险交易，建议减小仓位或放弃此交易机会"
            elif risk_level == 'MEDIUM':
                if rr_ratio >= 2:
                    return "🟡 中等风险，风险收益比良好，建议使用半仓位进入"
                else:
                    return "🟡 中等风险，建议等待更好的入场机会"
            else:
                if rr_ratio >= 1.5:
                    return "🟢 低风险高收益，建议按计划执行"
                else:
                    return "🟢 低风险，但收益相对较小，可以考虑增加仓位"
                    
        except Exception as e:
            logging.error(f"Error generating recommendation: {e}")
            return "无法生成建议"

    def calculate_position_size(self, account_balance: float, risk_per_trade: float,
                              signal: TradingSignal) -> float:
        """计算建议仓位大小"""
        try:
            # 基于账户风险计算
            risk_amount = account_balance * (risk_per_trade / 100)  # 风险金额
            
            entry_price = signal.entry_price
            if not entry_price and signal.entry_zones:
                prices = [zone.price for zone in signal.entry_zones]
                entry_price = sum(prices) / len(prices)
            
            # 计算每单位的风险
            stop_distance = abs(entry_price - signal.stop_loss)
            risk_per_unit = stop_distance * signal.leverage
            
            # 计算建议仓位
            position_size = risk_amount / risk_per_unit
            
            # 根据风险等级调整仓位
            risk_level = self._assess_risk_level(signal)
            if risk_level == 'HIGH':
                position_size *= 0.5
            elif risk_level == 'MEDIUM':
                position_size *= 0.75
            
            return position_size
            
        except Exception as e:
            logging.error(f"Error calculating position size: {e}")
            return 0

    async def analyze_market_context(self, signal: TradingSignal) -> Dict[str, Any]:
        """分析市场环境"""
        try:
            # TODO: 获取市场数据
            market_data = {}  # 这里应该从数据源获取市场数据
            
            analysis = {
                'market_trend': self._analyze_market_trend(market_data),
                'volume_analysis': self._analyze_volume(market_data),
                'momentum': self._analyze_momentum(market_data),
                'correlation': self._analyze_correlation(market_data),
                'sentiment': await self._analyze_market_sentiment(signal.symbol)
            }
            
            return analysis
            
        except Exception as e:
            logging.error(f"Error analyzing market context: {e}")
            return {}

    def _analyze_market_trend(self, market_data: Dict[str, Any]) -> Dict[str, str]:
        """分析市场趋势"""
        return {
            'trend_direction': 'BULLISH',
            'trend_strength': 'STRONG',
            'trend_duration': 'LONG_TERM'
        }

    def _analyze_volume(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析交易量"""
        return {
            'volume_trend': 'INCREASING',
            'volume_strength': 'HIGH',
            'unusual_activity': False
        }

    def _analyze_momentum(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析动量指标"""
        return {
            'rsi': 65,
            'macd': 'BULLISH',
            'momentum_strength': 'STRONG'
        }

    def _analyze_correlation(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析相关性"""
        return {
            'btc_correlation': 0.85,
            'market_correlation': 0.75,
            'sector_correlation': 0.90
        }

    async def _analyze_market_sentiment(self, symbol: str) -> Dict[str, Any]:
        """分析市场情绪"""
        return {
            'overall_sentiment': 'POSITIVE',
            'fear_greed_index': 65,
            'social_sentiment': 'BULLISH'
        }

    def validate_technical_levels(self, signal: TradingSignal) -> bool:
        """验证技术价位的有效性"""
        try:
            entry_price = signal.entry_price
            if not entry_price and signal.entry_zones:
                prices = [zone.price for zone in signal.entry_zones]
                entry_price = sum(prices) / len(prices)
            
            # 验证止损位置
            if signal.stop_loss:
                if signal.action == 'OPEN_LONG':
                    if signal.stop_loss >= entry_price:
                        return False
                else:
                    if signal.stop_loss <= entry_price:
                        return False
            
            # 验证止盈位置
            if signal.take_profit_levels:
                for tp in signal.take_profit_levels:
                    if signal.action == 'OPEN_LONG':
                        if tp.price <= entry_price:
                            return False
                    else:
                        if tp.price >= entry_price:
                            return False
            
            # 验证价格间隔
            min_price_distance = 0.001  # 最小价格间隔
            
            if signal.entry_zones:
                prices = sorted(zone.price for zone in signal.entry_zones)
                for i in range(1, len(prices)):
                    if abs(prices[i] - prices[i-1]) < min_price_distance:
                        return False
            
            return True
            
        except Exception as e:
            logging.error(f"Error validating technical levels: {e}")
            return False

    def adjust_for_market_conditions(self, signal: TradingSignal,
                                   market_conditions: Dict[str, Any]) -> TradingSignal:
        """根据市场条件调整信号"""
        try:
            # 根据波动性调整止损距离
            volatility = market_conditions.get('volatility', 'NORMAL')
            if volatility == 'HIGH':
                # 增加止损距离
                if signal.stop_loss:
                    entry_price = signal.entry_price or signal.entry_zones[0].price
                    current_distance = abs(entry_price - signal.stop_loss)
                    adjusted_distance = current_distance * 1.2  # 增加20%止损距离
                    
                    if signal.action == 'OPEN_LONG':
                        signal.stop_loss = entry_price - adjusted_distance
                    else:
                        signal.stop_loss = entry_price + adjusted_distance
            
            # 根据趋势强度调整止盈目标
            trend_strength = market_conditions.get('trend_strength', 'NORMAL')
            if trend_strength == 'STRONG' and signal.take_profit_levels:
                # 延长最后的止盈目标
                last_tp = signal.take_profit_levels[-1]
                entry_price = signal.entry_price or signal.entry_zones[0].price
                current_distance = abs(entry_price - last_tp.price)
                
                if signal.action == 'OPEN_LONG':
                    last_tp.price = entry_price + (current_distance * 1.2)
                else:
                    last_tp.price = entry_price - (current_distance * 1.2)
            
            return signal
            
        except Exception as e:
            logging.error(f"Error adjusting for market conditions: {e}")
            return signal

    def generate_trade_report(self, signal: TradingSignal,
                            analysis: Dict[str, Any]) -> str:
        """生成交易报告"""
        try:
            report = []
            report.append("📊 交易分析报告")
            report.append("\n🎯 交易信号:")
            report.append(f"交易对: {signal.symbol}")
            report.append(f"方向: {'做多' if signal.action == 'OPEN_LONG' else '做空'}")
            
            if signal.entry_zones:
                report.append("\n📍 入场区间:")
                for idx, zone in enumerate(signal.entry_zones, 1):
                    report.append(f"区间 {idx}: {zone.price} ({zone.percentage*100}%)")
            else:
                report.append(f"\n📍 入场价格: {signal.entry_price}")
            
            if signal.take_profit_levels:
                report.append("\n🎯 止盈目标:")
                for idx, tp in enumerate(signal.take_profit_levels, 1):
                    report.append(f"TP{idx}: {tp.price} ({tp.percentage*100}%)")
            
            report.append(f"\n🛑 止损: {signal.stop_loss}")
            
            report.append(f"\n📈 风险收益比: {self.calculate_risk_reward_ratio(signal):.2f}")
            report.append(f"⚠️ 风险等级: {self._assess_risk_level(signal)}")
            
            if analysis:
                report.append("\n📊 市场分析:")
                report.append(f"趋势: {analysis.get('trend', {}).get('direction', 'N/A')}")
                report.append(f"强度: {analysis.get('momentum', {}).get('strength', 'N/A')}")
                report.append(f"成交量: {analysis.get('volume', {}).get('trend', 'N/A')}")
            
            report.append(f"\n💡 建议: {self._generate_recommendation(signal)}")
            
            return "\n".join(report)
            
        except Exception as e:
            logging.error(f"Error generating trade report: {e}")
            return "无法生成交易报告"