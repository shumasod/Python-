import svgwrite

def create_python_svg(filename="python_snake.svg", size=400):
    dwg = svgwrite.Drawing(filename, size=(size, size))
    
    # ボディの色
    body_color = "#4B8BBE"
    
    # 体を描く
    dwg.add(dwg.path(d=f"M50,{size//2} Q{size//4},{size//4} {size//2},{size//2} T{size-50},{size//2}",
                     fill="none", stroke=body_color, stroke_width=30))
    
    # 頭を描く
    dwg.add(dwg.circle(center=(50, size//2), r=15, fill=body_color))
    
    # 目を描く
    dwg.add(dwg.circle(center=(45, size//2-5), r=3, fill="white"))
    
    # 舌を描く
    dwg.add(dwg.line(start=(35, size//2), end=(15, size//2-10), stroke="red", stroke_width=2))
    dwg.add(dwg.line(start=(35, size//2), end=(15, size//2+10), stroke="red", stroke_width=2))
    
    dwg.save()

create_python_svg()
print("SVG ファイルが作成されました: python_snake.svg")