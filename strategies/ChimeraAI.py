import logging
import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy

logger = logging.getLogger(__name__)

def EWO(dataframe, ema_length=5, ema2_length=35):
    df = dataframe.copy()
    ema1 = ta.EMA(df, timeperiod=ema_length)
    ema2 = ta.EMA(df, timeperiod=ema2_length)
    emadif = (ema1 - ema2) / df['close'] * 100
    return emadif

def supertrend(dataframe, multiplier, period):
    df = dataframe.copy()
    df['TR'] = ta.TRANGE(df)
    df['ATR'] = ta.SMA(df['TR'], timeperiod=period)

    st = 'ST_' + str(period) + '_' + str(multiplier)
    stx = 'STX_' + str(period) + '_' + str(multiplier)

    df['basic_ub'] = (df['high'] + df['low']) / 2 + multiplier * df['ATR']
    df['basic_lb'] = (df['high'] + df['low']) / 2 - multiplier * df['ATR']
    df['final_ub'] = 0.00
    df['final_lb'] = 0.00
    for i in range(period, len(df)):
        df['final_ub'].iat[i] = df['basic_ub'].iat[i] if df['basic_ub'].iat[i] < df['final_ub'].iat[i - 1] or df['close'].iat[i - 1] > df['final_ub'].iat[i - 1] else df['final_ub'].iat[i - 1]
        df['final_lb'].iat[i] = df['basic_lb'].iat[i] if df['basic_lb'].iat[i] > df['final_lb'].iat[i - 1] or df['close'].iat[i - 1] < df['final_lb'].iat[i - 1] else df['final_lb'].iat[i - 1]
    
    df[st] = 0.00
    for i in range(period, len(df)):
        df[st].iat[i] = df['final_ub'].iat[i] if df[st].iat[i - 1] == df['final_ub'].iat[i - 1] and df['close'].iat[i] <= df['final_ub'].iat[i] else \
                        df['final_lb'].iat[i] if df[st].iat[i - 1] == df['final_ub'].iat[i - 1] and df['close'].iat[i] >  df['final_ub'].iat[i] else \
                        df['final_lb'].iat[i] if df[st].iat[i - 1] == df['final_lb'].iat[i - 1] and df['close'].iat[i] >= df['final_lb'].iat[i] else \
                        df['final_ub'].iat[i] if df[st].iat[i - 1] == df['final_lb'].iat[i - 1] and df['close'].iat[i] <  df['final_lb'].iat[i] else 0.00
    
    df[stx] = np.where((df[st] > 0.00), np.where((df['close'] < df[st]), -1, 1), 0)
    return df

class ChimeraAI(IStrategy):
    """
    ChimeraAI: Bandtastic + Supertrend + NostalgiaForInfinityX7
    Powered by FreqAI
    """
    INTERFACE_VERSION = 3
    timeframe = '5m'
    can_short = False
    
    # Minimal ROI
    minimal_roi = {
        "0": 0.05,
        "30": 0.02,
        "60": 0.01,
        "120": 0
    }
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int, metadata: dict, **kwargs) -> DataFrame:
        """
        Extract features from the 3 strategies for FreqAI to analyze.
        All features must be prefixed with `%-` to be recognized by FreqAI.
        """
        # ==========================================
        # 1. BANDTASTIC FEATURES (Mean Reversion)
        # ==========================================
        dataframe['%-rsi'] = ta.RSI(dataframe, timeperiod=period)
        dataframe['%-mfi'] = ta.MFI(dataframe, timeperiod=period)
        
        for std in [1, 2, 3, 4]:
            bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=period, stds=std)
            dataframe[f'%-bb_lowerband_{std}'] = bollinger['lower']
            dataframe[f'%-bb_middleband_{std}'] = bollinger['mid']
            dataframe[f'%-bb_upperband_{std}'] = bollinger['upper']
            # Add distance to lower band as a feature
            dataframe[f'%-bb_lower_dist_{std}'] = (dataframe['close'] - bollinger['lower']) / dataframe['close']

        # ==========================================
        # 2. SUPERTREND FEATURES (Trend Following)
        # ==========================================
        # FreqAI handles standard indicators best when they are numeric.
        st_data = supertrend(dataframe, multiplier=3.0, period=period)
        dataframe[f'%-supertrend_dir_{period}'] = st_data[f'STX_{period}_3.0']

        # ==========================================
        # 3. NFI FEATURES (Momentum/Waves)
        # ==========================================
        dataframe['%-ewo'] = EWO(dataframe, ema_length=5, ema2_length=35)
        dataframe['%-ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['%-ema_200'] = ta.EMA(dataframe, timeperiod=200)

        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        Add basic time/volume features. Prefix with `%-`.
        """
        dataframe['%-volume'] = dataframe['volume']
        dataframe['%-day_of_week'] = dataframe['date'].dt.dayofweek
        dataframe['%-hour_of_day'] = dataframe['date'].dt.hour
        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        Add standard features. Prefix with `%` (no dash).
        """
        dataframe['%pct-change'] = dataframe['close'].pct_change()
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        Define what FreqAI is trying to predict.
        Here we want to predict the price change 15 candles into the future.
        """
        dataframe['&-target'] = (dataframe['close'].shift(-15) / dataframe['close']) - 1
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        This is where FreqAI hooks in and populates the predictions.
        """
        dataframe = self.freqai.start(dataframe, metadata, self)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on FreqAI's prediction (`do_predict`), we enter trades.
        """
        enter_long_conditions = []
        
        # If FreqAI predicts the price will go up by more than 1% (0.01)
        if 'do_predict' in dataframe.columns:
            enter_long_conditions.append(dataframe['do_predict'] == 1)
            enter_long_conditions.append(dataframe['&-target'] > 0.01)

        if enter_long_conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, enter_long_conditions),
                'enter_long'
            ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on FreqAI's prediction, we exit trades.
        """
        exit_long_conditions = []

        # If FreqAI predicts the price will drop by more than 0.5% (-0.005)
        if 'do_predict' in dataframe.columns:
            exit_long_conditions.append(dataframe['do_predict'] == 1)
            exit_long_conditions.append(dataframe['&-target'] < -0.005)

        if exit_long_conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, exit_long_conditions),
                'exit_long'
            ] = 1

        return dataframe

from functools import reduce
