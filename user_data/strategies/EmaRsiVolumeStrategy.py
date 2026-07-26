from datetime import datetime
import logging
import re

from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import DecimalParameter, IntParameter
from freqtrade.vendor.qtpylib import indicators as qtpylib

from BaseStrategy import BaseStrategy
from channels.config_loader import load_channel_config


logger = logging.getLogger(__name__)


class EmaRsiVolumeStrategy(BaseStrategy):
    """
    Estratégia com canais independentes por par.

    Ideia:
    - Cada par funciona como um canal separado.
    - Cada canal tem seu próprio contador de perdas.
    - Se o trade daquele par ganhar, o canal reseta.
    - Se perder, o próximo trade daquele par usa stake maior.
    - Se perder X vezes seguidas, o canal reseta.
    - Todos os canais usam o mesmo saldo USDT.

    Esta versão adiciona configurações diferentes por par:
    - base_stake diferente por canal
    - filtro de volume diferente por canal
    - faixa de RSI diferente por canal
    """

    INTERFACE_VERSION = 3

    timeframe = "5m"
    can_short = False

    process_only_new_candles = True
    startup_candle_count = 220

    # ROI alvo.
    # 0.005 = 0.5%
    minimal_roi = {
        "0": 0.006
    }

    # Voltei para o stop que performou melhor que -2%.
    # -0.04 = -4%
    stoploss = -0.04

    # Não usa saída por sinal.
    # Sai por ROI, stoploss ou force_exit.
    use_exit_signal = False
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Sem DCA dentro do mesmo trade.
    # Martingale acontece no próximo trade do mesmo par/canal.
    position_adjustment_enable = False
    max_entry_position_adjustment = 0

    # ---------- Parâmetros globais para Hyperopt ----------

    buy_ema_fast = IntParameter(3, 15, default=9, space="buy", optimize=True)
    buy_ema_slow = IntParameter(16, 60, default=21, space="buy", optimize=True)
    buy_ema_trend = IntParameter(100, 300, default=200, space="buy", optimize=True)

    buy_rsi_min = IntParameter(30, 60, default=45, space="buy", optimize=True)
    buy_rsi_max = IntParameter(45, 75, default=58, space="buy", optimize=True)
    buy_volume_mult = DecimalParameter(
        1.0,
        3.0,
        default=1.5,
        decimals=1,
        space="buy",
        optimize=True,
    )

    def __init__(self, config: dict) -> None:
        super().__init__(config)

        channel_config = load_channel_config(config.get("user_data_dir"))
        default_settings = channel_config["defaults"]
        martingale_settings = channel_config["martingale"]
        monitoring_settings = channel_config["monitoring"]

        # Configuração por canal carregada de user_data/channels/config.json.
        self.base_stake_amount = default_settings["base_stake"]
        self.default_pair_settings = default_settings
        self.pair_settings = channel_config["pairs"]

        self.martingale_multiplier = martingale_settings["multiplier"]
        self.reset_after_losses = martingale_settings["reset_after_losses"]
        self.max_martingale_level = martingale_settings["max_level"]
        self.max_channel_stake = martingale_settings["max_channel_stake"]
        self.channel_monitor_interval = int(monitoring_settings["log_interval_seconds"])

        # Estado dos canais.
        # Exemplo:
        # {
        #   "BTC/USDT": {"loss_streak": 2, "level": 2},
        #   "ETH/USDT": {"loss_streak": 0, "level": 0}
        # }
        self.channel_state = {}

        # Evita processar o mesmo fechamento mais de uma vez.
        self.processed_closed_trades = set()

        self.last_channel_monitor_log = None
        self.trade_summary = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "profit_abs": 0.0,
        }

    def ft_bot_cleanup(self) -> None:
        super().ft_bot_cleanup()

        if self._is_operation_mode():
            self.log_channel_summary()

    def _is_operation_mode(self) -> bool:
        return self._runmode_name() in {"dry_run", "live"}

    def _monitor_pairs(self) -> list[str]:
        exchange_config = self.config.get("exchange", {})
        whitelist = exchange_config.get("pair_whitelist", [])
        blacklist = exchange_config.get("pair_blacklist", [])
        pairs = [*whitelist, *self.pair_settings.keys(), *self.channel_state.keys()]
        unique_pairs = list(dict.fromkeys(pair for pair in pairs if "/" in pair))

        return [
            pair
            for pair in unique_pairs
            if not any(re.fullmatch(pattern, pair) for pattern in blacklist)
        ]

    def _planned_channel_stake(self, pair: str) -> float:
        state = self.get_channel_state(pair)
        settings = self.get_pair_settings(pair)
        stake = settings["base_stake"] * (self.martingale_multiplier ** state["level"])

        return min(stake, self.max_channel_stake)

    def _update_channel_monitor(
        self,
        pair: str,
        *,
        stake: float | None = None,
        result: str | None = None,
        current_time: datetime | None = None,
    ) -> None:
        state = self.get_channel_state(pair)

        if stake is None:
            stake = self._planned_channel_stake(pair)

        state["current_stake"] = float(stake)
        state["max_level_seen"] = max(state["max_level_seen"], state["level"])
        state["max_stake_seen"] = max(state["max_stake_seen"], float(stake))

        if result is not None:
            state["last_result"] = result

        if current_time is not None:
            state["last_update"] = current_time

    def _format_channel_time(self, value) -> str:
        return value.isoformat() if value is not None else "never"

    def log_channel_monitor(self, current_time: datetime) -> None:
        logger.info("Martingale channel monitor")

        for pair in self._monitor_pairs():
            self._update_channel_monitor(pair)
            state = self.get_channel_state(pair)
            logger.info(
                (
                    "channel=%s level=%s loss_streak=%s current_stake=%.4f "
                    "last_result=%s last_update=%s"
                ),
                pair,
                state["level"],
                state["loss_streak"],
                state["current_stake"],
                state["last_result"],
                self._format_channel_time(state["last_update"]),
            )

        self.last_channel_monitor_log = current_time

    def log_channel_summary(self) -> None:
        logger.info(
            (
                "Dry run summary total_trades=%s wins=%s losses=%s profit_abs=%.8f"
            ),
            self.trade_summary["total_trades"],
            self.trade_summary["wins"],
            self.trade_summary["losses"],
            self.trade_summary["profit_abs"],
        )

        for pair in self._monitor_pairs():
            self._update_channel_monitor(pair)
            state = self.get_channel_state(pair)
            logger.info(
                (
                    "channel_summary=%s max_level_seen=%s max_stake_seen=%.4f "
                    "current_level=%s current_loss_streak=%s last_result=%s "
                    "last_update=%s"
                ),
                pair,
                state["max_level_seen"],
                state["max_stake_seen"],
                state["level"],
                state["loss_streak"],
                state["last_result"],
                self._format_channel_time(state["last_update"]),
            )

    def get_pair_settings(self, pair: str) -> dict:
        """
        Retorna configurações específicas do par.
        Se o par não estiver configurado, usa padrão.
        """

        return self.pair_settings.get(pair, self.default_pair_settings)

    def get_channel_state(self, pair: str) -> dict:
        """
        Cria ou retorna o estado do canal daquele par.
        """

        if pair not in self.channel_state:
            self.channel_state[pair] = {
                "loss_streak": 0,
                "level": 0,
                "current_stake": 0.0,
                "last_result": "NONE",
                "last_update": None,
                "max_level_seen": 0,
                "max_stake_seen": 0.0,
            }

        return self.channel_state[pair]

    def bot_loop_start(self, current_time: datetime, **kwargs) -> None:
        if not self._is_operation_mode():
            return

        if self.channel_monitor_interval <= 0:
            return

        if self.last_channel_monitor_log is not None:
            seconds_since_last_log = (
                current_time - self.last_channel_monitor_log
            ).total_seconds()
            if seconds_since_last_log < self.channel_monitor_interval:
                return

        self.log_channel_monitor(current_time)

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        """
        Define o tamanho da entrada de acordo com o canal/par.

        Exemplo:
        - BTC level 0 usa base_stake de BTC.
        - BTC level 1 usa base_stake * multiplicador.
        - ETH pode usar outro base_stake.
        """

        state = self.get_channel_state(pair)
        settings = self.get_pair_settings(pair)

        level = state["level"]
        base_stake = settings["base_stake"]

        stake = base_stake * (self.martingale_multiplier ** level)

        # Limite máximo por canal.
        stake = min(stake, self.max_channel_stake)

        # Limite máximo permitido pelo Freqtrade/carteira.
        stake = min(stake, max_stake)

        # Respeita mínimo da exchange, se existir.
        if min_stake is not None:
            stake = max(stake, min_stake)

        self._update_channel_monitor(pair, stake=stake, current_time=current_time)

        return stake

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entrada com parâmetros globais otimizáveis.

        A configuração por par continua sendo usada para:
        - base_stake é usado no custom_stake_amount

        Os filtros de volume, RSI e EMA são globais para Hyperopt.
        """

        ema_fast = dataframe[f"ema_fast_{self.buy_ema_fast.value}"]
        ema_slow = dataframe[f"ema_slow_{self.buy_ema_slow.value}"]
        ema_trend = dataframe[f"ema_trend_{self.buy_ema_trend.value}"]

        dataframe.loc[
            (
                qtpylib.crossed_above(ema_fast, ema_slow)
                & (dataframe["close"] > ema_trend)
                & (ema_slow > ema_trend)
                & (dataframe["rsi"] > self.buy_rsi_min.value)
                & (dataframe["rsi"] < self.buy_rsi_max.value)
                & (dataframe["volume"] > dataframe["volume_mean_20"] * self.buy_volume_mult.value)
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Saída por sinal desativada.
        O trade sai por ROI, stoploss ou force_exit.
        """

        dataframe["exit_long"] = 0

        if self._is_backtest_mode():
            from evaluation.shadow_trades import add_shadow_decisions
            from reports.framework_report import record_framework_report_data
            from reports.research_dataset import record_research_feature_frame

            dataframe = add_shadow_decisions(dataframe)
            dataframe = record_research_feature_frame(dataframe, metadata, self.config)
            dataframe = record_framework_report_data(dataframe, metadata, self.config)

        return dataframe

    def confirm_trade_exit(
        self,
        pair: str,
        trade: Trade,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        exit_reason: str,
        current_time: datetime,
        **kwargs,
    ) -> bool:
        """
        Atualiza o canal quando um trade fecha.

        Se o trade fechou positivo:
            reseta o canal.

        Se o trade fechou negativo:
            aumenta loss_streak e level.

        Se loss_streak chegar em reset_after_losses:
            reseta o canal.
        """

        # Chave única aproximada para evitar processar o mesmo trade 2 vezes.
        trade_key = f"{pair}-{trade.open_date_utc}-{trade.open_rate}-{exit_reason}"

        if trade_key in self.processed_closed_trades:
            return True

        self.processed_closed_trades.add(trade_key)

        state = self.get_channel_state(pair)

        profit_ratio = trade.calc_profit_ratio(rate)
        profit_abs = 0.0
        try:
            profit_abs = float(trade.calc_profit(rate))
        except Exception:
            logger.warning("Could not calculate absolute profit for %s", pair)

        result = "WIN" if profit_ratio > 0 else "LOSS"

        self.trade_summary["total_trades"] += 1
        self.trade_summary["profit_abs"] += profit_abs
        if result == "WIN":
            self.trade_summary["wins"] += 1
        else:
            self.trade_summary["losses"] += 1

        if profit_ratio > 0:
            # Ganhou: reseta o canal.
            state["loss_streak"] = 0
            state["level"] = 0

        else:
            # Perdeu: aumenta contador.
            state["loss_streak"] += 1

            # Se chegou no limite de perdas, reseta.
            if state["loss_streak"] >= self.reset_after_losses:
                state["loss_streak"] = 0
                state["level"] = 0
            else:
                # Sobe o nível do martingale para o próximo trade daquele par.
                state["level"] = min(
                    state["loss_streak"],
                    self.max_martingale_level,
                )

        self._update_channel_monitor(pair, result=result, current_time=current_time)

        return True

    class HyperOpt:
        @staticmethod
        def roi_space():
            from freqtrade.optimize.space import SKDecimal

            return [SKDecimal(0.001, 0.02, decimals=3, name="roi_p")]

        @staticmethod
        def generate_roi_table(params: dict) -> dict[int, float]:
            return {0: params["roi_p"]}

        @staticmethod
        def stoploss_space():
            from freqtrade.optimize.space import SKDecimal

            return [SKDecimal(-0.08, -0.01, decimals=3, name="stoploss")]
