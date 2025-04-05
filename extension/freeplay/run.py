# Copied from eval/open/independent_runs/run.py
import argparse
from dotenv import load_dotenv
from extension.freeplay.trajectory_runner import (
    run_process,
    PlayConfig,
)
from eval.tasks.task_factory import TaskFactory
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

    run_config = run_configs[0]
    task = TaskFactory.create_task(run_config["task"])
    version = run_config["version"]

    config = PlayConfig(
        task=task,
        model=run_config["model"],
        version=version,
        version_description=f"model:{run_config['model']}\ntype:{task.task_key}",
        runtime_version=run_config["runtime_version"],
    )

    run_process(0, config)


if __name__ == "__main__":
    main()
