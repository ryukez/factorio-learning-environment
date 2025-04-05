from abc import ABC, abstractmethod
from enum import Enum


class InputKey(Enum):
    INSTRUCTION = "instruction"


class OutputKey(Enum):
    UPDATE_SYSTEM_STATUS = "update_system_status"
    INSERT_ITERATION_DATA = "insert_iteration_data"
    INSERT_STEP_DATA = "insert_step_data"
    UPDATE_STEP_EVALUATION = "update_step_evaluation"
    UPDATE_ITERATION_SUMMARY = "update_iteration_summary"


class HumanInterface(ABC):
    """人間とのインターフェースを抽象化するクラス"""

    @abstractmethod
    async def input(self, key: InputKey, context) -> str:
        """人間からの入力を取得する"""
        pass

    @abstractmethod
    async def output(self, key: OutputKey, data):
        """人間にデータを出力する"""
        pass
