from abc import ABC, abstractmethod
from env.src.models.game_state import GameState
from typing import List
from definitions import Step, Execution, AgentOutput, Agent


class BasicAgent(Agent):
    async def run(
        self,
        step: Step,
        game_state: GameState,
        execution_history: List[Execution],
    ) -> AgentOutput:
        raw_response = """
[Planning]
Okay, I understand the situation. 

1. **Error Analysis:** The previous attempt failed because I ran out of iron ore while trying to insert it into the furnace. I need to ensure I have enough iron ore before attempting to craft the iron gear wheel. Also, the furnace fuel source is full.

2. **Next Step Planning:**
    * Harvest more Iron Ore
    * Craft Iron Gear Wheel
    * Craft Offshore Pump
    * Place Offshore Pump
    * Craft Boiler and Steam Engine

[Policy]
```python
# Harvest Iron Ore
iron_ore_pos = nearest(Resource.IronOre)
move_to(iron_ore_pos)
harvest_resource(iron_ore_pos, quantity=50)
print("Iron Ore Harvested")
```
"""

        return AgentOutput(
            input_messages=[],
            raw_response=raw_response,
            thinkng="""
Okay, I understand the situation. 

1. **Error Analysis:** The previous attempt failed because I ran out of iron ore while trying to insert it into the furnace. I need to ensure I have enough iron ore before attempting to craft the iron gear wheel. Also, the furnace fuel source is full.

2. **Next Step Planning:**
    * Harvest more Iron Ore
    * Craft Iron Gear Wheel
    * Craft Offshore Pump
    * Place Offshore Pump
    * Craft Boiler and Steam Engine
""",
            code="""
# Harvest Iron Ore
iron_ore_pos = nearest(Resource.IronOre)
move_to(iron_ore_pos)
harvest_resource(iron_ore_pos, quantity=50)
print("Iron Ore Harvested")
""",
        )
