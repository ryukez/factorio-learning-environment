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
from agent import BasicAgent
from evaluator import SimpleFactorioEvaluator
import asyncio
from typing import List
from dataclasses import dataclass
import copy


@dataclass
class StepExecution:
    agent_output: AgentOutput
    evaluation: Evaluation


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
    evaluator_output = await evaluator.evaluate(agent_output.code)
    return StepExecution(agent_output=agent_output, evaluation=evaluator_output)


async def main():
    instance = create_factorio_instance()

    with open("game_state.json", "r") as f:
        state = GameState.parse(json.load(f))
        instance.reset(state)

    agent = BasicAgent(
        model="open-router-google/gemini-2.0-flash-001",
        system_prompt=instance.get_system_prompt(),
    )
    evaluator = SimpleFactorioEvaluator(instance)

    step = Step(
        number=1,
        instruction="Harvest Iron Ore",
        iteration_number=1,
        in_iteration_number=1,
    )

    parsed_game_state = ParsedGameState(
        raw=state,
        entities=f"{instance.namespace.get_entities()}",
    )

    execution_history = []

    data_points = []
    for i in range(3):
        execution = await execute_step(
            agent=agent,
            evaluator=evaluator,
            step=step,
            game_state=parsed_game_state,
            execution_history=execution_history,
        )

        execution = Execution(
            step=step,
            game_state=parsed_game_state,
            agent_output=execution.agent_output,
            evaluation=execution.evaluation,
        )

        data_points.append(
            copy.deepcopy(
                create_data_point(
                    collection_id="test",
                    agent_name="BasicAgent",
                    agent_version="1",
                    execution=execution,
                    execution_history=execution_history,
                ).to_json()
            )
        )

        # tick
        execution_history.append(copy.deepcopy(execution))
        step.number += 1
        step.in_iteration_number += 1
        parsed_game_state = execution.evaluation.game_state

    with open("execution.json", "w") as f:
        json.dump(data_points, f)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
