# Tests

このディレクトリにはPython Utilitiesプロジェクトのテストが含まれます。

## テストの実行

```bash
# すべてのテストを実行
pytest

# カバレッジ付きでテストを実行
pytest --cov

# 特定のテストファイルを実行
pytest tests/test_filename.py

# 特定のテストを実行
pytest tests/test_filename.py::test_function_name

# マーカーを使用してテストを選択
pytest -m unit          # ユニットテストのみ
pytest -m integration   # 統合テストのみ
pytest -m "not slow"    # 遅いテストを除外
```

## テストの構造

```
tests/
├── __init__.py
├── conftest.py          # pytest設定とフィクスチャ
├── README.md           # このファイル
├── test_filename.py    # ファイル名リネームのテスト
├── test_sightcheck.py  # Webサイト監視のテスト
└── ...
```

## フィクスチャ

`conftest.py` に以下のフィクスチャが定義されています：

- `temp_dir`: テンポラリディレクトリを作成
- `sample_files`: テスト用のサンプルファイルを作成
- `mock_config`: モック設定を提供

## テストマーカー

- `@pytest.mark.unit`: ユニットテスト
- `@pytest.mark.integration`: 統合テスト
- `@pytest.mark.slow`: 実行に時間がかかるテスト
