import json
import numpy as np
from trainer.definitions import DataPoint, Step, Execution
import openai
from openai import OpenAI
from typing import List
import os
import pandas as pd


def get_embeddings(texts: List[str]) -> np.ndarray:
    """OpenAIのAPIを使用してテキストの埋め込みベクトルを取得"""
    client = OpenAI()

    # テキストを埋め込みベクトルに変換
    response = client.embeddings.create(model="text-embedding-3-large", input=texts)

    return np.array([np.array(embedding.embedding) for embedding in response.data])


def cos_sim(embeddings: np.ndarray) -> np.ndarray:
    """埋め込みベクトル間のコサイン類似度行列を計算"""
    # ベクトルを正規化
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normalized = embeddings / norms

    # コサイン類似度行列を計算
    sim_matrix = np.dot(normalized, normalized.T)
    return sim_matrix


def select_max_min_similarity(sim_matrix: np.ndarray, M: int) -> List[int]:
    """
    sim_matrix: (N, N) の類似度行列 (0〜1, 対称, 対角は1)
    M: 選びたい点の数
    """
    N = sim_matrix.shape[0]
    selected = []
    remaining = set(range(N))

    # 1. 初期点：最も平均類似度が低い点（＝最も孤立している点）
    avg_sim = sim_matrix.mean(axis=1)
    first = np.argmin(avg_sim)
    selected.append(first)
    remaining.remove(first)

    while len(selected) < M:
        max_min_sim = -1
        next_candidate = None

        for idx in remaining:
            min_sim_to_selected = min(sim_matrix[idx, sel] for sel in selected)
            if min_sim_to_selected > max_min_sim:
                max_min_sim = min_sim_to_selected
                next_candidate = idx

        selected.append(next_candidate)
        remaining.remove(next_candidate)

    return selected


codes = []
dps = []

for filename in [
    "raw/20250401_live.csv",
    "raw/data_points.csv",
]:
    print(f"Processing {filename}...")

    # データポイントを読み込み
    data_points = pd.read_csv(filename).to_dict("records")

    # コードを抽出
    for index, d in enumerate(data_points):
        print(f"Processing {index + 1} / {len(data_points)}")

        d["step"] = {
            "number": d["step_number"],
            "instruction": d["instruction"],
            "iteration_number": d["iteration_number"],
            "in_iteration_number": d["in_iteration_number"],
        }
        d["execution_history"] = json.loads(d["execution_history_json"])
        d["input_game_state"] = json.loads(d["input_game_state_json"])
        d["evaluated_game_state"] = json.loads(d["evaluated_game_state_json"])
        d["agent_output"] = json.loads(d["agent_output_json"])
        d["evaluation"] = json.loads(d["evaluation_json"])

        dp = DataPoint.from_dict(d)

        if dp.evaluation.reward <= 0:
            continue

        codes.append(dp.agent_output.code)
        dps.append(dp)

print("Total data points:", len(dps))

# コードを埋め込みベクトルに変換
embeddings = get_embeddings(codes)

print("Generated embeddings for code examples.")

# コサイン類似度行列を計算
sim_matrix = cos_sim(embeddings)

print("Calculated cosine similarity matrix.")

# M個の多様なコードを選択 (ここではM=10とする)
M = 300
selected_indices = select_max_min_similarity(sim_matrix, M)
# selected_indices = [i for i in range(M)]

print("Selected diverse code examples")
# for idx in selected_indices:
#     print(f"\n=== Code {idx} ===")
#     print(codes[idx])

# 選択されたデータポイントを保存
selected_dps = [dps[i] for i in selected_indices]
with open("datasets/converted.jsonl", "w") as f:
    for dp in selected_dps:
        f.write(json.dumps(dp.to_dict()) + "\n")

print("Calculating average similarity of selected pairs...")

# 選択されたデータポイントの全ペアの類似度の平均を出力
similarity_pairs = []
for i in range(len(selected_indices)):
    for j in range(i + 1, len(selected_indices)):
        similarity_pairs.append(sim_matrix[selected_indices[i], selected_indices[j]])
average_similarity = np.mean(similarity_pairs)
print(f"Average similarity of selected pairs: {average_similarity:.4f}")
print(f"Min similarity of selected pairs: {np.min(similarity_pairs):.4f}")
