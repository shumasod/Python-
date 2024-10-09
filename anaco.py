import svgwrite
import random

def create_anaconda_svg(filename="anaconda.svg", size=600):
    dwg = svgwrite.Drawing(filename, size=(size, size))
    
    # 背景色（ジャングルっぽい緑）
    dwg.add(dwg.rect(insert=(0, 0), size=(size, size), fill="#2F4F4F"))
    
    # アナコンダの体の色
    body_color = "#4A5D23"
    pattern_color = "#2F3A17"
    
    # アナコンダの体を描く
    points = [(50, size//2)]
    for i in range(1, 8):
        x = 50 + (size - 100) * i // 7
        y = size//2 + random.randint(-100, 100)
        points.append((x, y))
    
    # 体の輪郭
    dwg.add(dwg.polyline(points=points, fill="none", stroke=body_color, stroke_width=60))
    
    # 模様を追加
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i+1]
        mid_x, mid_y = (x1 + x2) // 2, (y1 + y2) // 2
        dwg.add(dwg.circle(center=(mid_x, mid_y), r=20, fill=pattern_color))
    
    # 頭を描く
    head_x, head_y = points[0]
    dwg.add(dwg.ellipse(center=(head_x-10, head_y), r=(30, 20), fill=body_color))
    
    # 目を描く
    dwg.add(dwg.circle(center=(head_x-25, head_y-10), r=5, fill="yellow"))
    dwg.add(dwg.circle(center=(head_x-25, head_y-10), r=2, fill="black"))
    
    # 舌を描く
    dwg.add(dwg.line(start=(head_x-40, head_y), end=(head_x-70, head_y-15), stroke="red", stroke_width=3))
    dwg.add(dwg.line(start=(head_x-40, head_y), end=(head_x-70, head_y+15), stroke="red", stroke_width=3))
    
    dwg.save()

create_anaconda_svg()
print("SVG ファイルが作成されました: anaconda.svg")