"""
特徴量エンジニアリングモジュール
競艇予想に使用する特徴量の生成・前処理を担当する
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any

from app.utils.logger import get_logger

logger = get_logger(__name__)

N_BOATS = 6  # 競艇は常に6艇出走

# 使用する特徴量カラム名（モデル学習・推論で共通使用）
FEATURE_COLUMNS = [
    "win_rate",           # 全体勝率
    "motor_score",        # モーター性能スコア
    "course_win_rate",    # 枠番別勝率
    "start_timing",       # スタートタイミング（ST: 0に近いほど良い）
    "weather_code",       # 天候コード（0=晴, 1=曇, 2=雨）
    "wind_speed",         # 風速 (m/s)
    "water_temp",         # 水温 (℃)
    "boat_number",        # 艇番（1〜6）
    "racer_rank",         # 選手ランク（A1=1, A2=2, B1=3, B2=4）
    "motor_2rate",        # モーター2連対率
    "boat_2rate",         # ボート2連対率
    "recent_3_avg",       # 直近3レース平均着順
]


def build_features(race_data: Dict[str, Any]) -> pd.DataFrame:
    """
    レースデータから特徴量DataFrameを構築する

    Args:
        race_data: APIリクエストで受け取ったレース情報辞書
            必須キー: boats（6艇分のリスト）, weather, wind_speed, water_temp

    Returns:
        shape=(6, len(FEATURE_COLUMNS)) の特徴量 DataFrame
    """
    logger.info("特徴量の構築を開始します")

    boats: List[Dict] = race_data.get("boats", [])
    if len(boats) != N_BOATS:
        raise ValueError(f"boats は{N_BOATS}艇必要です。受け取った艇数: {len(boats)}")

    weather = race_data.get("weather", {})
    weather_code = _encode_weather(weather.get("condition", "晴"))
    wind_speed = float(weather.get("wind_speed", 0.0))
    water_temp = float(weather.get("water_temp", 20.0))

    rows = []
    for boat in boats:
        row = {
            "win_rate": float(boat.get("win_rate", 0.0)),
            "motor_score": float(boat.get("motor_score", 50.0)),
            "course_win_rate": float(boat.get("course_win_rate", 0.0)),
            "start_timing": float(boat.get("start_timing", 0.18)),
            "weather_code": weather_code,
            "wind_speed": wind_speed,
            "water_temp": water_temp,
            "boat_number": int(boat.get("boat_number", 1)),
            "racer_rank": _encode_rank(boat.get("racer_rank", "B1")),
            "motor_2rate": float(boat.get("motor_2rate", 30.0)),
            "boat_2rate": float(boat.get("boat_2rate", 30.0)),
            "recent_3_avg": float(boat.get("recent_3_avg", 3.5)),
        }
        rows.append(row)

    df = pd.DataFrame(rows, columns=FEATURE_COLUMNS)
    logger.info(f"特徴量DataFrame shape: {df.shape}")
    return df


def _encode_weather(condition: str) -> int:
    """天候文字列を数値コードに変換する"""
    mapping = {"晴": 0, "曇": 1, "雨": 2, "snow": 3}
    return mapping.get(condition, 0)


def _encode_rank(rank: str) -> int:
    """選手ランクを数値に変換する（小さいほど上位）"""
    mapping = {"A1": 1, "A2": 2, "B1": 3, "B2": 4}
    return mapping.get(rank.upper(), 3)


def preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    学習用DataFrameの前処理を行う

    Args:
        df: 生データのDataFrame（FEATURE_COLUMNS + "label" カラムを含む）

    Returns:
        前処理済みDataFrame
    """
    logger.info("DataFrameの前処理を開始します")

    # 欠損値を列ごとの中央値で補完
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())

    # スタートタイミングのクリッピング（物理的にあり得る範囲）
    if "start_timing" in df.columns:
        df["start_timing"] = df["start_timing"].clip(lower=0.0, upper=1.0)

    # 勝率・2連対率を0-100スケールに正規化（もし0-1スケールなら変換）
    for col in ["win_rate", "course_win_rate", "motor_2rate", "boat_2rate"]:
        if col in df.columns:
            max_val = df[col].max()
            if max_val <= 1.0:
                df[col] = df[col] * 100.0

    logger.info("前処理完了")
    return df


def generate_sample_training_data(n_races: int = 1000) -> pd.DataFrame:
    """
    学習用サンプルデータを生成する（実データが無い場合のテスト用）

    Args:
        n_races: 生成するレース数

    Returns:
        6 * n_races 行の学習用DataFrame
    """
    np.random.seed(42)
    rows = []

    for race_id in range(n_races):
        for boat_num in range(1, N_BOATS + 1):
            # 内側コース（小さい艇番）ほど勝率が高い傾向を模倣
            course_advantage = (6 - boat_num) * 0.03

            row = {
                "win_rate": np.clip(
                    np.random.normal(15 + course_advantage * 100, 8), 0, 60
                ),
                "motor_score": np.random.normal(50, 15),
                "course_win_rate": np.clip(
                    np.random.normal(20 + course_advantage * 100, 10), 0, 80
                ),
                "start_timing": np.clip(np.random.normal(0.17, 0.05), 0.01, 0.50),
                "weather_code": np.random.choice([0, 1, 2], p=[0.6, 0.3, 0.1]),
                "wind_speed": np.clip(np.random.exponential(3), 0, 15),
                "water_temp": np.random.normal(20, 5),
                "boat_number": boat_num,
                "racer_rank": np.random.choice([1, 2, 3, 4], p=[0.2, 0.3, 0.35, 0.15]),
                "motor_2rate": np.clip(np.random.normal(35, 12), 0, 80),
                "boat_2rate": np.clip(np.random.normal(32, 10), 0, 70),
                "recent_3_avg": np.clip(np.random.normal(3.5, 1.5), 1, 6),
                "label": boat_num - 1,  # 0始まりのクラスラベル（仮）
                "race_id": race_id,
            }
            rows.append(row)

    df = pd.DataFrame(rows)

    # 各レースで1着を確率的に決定（コースアドバンテージを反映）
    for race_id in df["race_id"].unique():
        mask = df["race_id"] == race_id
        race_df = df[mask]
        weights = np.array(range(N_BOATS, 0, -1), dtype=float)
        weights /= weights.sum()
        winner = np.random.choice(range(N_BOATS), p=weights)
        df.loc[mask, "label"] = winner

    logger.info(f"サンプルデータ生成完了: {len(df)} 行")
    return df
