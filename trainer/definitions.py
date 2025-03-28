from abc import ABC, abstractmethod
from dataclasses import dataclass
from env.src.models.game_state import GameState
from typing import List


@dataclass
class Step:
    number: int
    instruction: str
    iteration_number: int
    in_iteration_number: int


@dataclass
class Message:
    role: str
    content: str


@dataclass
class AgentOutput:
    input_messages: List[Message]
    raw_response: str
    thinkng: str
    code: str


@dataclass
class Evaluation:
    game_state: GameState
    response: str


@dataclass
class Execution:
    step: Step
    game_state: GameState
    agent_output: AgentOutput
    evaluation: Evaluation


class Agent(ABC):
    @abstractmethod
    async def run(
        self,
        step: Step,
        game_state: GameState,
        execution_history: List[Execution],
    ) -> AgentOutput:
        pass
