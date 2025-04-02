import json
from trainer.definitions import DataPoint, Step, Execution
import math
import random

data_points = []
with open("outputs/gemma-14b.jsonl", "r") as f:
    # with open("datasets/claude37_100.jsonl", "r") as f:
    # with open("datasets/sample.jsonl", "r") as f:
    # with open("outputs/claude37_100-gemini-20-flash.jsonl", "r") as f:
    for line in f:
        data_points.append(DataPoint.from_dict(json.loads(line)))

print("Total data points:", len(data_points))

rewards = [dp.evaluation.reward for dp in data_points]
print(
    "Average log reward:",
    [sum([math.log(max(0, r) + 1) for r in rewards]) / len(rewards)],
)

passed_lines = [
    len(
        Execution(
            step=dp.step, agent_output=dp.agent_output, evaluation=dp.evaluation
        ).executed_commands()
    )
    for dp in data_points
]
print("Average commands:", sum(passed_lines) / len(passed_lines))

# for d in data_points:
#     # if dp.evaluation.reward >= 10:
#     #     count += 1
#     #     print(dp.evaluation.reward, dp.evaluation.achievements)

#     # execution = Execution(
#     #     step=dp.step,
#     #     agent_output=dp.agent_output,
#     #     evaluation=dp.evaluation,
#     # )

#     # if dp.agent_name == "IterationAgent-open-router-anthropic/claude-3.7-sonnet":
#     #     dps.append(dp)


# with open("data_points_claude3.7.jsonl", "w") as f:
#     for d in dps:
#         f.write(json.dumps(d.to_dict()) + "\n")

# #     passed_lines = len(execution.passed_code().split("\n"))
# #     if dp.evaluation.reward >= 20:
# #         print(passed_lines, dp.evaluation.reward, dp.evaluation.achievements)
# #         count += 1

# # print(count)
