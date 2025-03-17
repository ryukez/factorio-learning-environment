# Copied from agents/basic_agent.py
import tenacity
import json

from agents import Response, CompletionResult, Policy
from agents.agent_abc import AgentABC
from agents.utils.llm_factory import LLMFactory
from agents.utils.parse_response import parse_response
from models.conversation import Conversation
from models.generation_parameters import GenerationParameters
from tenacity import (
    wait_exponential,
    retry_if_exception_type,
    wait_random_exponential,
    stop_after_attempt,
)
from freeplay.recursive_report_formatter import RecursiveReportFormatter
import logging

from namespace import FactorioNamespace
from freeplay.conversation_formatter import ConversationFormatter

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

## Important Notes
- Use transport belts to keep burners fed with coal
- Always inspect game state before making changes
- Consider long-term implications of actions
- Maintain working systems, and clear entities that aren't working or don't have a clear purpose
- Build incrementally and verify each step
- DON'T REPEAT YOUR PREVIOUS STEPS - just continue from where you left off. Take into account what was the last action that was executed and continue from there. If there was a error previously, do not repeat your last lines - as this will alter the game state unnecessarily.
- Do not encapsulate your code in a function _unless_ you are writing a utility for future use - just write it as if you were typing directly into the Python interpreter.
- Your inventory has space for ~2000 items. If it fills up, insert the items into a chest.
- Ensure that your factory is arranged in a grid, as this will make things easier.
"""


def entity_summary_prompt(entities: str):
    return f"""
You are a report generating model for the game factorio. 
Given existing entities, you must summarise what structures the agent has created on the map and what are the use-cases of those structures. You must also bring out the entities and positions of entities of each of those structures.

Focus on the structures themselves. Do not bring out entities separately, create sections like 
###Electricity generator at position(x)
Consists of steam engine(position x), boiler(position y) and offshore pump (position z)

###Copper plate mine at position(x)
Consists of following entities
-  Burner mining drill (position x1) and a furnace at position(y1)
-  Burner mining drill (position x2) and a furnace at position(y2)
-  Burner mining drill (position x3) and a furnace at position(y3)

###Copper cable factory
Consists of following entities
-  Burner mining drill (position x1) and a furnace at position(y1)
-  Assembling machine at position(z1) and inserter at position(a) that puts into assembling machine
-  Beltgroup (position ) that connects the furnace at position y1 to assembling machine at position(z1)

- If multiple sections are connected, summarise them as one structure
- Do not include any mention of harvesting or crafting activities. That is not the aim of this report and is self-evident as the agent can see its own inventory
- All structures from the previous report that did not have any updates, include them in the new report unchanged

Output the summary only, do not include any other information.

[Input]
{entities}

[Output]
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


class BasicAgent(AgentABC):
    def __init__(self, model, system_prompt, task, *args, **kwargs):
        self.task = task
        goal_description = f"\n\n### Your Final Goal\n{task.goal_description}\n\n"
        instructions = GENERAL_INSTRUCTIONS + system_prompt + goal_description

        super().__init__(model, instructions, *args, **kwargs)
        self.llm_factory = LLMFactory(model)
        self.formatter = ConversationFormatter(instructions)
        self.generation_params = GenerationParameters(n=1, max_tokens=2048, model=model)

    async def start_iteration(self, entities: str):
        response = await self.llm_factory.acall(
            messages=[
                {
                    "role": "user",
                    "content": entity_summary_prompt(entities),
                }
            ],
            n_samples=1,  # We only need one program per iteration
            temperature=self.generation_params.temperature,
            max_tokens=16384,  # use longer max_tokens
            model=self.generation_params.model,
        )

        self.formatter.set_entity_summary(response.choices[0].message.content)

    async def step(
        self,
        conversation: Conversation,
        response: Response,
        namespace: FactorioNamespace,
    ) -> Policy:
        # We format the conversation every N steps to add a context summary to the system prompt
        formatted_conversation = await self.formatter.format_conversation(
            conversation, namespace
        )
        # We set the new conversation state for external use
        self.set_conversation(formatted_conversation)

        return await self._get_policy(formatted_conversation)

    @tenacity.retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        before_sleep=my_before_sleep,
        stop=stop_after_attempt(3),
    )
    async def _get_policy(self, conversation: Conversation):
        messages = self.formatter.to_llm_messages(conversation)

        with open("messages.json", "w") as f:
            json.dump(messages, f)

        response = await self.llm_factory.acall(
            messages=messages,
            n_samples=1,  # We only need one program per iteration
            temperature=self.generation_params.temperature,
            max_tokens=self.generation_params.max_tokens,
            model=self.generation_params.model,
        )

        text: str = response.choices[0].message.content
        splits = text.split("```python")

        thinking = ""
        if len(splits) > 1:
            thinking = splits[0]
            thinking = thinking.replace("[Planning]", "")
            thinking = thinking.replace("[Policy]", "")

        with open("thinking.txt", "w") as f:
            f.write(thinking)

        policy = parse_response(response)
        if not policy:
            raise Exception("Not a valid Python policy")

        return policy

    async def end(self, conversation: Conversation, completion: CompletionResult):
        pass
