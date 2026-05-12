import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy, IntParameter, merge_informative_pair


class TriRegimeStrategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = '15m'
    informative_timeframe = '1h'

    startup_candle_count = 300
    can_short = False
    process_only_new_candles = True

    # Entry-only parameters
    buy_rsi = IntParameter(15, 45, default=30, space='buy', optimize=True)
    bear_buy_rsi = IntParameter(10, 25, default=20, space='buy', optimize=True)

    # Exit-only parameters (split from entry params to stop hyperopt bleeding)
    exit_rsi = IntParameter(55, 85, default=70, space='sell', optimize=True)
    bear_exit_rsi = IntParameter(40, 65, default=50, space='sell', optimize=True)

    stoploss = -0.10
    minimal_roi = {"0": 100}

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [(pair, self.informative_timeframe) for pair in pairs]

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        informative = self.dp.get_pair_dataframe(
            pair=metadata['pair'], timeframe=self.informative_timeframe
        )
        informative['ema_macro'] = ta.EMA(informative, timeperiod=50)
        informative['adx_macro'] = ta.ADX(informative, timeperiod=14)
        informative['regime_bull'] = (
            (informative['close'] > informative['ema_macro'])
            & (informative['adx_macro'] > 20)
        )
        informative['regime_bear'] = (
            (informative['close'] < informative['ema_macro'])
            & (informative['adx_macro'] > 20)
        )
        informative['regime_crab'] = informative['adx_macro'] <= 20

        dataframe = merge_informative_pair(
            dataframe, informative, self.timeframe, self.informative_timeframe, ffill=True
        )

        suffix = f'_{self.informative_timeframe}'
        dataframe['regime_bull'] = dataframe[f'regime_bull{suffix}'].fillna(False).astype(bool)
        dataframe['regime_bear'] = dataframe[f'regime_bear{suffix}'].fillna(False).astype(bool)
        dataframe['regime_crab'] = dataframe[f'regime_crab{suffix}'].fillna(False).astype(bool)

        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_lowerband'] = bollinger['lowerband']
        dataframe['bb_middleband'] = bollinger['middleband']
        dataframe['bb_upperband'] = bollinger['upperband']

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[:, 'enter_long'] = 0
        dataframe.loc[:, 'enter_tag'] = ''

        bull_cond = (
            dataframe['regime_bull']
            & (dataframe['rsi'] < self.buy_rsi.value)
            & (dataframe['volume'] > 0)
        )
        dataframe.loc[bull_cond, 'enter_long'] = 1
        dataframe.loc[bull_cond, 'enter_tag'] = 'bull_pullback'

        bear_cond = (
            dataframe['regime_bear']
            & (dataframe['rsi'] < self.bear_buy_rsi.value)
            & (dataframe['volume'] > 0)
        )
        dataframe.loc[bear_cond, 'enter_long'] = 1
        dataframe.loc[bear_cond, 'enter_tag'] = 'bear_oversold'

        crab_cond = (
            dataframe['regime_crab']
            & (dataframe['close'] < dataframe['bb_lowerband'])
            & (dataframe['volume'] > 0)
        )
        dataframe.loc[crab_cond, 'enter_long'] = 1
        dataframe.loc[crab_cond, 'enter_tag'] = 'crab_lower'

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Exit logic lives in custom_exit so it can branch on enter_tag
        # (regime-flip exits, BB-middle for crab longs, regime-specific RSI exits).
        dataframe.loc[:, 'exit_long'] = 0
        return dataframe

    def custom_exit(self, pair: str, trade, current_time, current_rate: float,
                    current_profit: float, **kwargs):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        last = dataframe.iloc[-1].squeeze()

        tag = trade.enter_tag or ''

        if tag == 'bull_pullback' and not bool(last['regime_bull']):
            return 'regime_flip'
        if tag == 'bear_oversold' and not bool(last['regime_bear']):
            return 'regime_flip'
        if tag == 'crab_lower' and not bool(last['regime_crab']):
            return 'regime_flip'

        if tag == 'bull_pullback' and last['rsi'] > self.exit_rsi.value:
            return 'bull_rsi_exit'
        if tag == 'bear_oversold' and last['rsi'] > self.bear_exit_rsi.value:
            return 'bear_bounce_exit'
        if tag == 'crab_lower' and current_rate >= last['bb_middleband']:
            return 'crab_middle_exit'

        return None
