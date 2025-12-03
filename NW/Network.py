#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import ipaddress
import json
import logging
import os
import socket
import subprocess
import sys
import time
from getpass import getpass
from typing import Optional, Tuple

import requests
from requests import Session
from requests.exceptions import ConnectionError, RequestException, Timeout

# --- 設定 ---
LOG_FILE = "router_config.log"
DEFAULT_TIMEOUT = 10  # seconds

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)


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
    """IPアドレス形式の最低限の検証を行う"""
    try:
        ipaddress.ip_address(ip_str)
        return True
    except Exception:
        return False


def create_session() -> Session:
    """requests.Session を生成（必要ならカスタム設定を追加）"""
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "RouterConfigScript/1.0",
            "Accept": "application/json, text/plain, */*",
        }
    )
    return s


def login_router(router_ip: str, username: str, password: str, max_retries: int = 3, timeout: int = DEFAULT_TIMEOUT) -> Optional[Session]:
    """
    ルーター管理画面にログインして認証済みセッションを返す（失敗時は None）。
    再試行は指数バックオフで行う。
    """
    login_url = f"http://{router_ip}/admin"
    payload = {"username": username, "password": password}
    session = create_session()

    for attempt in range(1, max_retries + 1):
        try:
            logging.info("ログイン試行 %d/%d -> %s", attempt, max_retries, login_url)
            resp = session.post(login_url, json=payload, timeout=timeout)

            # ステータスコードが 200 で、レスポンスに明示的なエラー文字列が含まれなければ成功とみなす
            if resp.status_code == 200:
                text = resp.text.lower()
                if ("error" not in text) and ("fail" not in text) and ("unauthorized" not in text):
                    logging.info("ログイン成功")
                    return session
                else:
                    logging.warning("ログイン応答にエラーが含まれます。レスポンスサマリ: %s", resp.text[:200])
            else:
                logging.warning("ログイン失敗: HTTP %d", resp.status_code)

        except Timeout:
            logging.error("ログインタイムアウト (attempt %d)", attempt)
        except ConnectionError:
            logging.error("接続エラー: %s にアクセスできません (attempt %d)", login_url, attempt)
        except RequestException as e:
            logging.error("リクエストエラー: %s (attempt %d)", e, attempt)

        # バックオフ（最後の試行なら待たない）
        if attempt < max_retries:
            sleep_time = 2 ** attempt
            logging.info("リトライ前に %d 秒待機します...", sleep_time)
            time.sleep(sleep_time)

    logging.error("ログインに失敗しました（最大試行回数到達）")
    return None


def change_router_setting(session: Session, router_ip: str, setting_name: str, setting_value: str, timeout: int = DEFAULT_TIMEOUT, dry_run: bool = False) -> bool:
    """
    ルーターの設定を変更する。
    dry_run=True の場合は実際の POST を行わずにログ出力のみ行う。
    """
    url = f"http://{router_ip}/admin/settings/{setting_name}"
    payload = {"setting_value": setting_value}

    logging.info("設定変更: %s -> %s (URL: %s)", setting_name, ("****" if "password" in setting_name.lower() else setting_value), url)
    if dry_run:
        logging.info("dry-run モード: 実際のリクエストは送信されません。")
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
                logging.info("'%s' を更新しました。", setting_name)
                return True
            else:
                logging.error("API応答で失敗: %s", resp.text[:500])
                return False
        else:
            logging.error("設定変更失敗: HTTP %d - %s", resp.status_code, resp.text[:500])
            return False

    except Timeout:
        logging.error("設定変更タイムアウト: %s", setting_name)
    except ConnectionError:
        logging.error("接続エラー: %s にアクセスできません", url)
    except RequestException as e:
        logging.error("設定変更リクエストエラー: %s", e)

    return False


def confirm(prompt: str = "これらの設定を変更してもよろしいですか？ (y/n): ") -> bool:
    ans = input(prompt).strip().lower()
    return ans in ("y", "yes")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ルーター設定変更スクリプト")
    p.add_argument("--router", "-r", help="ルーターのIPアドレス（省略すると自動検出）")
    p.add_argument("--username", "-u", default="admin", help="ログインユーザー名（デフォルト: admin）")
    p.add_argument("--no-confirm", action="store_true", help="変更確認プロンプトをスキップする")
    p.add_argument("--dry-run", action="store_true", help="実際のリクエストを送信せずログのみ出す")
    p.add_argument("--retries", type=int, default=3, help="ログイン試行回数（デフォルト: 3）")
    return p.parse_args()


def main():
    args = parse_args()

    router_ip = args.router or detect_default_gateway()
    if not router_ip:
        router_ip = input("ルーターのIPアドレスを入力してください: ").strip()

    if not validate_ip(router_ip):
        logging.error("無効なIPアドレス: %s", router_ip)
        print("無効なIPアドレスです。スクリプトを終了します。")
        return

    logging.info("ターゲットルーター: %s", router_ip)

    username = args.username
    password = getpass("ルーターのパスワードを入力してください: ")

    session = login_router(router_ip, username, password, max_retries=args.retries)
    if not session:
        print("ログインに失敗しました。ログを確認してください。")
        return

    # 変更したい設定をユーザーから取得
    wifi_ssid = input("新しいWi-Fi SSID（ネットワーク名）を入力してください: ").strip()
    wifi_password = getpass("新しいWi-Fiパスワードを入力してください: ").strip()

    print("\n変更予定の設定:")
    print(f"Wi-Fi SSID: {wifi_ssid}")
    print(f"Wi-Fi パスワード: {'*' * len(wifi_password)}")

    if not args.no_confirm:
        if not confirm():
            print("設定変更がキャンセルされました。")
            return
    else:
        logging.info("--no-confirm により確認プロンプトをスキップします。")

    # 実行
    ssid_ok = change_router_setting(session, router_ip, "wifi_ssid", wifi_ssid, dry_run=args.dry_run)
    pwd_ok = change_router_setting(session, router_ip, "wifi_password", wifi_password, dry_run=args.dry_run)

    if ssid_ok and pwd_ok:
        logging.info("すべての設定が更新されました。")
        print("\n設定変更が完了しました。ルーターによりWi-Fiの再起動が発生する場合があります。")
    else:
        logging.warning("一部またはすべての設定変更に失敗しました。ログを確認してください。")
        print("\n一部の設定変更が失敗しました。ログを確認してください。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nユーザーにより中断されました。")
    except Exception as e:
        logging.exception("予期せぬエラー: %s", e)
        print(f"予期しないエラーが発生しました: {e}")
