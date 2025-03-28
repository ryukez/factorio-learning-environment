# Copied from eval/open/independent_runs/run.py
from dotenv import load_dotenv
import json
from env.src.models.game_state import GameState
from env.src.instance import FactorioInstance
from definitions import Step, Agent, Execution, Evaluation
from agent import BasicAgent
from evaluator import SimpleFactorioEvaluator
import asyncio
from typing import List


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


async def main():
    instance = create_factorio_instance()

    with open("game_state.json", "r") as f:
        state = GameState.parse(json.load(f))
        instance.reset(state)

    agent = BasicAgent()
    evaluator = SimpleFactorioEvaluator(instance)

    step = Step(
        number=1,
        instruction="Harvest Iron Ore",
        iteration_number=1,
        in_iteration_number=1,
    )

    execution_history = []

    output = await execute_step(agent, evaluator, step, state, execution_history)
    print(output.response)


async def execute_step(
    agent: Agent,
    evaluator: SimpleFactorioEvaluator,
    step: Step,
    game_state: GameState,
    execution_history: List[Execution],
) -> Evaluation:
    agent_output = await agent.run(step, game_state, execution_history)
    evaluator_output = await evaluator.evaluate(agent_output.code)
    return evaluator_output


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
