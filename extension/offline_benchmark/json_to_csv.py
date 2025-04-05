import json
import pandas as pd
import argparse
from pathlib import Path


def convert_json_to_csv(input_path: str, output_path: str) -> None:
    """
    JSON配列ファイルをCSVファイルに変換する

    Args:
        input_path (str): 入力JSONファイルのパス
        output_path (str): 出力CSVファイルのパス
    """
    # JSONファイルを読み込む
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # データがリストでない場合はエラー
    if not isinstance(data, list):
        raise ValueError("入力JSONファイルは配列形式である必要があります")

    # DataFrameに変換
    df = pd.DataFrame(data)

    # CSVとして出力
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"変換完了: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="JSON配列をCSVに変換するツール")
    parser.add_argument("input", help="入力JSONファイルのパス")
    parser.add_argument("output", help="出力CSVファイルのパス")

    args = parser.parse_args()

    try:
        convert_json_to_csv(args.input, args.output)
    except Exception as e:
        print(f"エラーが発生しました: {str(e)}")
        return 1

    return 0


if __name__ == "__main__":
    main()
