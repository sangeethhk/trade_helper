from abc import ABC, abstractmethod
from typing import Optional, List
import pandas as pd
from core.models import PatternResult, CalibrationParams

class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def detect(self, df: pd.DataFrame, symbol: str, timeframe: str, calibration: Optional[CalibrationParams] = None) -> Optional[PatternResult]:
        """
        Analyze candlestick DataFrame and return a PatternResult if the pattern is detected,
        else return None.
        """
        pass
