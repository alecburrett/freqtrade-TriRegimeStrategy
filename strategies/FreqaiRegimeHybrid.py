import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy, DecimalParameter

class FreqaiRegimeHybrid(IStrategy):
    """
    The Ultimate Hybrid:
    Combines Machine Learning (FreqAI) with Macro Regime Filters (ADX/EMA).
    - Bull Market: AI is only allowed to go Long.
    - Bear Market: AI is only allowed to go Short.
    - Crab Market: AI can do both (mean reversion).
    """
    timeframe = '5m'
    startup_candle_count = 2000
    can_short = True

    # AI Conviction Thresholds (Hyperopt will tune these)
    buy_target_threshold = DecimalParameter(0.001, 0.020, default=0.008, space='buy', optimize=True)
    sell_target_threshold = DecimalParameter(-0.020, -0.001, default=-0.008, space='sell', optimize=True)

    # Risk Management (Hyperopt will tune these)
    stoploss = -0.10
    minimal_roi = {"0": 100}

    def feature_engineering_expand_all(self, dataframe: pd.DataFrame, period: int, metadata: dict, **kwargs) -> pd.DataFrame:
        dataframe[f"%-rsi-period"] = ta.RSI(dataframe, timeperiod=period)
        dataframe[f"%-roc-period"] = ta.ROC(dataframe, timeperiod=period)
        
        ema = ta.EMA(dataframe, timeperiod=period)
        dataframe[f"%-ema_dist-period"] = (dataframe['close'] - ema) / ema
        
        atr = ta.ATR(dataframe, timeperiod=period)
        dataframe[f"%-atr_norm-period"] = atr / dataframe['close']
        
        dataframe[f"%-mfi-period"] = ta.MFI(dataframe, timeperiod=period)
        return dataframe

    def feature_engineering_expand_basic(self, dataframe: pd.DataFrame, metadata: dict, **kwargs) -> pd.DataFrame:
        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-volume_mean_ratio"] = dataframe["volume"] / ta.SMA(dataframe["volume"], timeperiod=20)
        return dataframe

    def feature_engineering_standard(self, dataframe: pd.DataFrame, metadata: dict, **kwargs) -> pd.DataFrame:
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: pd.DataFrame, metadata: dict, **kwargs) -> pd.DataFrame:
        label_candles = self.freqai_info["feature_parameters"].get("label_period_candles", 5)
        dataframe["&-s_close"] = (dataframe["close"].shift(-label_candles) / dataframe["close"]) - 1
        return dataframe

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # 1. Run FreqAI (Injects AI Predictions)
        dataframe = self.freqai.start(dataframe, metadata, self)
        
        # 2. Calculate Macro Regime Filters natively on 5m data
        dataframe['ema_macro'] = ta.EMA(dataframe, timeperiod=1152) # 4 Days
        dataframe['adx_macro'] = ta.ADX(dataframe, timeperiod=288)  # 1 Day

        dataframe['regime_bull'] = (dataframe['close'] > dataframe['ema_macro']) & (dataframe['adx_macro'] > 20)
        dataframe['regime_bear'] = (dataframe['close'] < dataframe['ema_macro']) & (dataframe['adx_macro'] > 20)
        dataframe['regime_crab'] = (dataframe['adx_macro'] <= 20)

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[:, 'enter_long'] = 0
        dataframe.loc[:, 'enter_short'] = 0

        # AI Long Logic: Only permitted in Bull or Crab markets
        long_mask = (
            (dataframe['do_predict'] == 1) &
            (dataframe['&-s_close'] > self.buy_target_threshold.value) &
            (dataframe['regime_bull'] | dataframe['regime_crab'])
        )
        dataframe.loc[long_mask, ['enter_long', 'enter_tag']] = (1, 'ai_bull_long')

        # AI Short Logic: Only permitted in Bear or Crab markets
        short_mask = (
            (dataframe['do_predict'] == 1) &
            (dataframe['&-s_close'] < self.sell_target_threshold.value) &
            (dataframe['regime_bear'] | dataframe['regime_crab'])
        )
        dataframe.loc[short_mask, ['enter_short', 'enter_tag']] = (1, 'ai_bear_short')

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[:, 'exit_long'] = 0
        dataframe.loc[:, 'exit_short'] = 0
        # AI relies completely on Hyperopted ROI and Trailing Stoploss for exits
        return dataframe
