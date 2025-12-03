from typing import List, Tuple, Optional
import svgwrite
import random
import numpy as np
from dataclasses import dataclass
import logging

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class DrawingConstants:
    """描画用の定数"""
    SEGMENT_COUNT: int = 7
    PATTERN_RADIUS: Tuple[int, int] = (20, 15)
    HEAD_RADIUS: Tuple[int, int] = (30, 20)
    EYE_OUTER_RADIUS: int = 5
    EYE_INNER_RADIUS: int = 2
    TONGUE_LENGTH: int = 30
    STROKE_WIDTH: int = 60
    HEAD_OFFSET: int = 10

@dataclass(frozen=True)
class Colors:
    """アナコンダの描画に使用する色の定数"""
    BACKGROUND: str = "#2F4F4F"  # ジャングルの背景色
    BODY: str = "#4A5D23"       # アナコンダの体の色
    PATTERN: str = "#2F3A17"    # 模様の色
    EYE_OUTER: str = "yellow"   # 目の外側
    EYE_INNER: str = "black"    # 目の内側
    TONGUE: str = "red"         # 舌の色

class AnacondaDrawer:
    """
    アナコンダのSVG描画を行うクラス
    """

    def __init__(self, filename: str = "anaconda.svg", size: int = 600):
        """
        Args:
            filename: 出力するSVGファイル名
            size: SVGのサイズ（幅・高さ）
        """
        if not isinstance(size, int) or size <= 0:
            raise ValueError("サイズは正の整数である必要があります")

        self.size = size
        self.dwg = svgwrite.Drawing(filename, size=(size, size))
        self.colors = Colors()
        self.constants = DrawingConstants()
        self.points: List[Tuple[int, int]] = []

    def _generate_body_points(self) -> None:
        """
        アナコンダの体の座標を生成（常に SEGMENT_COUNT 点を返す）
        """
        seg = self.constants.SEGMENT_COUNT
        # 左右に50pxのマージンをとる
        x_coords = np.linspace(50, self.size - 50, seg)
        # 正弦波で自然な蛇行を作る
        amplitude = max(40, int(self.size * 0.15))  # サイズに応じた振幅
        phase = random.random() * 2 * np.pi
        y_center = self.size // 2
        angles = np.linspace(0, 2 * np.pi, seg) + phase
        y_coords = y_center + amplitude * np.sin(angles)
        # 整数のタプルに変換
        self.points = [(int(x), int(y)) for x, y in zip(x_coords, y_coords)]

        # 最低でも2点は必要
        if len(self.points) < 2:
            raise RuntimeError("体の座標が不足しています（points < 2）")

    def _draw_background(self) -> None:
        """背景を描画"""
        self.dwg.add(self.dwg.rect(
            insert=(0, 0),
            size=(self.size, self.size),
            fill=self.colors.BACKGROUND
        ))

    def _draw_body(self) -> None:
        """アナコンダの体を描画（polyline + 太めの stroke）"""
        if not self.points:
            self._generate_body_points()

        body_group = self.dwg.g(stroke=self.colors.BODY,
                               stroke_width=self.constants.STROKE_WIDTH,
                               stroke_linecap="round",
                               fill="none")

        # polyline は点のリストを受け取る
        body_group.add(self.dwg.polyline(points=self.points))
        self.dwg.add(body_group)

    def _draw_patterns(self) -> None:
        """体の模様を描画（模様は体の中間点に楕円を描く）"""
        if not self.points:
            self._generate_body_points()

        pattern_group = self.dwg.g(fill=self.colors.PATTERN, stroke="none")

        # 中間点を計算
        if len(self.points) > 1:
            for (x1, y1), (x2, y2) in zip(self.points[:-1], self.points[1:]):
                mid_x = (x1 + x2) // 2
                mid_y = (y1 + y2) // 2
                # 少しランダムに位置や大きさを変えて自然さを出す
                rx = int(self.constants.PATTERN_RADIUS[0] * (0.8 + random.random() * 0.4))
                ry = int(self.constants.PATTERN_RADIUS[1] * (0.8 + random.random() * 0.4))
                pattern_group.add(self.dwg.ellipse(center=(mid_x, mid_y), r=(rx, ry)))
        self.dwg.add(pattern_group)

    def _draw_head(self) -> None:
        """頭部を描画（先頭の座標を基準）"""
        if not self.points:
            self._generate_body_points()

        head_x, head_y = self.points[0]
        head_group = self.dwg.g()

        # 頭部の楕円
        head_group.add(self.dwg.ellipse(
            center=(head_x - self.constants.HEAD_OFFSET, head_y),
            r=self.constants.HEAD_RADIUS,
            fill=self.colors.BODY
        ))

        # 目 (左右に少しずらして2つ)
        eye_offset_x = 15
        eye_offset_y = -8
        self._add_eye_to_group(head_group, head_x - eye_offset_x, head_y + eye_offset_y)
        self._add_eye_to_group(head_group, head_x - eye_offset_x, head_y - eye_offset_y)

        # 舌
        self._add_tongue_to_group(head_group, head_x - 40, head_y)

        self.dwg.add(head_group)

    def _add_eye_to_group(self, group: svgwrite.container.Group, x: int, y: int) -> None:
        """目をグループに追加"""
        group.add(self.dwg.circle(center=(x, y), r=self.constants.EYE_OUTER_RADIUS, fill=self.colors.EYE_OUTER))
        group.add(self.dwg.circle(center=(x, y), r=self.constants.EYE_INNER_RADIUS, fill=self.colors.EYE_INNER))

    def _add_tongue_to_group(self, group: svgwrite.container.Group, x: int, y: int) -> None:
        """分岐した舌をグループに追加"""
        tongue_group = self.dwg.g(stroke=self.colors.TONGUE,
                                  stroke_width=2,
                                  fill="none",
                                  stroke_linecap="round")

        length = self.constants.TONGUE_LENGTH
        # 上下に2本の舌を出す
        offsets = [-int(length / 2), int(length / 2)]
        for offset in offsets:
            control_x = x - int(length * 0.4)
            control_y = y + offset // 2
            end_x = x - length
            end_y = y + offset
            # 二次ベジェ曲線 (Q)
            path_d = f"M {x} {y} Q {control_x} {control_y} {end_x} {end_y}"
            tongue_group.add(self.dwg.path(d=path_d))
        # 舌先をV字に少し折る（先端を描画）
        tip_group = self.dwg.g(stroke=self.colors.TONGUE, stroke_width=2, fill="none")
        tip_group.add(self.dwg.path(d=f"M {x - length} {y - int(length / 2)} l -6 6"))
        tip_group.add(self.dwg.path(d=f"M {x - length} {y + int(length / 2)} l -6 -6"))
        group.add(tongue_group)
        group.add(tip_group)

    def draw(self) -> bool:
        """アナコンダの全体を描画し、成功/失敗を返す"""
        try:
            self._generate_body_points()
            self._draw_background()
            self._draw_body()
            self._draw_patterns()
            self._draw_head()
            self.save()
            return True
        except Exception as e:
            logger.exception("SVGの生成中にエラーが発生しました")
            return False

    def save(self) -> None:
        """SVGファイルを保存"""
        try:
            self.dwg.save()
            logger.info(f"SVGファイルが作成されました: {self.dwg.filename}")
        except IOError as e:
            logger.error(f"ファイル保存エラー: {e}")
            raise

def create_anaconda_svg(filename: str = "anaconda.svg", size: int = 600) -> bool:
    drawer = AnacondaDrawer(filename, size)
    return drawer.draw()

if __name__ == "__main__":
    create_anaconda_svg()
