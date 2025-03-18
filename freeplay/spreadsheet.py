from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time


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


def insert_to_spreadsheet(spreadsheet_id, range_name, values, max_retries=3):
    """
    スプレッドシートにデータを挿入する関数

    Args:
        spreadsheet_id (str): スプレッドシートのID
        range_name (str): データを挿入する範囲（例：'Sheet1!A1:B2'）
        values (list): 挿入するデータ（2次元配列）
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
            return result

        except HttpError as error:
            print(f"試行 {attempt + 1}/{max_retries} でエラーが発生しました: {error}")
            if attempt < max_retries - 1:
                print("60秒後にリトライします...")
                time.sleep(60)
            else:
                print("最大リトライ回数に達しました。")
                return None
