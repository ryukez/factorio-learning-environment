# Copied from eval/open/independent_runs/run.py
import argparse
import multiprocessing
from dotenv import load_dotenv
from freeplay.trajectory_runner import (
    run_process,
    create_factorio_instance,
    PlayConfig,
)
from eval.tasks.task_factory import TaskFactory
from eval.tasks.task_abc import TaskABC
from pathlib import Path
import json


def main():
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run_config",
        type=str,
        help="Path of the run config file",
        default=Path("freeplay", "configs", "run_config.json"),
    )
    args = parser.parse_args()
    # read in run_config
    run_config_location = args.run_config
    with open(run_config_location, "r") as f:
        run_configs = json.load(f)

    version_offset = 0
    # Get starting version number for new runs
    base_version = 1

    run_config = run_configs[0]

    task = TaskFactory.create_task(run_config["task"])
    if "version" in run_config:
        version = run_config["version"]
    else:
        version = base_version + version_offset
        version_offset += 1

    config = PlayConfig(
        task=task,
        model=run_config["model"],
        version=version,
        version_description=f"model:{run_config['model']}\ntype:{task.task_key}",
    )

    run_process(0, config)


if __name__ == "__main__":
    main()
