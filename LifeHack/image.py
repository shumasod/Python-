# 10. 画像の一括リサイズ
from PIL import Image
def batch_resize_images(folder_path, size):
    for filename in os.listdir(folder_path):
        if filename.endswith(('.png', '.jpg', '.jpeg')):
            img = Image.open(os.path.join(folder_path, filename))
            img_resized = img.resize(size)
            img_resized.save(os.path.join(folder_path, f'resized_{filename}'))
