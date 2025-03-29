from typing import List
from trainer.definitions import Step, Execution, AgentOutput, Agent

# Copied from agents/basic_agent.py
import tenacity
from agents.utils.llm_factory import LLMFactory
from agents.utils.parse_response import parse_response
from models.conversation import Conversation
from models.generation_parameters import GenerationParameters
from tenacity import (
    wait_exponential,
    retry_if_exception_type,
    stop_after_attempt,
)
import logging
from trainer.definitions import Message, ParsedGameState


GENERAL_INSTRUCTIONS = """
# Factorio LLM Agent Instructions

## Overview
You are an AI agent designed to play Factorio, specializing in:
- Long-horizon planning
- Spatial reasoning 
- Systematic automation

## Environment Structure
- Operates like an interactive Python shell
- Agent messages = Python programs to execute
- User responses = STDOUT/STDERR from REPL
- Interacts through 27 core API methods (to be specified)

## Best Practices

### Modularity
- Create small, modular policies
- Each policy should have a single clear purpose
- Keep policies easy to debug and modify
- Avoid breaking existing automated structures
- Encapsulate working logic into functions if needed

### Debugging & Verification
- Use print statements to monitor important state
- Implement assert statements for self-verification
- Use specific, parameterized assertion messages
- Example: `assert condition, f"Expected {expected}, got {actual}"`

### State Management
- Consider entities needed for each step
- Track entities across different inventories
- Monitor missing requirements
- Preserve working automated structures

### Error Handling
- Fix errors as they occur
- Don't repeat previous steps
- Continue from last successful execution
- Avoid unnecessary state changes
- Analyze the root cause of entities that aren't working, and prioritize automated solutions (like transport belts) above manual triage

### Code Structure
- Write code as direct Python interpreter commands
- Only encapsulate reusable utility code into functions 
- Use appropriate spacing and formatting

## Understanding Output

### Error Messages
```stderr
Error: 1: ("Initial Inventory: {...}")
10: ("Error occurred in following lines...")
```
- Numbers indicate line of execution
- Previous lines executed successfully
- Fix errors at indicated line

### Status Updates
```stdout
23: ('Resource collection completed...')
78: ('Entities on map: [...]')
```
- Shows execution progress
- Provides entity status
- Lists warnings and conditions

### Entity Status Checking
- Monitor entity `warnings` field
- Check entity `status` field
- Verify resource levels
- Track production states

## Game Progression
- Think about long term objectives, and break them down into smaller, manageable steps.
- Advance toward more complex automation
- Build on previous successes
- Maintain efficient resource usage

## Utility Functions
- Create functions to encapsulate proven, reusable logic
- Place function definitions before their first use
- Document function purpose, parameters, and return values
- Test functions thoroughly before relying on them
- Example:
```python
def find_idle_furnaces(entities):
    \"\"\"Find all furnaces that are not currently working.
    
    Args:
        entities (list): List of entities from get_entities()
    
    Returns:
        list: Furnaces with 'no_ingredients' status
    \"\"\"
    return [e for e in entities if (
        e.name == 'stone-furnace' and 
        e.status == EntityStatus.NO_INGREDIENTS
    )]
```

## Data Structures
- Use Python's built-in data structures to organize entities
- Sets for unique entity collections:
```python
working_furnaces = {e for e in get_entities() 
                   if e.status == EntityStatus.WORKING}
```
- Dictionaries for entity mapping:
```python
furnace_by_position = {
    (e.position.x, e.position.y): e 
    for e in get_entities() 
    if isinstance(e, Furnace)
}
```
- Lists for ordered operations:
```python
sorted_furnaces = sorted(
    get_entities(),
    key=lambda e: (e.position.x, e.position.y)
)
```
"""

FINAL_INSTRUCTION = """"
You are given updated state of existing entities on map and your inventory at each step.
You are supposed to take a look at these information carefully to plan your next step.

- You can place nothing but entities in your current inventory. If you don't have any entities in your inventory, you need to get them first by crafting, harvesting or smelting etc.
- Try to understand the role of each exsting entities on map. For example, one stone furnace might be used to smelt iron ore into iron plates, while another one might be used to smelt copper ore into copper plates, or to smelt iron plates into steel plates.
- In opposite, not-working entities have no use in the game. If you need to place some entities, you should first consider replacing existing ones. Example abundoned pipes or belts, not-working inserters, or empty chests.

## Response Format

### 1. PLANNING Stage
Think through each step extensively in natural language, addressing:
1. Error Analysis
- Was there an error in the previous execution?
- If yes, what was the problem?
- To avoid the error, how different approach can be taken?
2. Next Step Planning
- What specific actions are needed?
- What resources are required?
- Then, what is the most useful next step of reasonable size?

### 2. POLICY Stage
Write Python code to execute the planned actions:
```python
# Code must be enclosed in Python tags
your_code_here
```

Your output should be in the following format:
[Planning]
your_planning_here

[Policy]
```python
your_code_here
```
"""


def iteration_summary_prompt(
    instruction: str, entities: str, inventory: str, logs: str
):
    return f"""
You are an AI agent designed to play Factorio, specializing in:
- Long-horizon planning
- Spatial reasoning 
- Systematic automation

## Instruction
You are given current existing entities, inventory state and logs you have executed in the game, during the previous interation.
You have the following instruction from supervisor:

[Task]
Build a power plant, consisting of a offshore pomp, boiler, and steam engine.

[Hints From Supervisor]
- You need to prepare enough iron and copper plates first to craft facilities

Based on the entities on the map, inventory state and execution logs, you must generate a report of the previous iteration.
The report must have 3 sections: CHANGES, NEXT ITERATION PLANING and ERROR TIPS. Below are instructions for both of them:

CHANGES
Describe what is done duration the iteration.
- Newly built facilities with position
- Obtained items
- Working status changes of facilities

Example:
In the previous iteration, 
- we built burner mining drill at position(x1). It is supplying iron ores to stone furnace nearby at position(x2). There iron ores are smelted into iron plates, and stored into a wooden chest at position(x3) by a burner inserter at position(x4).
- now we have boiler and steam engine in the inventory, so we can place them in the neighbor of existing offshore pomp at position(x5) to build power plant!
- The burner drill at position(x6) was not working due to insufficient fuel. I fixed the issue by feeding some coals. Because we have no automated coal supplies, I should feed them manually for a while when it is out of fuel.

NEXT ITERATION PLANING
Analyze how is the task is going and plan the next iteration (consists of 20 steps).
If the given task is completed, you can just summarize the completion.

If the task is not completed yet, you should first difficulties or obstacles you are facing.
Then you should plan the next iteration to complete the task.
- What are the remaining steps to complete the task
- required items to complete the task

Example:
We have not yet built achive the objective of building power plant.

Difficulties and Obstacles:
- We are facing difficulties in extracting resources from chests and furnaces. This is because my inventory is full. I need to clear some space in my inventory to extract more items, by either crafting them into higher level items or storing them in chests.
- We need to ensure a consistent supply of coal to the furnaces to keep them operational.

To complete the task, we need to:
- 1. Get enough amount of iron and copper plates to craft offshore pomp, boiler and steam engine. We need more 30 iron plates and 3 copper plates.
- 2. Craft the entities and onnect them with pipes

ERROR TIPS
In this section you must analyse the errors that the agent has made and bring out tips how to mitigate these errors. 
Usually error messages tell you what the agent did wrong. The errors can be incorrect use of API, misplaced objects etc. 
Make this a succinct detailed list, group common similar error patterns and solutions how to avoid these errors. 
Group similar mistakes, if the agent made the same mistake multiple times but at many places, bring it out as one section/bulletpoint. 
Include new mistakes and all mistake tips from the previous report

Make the sections accurate and thorough. Do not mention things like "The error message suggests" etc, this is self evident.
Some examples

### Errors when using extracting but being too far
 -  Make sure to move to the target entity where you want to extract from before extracting items
### Errors when placing into a tile which is occupied by another entity
- Ensure you can place a entity to a tile before attempting placing

You must output only the report. Any other texts are forbidden.

## Instruction
{instruction}

## Entities on the map
{entities}

## Your Inventory
{inventory}

## Execution Logs
{logs}

## Output
"""


def my_before_sleep(retry_state):
    if retry_state.attempt_number < 1:
        loglevel = logging.INFO
    else:
        loglevel = logging.WARNING
    logging.log(
        loglevel,
        "Retrying %s: attempt %s ended with: %s",
        retry_state.fn,
        retry_state.attempt_number,
        retry_state.outcome,
    )


class IterationAgent(Agent):
    def __init__(self, model: str, system_prompt: str):
        goal_description = "\n\n### Your Final Goal\n- Build the biggest possible factory\n- Maximise automation, efficiency and scale\n\n"
        instructions = GENERAL_INSTRUCTIONS + system_prompt + goal_description
        self.system_prompt = instructions

        self.model = model
        self.llm_factory = LLMFactory(model)
        self.generation_params = GenerationParameters(n=1, max_tokens=8192, model=model)

    def name(self) -> str:
        return f"IterationAgent-{self.model}"

    async def run(
        self,
        step: Step,
        game_state: ParsedGameState,
        execution_history: List[Execution],
    ) -> AgentOutput:
        messages = self._format_messages(step, game_state, execution_history)
        return await self._get_policy(messages)

    def _format_messages(
        self,
        step: Step,
        game_state: ParsedGameState,
        execution_history: List[Execution],
    ) -> List[Message]:
        iteration_messages: List[Message] = []
        for execution in execution_history:
            if execution.step.iteration_number == step.iteration_number:
                iteration_messages += [
                    Message(
                        role="assistant",
                        content=execution.agent_output.code,
                    ),
                    Message(
                        role="user",
                        content=execution.evaluation.response,
                    ),
                ]

        updated_system_prompt = f"""
{self.system_prompt}

{FINAL_INSTRUCTION}

{step.instruction}
"""

        messages = (
            [
                Message(
                    role="system",
                    content=updated_system_prompt,
                )
            ]
            + iteration_messages
            + [
                Message(
                    role="user",
                    content=f"""
## Existing Entities on Map
Here is a list of existing entities on the map.
If there are issues with existing entities, you should try to fix them, by supplying missing resources, repairing broken connections, or removing unnecessary entities.
Note that you don't need to care about "Chest is full". Chests are entities to store items, and they can be full.
You should consider making use of items in the inventories of entities, before crafting or harvesting new items.

{game_state.entities}

## Your Inventory
Here is a list of entities in your inventory.
Note that  you can only place entities that are in your inventory. If you don't have any entities in your inventory, you need to get them first by crafting, harvesting or smelting etc.
Make sure to keep at least free 20 slots in your inventory, otherwise you will not be able to pick up or craft new items.

{game_state.inventory()}

## Important Notes
- Always inspect game state before making changes
- Consider long-term implications of actions
- Maintain working systems, and clear entities that aren't working or don't have a clear purpose
- Build incrementally and verify each step
- DON'T REPEAT YOUR PREVIOUS STEPS - just continue from where you left off. Take into account what was the last action that was executed and continue from there. If there was a error previously, do not repeat your last lines - as this will alter the game state unnecessarily.

Remember that your python code must be always enclosed with ```python ... ``` decorator. It's very import for parsing your code. It you can't, you will be fired.

Your output
[Planning]""",
                ),
            ]
        )

        return messages

    @tenacity.retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        before_sleep=my_before_sleep,
        stop=stop_after_attempt(3),
    )
    async def _get_policy(self, messages: List[Message]) -> AgentOutput:
        response = await self.llm_factory.acall(
            messages=[{"role": msg.role, "content": msg.content} for msg in messages],
            n_samples=1,  # We only need one program per iteration
            temperature=self.generation_params.temperature,
            max_tokens=self.generation_params.max_tokens,
            model=self.generation_params.model,
        )

        policy = parse_response(response)
        if not policy:
            raise Exception("Not a valid Python policy")

        return AgentOutput(
            input_messages=messages,
            raw_response=policy.meta.text_response,
            thinking=policy.thinking,
            code=policy.code,
        )

    async def report_summary(
        self,
        iteration: int,
        current_inventory: str,
        current_entities: str,
        current_conversation: Conversation,
    ):
        instruction = ""
        iteration_messages = []
        for message in current_conversation.messages:
            if message.metadata.get("iteration") == iteration:
                iteration_messages.append(message)
                instruction = message.metadata.get("instruction")

        iteration_summary = ""
        if iteration_messages:
            try:
                iteration_summary_response = await self.llm_factory.acall(
                    messages=[
                        {
                            "role": "user",
                            "content": iteration_summary_prompt(
                                instruction,
                                current_entities,
                                current_inventory,
                                "\n".join(
                                    [
                                        f"role: {m.role}\ncontent: {m.content}\n"
                                        for m in iteration_messages
                                    ]
                                ),
                            ),
                        }
                    ],
                    n_samples=1,  # We only need one program per iteration
                    temperature=self.generation_params.temperature,
                    max_tokens=2048,  # use longer max_tokens
                    model=self.generation_params.model,
                )
                iteration_summary = iteration_summary_response.choices[
                    0
                ].message.content
            except Exception as e:
                logging.error(f"Failed to generate iteration summary: {e}")
                iteration_summary = ""

        return (
            # entity_summary,
            f"{iteration_summary}",
        )
