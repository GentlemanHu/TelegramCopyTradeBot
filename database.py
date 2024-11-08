# database.py
import sqlite3
from typing import List, Dict, Optional, Any
import logging
from datetime import datetime, date
import json
from models import TradingSignal, EntryZone, TakeProfitLevel

class Database:
    def __init__(self, db_name: str):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.setup_database()
        

    def setup_database(self):
        """初始化数据库表"""
        self.cursor.executescript('''
            CREATE TABLE IF NOT EXISTS channels (
                channel_id INTEGER PRIMARY KEY,
                channel_name TEXT,
                channel_username TEXT,
                channel_type TEXT CHECK(channel_type IN ('MONITOR', 'FORWARD')),
                prompt TEXT,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS channel_pairs (
                monitor_channel_id INTEGER,
                forward_channel_id INTEGER,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                PRIMARY KEY (monitor_channel_id, forward_channel_id),
                FOREIGN KEY (monitor_channel_id) REFERENCES channels(channel_id),
                FOREIGN KEY (forward_channel_id) REFERENCES channels(channel_id)
            );

            CREATE TABLE IF NOT EXISTS strategy_settings (
                id INTEGER PRIMARY KEY,
                strategy_name TEXT NOT NULL,
                default_position_size REAL DEFAULT 50.0,
                default_leverage INTEGER DEFAULT 50,
                enable_dynamic_sl BOOLEAN DEFAULT true,
                tp_distribution TEXT,
                entry_distribution TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS signal_tracking (
                id INTEGER PRIMARY KEY,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                entry_price REAL,
                current_price REAL,
                position_size REAL,
                leverage INTEGER,
                margin_mode TEXT,
                entry_zones TEXT,
                take_profit_levels TEXT,
                stop_loss REAL,
                dynamic_sl BOOLEAN DEFAULT false,
                status TEXT DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source_message TEXT,
                source_channel INTEGER,
                FOREIGN KEY(source_channel) REFERENCES channels(channel_id)
            );

            CREATE TABLE IF NOT EXISTS order_tracking (
                id INTEGER PRIMARY KEY,
                signal_id INTEGER,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                order_id TEXT NOT NULL,
                order_type TEXT NOT NULL,
                price REAL,
                size REAL,
                status TEXT DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                extra_info TEXT,
                FOREIGN KEY(signal_id) REFERENCES signal_tracking(id)
            );

            CREATE TABLE IF NOT EXISTS tp_hit_history (
                id INTEGER PRIMARY KEY,
                signal_id INTEGER,
                tp_level INTEGER,
                price REAL,
                amount REAL,
                pnl REAL,
                hit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(signal_id) REFERENCES signal_tracking(id)
            );

            CREATE TABLE IF NOT EXISTS trade_statistics (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                exchange TEXT NOT NULL,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                largest_win REAL DEFAULT 0,
                largest_loss REAL DEFAULT 0,
                average_win REAL DEFAULT 0,
                average_loss REAL DEFAULT 0,
                win_rate REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, exchange)
            );
            CREATE INDEX IF NOT EXISTS idx_signal_tracking_status 
            ON signal_tracking(status);

            CREATE INDEX IF NOT EXISTS idx_signal_tracking_symbol 
            ON signal_tracking(symbol);

            CREATE INDEX IF NOT EXISTS idx_order_tracking_signal_id 
            ON order_tracking(signal_id);

            CREATE INDEX IF NOT EXISTS idx_channels_type 
            ON channels(channel_type);

            CREATE INDEX IF NOT EXISTS idx_trade_statistics_date 
            ON trade_statistics(date);
            
            
            CREATE TABLE IF NOT EXISTS risk_metrics (
                id INTEGER PRIMARY KEY,
                exchange TEXT NOT NULL,
                margin_usage REAL,
                total_exposure REAL,
                account_health TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS account_status (
            exchange TEXT PRIMARY KEY,
            total_equity REAL,
            used_margin REAL,
            available_margin REAL,
            margin_ratio REAL,
            last_update TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        self.conn.commit()

    # 频道管理方法

    def remove_channel(self, channel_id: int) -> bool:
        """移除频道"""
        try:
            # 停用配对
            self.cursor.execute('''
                UPDATE channel_pairs 
                SET is_active = 0 
                WHERE monitor_channel_id = ? OR forward_channel_id = ?
            ''', (channel_id, channel_id))
            
            # 停用频道
            self.cursor.execute('''
                UPDATE channels 
                SET is_active = 0 
                WHERE channel_id = ?
            ''', (channel_id,))
            
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error in remove_channel: {e}")
            return False

    # 信号跟踪方法
    def add_signal_tracking(self, signal: TradingSignal) -> int:
        """添加信号跟踪记录"""
        try:
            self.cursor.execute('''
                INSERT INTO signal_tracking (
                    exchange, symbol, signal_type, entry_price,
                    position_size, leverage, margin_mode,
                    entry_zones, take_profit_levels, stop_loss,
                    dynamic_sl, source_message, source_channel
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal.exchange,
                signal.symbol,
                signal.action,
                signal.entry_price,
                signal.position_size,
                signal.leverage,
                signal.margin_mode,
                json.dumps([{
                    'price': ez.price,
                    'percentage': ez.percentage,
                    'status': ez.status
                } for ez in signal.entry_zones]) if signal.entry_zones else None,
                json.dumps([{
                    'price': tp.price,
                    'percentage': tp.percentage,
                    'is_hit': tp.is_hit,
                    'hit_time': tp.hit_time.isoformat() if tp.hit_time else None
                } for tp in signal.take_profit_levels]) if signal.take_profit_levels else None,
                signal.stop_loss,
                signal.dynamic_sl,
                signal.source_message,
                getattr(signal, 'source_channel', None)
            ))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            logging.error(f"Error in add_signal_tracking: {e}")
            return -1

    def get_active_signals(self, exchange: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取活动信号"""
        try:
            query = '''
                SELECT * FROM signal_tracking
                WHERE status IN ('PENDING', 'ACTIVE')
            '''
            if exchange:
                query += ' AND exchange = ?'
                self.cursor.execute(query, (exchange,))
            else:
                self.cursor.execute(query)

            columns = [description[0] for description in self.cursor.description]
            signals = []
            
            for row in self.cursor.fetchall():
                signal_dict = dict(zip(columns, row))
                
                # 解析JSON字段
                if signal_dict.get('entry_zones'):
                    signal_dict['entry_zones'] = [
                        EntryZone(**zone) for zone in json.loads(signal_dict['entry_zones'])
                    ]
                if signal_dict.get('take_profit_levels'):
                    signal_dict['take_profit_levels'] = [
                        TakeProfitLevel(**tp) for tp in json.loads(signal_dict['take_profit_levels'])
                    ]
                    
                signals.append(signal_dict)
                
            return signals
        except sqlite3.Error as e:
            logging.error(f"Error in get_active_signals: {e}")
            return []

    def update_risk_metrics(self, metrics: Dict[str, Any]) -> bool:
        """更新风险指标"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO risk_metrics (
                    exchange, margin_usage, total_exposure, account_health,
                    updated_at
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                metrics['exchange'],
                metrics['margin_usage'],
                metrics['total_exposure'],
                metrics['account_health']
            ))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error updating risk metrics: {e}")
            return False

    def update_signal_status(self, signal_id: int, status: str, 
                           current_price: Optional[float] = None,
                           extra_info: Optional[Dict] = None) -> bool:
        """更新信号状态"""
        try:
            update_fields = ['status = ?', 'updated_at = CURRENT_TIMESTAMP']
            params = [status]
            
            if current_price is not None:
                update_fields.append('current_price = ?')
                params.append(current_price)
                
            if extra_info:
                update_fields.append('extra_info = ?')
                params.append(json.dumps(extra_info))
                
            params.append(signal_id)
            
            self.cursor.execute(f'''
                UPDATE signal_tracking
                SET {', '.join(update_fields)}
                WHERE id = ?
            ''', params)
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error in update_signal_status: {e}")
            return False

    # 订单跟踪方法
    def add_order_tracking(self, order_data: Dict[str, Any]) -> bool:
        """添加订单跟踪"""
        try:
            self.cursor.execute('''
                INSERT INTO order_tracking (
                    signal_id, exchange, symbol, order_id,
                    order_type, price, size, status, extra_info
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                order_data['signal_id'],
                order_data['exchange'],
                order_data['symbol'],
                order_data['order_id'],
                order_data['order_type'],
                order_data['price'],
                order_data['size'],
                order_data['status'],
                json.dumps(order_data.get('extra_info', {}))
            ))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error in add_order_tracking: {e}")
            return False

    # 统计方法
    def update_trade_statistics(self, trade_data: Dict[str, Any]) -> bool:
        """更新交易统计"""
        try:
            today = date.today().isoformat()
            
            self.cursor.execute('''
                INSERT INTO trade_statistics (
                    date, exchange, total_trades, winning_trades,
                    losing_trades, total_pnl, largest_win,
                    largest_loss
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?)
                ON CONFLICT(date, exchange) DO UPDATE SET
                    total_trades = total_trades + 1,
                    winning_trades = winning_trades + ?,
                    losing_trades = losing_trades + ?,
                    total_pnl = total_pnl + ?,
                    largest_win = MAX(largest_win, ?),
                    largest_loss = MIN(largest_loss, ?)
            ''', (
                today,
                trade_data['exchange'],
                1 if trade_data['pnl'] > 0 else 0,
                1 if trade_data['pnl'] < 0 else 0,
                trade_data['pnl'],
                trade_data['pnl'] if trade_data['pnl'] > 0 else 0,
                trade_data['pnl'] if trade_data['pnl'] < 0 else 0,
                1 if trade_data['pnl'] > 0 else 0,
                1 if trade_data['pnl'] < 0 else 0,
                trade_data['pnl'],
                trade_data['pnl'] if trade_data['pnl'] > 0 else 0,
                trade_data['pnl'] if trade_data['pnl'] < 0 else 0
            ))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error in update_trade_statistics: {e}")
            return False

    # 策略设置方法
    def get_strategy_settings(self) -> Dict[str, Any]:
        """获取策略设置"""
        try:
            self.cursor.execute('''
                SELECT * FROM strategy_settings
                WHERE id = 1
            ''')
            row = self.cursor.fetchone()
            if row:
                result = {
                    'default_position_size': row[2],
                    'default_leverage': row[3],
                    'enable_dynamic_sl': row[4]
                }
                if row[5]:  # tp_distribution
                    result['tp_distribution'] = json.loads(row[5])
                if row[6]:  # entry_distribution
                    result['entry_distribution'] = json.loads(row[6])
                return result
            return None
        except sqlite3.Error as e:
            logging.error(f"Error in get_strategy_settings: {e}")
            return None

    def update_strategy_settings(self, settings: Dict[str, Any]) -> bool:
        """更新策略设置"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO strategy_settings (
                    id, strategy_name, default_position_size,
                    default_leverage, enable_dynamic_sl,
                    tp_distribution, entry_distribution
                ) VALUES (1, ?, ?, ?, ?, ?, ?)
            ''', (
                settings.get('strategy_name', 'default'),
                settings.get('default_position_size', 50.0),
                settings.get('default_leverage', 50),
                settings.get('enable_dynamic_sl', True),
                json.dumps(settings.get('tp_distribution')) if settings.get('tp_distribution') else None,
                json.dumps(settings.get('entry_distribution')) if settings.get('entry_distribution') else None
            ))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error in update_strategy_settings: {e}")
            
    def get_channel_pairs(self) -> List[Dict[str, Any]]:
            """获取所有频道配对"""
            try:
                self.cursor.execute('''
                    SELECT cp.*, m.channel_name as monitor_name, f.channel_name as forward_name
                    FROM channel_pairs cp
                    JOIN channels m ON cp.monitor_channel_id = m.channel_id
                    JOIN channels f ON cp.forward_channel_id = f.channel_id
                    WHERE cp.is_active = 1
                ''')
                pairs = [{
                    'monitor_channel_id': row[0],
                    'forward_channel_id': row[1],
                    'monitor_name': row[3],
                    'forward_name': row[4]
                } for row in self.cursor.fetchall()]
                return pairs
            except sqlite3.Error as e:
                logging.error(f"Error in get_channel_pairs: {e}")
                return []


    def get_channels_by_type(self, channel_type: str) -> List[Dict[str, Any]]:
        """获取指定类型的所有频道"""
        try:
            self.cursor.execute('''
                SELECT channel_id, channel_name, channel_username, prompt, is_active 
                FROM channels 
                WHERE channel_type = ? AND is_active = 1
            ''', (channel_type,))
            return [{
                'channel_id': row[0],
                'channel_name': row[1],
                'channel_username': row[2],
                'prompt': row[3],
                'is_active': row[4]
            } for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Error in get_channels_by_type: {e}")
            return []

    def update_channel_prompt(self, channel_id: int, prompt: str) -> bool:
        """更新频道的prompt"""
        try:
            self.cursor.execute('''
                UPDATE channels 
                SET prompt = ? 
                WHERE channel_id = ?
            ''', (prompt, channel_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error in update_channel_prompt: {e}")
            return False


    def get_recent_trades(self, days: int = 30) -> List[Dict[str, Any]]:
        """获取最近的交易记录"""
        try:
            self.cursor.execute('''
                SELECT * FROM order_tracking
                WHERE created_at >= date('now', ?)
                AND order_type = 'CLOSE'
                ORDER BY created_at DESC
            ''', (f'-{days} days',))
            
            columns = [description[0] for description in self.cursor.description]
            trades = []
            
            for row in self.cursor.fetchall():
                trade_dict = dict(zip(columns, row))
                # 解析JSON额外信息
                if trade_dict.get('extra_info'):
                    trade_dict['extra_info'] = json.loads(trade_dict['extra_info'])
                trades.append(trade_dict)
                
            return trades
        except sqlite3.Error as e:
            logging.error(f"Error in get_recent_trades: {e}")
            return []

    def get_trade_history(self, start_date: str, end_date: str, 
                         exchange: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取交易历史"""
        try:
            query = '''
                SELECT * FROM trade_statistics
                WHERE date BETWEEN ? AND ?
            '''
            params = [start_date, end_date]
            
            if exchange:
                query += " AND exchange = ?"
                params.append(exchange)
                
            self.cursor.execute(query, params)
            
            columns = [description[0] for description in self.cursor.description]
            return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Error in get_trade_history: {e}")
            return []

    def add_tp_hit(self, signal_id: int, tp_level: int, price: float, 
                  amount: float, pnl: float) -> bool:
        """记录止盈触发"""
        try:
            self.cursor.execute('''
                INSERT INTO tp_hit_history (
                    signal_id, tp_level, price, amount, pnl
                ) VALUES (?, ?, ?, ?, ?)
            ''', (signal_id, tp_level, price, amount, pnl))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error in add_tp_hit: {e}")
            return False

    def update_order_status(self, order_id: str, status: str, 
                          extra_info: Optional[Dict] = None) -> bool:
        """更新订单状态"""
        try:
            if extra_info:
                self.cursor.execute('''
                    UPDATE order_tracking
                    SET status = ?, 
                        extra_info = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE order_id = ?
                ''', (status, json.dumps(extra_info), order_id))
            else:
                self.cursor.execute('''
                    UPDATE order_tracking
                    SET status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE order_id = ?
                ''', (status, order_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error in update_order_status: {e}")
            return False

    def cleanup(self):
        """清理并关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def get_signal_orders(self, signal_id: int) -> List[Dict[str, Any]]:
        """获取信号相关的订单"""
        try:
            self.cursor.execute('''
                SELECT * FROM order_tracking 
                WHERE signal_id = ?
                ORDER BY created_at DESC
            ''', (signal_id,))
            
            columns = [description[0] for description in self.cursor.description]
            return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Error in get_signal_orders: {e}")
            return []
        
        
    def get_pending_signals(self) -> List[Dict[str, Any]]:
        """获取所有待处理的信号"""
        try:
            self.cursor.execute('''
                SELECT * FROM signal_tracking 
                WHERE status = 'PENDING'
                ORDER BY created_at DESC
            ''')
            
            columns = [description[0] for description in self.cursor.description]
            return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Error in get_pending_signals: {e}")
            return []

    def get_signal_orders(self, signal_id: int) -> List[Dict[str, Any]]:
        """获取信号相关的订单"""
        try:
            self.cursor.execute('''
                SELECT * FROM order_tracking 
                WHERE signal_id = ?
                ORDER BY created_at DESC
            ''', (signal_id,))
            
            columns = [description[0] for description in self.cursor.description]
            return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Error in get_signal_orders: {e}")
            return []

    def update_signal_status(self, signal_id: int, status: str) -> bool:
        """更新信号状态"""
        try:
            self.cursor.execute('''
                UPDATE signal_tracking
                SET status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, signal_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error updating signal status: {e}")
            return False
        
        

            
    def update_account_status(self, exchange: str, status: Dict[str, Any]) -> bool:
        """更新账户状态"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO account_status (
                    exchange,
                    total_equity,
                    used_margin,
                    available_margin,
                    margin_ratio,
                    last_update
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                exchange,
                status['total_equity'],
                status['used_margin'],
                status['available_margin'],
                status['margin_ratio'],
                status['last_update'].isoformat() if isinstance(status['last_update'], datetime) else status['last_update']
            ))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error updating account status: {e}")
            return False
        
        

    def check_forward_channel(self, channel_id: int) -> bool:
        """检查转发频道是否存在且有效"""
        try:
            self.cursor.execute('''
                SELECT COUNT(*) 
                FROM channels 
                WHERE channel_id = ? 
                AND channel_type = 'FORWARD' 
                AND is_active = 1
            ''', (channel_id,))
            count = self.cursor.fetchone()[0]
            return count > 0
        except sqlite3.Error as e:
            logging.error(f"Error checking forward channel: {e}")
            return False

    def get_channel_forward_settings(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """获取频道的转发设置"""
        try:
            self.cursor.execute('''
                SELECT c.*, cp.monitor_channel_id 
                FROM channels c
                LEFT JOIN channel_pairs cp ON c.channel_id = cp.forward_channel_id
                WHERE c.channel_id = ? AND c.is_active = 1
            ''', (channel_id,))
            
            row = self.cursor.fetchone()
            if not row:
                return None
                
            columns = [description[0] for description in self.cursor.description]
            return dict(zip(columns, row))
            
        except sqlite3.Error as e:
            logging.error(f"Error getting channel forward settings: {e}")
            return None
        
        
    def update_channel_status(self, channel_id: int, is_active: bool) -> bool:
        """更新频道状态"""
        try:
            self.cursor.execute('''
                UPDATE channels 
                SET is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE channel_id = ?
            ''', (is_active, channel_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error updating channel status: {e}")
            return False

    def add_channel(self, channel_id: int, channel_name: str, 
                   channel_username: Optional[str], channel_type: str,
                   prompt: Optional[str] = None) -> bool:
        """添加新频道"""
        try:
            # 直接使用原始channel_id
            self.cursor.execute('''
                INSERT OR REPLACE INTO channels 
                (channel_id, channel_name, channel_username, channel_type, prompt) 
                VALUES (?, ?, ?, ?, ?)
            ''', (channel_id, channel_name, channel_username, channel_type, prompt))
            self.conn.commit()
            logging.info(f"Added channel: {channel_id} ({channel_name})")
            return True
        except sqlite3.Error as e:
            logging.error(f"Error in add_channel: {e}")
            return False

    def add_channel_pair(self, monitor_channel_id: int, forward_channel_id: int) -> bool:
        """添加频道配对"""
        try:
            # 直接使用原始ID
            self.cursor.execute('''
                INSERT OR REPLACE INTO channel_pairs 
                (monitor_channel_id, forward_channel_id) 
                VALUES (?, ?)
            ''', (monitor_channel_id, forward_channel_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error in add_channel_pair: {e}")
            return False

    def get_channel_info(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """获取频道信息"""
        try:
            self.cursor.execute('''
                SELECT * FROM channels WHERE channel_id = ?
            ''', (channel_id,))
            row = self.cursor.fetchone()
            if row:
                return {
                    'channel_id': row[0],
                    'channel_name': row[1],
                    'channel_username': row[2],
                    'channel_type': row[3],
                    'prompt': row[4],
                    'is_active': row[6]
                }
            return None
        except sqlite3.Error as e:
            logging.error(f"Error in get_channel_info: {e}")
            return None
    def _normalize_channel_id(self, channel_id: int) -> int:
        """将频道ID转换为正确的格式"""
        # 将正数ID转换为完整的负数形式
        str_id = str(abs(channel_id))
        if not str_id.startswith('100'):
            str_id = '100' + str_id
        return -int(str_id)
    def get_forward_channels(self, monitor_channel_id: int) -> List[Dict[str, Any]]:
        """获取监控频道对应的所有转发频道"""
        try:
            monitor_id = monitor_channel_id #self._normalize_channel_id(monitor_channel_id)
            self.cursor.execute('''
                SELECT c.* 
                FROM channels c
                JOIN channel_pairs cp ON c.channel_id = cp.forward_channel_id
                WHERE cp.monitor_channel_id = ? 
                AND cp.is_active = 1 
                AND c.is_active = 1
            ''', (monitor_id,))
            
            return [{
                'channel_id': row[0],
                'channel_name': row[1],
                'channel_username': row[2]
            } for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Error in get_forward_channels: {e}")
            return []

    def get_signal_info(self, signal_id: int) -> Optional[Dict[str, Any]]:
        """获取信号信息"""
        try:
            self.cursor.execute('''
                SELECT * FROM signal_tracking WHERE id = ?
            ''', (signal_id,))
            
            row = self.cursor.fetchone()
            if not row:
                return None
                
            columns = [description[0] for description in self.cursor.description]
            signal_info = dict(zip(columns, row))
            
            # 解析JSON字段
            try:
                if signal_info.get('entry_zones'):
                    signal_info['entry_zones'] = json.loads(signal_info['entry_zones'])
                if signal_info.get('take_profit_levels'):
                    signal_info['take_profit_levels'] = json.loads(signal_info['take_profit_levels'])
                if signal_info.get('extra_info'):
                    signal_info['extra_info'] = json.loads(signal_info['extra_info'])
            except json.JSONDecodeError as e:
                logging.error(f"Error parsing JSON in signal info: {e}")
            
            return signal_info
            
        except sqlite3.Error as e:
            logging.error(f"Error getting signal info: {e}")
            return None