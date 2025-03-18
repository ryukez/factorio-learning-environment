import os
import json
import hashlib
import re
from typing import List, Optional, Callable, TypedDict, Union, Dict, Any, Awaitable

from agents.utils.llm_factory import LLMFactory
from agents.utils.formatters.conversation_formatter_abc import ConversationFormatter
from models.conversation import Conversation
from models.message import Message
import copy

from namespace import FactorioNamespace

FINAL_INSTRUCTION = """"
## Response Format

### 1. PLANNING Stage
Think through each step extensively in natural language, addressing:
1. Error Analysis
   - Was there an error in the previous execution?
   - If yes, what was the problem?
2. Next Step Planning
   - What is the most useful next step of reasonable size?
   - Why is this step valuable?
   - Should I 
3. Action Planning
   - What specific actions are needed?
   - What resources are required?

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


class ConversationFormatter(ConversationFormatter):
    """
    Formatter that maintains a fixed context window through hierarchical summarization.
    Recursively summarizes from left to right, incorporating newer messages into the summary.
    """

    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt

    def start_iteration(
        self,
        iteration: int,
        instruction: str,
        previous_iteration_summary: str,
    ):
        self.iteration = iteration
        self.instruction = instruction
        self.previous_iteration_summary = previous_iteration_summary

    async def format_conversation(
        self,
        conversation: Conversation,
        namespace: FactorioNamespace,
        current_entities: str,
        current_inventory: str,
    ) -> Conversation:
        """
        conversations:
          - role: system
            content: System message
          # recent actions
          - role: assistent
            content: policy
          - role: user
            content: execution log
          ...
        """

        iteration_messages = []
        for message in conversation.messages:
            if message.metadata.get("iteration") == self.iteration:
                iteration_messages.append(message)

        updated_system_prompt = f"""
{self.system_prompt}

## Previous Iteration Summary
{self.previous_iteration_summary}

## Existing Entities
{current_entities}

## Current Inventory
{current_inventory}

{FINAL_INSTRUCTION}

{self.instruction}
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
                    content="Remember that your python code must be always enclosed with ```python ... ``` decorator. It's very import for parsing your code. It you can't, you will be fired.\n\nYour output\n[Planning]",
                ),
            ]
        )

        return Conversation(messages=messages)

    def format_message(self, message: Message) -> Message:
        return message
