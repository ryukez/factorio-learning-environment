# Copied from eval/open/independent_runs/simple_evaluator.py
import asyncio
import copy
from typing import List, Tuple, Union, Dict

from models.achievements import ProductionFlows
from models.game_state import GameState
from models.program import Program
from entities import Entity, EntityGroup
from instance import FactorioInstance
from utils.profits import get_achievements
from models.conversation import Conversation
from trainer.definitions import Evaluation, ParsedGameState


class SimpleFactorioEvaluator:
    def __init__(
        self,
        instance: FactorioInstance,
        value_accrual_time=10,
        error_penalty=10,
        logger=None,
    ):
        self.instance = instance  # Main instances
        # self.holdout = instances[-1]  # Holdout instance
        self.value_accrual_time = (
            value_accrual_time  # Time to accrue value before evaluating
        )
        self.error_penalty = error_penalty  # Penalty for errors during evaluation

        if logger:
            self.port_to_group = logger.port_to_group

    async def evaluate(
        self,
        code: str,
    ) -> Evaluation:
        try:
            # self.instance.reset(start_state)
            (
                raw_reward,
                state,
                response,
                entities,
                achievements,
                flows,
                ticks,
            ) = await self._evaluate_single(self.instance, code)
            # relative_reward = raw_reward  # - holdout_value

            return Evaluation(
                game_state=ParsedGameState(
                    raw=state,
                    entities=f"{entities}",
                ),
                response=response,
                reward=raw_reward,
                achievements=achievements,
                flows=flows,
                ticks=ticks,
            )

        except Exception as e:
            print(e)
            raise e

    async def _evaluate_single(
        self,
        instance: FactorioInstance,
        code: str,
    ) -> Tuple[
        float,
        GameState,
        str,
        List[Union[Entity, EntityGroup]],
        Dict,
        ProductionFlows,
        int,
    ]:
        # tcp_port = instance_port

        try:
            # Get initial state information

            # start_entities = instance.namespace.get_entities()
            # start_inventory = instance.namespace.inspect_inventory()
            # start_production_flows = instance.namespace._get_production_stats()
            start_production_flows = ProductionFlows.from_dict(
                instance.namespace._get_production_stats()
            )

            initial_value, start_time = instance.namespace.score()
            reward, time, result = instance.eval(code, timeout=60)

            # final_inventory = instance.namespace.inspect_inventory()

            # # Check to see if the inventories are different
            # # If so, we manually put a hint in the generated code and result from the game
            # get_inventory_code = 'print(f"Current inventory {inspect_inventory()}")'
            # if (
            #     start_inventory.__dict__ != final_inventory.__dict__
            #     and "error" not in result.lower()
            #     and get_inventory_code not in program.code
            #     and "inspect_inventory()" not in program.code
            # ):
            #     program.code += f"\n{get_inventory_code}"
            #     result += (
            #         f"\n"
            #         + str(len(program.code.split("\n")))
            #         + f": ('Current inventory {final_inventory}',)"
            #     )

            # # Check to see if the entities are different
            # # If they are, we put a hint in the code AND result
            # get_entities_code = 'print(f"Entities on the map: {get_entities()}")'
            # if (
            #     start_entities != entities
            #     and "error" not in result.lower()
            #     and get_entities_code not in program.code
            #     and "get_entities()" not in program.code
            # ):
            #     program.code += f"\n{get_entities_code}\n"
            #     result += (
            #         "\n"
            #         + str(len(program.code.split("\n")))
            #         + f": ('Entities on the map: {entities}',)"
            #     )

            result = result.rstrip() + "\n"

            # if "error" in result.lower():
            #     result += f"final: ('Current inventory: {final_inventory}',)\n"
            #     result += f"final: ('Entities on the map after the current step: {entities}',)"

            # Sleep for 3 seconds to get output flows
            await asyncio.sleep(self.value_accrual_time)
            state = GameState.from_instance(instance)
            entities = instance.namespace.get_entities()

            score, _ = instance.namespace.score()
            final_reward = score - initial_value
            ticks = instance.get_elapsed_ticks()

            post_production_flows = ProductionFlows.from_dict(
                instance.namespace._get_production_stats()
            )

            achievements = get_achievements(
                start_production_flows.__dict__, post_production_flows.__dict__
            )
            flows = start_production_flows.get_new_flows(post_production_flows)  #

            return final_reward, state, result, entities, achievements, flows, ticks

        except Exception as e:
            print(f"Error in _evaluate_single:")

            print(f"Error: {str(e)}")
            import traceback

            traceback.print_exc()
            raise e
