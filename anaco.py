from typing import List, Tuple
import svgwrite
import random
import numpy as np
from dataclasses import dataclass

@dataclass(frozen=True)
class DrawingConstants:
    """描画用の定数"""
    SEGMENT_COUNT = 7
    PATTERN_RADIUS = (20, 15)
    HEAD_RADIUS = (30, 20)
    EYE_OUTER_RADIUS = 5
    EYE_INNER_RADIUS = 2
    TONGUE_LENGTH = 30
    STROKE_WIDTH = 60
    HEAD_OFFSET = 10

@dataclass(frozen=True)
class Colors:
    """アナコンダの描画に使用する色の定数"""
    BACKGROUND = "#2F4F4F"  # ジャングルの背景色
    BODY = "#4A5D23"       # アナコンダの体の色
    PATTERN = "#2F3A17"    # 模様の色
    EYE_OUTER = "yellow"   # 目の外側
    EYE_INNER = "black"    # 目の内側
    TONGUE = "red"         # 舌の色

class AnacondaDrawer:
    def __init__(self, filename: str = "anaconda.svg", size: int = 600):
        """
        アナコンダSVG描画クラスの初期化
        
        Args:
            filename (str): 出力するSVGファイル名
            size (int): SVGのサイズ（幅・高さ）
        """
        if not isinstance(size, int) or size <= 0:
            raise ValueError("サイズは正の整数である必要があります")
            
        self.size = size
        self.dwg = svgwrite.Drawing(filename, size=(size, size))
        self.colors = Colors()
        self.constants = DrawingConstants()
        self.points: List[Tuple[int, int]] = []
        
    def _generate_body_points(self) -> None:
        """アナコンダの体の座標を生成（NumPyを使用して最適化）"""
        segment_width = (self.size - 100) // self.constants.SEGMENT_COUNT
        
        # X座標を一括生成
        x_coords = np.arange(50, self.size - 50, segment_width)
        
        # より自然な動きのために正弦波を使用
        amplitude = 100
        phase = random.random() * 2 * np.pi
        y_coords = self.size // 2 + amplitude * np.sin(np.linspace(0, 2 * np.pi, self.constants.SEGMENT_COUNT + 1) + phase)
        
        # numpy配列をタプルのリストに変換
        self.points = list(zip(x_coords, y_coords.astype(int)))
            
    def _draw_background(self) -> None:
        """背景を描画"""
        self.dwg.add(self.dwg.rect(
            insert=(0, 0),
            size=(self.size, self.size),
            fill=self.colors.BACKGROUND
        ))
        
    def _draw_body(self) -> None:
        """アナコンダの体を描画（グループ化して最適化）"""
        body_group = self.dwg.g(stroke=self.colors.BODY, 
                              stroke_width=self.constants.STROKE_WIDTH,
                              stroke_linecap="round")
        
        body_group.add(self.dwg.polyline(
            points=self.points,
            fill="none"
        ))
        
        self.dwg.add(body_group)
        
    def _draw_patterns(self) -> None:
        """体の模様を描画（グループ化して最適化）"""
        pattern_group = self.dwg.g(fill=self.colors.PATTERN)
        
        # 中間点を一括計算
        points_array = np.array(self.points)
        mid_points = (points_array[:-1] + points_array[1:]) // 2
        
        for mid_x, mid_y in mid_points:
            pattern_group.add(self.dwg.ellipse(
                center=(mid_x, mid_y),
                r=self.constants.PATTERN_RADIUS
            ))
            
        self.dwg.add(pattern_group)
            
    def _draw_head(self) -> None:
        """頭部を描画（グループ化して最適化）"""
        head_x, head_y = self.points[0]
        head_group = self.dwg.g()
        
        # 頭部の形状
        head_group.add(self.dwg.ellipse(
            center=(head_x - self.constants.HEAD_OFFSET, head_y),
            r=self.constants.HEAD_RADIUS,
            fill=self.colors.BODY
        ))
        
        # 目と舌をグループに追加
        self._add_eye_to_group(head_group, head_x - 25, head_y - 10)
        self._add_tongue_to_group(head_group, head_x - 40, head_y)
        
        self.dwg.add(head_group)
        
    def _add_eye_to_group(self, group, x, y) -> None:
        """目をグループに追加"""
        group.add(self.dwg.circle(
            center=(x, y),
            r=self.constants.EYE_OUTER_RADIUS,
            fill=self.colors.EYE_OUTER
        ))
        group.add(self.dwg.circle(
            center=(x, y),
            r=self.constants.EYE_INNER_RADIUS,
            fill=self.colors.EYE_INNER
        ))
        
    def _add_tongue_to_group(self, group, x, y) -> None:
        """舌をグループに追加"""
        group.add(self.dwg.line(
            start=(x, y),
            end=(x - self.constants.TONGUE_LENGTH, y),
            stroke=self.colors.TONGUE,
            stroke_width=2
        ))

    def save(self) -> None:
        """SVGファイルを保存"""
        try:
            self.dwg.save()
        except IOError as e:
            print(f"ファイル保存エラー: {e}")

# 使用例
drawer = AnacondaDrawer()
drawer._generate_body_points()
drawer._draw_background()
drawer._draw_body()
drawer._draw_patterns()
drawer._draw_head()
drawer.save()     
    def _add_eye_to_group(self, group: svgwrite.container.Group, x: int, y: int) -> None:
        """目をグループに追加"""
        group.add(self.dwg.circle(
            center=(x, y),
            r=self.constants.EYE_OUTER_RADIUS,
            fill=self.colors.EYE_OUTER
        ))
        group.add(self.dwg.circle(
            center=(x, y),
            r=self.constants.EYE_INNER_RADIUS,
            fill=self.colors.EYE_INNER
        ))
        
    def _add_tongue_to_group(self, group: svgwrite.container.Group, x: int, y: int) -> None:
        """舌をグループに追加"""
        tongue_group = self.dwg.g(stroke=self.colors.TONGUE,
                                stroke_width=3,
                                fill="none")
        
        for offset in [-15, 15]:  # 上下の舌の先端
            tongue_group.add(self.dwg.path(
                d=f"M {x} {y} Q {x-20} {y+offset//2} {x-30} {y+offset}"
            ))
            
        group.add(tongue_group)
            
    def draw(self) -> bool:
        """アナコンダの全体を描画し、成功/失敗を返す"""
        try:
            self._generate_body_points()
            self._draw_background()
            self._draw_body()
            self._draw_patterns()
            self._draw_head()
            self.dwg.save()
            print(f"SVGファイルが作成されました: {self.dwg.filename}")
            return True
        except Exception as e:
            print(f"SVGの生成中にエラーが発生しました: {str(e)}")
            return False

def create_anaconda_svg(filename: str = "anaconda.svg", size: int = 600) -> bool:
    """
    アナコンダのSVGを生成する関数
    
    Args:
        filename (str): 出力するSVGファイル名
        size (int): SVGのサイズ（幅・高さ）
    
    Returns:
        bool: 生成が成功した場合はTrue、失敗した場合はFalse
    """
    drawer = AnacondaDrawer(filename, size)
    return drawer.draw()

if __name__ == "__main__":
    create_anaconda_svg()
