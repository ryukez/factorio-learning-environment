# Copied from eval/open/independent_runs/trajectory_runner.py
import asyncio
import copy
from dataclasses import dataclass
import multiprocessing
from dotenv import load_dotenv

from agents.agent_abc import AgentABC
from freeplay.evaluator import SimpleFactorioEvaluator
from models.conversation import Conversation
from models.message import Message
from models.program import Program
from instance import FactorioInstance
from freeplay.basic_agent import BasicAgent

from namespace import FactorioNamespace

from agents import Response
from eval.tasks.task_abc import TaskABC
from eval.open.db_client import DBClient, SQLliteDBClient
import os
import json
from typing import List
from spreadsheet import (
    insert_to_spreadsheet,
    get_spreadsheet_values,
    update_spreadsheet_cell,
)
from models.game_state import GameState

load_dotenv()

COURTESY_SLEEP = 5


@dataclass
class PlayConfig:
    """Configuration for evaluation"""

    task: TaskABC
    model: str
    version: int
    version_description: str


def format_inventory(inventory: dict) -> str:
    slot = 0
    for item, count in inventory.items():
        slot += (count - 1) // 50 + 1
    return f"{inventory}, {max(80 - slot, 0)} slots remaining"


class TrajectoryRunner:
    """Handles program generation and evaluation for a single trajectory"""

    def __init__(
        self,
        agent: BasicAgent,
        db_client: DBClient,
        evaluator: SimpleFactorioEvaluator,
        config: PlayConfig,
        process_id: int,
    ):
        self.agent = agent
        self.db = db_client
        self.evaluator = evaluator
        self.config = config
        self.iteration_times = []
        self.process_id = process_id

    def _is_model_compatible_with_n_samples(self, model):
        """Check if model supports batch sampling"""
        return "gpt" in model or "o1" in model or "gemini" in model

    async def _generate_program(
        self,
        conversation: Conversation,
        response: Response,
        namespace: FactorioNamespace,
        entities: str,
        inventory: str,
        meta={},
    ) -> Program:
        conversation = copy.deepcopy(conversation)
        try:
            policy = await self.agent.step(
                conversation, response, namespace, entities, inventory
            )

            if not policy:
                raise Exception("Policy not valid Python. Skipping.")

            try:
                messages = conversation.model_dump()["messages"]
            except Exception:
                messages = conversation.dict()["messages"]

            program = Program(
                thinking=policy.thinking,
                code=policy.code,
                conversation=conversation,
                response=response.response if response else None,
                token_usage=policy.meta.total_tokens,
                completion_token_usage=policy.meta.output_tokens,
                prompt_token_usage=policy.meta.input_tokens,
                version=self.config.version,
                model=self.agent.model,
                version_description=self.config.version_description,
                meta={"model": self.agent.model, "process_id": self.process_id},
                depth=len(messages) - 2,
            )

            if meta:
                program.meta.update(meta)

            return program

        except Exception as e:
            print(f"Program generation failed: {str(e)}")
            return []

    async def run(self):
        """Run a single trajectory"""
        # Initialize state based on resume or fresh start
        import time

        self.start_time = time.time()

        print(self.start_time)

        current_state = None
        # Continue
        if self.config.version:
            (
                current_state,
                current_conversation,
                parent_id,
                depth,
            ) = await self.db.get_resume_state(
                resume_version=self.config.version, process_id=self.process_id
            )
            self.agent.conversation = current_conversation

            if current_state:
                instance = self.evaluator.instance
                instance.reset(current_state)

        # print(current_state.inventory)
        # print(current_state.research)
        # print(current_state.timestamp)
        # print(
        #     instance.namespace._load_entity_state(
        #         current_state.entities, decompress=True
        #     )
        # )

        # New game
        if not current_state:
            current_state = self.agent.task.starting_game_state
            depth = 0
            instance = self.evaluator.instance
            instance.reset(current_state)
            entities = instance.namespace.get_entities()
            current_conversation = Conversation(
                messages=[
                    Message(role="system", content=self.agent.system_prompt),
                    Message(
                        role="assistant",
                        content="print(f'Inventory: {inspect_inventory()}')\n"
                        "print(f'Entities: {get_entities()}')\n",
                    ),
                    Message(
                        role="user",
                        content=f"1: ('Inventory: {current_state.inventory.__dict__}')\n"
                        f"2: ('Entities: {entities}')",
                    ),
                ]
            )
            self.agent.conversation = current_conversation
            parent_id = None

        # with open("entities.txt", "w") as f:
        #     f.write(f"{instance.namespace.get_entities()}")
        # with open("inventory.txt", "w") as f:
        #     f.write(f"{instance.namespace.inspect_inventory()}")

        # os.exit(1)

        last_response = None
        # Run trajectory
        STEPS_PER_ITERATION = 30
        iteration = (depth // STEPS_PER_ITERATION) + 1

        current_entities = f"{instance.namespace.get_entities()}"
        current_inventory = format_inventory(instance.namespace.inspect_inventory())

        (previous_iteration_summary,) = await self.agent.report_summary(
            iteration=iteration,
            current_inventory=current_inventory,
            current_entities=current_entities,
            current_conversation=current_conversation,
        )

        while True:
            iteration += 1
            print(f"### Iteration {iteration} ###")

            update_spreadsheet_cell(
                os.getenv("SPREADSHEET_ID"),
                "System!B1",
                f"[Iteration {iteration}] 指示の入力を待っています...",
            )

            # 1分ごとにスプレッドシートにアクセスし、指示が更新されているかを確認
            instruction = ""
            while True:
                try:
                    user_input = get_spreadsheet_values(
                        os.getenv("SPREADSHEET_ID"), "Input!E2:E3"
                    )
                    if user_input and int(user_input[0][0]) == iteration:
                        instruction = user_input[1][0]
                        break
                except Exception as e:
                    print(f"Error in getting instruction: {e}")

                time.sleep(60)

            await self.agent.start_iteration(
                iteration=iteration,
                instruction=instruction,
                previous_iteration_summary=previous_iteration_summary,
            )

            update_spreadsheet_cell(
                os.getenv("SPREADSHEET_ID"),
                "System!B1",
                f"[Iteration {iteration}] LLM実行中...",
            )

            current_entities = f"{instance.namespace.get_entities()}"
            current_inventory = format_inventory(instance.namespace.inspect_inventory())

            # Save results to spreadsheet
            (_, iteration_row_number) = insert_to_spreadsheet(
                os.getenv("SPREADSHEET_ID"),
                "Iterations!A1:Z",
                [
                    [
                        self.config.version,
                        self.config.model,
                        iteration,
                        instruction,
                        current_entities,
                        current_inventory,
                    ],
                ],
            )

            for step in range(STEPS_PER_ITERATION):
                time.sleep(COURTESY_SLEEP)  # courtesy sleep
                try:
                    current_entities = f"{instance.namespace.get_entities()}"
                    current_inventory = format_inventory(
                        instance.namespace.inspect_inventory()
                    )

                    print("generation starting...")
                    program = await self._generate_program(
                        current_conversation,
                        last_response,
                        self.evaluator.instance.namespace,
                        entities=current_entities,
                        inventory=current_inventory,
                    )

                    print(
                        f"Generated program {multiprocessing.current_process().name} - "
                        f"Model: {self.agent.model} - "
                        f"Step {iteration}-{step + 1}"
                    )

                    # Save results to spreadsheet
                    (_, step_row_number) = insert_to_spreadsheet(
                        os.getenv("SPREADSHEET_ID"),
                        "Steps!A1:Z",
                        [
                            [
                                self.config.version,
                                self.config.model,
                                iteration,
                                step + 1,
                                program.depth // 2,
                                current_entities,
                                current_inventory,
                                program.thinking,
                                program.code,
                            ]
                        ],
                    )

                    if not program:
                        continue

                    program.parent_id = parent_id

                    # Evaluate program
                    instance = self.evaluator.instance
                    # instance.reset(current_state)
                    (
                        evaluated_program,
                        task_verification_response,
                    ) = await self.evaluator.evaluate(
                        program, current_state, iteration, instruction, self.agent.task
                    )
                    print(program.code + "\n" + "=" * 50)
                    print(
                        "\033[1m\n".join(
                            [
                                ">>>\t" + line
                                for line in program.response.strip()
                                .replace("\\n", "\n\t")
                                .split("\n")
                            ]
                        ).strip()
                        + "\033[0m"
                    )
                    print(
                        f"Evaluated program {multiprocessing.current_process().name} - "
                        f"Model: {self.agent.model} - "
                        f"Step {iteration}-{step + 1}"
                    )

                    if not evaluated_program:
                        continue

                    program = evaluated_program
                    self.agent.conversation = program.conversation
                    program.meta["task_key"] = self.agent.task.task_key
                    last_response = Response(
                        code=program.code,
                        created_at=program.created_at,
                        score=program.value,
                        achievements=program.achievements,
                        step=depth,
                        ticks=program.ticks,
                        flows=program.flows,
                        response=program.response,
                        task=task_verification_response,
                    )

                    # Save program
                    saved_program = await self.db.create_program(program)
                    print(
                        f"Saved program {multiprocessing.current_process().name} - "
                        f"Model: {self.agent.model} - "
                        f"Step {iteration}-{step + 1}"
                    )

                    parent_id = saved_program.id

                    if step_row_number:
                        update_spreadsheet_cell(
                            os.getenv("SPREADSHEET_ID"),
                            f"Steps!J{step_row_number}",
                            program.response,
                        )

                    # Update state for next iteration
                    if program.state:
                        current_state = program.state
                        current_conversation = program.conversation

                    with open("messages.json", "w") as f:
                        json.dump(current_conversation.messages, f, indent=2)

                except Exception as e:
                    print(f"Error in Step {iteration}-{step + 1}: {e}")
                    continue

            current_entities = f"{instance.namespace.get_entities()}"
            current_inventory = format_inventory(instance.namespace.inspect_inventory())

            (previous_iteration_summary,) = await self.agent.report_summary(
                iteration=iteration,
                current_inventory=current_inventory,
                current_entities=current_entities,
                current_conversation=current_conversation,
            )

            if iteration_row_number:
                update_spreadsheet_cell(
                    os.getenv("SPREADSHEET_ID"),
                    f"Iterations!G{iteration_row_number}",
                    previous_iteration_summary,
                )

            elapsed = time.time() - self.start_time
            elapsed_str = f"{int(elapsed // 3600):02d}:{int((elapsed % 3600) // 60):02d}:{int(elapsed % 60):02d}"
            print(
                f"\033[92m Process {multiprocessing.current_process().name} - "
                f"Model: {self.agent.model} - "
                f"Itertion {iteration} - "
                f"Value: {program.value:.2f} - "
                f"Elapsed: {elapsed_str} - "
            )


def create_factorio_instance(instance_id: int) -> FactorioInstance:
    """Create a single Factorio instance"""
    # ips, udp_ports, tcp_ports = get_local_container_ips()
    if instance_id > 0:
        raise ValueError("Only one instance is supported")

    ips = ["192.168.0.108"]
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


async def create_db_client() -> DBClient:
    """Create database client with connection pool"""
    return SQLliteDBClient(
        max_conversation_length=40,
        min_connections=2,
        max_connections=5,
        database_file=os.getenv("SQLITE_DB_FILE"),
    )


async def run_trajectory(process_id: int, config: PlayConfig):
    """Entry point for running a single trajectory"""
    db_client = await create_db_client()
    instance = create_factorio_instance(0)
    system_prompt = instance.get_system_prompt()

    evaluator = SimpleFactorioEvaluator(
        instance=instance, value_accrual_time=1, error_penalty=0
    )

    agent = BasicAgent(
        model=config.model, system_prompt=system_prompt, task=config.task
    )

    # setup the instance
    task = config.task
    task.setup(instance)
    runner = TrajectoryRunner(agent, db_client, evaluator, config, process_id)
    await runner.run()


def run_process(process_id: int, config: PlayConfig):
    """Process entry point"""
    asyncio.run(run_trajectory(process_id, config))
