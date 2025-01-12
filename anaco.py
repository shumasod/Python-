from typing import List, Tuple
import svgwrite
import random
from dataclasses import dataclass

@dataclass
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
        if size <= 0:
            raise ValueError("サイズは正の整数である必要があります")
            
        self.size = size
        self.dwg = svgwrite.Drawing(filename, size=(size, size))
        self.colors = Colors()
        self.points: List[Tuple[int, int]] = []
        
    def _generate_body_points(self) -> None:
        """アナコンダの体の座標を生成"""
        self.points = [(50, self.size//2)]
        segment_width = (self.size - 100) // 7
        
        for i in range(1, 8):
            x = 50 + segment_width * i
            # より自然な動きのために正弦波を使用
            y = self.size//2 + int(random.randint(-100, 100) * 
                                 abs(random.random() * random.random()))
            self.points.append((x, y))
            
    def _draw_background(self) -> None:
        """背景を描画"""
        self.dwg.add(self.dwg.rect(
            insert=(0, 0),
            size=(self.size, self.size),
            fill=self.colors.BACKGROUND
        ))
        
    def _draw_body(self) -> None:
        """アナコンダの体を描画"""
        self.dwg.add(self.dwg.polyline(
            points=self.points,
            fill="none",
            stroke=self.colors.BODY,
            stroke_width=60,
            stroke_linecap="round"  # 端を丸くして自然な見た目に
        ))
        
    def _draw_patterns(self) -> None:
        """体の模様を描画"""
        for i in range(len(self.points) - 1):
            x1, y1 = self.points[i]
            x2, y2 = self.points[i+1]
            mid_x = (x1 + x2) // 2
            mid_y = (y1 + y2) // 2
            
            # 楕円形の模様でより自然な見た目に
            self.dwg.add(self.dwg.ellipse(
                center=(mid_x, mid_y),
                r=(20, 15),
                fill=self.colors.PATTERN
            ))
            
    def _draw_head(self) -> None:
        """頭部を描画"""
        head_x, head_y = self.points[0]
        
        # 頭部の形状
        self.dwg.add(self.dwg.ellipse(
            center=(head_x-10, head_y),
            r=(30, 20),
            fill=self.colors.BODY
        ))
        
        # 目
        self._draw_eye(head_x-25, head_y-10)
        
        # 舌
        self._draw_tongue(head_x-40, head_y)
        
    def _draw_eye(self, x: int, y: int) -> None:
        """目を描画"""
        self.dwg.add(self.dwg.circle(
            center=(x, y),
            r=5,
            fill=self.colors.EYE_OUTER
        ))
        self.dwg.add(self.dwg.circle(
            center=(x, y),
            r=2,
            fill=self.colors.EYE_INNER
        ))
        
    def _draw_tongue(self, x: int, y: int) -> None:
        """舌を描画"""
        for offset in [-15, 15]:  # 上下の舌の先端
            self.dwg.add(self.dwg.path(
                d=f"M {x} {y} Q {x-20} {y+offset//2} {x-30} {y+offset}",
                stroke=self.colors.TONGUE,
                stroke_width=3,
                fill="none"
            ))
            
    def draw(self) -> None:
        """アナコンダの全体を描画"""
        try:
            self._generate_body_points()
            self._draw_background()
            self._draw_body()
            self._draw_patterns()
            self._draw_head()
            self.dwg.save()
            print(f"SVGファイルが作成されました: {self.dwg.filename}")
        except Exception as e:
            print(f"SVGの生成中にエラーが発生しました: {str(e)}")

def create_anaconda_svg(filename: str = "anaconda.svg", size: int = 600) -> None:
    """
    アナコンダのSVGを生成する関数
    
    Args:
        filename (str): 出力するSVGファイル名
        size (int): SVGのサイズ（幅・高さ）
    """
    drawer = AnacondaDrawer(filename, size)
    drawer.draw()

if __name__ == "__main__":
    create_anaconda_svg()
