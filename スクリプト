ディレクトリ/ファイル操作

from pathlib import Path

# 相対パスでも絶対パスでも
r = Path("piyo.txt")
a = Path("/home/hoge/fuga/piyo.txt")

# 相互変換も可能
r.absolute()
>>> PosixPath('/home/hoge/fuga/piyo.txt')

# カレントディレクトリ
Path.cwd()
>>> PosixPath('/home/hoge/fuga')
Path()
>>> PosixPath('.')

# ホームディレクトリ
Path.home()
>>> PosixPath('/home/hoge')

# スクリプト自身のパス
Path(__file__)
>>> PosixPath('/home/hoge/fuga/piyo.py')


移動/検索

from pathlib import Path

cwd = Path()

# 移動
child = cwd / "hoge"
child
>>> PosixPath('./hoge')
child.parent
>>> PosixPath('.')
child.joinpath("fuga", "piyo")
>>> PosixPath('./hoge/fuga/piyo')

# 検索
[*cwd.glob("*.py")]
>>> [PosixPath('./fuga.py'), PosixPath('./hoge.py')]
# サブディレクトリ内も含めて検索
[*cwd.glob("**/*.py")]
>>> [PosixPath('./fuga.py'), PosixPath('./hoge.py'), PosixPath('./piyo/piyo.py')]
# ls
[*cwd.glob("*")]
>>> [PosixPath('./fuga.py'), PosixPath('./hoge.py'), PosixPath('./piyo')]


属性

from pathlib import Path

hoge = Path("hoge.txt")

# ステータス(ls -lとかstatで見るようなやつ)
hoge.stat()
>>> os.stat_result(st_mode=33206, st_ino=20829148276990953, st_dev=105550640, st_nlink=1, st_uid=0, st_gid=0, st_size=3039, st_atime=1680457867, st_mtime=1679661130, st_ctime=1680457867)
# 表示されるもの以外も見れるので詳しくは↓
# https://docs.python.org/ja/3/library/os.html#os.stat_result

# モード(パーミッション)変更
hoge.chmod(0o664)  # プレフィックス"0o"のついた数値は8進数と見なされます
oct(hoge.stat().st_mode)
>>> 0o100664

# 存在確認
hoge.exists()
>>> True

# 名前系
hoge.name
>>> hoge.txt
hoge.suffix
>>> .txt
hoge.stem
>>> hoge

# is_hoge()
hoge.is_dir()
>>> False
hoge.is_file()
>>> True
# 他にも色々

読み書き

from pathlib import Path

hoge = Path("hoge.txt")
hoge.write_text("hoge!!")
hoge.read_text()
>>> 'hoge!!'

