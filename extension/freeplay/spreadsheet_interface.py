import time
from extension.freeplay.human_interface import HumanInterface
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from extension.freeplay.human_interface import InputKey, OutputKey


def get_spreadsheet_values(spreadsheet_id, range_name, max_retries=3):
    """
    スプレッドシートから特定の範囲の値を取得する関数

    Args:
        spreadsheet_id (str): スプレッドシートのID
        range_name (str): データを取得する範囲（例：'Sheet1!A1:B2'）

    Returns:
        list: 取得したデータ（2次元配列）、エラー時はNone
    """
    for attempt in range(max_retries):
        try:
            # サービスアカウントの認証情報JSONファイルから認証情報を作成
            creds = Credentials.from_service_account_file(
                "credentials/google.json",
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )

            # Sheets APIのサービスを構築
            service = build("sheets", "v4", credentials=creds)

            # APIリクエストを実行してデータを取得
            result = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=range_name)
                .execute()
            )

            values = result.get("values", [])
            print(f"{len(values)} 行のデータを取得しました。")
            return values

        except HttpError as error:
            print(f"試行 {attempt + 1}/{max_retries} でエラーが発生しました: {error}")
            if attempt < max_retries - 1:
                print("60秒後にリトライします...")
                time.sleep(60)
            else:
                print("最大リトライ回数に達しました。")
                return None


def update_spreadsheet_cell(spreadsheet_id, range_name, value, max_retries=3):
    """
    スプレッドシートの特定のセルを更新する関数

    Args:
        spreadsheet_id (str): スプレッドシートのID
        range_name (str): 更新するセルの範囲（例：'Sheet1!A1'）
        value: 更新する値
        max_retries (int): 最大リトライ回数

    Returns:
        dict: 更新結果、エラー時はNone
    """
    for attempt in range(max_retries):
        try:
            # サービスアカウントの認証情報JSONファイルから認証情報を作成
            creds = Credentials.from_service_account_file(
                "credentials/google.json",
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )

            # Sheets APIのサービスを構築
            service = build("sheets", "v4", credentials=creds)

            # 更新するデータを準備（2次元配列として）
            body = {
                "values": [[value]]  # 単一のセルの値を2次元配列として設定
            }

            # APIリクエストを実行してセルを更新
            result = (
                service.spreadsheets()
                .values()
                .update(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption="USER_ENTERED",
                    body=body,
                )
                .execute()
            )

            print(f"セル {range_name} を更新しました。")
            return result

        except HttpError as error:
            print(f"試行 {attempt + 1}/{max_retries} でエラーが発生しました: {error}")
            if attempt < max_retries - 1:
                print("60秒後にリトライします...")
                time.sleep(60)
            else:
                print("最大リトライ回数に達しました。")
                return None


def insert_to_spreadsheet(spreadsheet_id, range_name, values, max_retries=3):
    """
    スプレッドシートにデータを挿入する関数

    Args:
        spreadsheet_id (str): スプレッドシートのID
        range_name (str): データを挿入する範囲（例：'Sheet1!A1:B2'）
        values (list): 挿入するデータ（2次元配列）

    Returns:
        tuple: (result, row_number) resultはAPIレスポンス、row_numberは挿入された最初の行番号
              エラー時は (None, None)
    """
    for attempt in range(max_retries):
        try:
            # サービスアカウントの認証情報JSONファイルから認証情報を作成
            creds = Credentials.from_service_account_file(
                "credentials/google.json",
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )

            # Sheets APIのサービスを構築
            service = build("sheets", "v4", credentials=creds)

            # データを挿入するリクエストを作成
            body = {"values": values}

            # APIリクエストを実行（appendを使用して新しい行を追加）
            result = (
                service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",
                    body=body,
                )
                .execute()
            )

            print(f"{len(values)} 行のデータを追加しました。")
            # updatedRangeから行番号を抽出 (例: 'Sheet1!A371:B371' -> 371)
            updated_range = result.get("updates", {}).get("updatedRange", "")
            row_number = None
            if updated_range:
                # 'Sheet1!A371:B371' から '371' を抽出
                try:
                    row_number = int(
                        "".join(filter(str.isdigit, updated_range.split(":")[0]))
                    )
                except (ValueError, IndexError):
                    print("行番号の抽出に失敗しました。")

            return result, row_number

        except HttpError as error:
            print(f"試行 {attempt + 1}/{max_retries} でエラーが発生しました: {error}")
            if attempt < max_retries - 1:
                print("60秒後にリトライします...")
                time.sleep(60)
            else:
                print("最大リトライ回数に達しました。")
                return None, None


# 実行結果の出力や指示の入力をスプレッドシートを使って行う
# https://docs.google.com/spreadsheets/d/11Y-tE6hSS81UxZ6mSck1t5ahDEs2xd9es-JH4HGYplk/edit?usp=sharing
class SpreadsheetHumanInterface(HumanInterface):
    """スプレッドシートを使用した人間とのインターフェース"""

    def __init__(self, spreadsheet_id: str):
        self.spreadsheet_id = spreadsheet_id

    async def input(self, key: InputKey, context) -> str:
        """スプレッドシートから指示を取得する"""
        cell = ""
        if key == InputKey.INSTRUCTION:
            cell = "Input!E2:E3"
            iteration_number = context["iteration_number"]

        while True:
            try:
                user_input = get_spreadsheet_values(self.spreadsheet_id, cell)
                print(f"User input: {user_input}, iteration: {iteration_number}")
                if user_input and int(user_input[0][0]) == iteration_number:
                    return user_input[1][0]
            except Exception as e:
                print(f"Error in getting instruction: {e}")

            time.sleep(60)

    async def output(self, key: OutputKey, data):
        if key == OutputKey.UPDATE_SYSTEM_STATUS:
            update_spreadsheet_cell(
                self.spreadsheet_id,
                "System!B1",
                data["status"],
            )

        if key == OutputKey.INSERT_ITERATION_DATA:
            _, row_number = insert_to_spreadsheet(
                self.spreadsheet_id,
                "Iterations!A1:Z",
                [
                    [
                        data["version"],
                        data["model"],
                        data["iteration_number"],
                        data["instruction"],
                        data["entities"],
                        data["inventory"],
                    ],
                ],
            )

            self.iteration_row_number = row_number

        if key == OutputKey.INSERT_STEP_DATA:
            _, row_number = insert_to_spreadsheet(
                self.spreadsheet_id,
                "Steps!A1:Z",
                [
                    [
                        data["version"],
                        data["model"],
                        data["iteration_number"],
                        data["in_iteration_number"],
                        data["step_number"],
                        data["entities"],
                        data["inventory"],
                        data["thinking"],
                        data["code"],
                    ],
                ],
            )

            self.step_row_number = row_number

        if key == OutputKey.UPDATE_STEP_EVALUATION:
            update_spreadsheet_cell(
                self.spreadsheet_id,
                f"Steps!J{self.step_row_number}",
                data["evaluation"],
            )

        if key == OutputKey.UPDATE_ITERATION_SUMMARY:
            update_spreadsheet_cell(
                self.spreadsheet_id,
                f"Iterations!G{self.iteration_row_number}",
                data["summary"],
            )
