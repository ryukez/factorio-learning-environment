# Copied from eval/open/independent_runs/run.py
from dotenv import load_dotenv
import json
from env.src.models.game_state import GameState
from env.src.instance import FactorioInstance
from trainer.definitions import (
    Step,
    Agent,
    Execution,
    Evaluation,
    AgentOutput,
    ParsedGameState,
    Message,
    DataPoint,
    create_data_point,
)
from trainer.agent import IterationAgent
from trainer.evaluator import SimpleFactorioEvaluator
import asyncio
from typing import List
from dataclasses import dataclass
import copy


@dataclass
class StepExecution:
    agent_output: AgentOutput | None
    evaluation: Evaluation | None
    evaluated_game_state: ParsedGameState | None


def create_factorio_instance():
    ip = "192.168.0.108"
    tcp_port = 27000

    instance = FactorioInstance(
        address=ip,
        tcp_port=tcp_port,
        bounding_box=200,
        fast=True,
        cache_scripts=True,
        inventory={},
        all_technologies_researched=True,
    )
    instance.speed(1)
    return instance


async def execute_step(
    agent: Agent,
    evaluator: SimpleFactorioEvaluator,
    step: Step,
    game_state: ParsedGameState,
    execution_history: List[Execution],
) -> StepExecution:
    agent_output = await agent.run(step, game_state, execution_history)
    evaluated_game_state, evaluator_output = await evaluator.evaluate(agent_output.code)

    return StepExecution(
        agent_output=agent_output,
        evaluation=evaluator_output,
        evaluated_game_state=evaluated_game_state,
    )


async def main():
    instance = create_factorio_instance()

    agent = IterationAgent(
        model="open-router-google/gemini-2.5-pro-preview-03-25",
        system_prompt=instance.get_system_prompt(),
    )
    evaluator = SimpleFactorioEvaluator(instance)

    data_points: List[DataPoint] = []
    with open("datasets/20250401_100.jsonl", "r") as f:
        for line in f:
            data_points.append(DataPoint.from_dict(json.loads(line)))

    results: List[DataPoint] = []
    for i, dp in enumerate(data_points):
        print(f"Processing {i + 1} / {len(data_points)}")

        execution = await execute_step(
            agent, evaluator, dp.step, dp.input_game_state, dp.execution_history
        )
        # print("Agent Thinking:", execution.agent_output.thinking)
        # print("Agent Code:", execution.agent_output.code)
        print("Evaluation:", execution.evaluation.to_dict())
        results.append(
            DataPoint(
                runtime_version=dp.runtime_version,
                collection_id=dp.collection_id,
                step=dp.step,
                execution_history=dp.execution_history,
                input_game_state=dp.input_game_state,
                agent_name=agent.name(),
                agent_output=execution.agent_output,
                evaluation=execution.evaluation,
                evaluated_game_state=execution.evaluated_game_state,
            )
        )

    with open("results.jsonl", "w") as f:
        for result in results:
            f.write(json.dumps(result.to_dict()) + "\n")


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
