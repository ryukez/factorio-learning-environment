from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def insert_to_spreadsheet(spreadsheet_id, range_name, values):
    """
    スプレッドシートにデータを挿入する関数

    Args:
        spreadsheet_id (str): スプレッドシートのID
        range_name (str): データを挿入する範囲（例：'Sheet1!A1:B2'）
        values (list): 挿入するデータ（2次元配列）
    """
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
        print(f"エラーが発生しました: {error}")
        return None
