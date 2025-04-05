# Copied from eval/open/independent_runs/trajectory_runner.py
import asyncio
import copy
from dataclasses import dataclass
import multiprocessing
from dotenv import load_dotenv

from instance import FactorioInstance
from extension.core.agent import IterationAgent
from extension.core.definitions import (
    Step,
    Execution,
    ParsedGameState,
    AgentOutput,
    create_data_point,
)
from extension.core.evaluator import SimpleFactorioEvaluator
from extension.core.db import SQLliteDBClient

from eval.tasks.task_abc import TaskABC
import os
from typing import List
from extension.freeplay.human_interface import (
    HumanInterface,
)
from extension.freeplay.spreadsheet_interface import SpreadsheetHumanInterface
from extension.freeplay.cli_interface import CLIHumanInterface
from extension.freeplay.human_interface import InputKey, OutputKey

load_dotenv()

COURTESY_SLEEP = 5


@dataclass
class PlayConfig:
    """Configuration for evaluation"""

    task: TaskABC
    model: str
    version: int
    version_description: str
    runtime_version: str


class TrajectoryRunner:
    """Handles program generation and evaluation for a single trajectory"""

    def __init__(
        self,
        agent: IterationAgent,
        evaluator: SimpleFactorioEvaluator,
        config: PlayConfig,
        human_interface: HumanInterface,
    ):
        self.agent = agent
        self.evaluator = evaluator
        self.config = config
        self.iteration_times = []
        self.human_interface = human_interface

        self.db = SQLliteDBClient(
            min_connections=2,
            max_connections=5,
            database_file=os.getenv("SQLITE_DB_FILE"),
        )

    def _is_model_compatible_with_n_samples(self, model):
        """Check if model supports batch sampling"""
        return "gpt" in model or "o1" in model or "gemini" in model

    async def _generate_program(
        self,
        step: Step,
        game_state: ParsedGameState,
        execution_history: List[Execution],
    ) -> AgentOutput:
        return await self.agent.run(
            step=step,
            game_state=game_state,
            execution_history=execution_history,
        )

    async def run(self):
        """Run a single trajectory"""
        # Initialize state based on resume or fresh start
        import time

        self.start_time = time.time()

        print(self.start_time)

        collection_id = f"{self.config.model}/{self.config.version}"
        agent_name = self.agent.name()
        runtime_version = self.config.runtime_version

        game_state = None
        # Continue
        if self.config.version:
            (
                step,
                game_state,
                execution_history,
            ) = await self.db.get_resume_state(collection_id=collection_id)

            if game_state:
                instance = self.evaluator.instance
                instance.reset(game_state.raw)

        # New game
        if not game_state:
            instance = self.evaluator.instance

            raw_state = self.config.task.starting_game_state
            instance.reset(raw_state)

            step = Step(
                number=0,
                instruction="- Build the biggest possible factory\n- Maximise automation, efficiency and scale",
                iteration_number=0,
                in_iteration_number=0,
            )
            game_state = ParsedGameState(
                raw=raw_state,
                entities=f"{instance.namespace.get_entities()}",
            )
            execution_history = []

        # Run trajectory
        STEPS_PER_ITERATION = 10

        while True:
            step.iteration_number += 1
            print(f"### Iteration {step.iteration_number} ###")

            await self.human_interface.output(
                OutputKey.UPDATE_SYSTEM_STATUS,
                {
                    "status": f"[Iteration {step.iteration_number}] 指示の入力を待っています...",
                },
            )

            instruction = await self.human_interface.input(
                InputKey.INSTRUCTION,
                {
                    "iteration_number": step.iteration_number,
                },
            )

            await self.human_interface.output(
                OutputKey.UPDATE_SYSTEM_STATUS,
                {
                    "status": f"[Iteration {step.iteration_number}] LLM実行中...",
                },
            )

            step.instruction = instruction

            # Save results to spreadsheet
            iteration_row_number = await self.human_interface.output(
                OutputKey.INSERT_ITERATION_DATA,
                {
                    "version": self.config.version,
                    "model": self.config.model,
                    "iteration_number": step.iteration_number,
                    "instruction": instruction,
                    "entities": game_state.entities,
                    "inventory": game_state.inventory(),
                },
            )

            for in_iteration_number in range(STEPS_PER_ITERATION):
                step.number += 1
                step.in_iteration_number = in_iteration_number + 1

                time.sleep(COURTESY_SLEEP)  # courtesy sleep
                try:
                    print("generation starting...")
                    agent_output = await self._generate_program(
                        step=step,
                        game_state=game_state,
                        execution_history=execution_history,
                    )

                    print(
                        f"Generated program {multiprocessing.current_process().name} - "
                        f"Model: {self.config.model} - "
                        f"Step {step.iteration_number}-{step.in_iteration_number}"
                    )

                    # Save results to spreadsheet
                    step_row_number = await self.human_interface.output(
                        OutputKey.INSERT_STEP_DATA,
                        {
                            "version": self.config.version,
                            "model": self.config.model,
                            "iteration_number": step.iteration_number,
                            "in_iteration_number": step.in_iteration_number,
                            "step_number": step.number,
                            "entities": game_state.entities,
                            "inventory": game_state.inventory(),
                            "thinking": agent_output.thinking,
                            "code": agent_output.code,
                        },
                    )

                    # Evaluate program
                    instance = self.evaluator.instance
                    # instance.reset(current_state)
                    (
                        evaluated_game_state,
                        evaluation,
                    ) = await self.evaluator.evaluate(agent_output.code)
                    print(agent_output.code + "\n" + "=" * 50)
                    print(
                        "\033[1m\n".join(
                            [
                                ">>>\t" + line
                                for line in evaluation.response.strip()
                                .replace("\\n", "\n\t")
                                .split("\n")
                            ]
                        ).strip()
                        + "\033[0m"
                    )
                    print(
                        f"Evaluated program {multiprocessing.current_process().name} - "
                        f"Model: {self.config.model} - "
                        f"Step {step.iteration_number}-{step.in_iteration_number}"
                    )

                    if step_row_number:
                        await self.human_interface.output(
                            OutputKey.UPDATE_STEP_EVALUATION,
                            {
                                "step_row_number": step_row_number,
                                "evaluation": evaluation.formatted(),
                            },
                        )

                    execution = Execution(
                        step=step,
                        agent_output=agent_output,
                        evaluation=evaluation,
                    )

                    data_point = create_data_point(
                        runtime_version=runtime_version,
                        collection_id=collection_id,
                        agent_name=agent_name,
                        input_game_state=game_state,
                        execution=execution,
                        execution_history=execution_history,
                        evaluated_game_state=evaluated_game_state,
                    )

                    await self.db.create_data_point(data_point)

                    game_state = evaluated_game_state
                    execution_history.append(copy.deepcopy(execution))

                except Exception as e:
                    print(
                        f"Error in Step {step.iteration_number}-{step.in_iteration_number}: {e}"
                    )
                    continue

            (previous_iteration_summary,) = await self.agent.report_summary(
                step,
                game_state,
                execution_history,
            )

            if iteration_row_number:
                await self.human_interface.output(
                    OutputKey.UPDATE_ITERATION_SUMMARY,
                    {
                        "iteration_row_number": iteration_row_number,
                        "previous_iteration_summary": previous_iteration_summary,
                    },
                )

            elapsed = time.time() - self.start_time
            elapsed_str = f"{int(elapsed // 3600):02d}:{int((elapsed % 3600) // 60):02d}:{int(elapsed % 60):02d}"
            print(
                f"\033[92m Process {multiprocessing.current_process().name} - "
                f"Model: {self.config.model} - "
                f"Itertion {step.iteration_number} - "
                f"Value: {evaluation.reward:.2f} - "
                f"Elapsed: {elapsed_str} - "
            )


def create_factorio_instance(instance_id: int) -> FactorioInstance:
    """Create a single Factorio instance"""
    # ips, udp_ports, tcp_ports = get_local_container_ips()
    if instance_id > 0:
        raise ValueError("Only one instance is supported")

    ips = ["localhost"]
    tcp_ports = [27000]

    instance = FactorioInstance(
        address=ips[instance_id],
        tcp_port=tcp_ports[instance_id],
        bounding_box=200,
        fast=True,
        cache_scripts=True,
        inventory={},
        all_technologies_researched=True,
    )
    instance.speed(1)
    return instance


async def run_trajectory(process_id: int, config: PlayConfig):
    """Entry point for running a single trajectory"""
    instance = create_factorio_instance(0)
    system_prompt = instance.get_system_prompt()

    evaluator = SimpleFactorioEvaluator(
        instance=instance, value_accrual_time=1, error_penalty=0
    )

    agent = IterationAgent(model=config.model, system_prompt=system_prompt)

    # setup the instance
    task = config.task
    task.setup(instance)

    # Create human interface based on environment
    if os.getenv("SPREADSHEET_ID"):
        human_interface = SpreadsheetHumanInterface(os.getenv("SPREADSHEET_ID"))
    else:
        human_interface = CLIHumanInterface()

    runner = TrajectoryRunner(agent, evaluator, config, human_interface)
    await runner.run()


def run_process(process_id: int, config: PlayConfig):
    """Process entry point"""
    asyncio.run(run_trajectory(process_id, config))
