#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import ipaddress
import json
import os
import socket
import subprocess
import sys
import time
from getpass import getpass
from typing import Optional, Tuple, Dict, Any

import requests
from requests import Session
from requests.exceptions import RequestException, Timeout

# 共通モジュールのインポート
from shared.logging_utils import setup_logging
from shared.exceptions import (
    AppError,
    ConnectionError as AppConnectionError,
    ValidationError
)
from shared.config import get_config

# --- 設定 ---
LOG_FILE = "router_config.log"
DEFAULT_TIMEOUT = 10  # seconds

# ロギング設定
logger = setup_logging(__name__)
config = get_config()


def detect_default_gateway() -> Optional[str]:
    """
    OSに合わせてデフォルトゲートウェイ（ルーターIP）を検出する。
    見つからなければ None を返す（呼び出し元で入力を求める）。
    """
    try:
        if sys.platform.startswith("linux") or sys.platform.startswith("darwin"):
            # まず `ip route` を試す（Linux/macOS）
            try:
                out = subprocess.check_output(["ip", "route"], stderr=subprocess.DEVNULL, text=True)
                for line in out.splitlines():
                    # 例: default via 192.0.2.1 dev eth0 ...
                    if line.startswith("default") and "via" in line:
                        parts = line.split()
                        via_idx = parts.index("via")
                        return parts[via_idx + 1]
            except Exception:
                # fallback to `route -n` on some systems
                try:
                    out = subprocess.check_output(["route", "-n"], stderr=subprocess.DEVNULL, text=True)
                    for line in out.splitlines():
                        cols = line.split()
                        if len(cols) >= 2 and cols[0] != "0.0.0.0" and cols[1] == "0.0.0.0":
                            return cols[0]
                except Exception:
                    pass

            # macOS alternative: `netstat -rn`
            try:
                out = subprocess.check_output(["netstat", "-rn"], stderr=subprocess.DEVNULL, text=True)
                for line in out.splitlines():
                    if line.startswith("default") or line.startswith("0.0.0.0"):
                        cols = line.split()
                        if len(cols) >= 2:
                            return cols[1]
            except Exception:
                pass

        elif sys.platform.startswith("win"):
            # Windows: ipconfig /all を解析
            try:
                out = subprocess.check_output(["ipconfig"], text=True, stderr=subprocess.DEVNULL)
                for line in out.splitlines():
                    if "Default Gateway" in line:
                        if ":" in line:
                            gw = line.split(":", 1)[1].strip()
                        else:
                            gw = line.split()[-1].strip()
                        if gw:
                            return gw
            except Exception:
                pass

    except Exception as e:
        logging.debug("デフォルトゲートウェイ検出中に予期しないエラー: %s", e)

    return None


def validate_ip(ip_str: str) -> bool:
    """
    IPアドレス形式の検証を行う

    Args:
        ip_str: 検証するIPアドレス文字列

    Returns:
        bool: 有効なIPアドレスの場合True

    Raises:
        ValidationError: 空文字列の場合
    """
    if not ip_str or not ip_str.strip():
        raise ValidationError(
            "IPアドレスが空です",
            code="EMPTY_IP_ADDRESS"
        )

    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError as e:
        logger.debug(f"IPアドレス検証失敗: {ip_str} - {e}")
        return False


def create_session() -> Session:
    """
    requests.Session を生成

    Returns:
        Session: カスタムヘッダー設定済みのセッション
    """
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "RouterConfigScript/1.0",
            "Accept": "application/json, text/plain, */*",
        }
    )
    return s


def login_router(
    router_ip: str,
    username: str,
    password: str,
    max_retries: int = 3,
    timeout: int = DEFAULT_TIMEOUT
) -> Optional[Session]:
    """
    ルーター管理画面にログインして認証済みセッションを返す

    Args:
        router_ip: ルーターのIPアドレス
        username: ログインユーザー名
        password: ログインパスワード
        max_retries: 最大リトライ回数（デフォルト: 3）
        timeout: タイムアウト秒数（デフォルト: DEFAULT_TIMEOUT）

    Returns:
        Optional[Session]: 認証済みセッション、失敗時はNone

    Raises:
        ValidationError: パラメータが不正な場合
        AppConnectionError: 接続に失敗した場合
    """
    # 入力検証
    if not router_ip:
        raise ValidationError(
            "ルーターIPアドレスが指定されていません",
            code="MISSING_ROUTER_IP"
        )
    if not username:
        raise ValidationError(
            "ユーザー名が指定されていません",
            code="MISSING_USERNAME"
        )
    if not password:
        raise ValidationError(
            "パスワードが指定されていません",
            code="MISSING_PASSWORD"
        )
    if max_retries <= 0:
        raise ValidationError(
            f"max_retriesは正の整数である必要があります: {max_retries}",
            code="INVALID_MAX_RETRIES",
            details={'value': max_retries, 'expected': '>0'}
        )

    login_url = f"http://{router_ip}/admin"
    payload = {"username": username, "password": password}
    session = create_session()

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("ログイン試行 %d/%d -> %s", attempt, max_retries, login_url)
            resp = session.post(login_url, json=payload, timeout=timeout)

            # ステータスコードが 200 で、レスポンスに明示的なエラー文字列が含まれなければ成功とみなす
            if resp.status_code == 200:
                text = resp.text.lower()
                if ("error" not in text) and ("fail" not in text) and ("unauthorized" not in text):
                    logger.info("ログイン成功")
                    return session
                else:
                    logger.warning("ログイン応答にエラーが含まれます。レスポンスサマリ: %s", resp.text[:200])
            else:
                logger.warning("ログイン失敗: HTTP %d", resp.status_code)

        except Timeout:
            logger.error("ログインタイムアウト (attempt %d)", attempt)
        except requests.ConnectionError as e:
            logger.error("接続エラー: %s にアクセスできません (attempt %d)", login_url, attempt)
            if attempt == max_retries:
                raise AppConnectionError(
                    f"ルーター {router_ip} への接続に失敗しました",
                    code="ROUTER_CONNECTION_FAILED",
                    details={'router_ip': router_ip, 'url': login_url, 'attempts': max_retries}
                ) from e
        except RequestException as e:
            logger.error("リクエストエラー: %s (attempt %d)", e, attempt)

        # バックオフ（最後の試行なら待たない）
        if attempt < max_retries:
            sleep_time = 2 ** attempt
            logger.info("リトライ前に %d 秒待機します...", sleep_time)
            time.sleep(sleep_time)

    logger.error("ログインに失敗しました（最大試行回数到達）")
    return None


def change_router_setting(
    session: Session,
    router_ip: str,
    setting_name: str,
    setting_value: str,
    timeout: int = DEFAULT_TIMEOUT,
    dry_run: bool = False
) -> bool:
    """
    ルーターの設定を変更する

    Args:
        session: 認証済みのセッション
        router_ip: ルーターのIPアドレス
        setting_name: 設定名
        setting_value: 設定値
        timeout: タイムアウト秒数（デフォルト: DEFAULT_TIMEOUT）
        dry_run: Trueの場合は実際のPOSTを行わずログ出力のみ（デフォルト: False）

    Returns:
        bool: 設定変更が成功した場合True

    Raises:
        ValidationError: パラメータが不正な場合
        AppError: 設定変更に失敗した場合
    """
    # 入力検証
    if not session:
        raise ValidationError(
            "セッションが指定されていません",
            code="MISSING_SESSION"
        )
    if not router_ip:
        raise ValidationError(
            "ルーターIPアドレスが指定されていません",
            code="MISSING_ROUTER_IP"
        )
    if not setting_name:
        raise ValidationError(
            "設定名が指定されていません",
            code="MISSING_SETTING_NAME"
        )

    url = f"http://{router_ip}/admin/settings/{setting_name}"
    payload: Dict[str, Any] = {"setting_value": setting_value}

    logger.info(
        "設定変更: %s -> %s (URL: %s)",
        setting_name,
        ("****" if "password" in setting_name.lower() else setting_value),
        url
    )

    if dry_run:
        logger.info("dry-run モード: 実際のリクエストは送信されません。")
        return True

    try:
        resp = session.post(url, json=payload, timeout=timeout)

        if resp.status_code == 200:
            # 念のため JSON に成功フラグがあるか確認
            try:
                data = resp.json()
                success = data.get("success", True) if isinstance(data, dict) else True
            except Exception:
                success = True  # JSON parse できなくてもステータス200で成功とみなす

            if success:
                logger.info("'%s' を更新しました。", setting_name)
                return True
            else:
                logger.error("API応答で失敗: %s", resp.text[:500])
                raise AppError(
                    f"設定'{setting_name}'の更新に失敗しました",
                    code="SETTING_UPDATE_FAILED",
                    details={'setting_name': setting_name, 'response': resp.text[:500]}
                )
        else:
            logger.error("設定変更失敗: HTTP %d - %s", resp.status_code, resp.text[:500])
            raise AppError(
                f"設定変更失敗: HTTP {resp.status_code}",
                code="HTTP_ERROR",
                details={'status_code': resp.status_code, 'setting_name': setting_name}
            )

    except Timeout as e:
        logger.error("設定変更タイムアウト: %s", setting_name)
        raise AppError(
            f"設定'{setting_name}'の変更がタイムアウトしました",
            code="SETTING_CHANGE_TIMEOUT",
            details={'setting_name': setting_name, 'timeout': timeout}
        ) from e
    except requests.ConnectionError as e:
        logger.error("接続エラー: %s にアクセスできません", url)
        raise AppConnectionError(
            f"ルーターへの接続に失敗しました: {url}",
            code="CONNECTION_ERROR",
            details={'url': url}
        ) from e
    except RequestException as e:
        logger.error("設定変更リクエストエラー: %s", e)
        raise AppError(
            f"設定変更中にリクエストエラーが発生しました",
            code="REQUEST_ERROR",
            details={'setting_name': setting_name, 'error': str(e)}
        ) from e


def confirm(prompt: str = "これらの設定を変更してもよろしいですか？ (y/n): ") -> bool:
    """
    ユーザーに確認を求める

    Args:
        prompt: 表示するプロンプト文字列

    Returns:
        bool: ユーザーが承認した場合True
    """
    ans = input(prompt).strip().lower()
    return ans in ("y", "yes")


def parse_args() -> argparse.Namespace:
    """
    コマンドライン引数をパースする

    Returns:
        argparse.Namespace: パース済みの引数
    """
    p = argparse.ArgumentParser(description="ルーター設定変更スクリプト")
    p.add_argument("--router", "-r", help="ルーターのIPアドレス（省略すると自動検出）")
    p.add_argument("--username", "-u", default="admin", help="ログインユーザー名（デフォルト: admin）")
    p.add_argument("--no-confirm", action="store_true", help="変更確認プロンプトをスキップする")
    p.add_argument("--dry-run", action="store_true", help="実際のリクエストを送信せずログのみ出す")
    p.add_argument("--retries", type=int, default=3, help="ログイン試行回数（デフォルト: 3）")
    return p.parse_args()


def main() -> int:
    """
    メイン実行関数

    Returns:
        int: 終了コード (0: 成功, 1: 失敗)
    """
    try:
        args = parse_args()

        router_ip = args.router or detect_default_gateway()
        if not router_ip:
            router_ip = input("ルーターのIPアドレスを入力してください: ").strip()

        if not validate_ip(router_ip):
            logger.error("無効なIPアドレス: %s", router_ip)
            print("無効なIPアドレスです。スクリプトを終了します。")
            return 1

        logger.info("ターゲットルーター: %s", router_ip)

        username = args.username
        password = getpass("ルーターのパスワードを入力してください: ")

        session = login_router(router_ip, username, password, max_retries=args.retries)
        if not session:
            print("ログインに失敗しました。ログを確認してください。")
            return 1

        # 変更したい設定をユーザーから取得
        wifi_ssid = input("新しいWi-Fi SSID（ネットワーク名）を入力してください: ").strip()
        wifi_password = getpass("新しいWi-Fiパスワードを入力してください: ").strip()

        # 入力検証
        if not wifi_ssid:
            raise ValidationError(
                "Wi-Fi SSIDが空です",
                code="EMPTY_SSID"
            )
        if len(wifi_password) < 8:
            raise ValidationError(
                "Wi-Fiパスワードは8文字以上である必要があります",
                code="PASSWORD_TOO_SHORT",
                details={'length': len(wifi_password), 'minimum': 8}
            )

        print("\n変更予定の設定:")
        print(f"Wi-Fi SSID: {wifi_ssid}")
        print(f"Wi-Fi パスワード: {'*' * len(wifi_password)}")

        if not args.no_confirm:
            if not confirm():
                print("設定変更がキャンセルされました。")
                return 0
        else:
            logger.info("--no-confirm により確認プロンプトをスキップします。")

        # 実行
        ssid_ok = change_router_setting(session, router_ip, "wifi_ssid", wifi_ssid, dry_run=args.dry_run)
        pwd_ok = change_router_setting(session, router_ip, "wifi_password", wifi_password, dry_run=args.dry_run)

        if ssid_ok and pwd_ok:
            logger.info("すべての設定が更新されました。")
            print("\n設定変更が完了しました。ルーターによりWi-Fiの再起動が発生する場合があります。")
            return 0
        else:
            logger.warning("一部またはすべての設定変更に失敗しました。ログを確認してください。")
            print("\n一部の設定変更が失敗しました。ログを確認してください。")
            return 1

    except ValidationError as e:
        logger.error(f"検証エラー: {e}")
        print(f"エラー: {e}")
        return 1

    except AppConnectionError as e:
        logger.error(f"接続エラー: {e}")
        print(f"接続エラー: {e}")
        return 1

    except AppError as e:
        logger.error(f"アプリケーションエラー: {e}")
        print(f"エラー: {e}")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nユーザーにより中断されました。")
        sys.exit(130)
    except Exception as e:
        logger.exception("予期せぬエラー: %s", e)
        print(f"予期しないエラーが発生しました: {e}")
        sys.exit(1)
