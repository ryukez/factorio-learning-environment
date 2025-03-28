from abc import ABC, abstractmethod
from dataclasses import dataclass
from env.src.models.game_state import GameState
from typing import List, Dict
from models.achievements import ProductionFlows


@dataclass
class Step:
    number: int
    instruction: str
    iteration_number: int
    in_iteration_number: int

    def to_json(self):
        return {
            "number": self.number,
            "instruction": self.instruction,
            "iteration_number": self.iteration_number,
            "in_iteration_number": self.in_iteration_number,
        }


@dataclass
class ParsedGameState:
    raw: GameState
    entities: str

    def to_json(self):
        return {
            "raw": self.raw.to_raw(),
            "entities": self.entities,
        }


@dataclass
class Message:
    role: str
    content: str


@dataclass
class AgentOutput:
    input_messages: List[Message]
    raw_response: str
    thinking: str
    code: str

    def to_json(self):
        return {
            "input_messages": [
                {"role": m.role, "content": m.content} for m in self.input_messages
            ],
            "raw_response": self.raw_response,
            "thinking": self.thinking,
            "code": self.code,
        }

    def to_json_partial(self):
        return {
            "thinking": self.thinking,
            "code": self.code,
        }


@dataclass
class Evaluation:
    game_state: ParsedGameState
    response: str
    reward: float
    achievements: Dict
    flows: ProductionFlows
    ticks: int

    def to_json(self):
        return {
            "game_state": self.game_state.to_json(),
            "response": self.response,
            "reward": self.reward,
            "achievements": self.achievements,
            "flows": self.flows.to_dict(),
            "ticks": self.ticks,
        }

    def to_json_partial(self):
        return {
            "response": self.response,
            "reward": self.reward,
            "achievements": self.achievements,
            "flows": self.flows.to_dict(),
            "ticks": self.ticks,
        }


@dataclass
class Execution:
    step: Step
    game_state: ParsedGameState
    agent_output: AgentOutput
    evaluation: Evaluation

    def to_json(self):
        return {
            "step": self.step.to_json(),
            "game_state": self.game_state.to_json(),
            "agent_output": self.agent_output.to_json(),
            "evaluation": self.evaluation.to_json(),
        }

    def to_json_partial(self):
        return {
            "step": self.step.to_json(),
            "agent_output": self.agent_output.to_json_partial(),
            "evaluation": self.evaluation.to_json_partial(),
        }


class Agent(ABC):
    @abstractmethod
    async def run(
        self,
        step: Step,
        game_state: ParsedGameState,
        execution_history: List[Execution],
    ) -> AgentOutput:
        pass
