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
Write Python code to execute the planned actions:
```python
# Code must be enclosed in Python tags
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
    ):
        self.iteration = iteration
        self.instruction = instruction

    async def format_conversation(
        self,
        conversation: Conversation,
        namespace: FactorioNamespace,
        current_entities: str,
        current_inventory: str,
        plan: str,
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
                    content=f"""
## Planned Actions
{plan}

## Your Inventory
{current_inventory}

[Policy]
""",
                ),
            ]
        )

        return Conversation(messages=messages)

    def format_message(self, message: Message) -> Message:
        return message
