import pandas as pd
import talib.abstract as ta
from functools import reduce
from freqtrade.strategy import IStrategy, DecimalParameter

class FreqaiEnhanced(IStrategy):
    minimal_roi = {"0": 0.05, "60": 0.02, "120": -1}
    stoploss = -0.05
    timeframe = '5m'
    can_short = False

    # AI trigger thresholds for hyperopt to test
    buy_target_threshold = DecimalParameter(0.001, 0.010, default=0.004, space='buy', optimize=True)
    sell_target_threshold = DecimalParameter(-0.010, -0.001, default=-0.002, space='sell', optimize=True)

    def feature_engineering_expand_all(self, dataframe: pd.DataFrame, period: int, metadata: dict, **kwargs) -> pd.DataFrame:
        dataframe[f"%-rsi-period"] = ta.RSI(dataframe, timeperiod=period)
        dataframe[f"%-roc-period"] = ta.ROC(dataframe, timeperiod=period)
        dataframe[f"%-ema-period"] = ta.EMA(dataframe, timeperiod=period)
        dataframe[f"%-ema_dist-period"] = (dataframe['close'] - dataframe[f"%-ema-period"]) / dataframe[f"%-ema-period"]
        dataframe[f"%-atr-period"] = ta.ATR(dataframe, timeperiod=period)
        dataframe[f"%-atr_norm-period"] = dataframe[f"%-atr-period"] / dataframe['close']
        dataframe[f"%-mfi-period"] = ta.MFI(dataframe, timeperiod=period)
        return dataframe

    def feature_engineering_expand_basic(self, dataframe: pd.DataFrame, metadata: dict, **kwargs) -> pd.DataFrame:
        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-raw_volume"] = dataframe["volume"]
        return dataframe

    def feature_engineering_standard(self, dataframe: pd.DataFrame, metadata: dict, **kwargs) -> pd.DataFrame:
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: pd.DataFrame, metadata: dict, **kwargs) -> pd.DataFrame:
        label_candles = self.freqai_info["feature_parameters"].get("label_period_candles", 5)
        dataframe["&-s_close"] = (
            dataframe["close"].shift(-label_candles) / dataframe["close"] - 1
        )
        return dataframe

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe = self.freqai.start(dataframe, metadata, self)
        # Add the EMA 200 after FreqAI finishes stripping out non-features
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        enter_long_conditions = [
            dataframe['do_predict'] == 1,
            dataframe['&-s_close'] > self.buy_target_threshold.value,
            dataframe['close'] > dataframe['ema_200'] 
        ]
        if enter_long_conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, enter_long_conditions),
                ['enter_long', 'enter_tag']
            ] = (1, 'ai_buy')
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        exit_long_conditions = [
            dataframe['do_predict'] == 1,
            dataframe['&-s_close'] < self.sell_target_threshold.value
        ]
        if exit_long_conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, exit_long_conditions),
                ['exit_long', 'exit_tag']
            ] = (1, 'ai_sell')
        return dataframe