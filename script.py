from pathlib import Path

# ディレクトリ/ファイル操作
r = Path("piyo.txt")
a = Path("/home/hoge/fuga/piyo.txt")
print(r.absolute())  # PosixPath('/home/hoge/fuga/piyo.txt')
print(Path.cwd())  # PosixPath('/home/hoge/fuga')
print(Path())  # PosixPath('.')
print(Path.home())  # PosixPath('/home/hoge')
print(Path(__file__))  # PosixPath('/home/hoge/fuga/piyo.py')

# 移動/検索
cwd = Path.cwd()
child = cwd / "hoge"
print(child)  # PosixPath('./hoge')
print(child.parent)  # PosixPath('.')
print(child.joinpath("fuga", "piyo"))  # PosixPath('./hoge/fuga/piyo')
print(list(cwd.glob("*.py")))  # [PosixPath('./fuga.py'), PosixPath('./hoge.py')]
print(list(cwd.glob("**/*.py")))  # [PosixPath('./fuga.py'), PosixPath('./hoge.py'), PosixPath('./piyo/piyo.py')]
print(list(cwd.glob("*")))  # [PosixPath('./fuga.py'), PosixPath('./hoge.py'), PosixPath('./piyo')]

# 属性
hoge = Path("hoge.txt")
print(hoge.stat())  # os.stat_result(st_mode=33206, st_ino=20829148276990953, st_dev=105550640, st_nlink=1, st_uid=0, st_gid=0, st_size=3039, st_atime=1680457867, st_mtime=1679661130, st_ctime=1680457867)
hoge.chmod(0o664)
print(oct(hoge.stat().st_mode))  # 0o100664
print(hoge.exists())  # True
print(hoge.name)  # hoge.txt
print(hoge.suffix)  # .txt
print(hoge.stem)  # hoge
print(hoge.is_dir())  # False
print(hoge.is_file())  # True

# 読み書き
hoge = Path("hoge.txt")
hoge.write_text("hoge!!")
print(hoge.read_text())  # hoge!!