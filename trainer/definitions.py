from abc import ABC, abstractmethod
from dataclasses import dataclass
from env.src.models.game_state import GameState
from typing import List, Dict
from models.achievements import ProductionFlows
import re


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
            "research_status": self.research_status(),
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            raw=GameState.parse_raw(data["raw"]),
            entities=data["entities"],
        )

    def inventory(self) -> str:
        return format_inventory(self.raw.inventory)

    def research_status(self) -> str:
        completed = []
        for name, tech in self.raw.research.technologies.items():
            if tech.researched:
                completed.append(name)

        current_research = "None"
        if self.raw.research.current_research:
            current_research = (
                f"{self.raw.research.current_research}"
                + " ("
                + "%.1f" % (self.raw.research.research_progress * 100)
                + "%)"
            )

        completed_researchs = f"{completed}"

        return (
            "Current Research: "
            + current_research
            + "\n"
            + "Completed: "
            + completed_researchs
        )


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

    def formatted(self) -> str:
        return f"""Code Execution:
{self.response}

Achievements:
{self.achievements}
"""


line_number_pattern = re.compile(r"^(\d+): \(")

command_pattern = re.compile(
    r"(can_place_entity|connect_entities|craft_item|extract_item|get_connection_amount|get_entities|get_entity|get_prototype_recipe|get_research_progress|get_resource_patch|harvet_resource|insert_item|inspect_inventory|launch_rocket|move_to|nearest|nearest_buildable|pickup_entity|place_entity|place_entity_next_to|rorate_entity|set_entity_recipe|set_research|shift_entity)\(.*\)"
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

    def _error_line_number(self) -> int:
        eval_lines = self.evaluation.response.split("\n")

        error_line_number = None
        for line in eval_lines:
            if ": ('Error occurred:\\n" in line or ": ('\\nException:" in line:
                line_number = line_number_pattern.match(line)
                if line_number:
                    error_line_number = int(line_number.group(1))
                    break

        return error_line_number

    def passed_code(self) -> str:
        error_line_number = self._error_line_number()

        lines = self.agent_output.code.split("\n")
        pass_line_number = (
            len(lines) if error_line_number is None else error_line_number
        )

        return "\n".join(lines[:pass_line_number])

    def executed_commands(self) -> List[str]:
        passed_code = self.passed_code().split("\n")
        commands: List[str] = []

        error_line_number = self._error_line_number()
        line_num = (
            error_line_number - 1 if error_line_number else len(passed_code)
        )  # last line is not included

        for _, line in enumerate(passed_code[:line_num]):
            if command_pattern.search(line):
                commands.append(line)
        return commands


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

    @classmethod
    def from_dict(cls, data):
        return cls(
            runtime_version=data["runtime_version"],
            collection_id=data["collection_id"],
            step=Step.from_dict(data["step"]),
            execution_history=[
                Execution.from_dict(e) for e in data["execution_history"]
            ],
            input_game_state=ParsedGameState.from_dict(data["input_game_state"]),
            agent_name=data["agent_name"],
            agent_output=AgentOutput.from_dict(data["agent_output"]),
            evaluation=Evaluation.from_dict(data["evaluation"]),
            evaluated_game_state=ParsedGameState.from_dict(
                data["evaluated_game_state"]
            ),
        )


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
