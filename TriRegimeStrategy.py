import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy, IntParameter

class TriRegimeStrategy(IStrategy):
    timeframe = '4h'
    # 200 candles on 4h = 33 days of history. Plenty for our indicators.
    startup_candle_count = 200 
    can_short = False
    
    # Hyperopt parameters for RSI thresholds
    buy_rsi = IntParameter(15, 45, default=30, space='buy', optimize=True)
    sell_rsi = IntParameter(55, 85, default=70, space='sell', optimize=True)

    stoploss = -0.10
    minimal_roi = {"0": 100}

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # 50 EMA on 4h chart = ~8.3 days (Macro Trend)
        dataframe['ema_macro'] = ta.EMA(dataframe, timeperiod=50)
        
        # 14 ADX on 4h chart = ~2.3 days (Trend Strength)
        dataframe['adx_macro'] = ta.ADX(dataframe, timeperiod=14)

        # Local (4h) Indicators for entries
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_lowerband'] = bollinger['lowerband']
        dataframe['bb_middleband'] = bollinger['middleband']
        dataframe['bb_upperband'] = bollinger['upperband']

        # Define Regimes (Lowered ADX threshold to 20 since 4h trends are smoother)
        dataframe['regime_bull'] = (dataframe['close'] > dataframe['ema_macro']) & (dataframe['adx_macro'] > 20)
        dataframe['regime_bear'] = (dataframe['close'] < dataframe['ema_macro']) & (dataframe['adx_macro'] > 20)
        dataframe['regime_crab'] = (dataframe['adx_macro'] <= 20)

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[:, 'enter_long'] = 0
        dataframe.loc[:, 'enter_short'] = 0

        dataframe.loc[
            (dataframe['regime_bull'] == True) &
            (dataframe['rsi'] < self.buy_rsi.value),
            'enter_long'] = 1

        dataframe.loc[
            (dataframe['regime_bear'] == True) &
            (dataframe['rsi'] > self.sell_rsi.value),
            'enter_short'] = 1

        dataframe.loc[
            (dataframe['regime_crab'] == True) &
            (dataframe['close'] < dataframe['bb_lowerband']),
            'enter_long'] = 1

        dataframe.loc[
            (dataframe['regime_crab'] == True) &
            (dataframe['close'] > dataframe['bb_upperband']),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[:, 'exit_long'] = 0
        dataframe.loc[:, 'exit_short'] = 0

        dataframe.loc[
            (dataframe['rsi'] > self.sell_rsi.value),
            'exit_long'] = 1
        
        dataframe.loc[
            (dataframe['rsi'] < self.buy_rsi.value),
            'exit_short'] = 1

        return dataframe