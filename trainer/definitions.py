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

    def to_dict(self):
        return {
            "number": self.number,
            "instruction": self.instruction,
            "iteration_number": self.iteration_number,
            "in_iteration_number": self.in_iteration_number,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            number=data["number"],
            instruction=data["instruction"],
            iteration_number=data["iteration_number"],
            in_iteration_number=data["in_iteration_number"],
        )


def format_inventory(inventory) -> str:
    dic = inventory if isinstance(inventory, dict) else inventory.__dict__

    slot = 0
    for item, count in dic.items():
        slot += (count - 1) // 50 + 1
    return f"{inventory}, {max(80 - slot, 0)} slots remaining"


@dataclass
class ParsedGameState:
    raw: GameState
    entities: str

    def to_dict(self):
        return {
            "raw": self.raw.to_raw(),
            "entities": self.entities,
            "inventory": self.inventory(),
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            raw=GameState.parse_raw(data["raw"]),
            entities=data["entities"],
        )

    def inventory(self) -> str:
        return format_inventory(self.raw.inventory)


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

    def to_dict(self):
        return {
            "input_messages": [
                {"role": m.role, "content": m.content} for m in self.input_messages
            ],
            "raw_response": self.raw_response,
            "thinking": self.thinking,
            "code": self.code,
        }

    def to_dict_partial(self):
        return {
            "input_messages": [],
            "raw_response": self.raw_response,
            "thinking": self.thinking,
            "code": self.code,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            input_messages=[
                Message(role=m["role"], content=m["content"])
                for m in data["input_messages"]
            ],
            raw_response=data["raw_response"],
            thinking=data["thinking"],
            code=data["code"],
        )


@dataclass
class Evaluation:
    response: str
    reward: float
    achievements: Dict
    flows: ProductionFlows
    ticks: int

    def to_dict(self):
        return {
            "response": self.response,
            "reward": self.reward,
            "achievements": self.achievements,
            "flows": self.flows.to_dict() if self.flows else None,
            "ticks": self.ticks,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            response=data["response"],
            reward=data["reward"],
            achievements=data["achievements"],
            flows=ProductionFlows.from_dict(data["flows"]) if data["flows"] else None,
            ticks=data["ticks"],
        )


@dataclass
class Execution:
    step: Step
    agent_output: AgentOutput
    evaluation: Evaluation

    def to_dict(self):
        return {
            "step": self.step.to_dict(),
            "agent_output": self.agent_output.to_dict_partial(),
            "evaluation": self.evaluation.to_dict(),
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            step=Step.from_dict(data["step"]),
            agent_output=AgentOutput.from_dict(data["agent_output"]),
            evaluation=Evaluation.from_dict(data["evaluation"]),
        )


class Agent(ABC):
    @abstractmethod
    async def run(
        self,
        step: Step,
        game_state: ParsedGameState,
        execution_history: List[Execution],
    ) -> AgentOutput:
        pass


@dataclass
class DataPoint:
    runtime_version: str

    collection_id: str

    step: Step
    execution_history: List[Execution]
    input_game_state: ParsedGameState

    agent_name: str

    agent_output: AgentOutput
    evaluation: Evaluation
    evaluated_game_state: ParsedGameState

    def to_dict(self):
        return {
            "runtime_version": self.runtime_version,
            "collection_id": self.collection_id,
            "step": self.step.to_dict(),
            "execution_history": [e.to_dict() for e in self.execution_history],
            "input_game_state": self.input_game_state.to_dict(),
            "agent_name": self.agent_name,
            "agent_output": self.agent_output.to_dict(),
            "evaluation": self.evaluation.to_dict(),
            "evaluated_game_state": self.evaluated_game_state.to_dict(),
        }


def create_data_point(
    runtime_version: str,
    collection_id: str,
    agent_name: str,
    input_game_state: ParsedGameState,
    execution: Execution,
    execution_history: List[Execution],
    evaluated_game_state: ParsedGameState,
) -> DataPoint:
    return DataPoint(
        runtime_version=runtime_version,
        collection_id=collection_id,
        step=execution.step,
        execution_history=execution_history,
        input_game_state=input_game_state,
        agent_name=agent_name,
        agent_output=execution.agent_output,
        evaluation=execution.evaluation,
        evaluated_game_state=evaluated_game_state,
    )
