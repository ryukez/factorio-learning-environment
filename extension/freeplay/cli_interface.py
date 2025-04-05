from extension.freeplay.human_interface import HumanInterface, InputKey, OutputKey
from rich.console import Console
from rich.prompt import Prompt


class CLIHumanInterface(HumanInterface):
    """CLIを使用した人間とのインターフェース"""

    def __init__(self):
        self.console = Console()
        self.current_instruction = "- Build the biggest possible factory\n- Maximise automation, efficiency and scale"

    async def input(self, key: InputKey, context) -> str:
        if key == InputKey.INSTRUCTION:
            text = Prompt.ask(
                f"[Iteration {context['iteration_number']}] 指示の入力を待っています... (Enterで現在の指示を実行)"
                + f"\nCurrent Instruction: {self.current_instruction}"
            )
            if text != "":
                return self.current_instruction
            else:
                self.current_instruction = text
                return text

    async def output(self, key: OutputKey, data):
        self.console.print(key, data)
