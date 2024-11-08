# config.py
from dataclasses import dataclass, field
import json
from typing import Any, Dict, Optional
import os
from datetime import datetime

@dataclass
class ProxyConfig:
    """代理配置"""
    enable_proxy: bool = False
    proxy_url: Optional[str] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    
    @property
    def formatted_proxy_url(self) -> Optional[str]:
        """获取格式化的代理URL"""
        if not self.enable_proxy or not self.proxy_url:
            return None
            
        if self.proxy_username and self.proxy_password:
            # 在URL中添加认证信息
            schema = self.proxy_url.split('://')[0]
            host = self.proxy_url.split('://')[1]
            return f"{schema}://{self.proxy_username}:{self.proxy_password}@{host}"
        return self.proxy_url
        
    def get_ccxt_proxy(self) -> dict:
        """获取CCXT格式的代理配置"""
        if not self.enable_proxy or not self.proxy_url:
            return {}
        return {
            'http': self.formatted_proxy_url,
            'https': self.formatted_proxy_url
        }

@dataclass
class ExchangeConfig:
    """交易所配置"""
    # Binance配置
    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet_api_key: str = ""
    binance_testnet_api_secret: str = ""
    
    # OKX配置
    okx_api_key: str = ""
    okx_api_secret: str = ""
    okx_passphrase: str = ""
    okx_testnet_api_key: str = ""
    okx_testnet_api_secret: str = ""
    okx_testnet_passphrase: str = ""

@dataclass
class TradingConfig:
    """交易配置"""
    auto_trade_enabled: bool = False
    use_testnet: bool = True
    default_position_size: float = 50.0
    default_leverage: int = 50
    max_leverage: int = 50
    enable_dynamic_sl: bool = True
    
    # 风险控制
    max_position_size: float = 1000.0
    max_daily_trades: int = 10
    max_drawdown_percentage: float = 10.0
    risk_warning_margin_ratio: float = 80.0
    risk_warning_loss_percentage: float = 20.0
    risk_warning_holding_time: int = 48
    
    
def get_default_strategy_settings() -> Dict[str, Any]:
    """返回默认策略设置"""
    return {
        'default_entry_distribution': [
            {'position': 'left', 'percentage': 0.3},
            {'position': 'middle', 'percentage': 0.5},
            {'position': 'right', 'percentage': 0.2}
        ],
        'default_tp_distribution': [
            {'level': 1, 'percentage': 0.4},
            {'level': 2, 'percentage': 0.3},
            {'level': 3, 'percentage': 0.3}
        ],
        'dynamic_sl_settings': {
            'enable': True,
            'move_to_break_even_at_tp': 1  # 第一个止盈触发后移动止损
        }
    }


@dataclass
class Config:
    """统一配置管理"""
    # Telegram配置
    TELEGRAM_TOKEN: str = field(default_factory=lambda: os.getenv("TELEGRAM_TOKEN", "123"))  # 保留默认值，方便测试
    API_ID: str = field(default_factory=lambda: os.getenv("API_ID", "123"))  # 保留默认值，方便测试
    API_HASH: str = field(default_factory=lambda: os.getenv("API_HASH", "123")) # 添加API_HASH默认值
    PHONE_NUMBER: str = field(default_factory=lambda: os.getenv("PHONE_NUMBER", "123")) # 添加PHONE_NUMBER默认值
    SESSION_NAME: str = field(default_factory=lambda: os.getenv("SESSION_NAME", "123"))
    OWNER_ID: int = field(default_factory=lambda: int(os.getenv("OWNER_ID", "123")))

    # OpenAI配置
    OPENAI_API_KEY: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", "123")) # 添加OPENAI_API_KEY默认值
    OPENAI_API_BASE_URL: str = field(default_factory=lambda: os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1")) # 添加OPENAI_API_BASE_URL默认值

    # 数据库配置
    DATABASE_NAME: str = field(default_factory=lambda: os.getenv("DATABASE_NAME", ""))

    # 代理配置
    proxy: ProxyConfig = field(default_factory=lambda: ProxyConfig(
        enable_proxy=os.getenv("ENABLE_PROXY", "false").lower() == "true",
        proxy_url=os.getenv("PROXY_URL") or os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY"),
        proxy_username=os.getenv("PROXY_USERNAME"),
        proxy_password=os.getenv("PROXY_PASSWORD")
    ))

    # 交易所配置
    exchange: ExchangeConfig = field(default_factory=lambda: ExchangeConfig(
        binance_api_key=os.getenv("BINANCE_API_KEY", ""),
        binance_api_secret=os.getenv("BINANCE_API_SECRET", ""),
        binance_testnet_api_key=os.getenv("BINANCE_TESTNET_API_KEY", ""), # 添加BINANCE_TESTNET默认值
        binance_testnet_api_secret=os.getenv("BINANCE_TESTNET_API_SECRET", ""), # 添加BINANCE_TESTNET默认值
        okx_api_key=os.getenv("OKX_API_KEY", ""),
        okx_api_secret=os.getenv("OKX_API_SECRET", ""),
        okx_passphrase=os.getenv("OKX_PASSPHRASE", ""),
        okx_testnet_api_key=os.getenv("OKX_TESTNET_API_KEY",  ""), # 添加OKX_TESTNET默认值
        okx_testnet_api_secret=os.getenv("OKX_TESTNET_API_SECRET", ""), # 添加OKX_TESTNET默认值
        okx_testnet_passphrase=os.getenv("OKX_TESTNET_PASSPHRASE", "") # 添加OKX_TESTNET默认值
    ))

    # 交易配置
    trading: TradingConfig = field(default_factory=lambda: TradingConfig(
        auto_trade_enabled=os.getenv("AUTO_TRADE_ENABLED", "true").lower() == "true",
        use_testnet=os.getenv("USE_TESTNET", "true").lower() == "true",
        default_position_size=float(os.getenv("DEFAULT_POSITION_SIZE", "50.0")),
        default_leverage=int(os.getenv("DEFAULT_LEVERAGE", "50")),
        max_leverage=int(os.getenv("MAX_LEVERAGE", "50")),
        enable_dynamic_sl=os.getenv("ENABLE_DYNAMIC_SL", "true").lower() == "true",
        max_position_size=float(os.getenv("MAX_POSITION_SIZE", "1000.0")),
        max_daily_trades=int(os.getenv("MAX_DAILY_TRADES", "10")),
        max_drawdown_percentage=float(os.getenv("MAX_DRAWDOWN_PERCENTAGE", "10.0")),
        risk_warning_margin_ratio=float(os.getenv("RISK_WARNING_MARGIN_RATIO", "80.0")),
        risk_warning_loss_percentage=float(os.getenv("RISK_WARNING_LOSS_PERCENTAGE", "20.0")),
        risk_warning_holding_time=int(os.getenv("RISK_WARNING_HOLDING_TIME", "48"))
    ))

    # 策略配置
    STRATEGY_SETTINGS: Dict[str, Any] = field(default_factory=get_default_strategy_settings)
    
    def __post_init__(self):
        """验证配置"""
        self._validate_config()
        self._load_custom_strategy()
    
    def _validate_config(self):
        """验证必要的配置项"""
        if not self.TELEGRAM_TOKEN:
            raise ValueError("Telegram token is required")
        if not self.OWNER_ID:
            raise ValueError("Owner ID is required")
        if not self.OPENAI_API_KEY:
            raise ValueError("OpenAI API key is required")
            
    def _load_custom_strategy(self):
        """加载自定义策略配置"""
        custom_strategy_file = "strategy_settings.json"
        if os.path.exists(custom_strategy_file):
            try:
                with open(custom_strategy_file, 'r') as f:
                    custom_settings = json.load(f)
                    self.STRATEGY_SETTINGS.update(custom_settings)
            except Exception as e:
                print(f"Error loading custom strategy settings: {e}")

    def get_exchange_config(self, exchange: str) -> Dict[str, str]:
        """获取特定交易所的配置"""
        exchange = exchange.upper()
        if exchange == "BINANCE":
            if self.trading.use_testnet:
                return {
                    "api_key": self.exchange.binance_testnet_api_key,
                    "api_secret": self.exchange.binance_testnet_api_secret,
                    "testnet": True,
                    "proxies": self.proxy.get_ccxt_proxy()
                }
            return {
                "api_key": self.exchange.binance_api_key,
                "api_secret": self.exchange.binance_api_secret,
                "testnet": False,
                "proxies": self.proxy.get_ccxt_proxy()
            }
        elif exchange == "OKX":
            if self.trading.use_testnet:
                return {
                    "api_key": self.exchange.okx_testnet_api_key,
                    "api_secret": self.exchange.okx_testnet_api_secret,
                    "passphrase": self.exchange.okx_testnet_passphrase,
                    "testnet": True,
                    "proxies": self.proxy.get_ccxt_proxy()
                }
            return {
                "api_key": self.exchange.okx_api_key,
                "api_secret": self.exchange.okx_api_secret,
                "passphrase": self.exchange.okx_passphrase,
                "testnet": False,
                "proxies": self.proxy.get_ccxt_proxy()
            }
        return {}

    def save_strategy_settings(self, settings: Dict[str, Any]):
        """保存自定义策略设置"""
        with open("strategy_settings.json", 'w') as f:
            json.dump(settings, f, indent=4)
        self.STRATEGY_SETTINGS.update(settings)
        
        
    def _validate_config(self):
        """验证必要的配置项"""
        if not self.TELEGRAM_TOKEN:
            raise ValueError("Telegram token is required")
        if not self.OWNER_ID:
            raise ValueError("Owner ID is required")
        if not self.OPENAI_API_KEY:
            raise ValueError("OpenAI API key is required")
            
    def _load_custom_strategy(self):
        """加载自定义策略配置"""
        custom_strategy_file = "strategy_settings.json"
        if os.path.exists(custom_strategy_file):
            try:
                with open(custom_strategy_file, 'r') as f:
                    import json
                    custom_settings = json.load(f)
                    self.STRATEGY_SETTINGS.update(custom_settings)
            except Exception as e:
                print(f"Error loading custom strategy settings: {e}")

