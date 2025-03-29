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
            "flows": self.flows.to_dict() if self.flows else None,
            "ticks": self.ticks,
        }

    def to_json_partial(self):
        return {
            "response": self.response,
            "reward": self.reward,
            "achievements": self.achievements,
            "flows": self.flows.to_dict() if self.flows else None,
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


@dataclass
class DataPoint:
    collection_id: str

    game_state: ParsedGameState
    step: Step
    execution_history: List[Execution]

    agent_name: str
    agent_version: str

    agent_output: AgentOutput
    evaluation: Evaluation

    def to_json(self):
        return {
            "collection_id": self.collection_id,
            "game_state": self.game_state.to_json(),
            "step": self.step.to_json(),
            "execution_history": [e.to_json_partial() for e in self.execution_history],
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
            "agent_output": self.agent_output.to_json(),
            "evaluation": self.evaluation.to_json_partial(),
        }


def create_data_point(
    collection_id: str,
    agent_name: str,
    agent_version: str,
    execution: Execution,
    execution_history: List[Execution],
) -> DataPoint:
    return DataPoint(
        collection_id=collection_id,
        game_state=execution.game_state,
        step=execution.step,
        execution_history=execution_history,
        agent_name="BasicAgent",
        agent_version="1",
        agent_output=execution.agent_output,
        evaluation=execution.evaluation,
    )
