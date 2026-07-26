from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pandas import DataFrame


class StrategyPlugin(ABC):
    """Minimal interface for experimental strategy ideas."""

    @abstractmethod
    def get_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_parameters(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def populate_entry(
        self,
        dataframe: DataFrame,
        metadata: dict[str, Any],
        parameters: dict[str, Any],
    ) -> DataFrame:
        raise NotImplementedError

    @abstractmethod
    def populate_exit(
        self,
        dataframe: DataFrame,
        metadata: dict[str, Any],
        parameters: dict[str, Any],
    ) -> DataFrame:
        raise NotImplementedError


class EmptySignalPlugin(StrategyPlugin):
    """Base skeleton for future ideas. It intentionally creates no signals."""

    name = "EmptySignalPlugin"

    def get_name(self) -> str:
        return self.name

    def get_parameters(self) -> dict[str, Any]:
        return {}

    def populate_entry(
        self,
        dataframe: DataFrame,
        metadata: dict[str, Any],
        parameters: dict[str, Any],
    ) -> DataFrame:
        dataframe["enter_long"] = 0
        return dataframe

    def populate_exit(
        self,
        dataframe: DataFrame,
        metadata: dict[str, Any],
        parameters: dict[str, Any],
    ) -> DataFrame:
        dataframe["exit_long"] = 0
        return dataframe
