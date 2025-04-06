from env.src.instance import FactorioInstance
from env.src.models.game_state import GameState
from datetime import datetime
from time import sleep
import os


def create_factorio_instance():
    ip = "localhost"
    tcp_port = 27000

    instance = FactorioInstance(
        address=ip,
        tcp_port=tcp_port,
        bounding_box=200,
        fast=False,
        cache_scripts=True,
        inventory={},
        all_technologies_researched=False,
        peaceful=False,
    )
    instance.speed(1)
    return instance


async def main():
    instance = create_factorio_instance()

    os.makedirs("recordings", exist_ok=True)
    while True:
        state = GameState.from_instance(instance)

        now = datetime.now()
        with open(
            f"recordings/{now.strftime('%Y%m%d%H%M%S')}.json",
            "w",
        ) as f:
            f.write(state.to_raw())

        sleep(60)
