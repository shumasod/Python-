#!/usr/bin/env python3
"""
ファイル名一括変更ツール
安全で柔軟なファイル名の一括変更機能を提供します。
"""

import os
import sys
import argparse
import logging
import re
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Callable, Tuple
from datetime import datetime
import json


def setup_logging(verbose: bool = False) -> None:
    """ロギングの設定"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('batch_rename.log', encoding='utf-8')
        ]
    )


class FileRenamer:
    """ファイル名変更クラス"""
    
    def __init__(self, folder_path: str, dry_run: bool = True, create_backup: bool = True):
        self.folder_path = Path(folder_path)
        self.dry_run = dry_run
        self.create_backup = create_backup
        self.operations_log = []
        self.backup_dir = None
        
        if not self.folder_path.exists():
            raise FileNotFoundError(f"フォルダが見つかりません: {folder_path}")
        
        if self.create_backup and not self.dry_run:
            self.backup_dir = self._create_backup_dir()
    
    def _create_backup_dir(self) -> Path:
        """バックアップディレクトリを作成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.folder_path / f"backup_{timestamp}"
        backup_dir.mkdir(exist_ok=True)
        logging.info(f"バックアップディレクトリを作成: {backup_dir}")
        return backup_dir
    
    def _safe_rename(self, old_path: Path, new_path: Path) -> bool:
        """安全なファイル名変更"""
        try:
            if new_path.exists():
                logging.warning(f"変更先ファイルが既に存在: {new_path}")
                return False
            
            if self.dry_run:
                logging.info(f"[DRY RUN] {old_path.name} → {new_path.name}")
                return True
            
            # バックアップ作成
            if self.backup_dir:
                backup_path = self.backup_dir / old_path.name
                shutil.copy2(old_path, backup_path)
            
            # ファイル名変更
            old_path.rename(new_path)
            logging.info(f"変更完了: {old_path.name} → {new_path.name}")
            return True
            
        except Exception as e:
            logging.error(f"変更エラー ({old_path.name}): {e}")
            return False
    
    def simple_replace(self, old_text: str, new_text: str, 
                      case_sensitive: bool = True, 
                      file_extensions: Optional[List[str]] = None) -> Dict[str, int]:
        """シンプルな文字列置換"""
        stats = {'total': 0, 'matched': 0, 'renamed': 0, 'failed': 0}
        
        for file_path in self.folder_path.iterdir():
            if file_path.is_file():
                stats['total'] += 1
                
                # 拡張子フィルタ
                if file_extensions and file_path.suffix.lower() not in [ext.lower() for ext in file_extensions]:
                    continue
                
                filename = file_path.name
                search_text = old_text if case_sensitive else old_text.lower()
                target_text = filename if case_sensitive else filename.lower()
                
                if search_text in target_text:
                    stats['matched'] += 1
                    
                    if case_sensitive:
                        new_filename = filename.replace(old_text, new_text)
                    else:
                        # 大文字小文字を無視した置換
                        new_filename = re.sub(re.escape(old_text), new_text, filename, flags=re.IGNORECASE)
                    
                    new_path = file_path.parent / new_filename
                    
                    if self._safe_rename(file_path, new_path):
                        stats['renamed'] += 1
                        self.operations_log.append({
                            'operation': 'replace',
                            'old_name': filename,
                            'new_name': new_filename,
                            'status': 'success'
                        })
                    else:
                        stats['failed'] += 1
                        self.operations_log.append({
                            'operation': 'replace',
                            'old_name': filename,
                            'new_name': new_filename,
                            'status': 'failed'
                        })
        
        return stats
    
    def regex_replace(self, pattern: str, replacement: str, 
                     flags: int = 0) -> Dict[str, int]:
        """正規表現による置換"""
        stats = {'total': 0, 'matched': 0, 'renamed': 0, 'failed': 0}
        
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            raise ValueError(f"正規表現エラー: {e}")
        
        for file_path in self.folder_path.iterdir():
            if file_path.is_file():
                stats['total'] += 1
                filename = file_path.name
                
                if regex.search(filename):
                    stats['matched'] += 1
                    new_filename = regex.sub(replacement, filename)
                    
                    if new_filename != filename:
                        new_path = file_path.parent / new_filename
                        
                        if self._safe_rename(file_path, new_path):
                            stats['renamed'] += 1
                            self.operations_log.append({
                                'operation': 'regex',
                                'pattern': pattern,
                                'old_name': filename,
                                'new_name': new_filename,
                                'status': 'success'
                            })
                        else:
                            stats['failed'] += 1
        
        return stats
    
    def sequential_rename(self, prefix: str = "", suffix: str = "", 
                         start_number: int = 1, digits: int = 3,
                         preserve_extension: bool = True,
                         file_extensions: Optional[List[str]] = None) -> Dict[str, int]:
        """連番リネーム"""
        stats = {'total': 0, 'matched': 0, 'renamed': 0, 'failed': 0}
        
        files = [f for f in self.folder_path.iterdir() if f.is_file()]
        
        # 拡張子フィルタ
        if file_extensions:
            files = [f for f in files if f.suffix.lower() in [ext.lower() for ext in file_extensions]]
        
        # ファイル名でソート
        files.sort(key=lambda x: x.name.lower())
        
        for i, file_path in enumerate(files):
            stats['total'] += 1
            stats['matched'] += 1
            
            number = start_number + i
            number_str = str(number).zfill(digits)
            
            if preserve_extension:
                new_filename = f"{prefix}{number_str}{suffix}{file_path.suffix}"
            else:
                new_filename = f"{prefix}{number_str}{suffix}"
            
            new_path = file_path.parent / new_filename
            
            if self._safe_rename(file_path, new_path):
                stats['renamed'] += 1
                self.operations_log.append({
                    'operation': 'sequential',
                    'old_name': file_path.name,
                    'new_name': new_filename,
                    'number': number,
                    'status': 'success'
                })
            else:
                stats['failed'] += 1
        
        return stats
    
    def case_change(self, mode: str, 
                   file_extensions: Optional[List[str]] = None) -> Dict[str, int]:
        """大文字小文字の変更"""
        stats = {'total': 0, 'matched': 0, 'renamed': 0, 'failed': 0}
        
        case_functions = {
            'upper': str.upper,
            'lower': str.lower,
            'title': str.title,
            'capitalize': str.capitalize
        }
        
        if mode not in case_functions:
            raise ValueError(f"無効なモード: {mode}. 使用可能: {list(case_functions.keys())}")
        
        case_func = case_functions[mode]
        
        for file_path in self.folder_path.iterdir():
            if file_path.is_file():
                stats['total'] += 1
                
                # 拡張子フィルタ
                if file_extensions and file_path.suffix.lower() not in [ext.lower() for ext in file_extensions]:
                    continue
                
                filename = file_path.name
                name_part = file_path.stem
                ext_part = file_path.suffix
                
                new_name_part = case_func(name_part)
                new_filename = new_name_part + ext_part
                
                if new_filename != filename:
                    stats['matched'] += 1
                    new_path = file_path.parent / new_filename
                    
                    if self._safe_rename(file_path, new_path):
                        stats['renamed'] += 1
                        self.operations_log.append({
                            'operation': 'case_change',
                            'mode': mode,
                            'old_name': filename,
                            'new_name': new_filename,
                            'status': 'success'
                        })
                    else:
                        stats['failed'] += 1
        
        return stats
    
    def add_timestamp(self, position: str = "prefix", 
                     timestamp_format: str = "%Y%m%d_%H%M%S",
                     separator: str = "_") -> Dict[str, int]:
        """タイムスタンプの追加"""
        stats = {'total': 0, 'matched': 0, 'renamed': 0, 'failed': 0}
        timestamp = datetime.now().strftime(timestamp_format)
        
        for file_path in self.folder_path.iterdir():
            if file_path.is_file():
                stats['total'] += 1
                stats['matched'] += 1
                
                filename = file_path.name
                name_part = file_path.stem
                ext_part = file_path.suffix
                
                if position == "prefix":
                    new_filename = f"{timestamp}{separator}{filename}"
                elif position == "suffix":
                    new_filename = f"{name_part}{separator}{timestamp}{ext_part}"
                else:
                    raise ValueError("position は 'prefix' または 'suffix' である必要があります")
                
                new_path = file_path.parent / new_filename
                
                if self._safe_rename(file_path, new_path):
                    stats['renamed'] += 1
                    self.operations_log.append({
                        'operation': 'add_timestamp',
                        'position': position,
                        'timestamp': timestamp,
                        'old_name': filename,
                        'new_name': new_filename,
                        'status': 'success'
                    })
                else:
                    stats['failed'] += 1
        
        return stats
    
    def clean_filename(self, remove_chars: str = None, 
                      replace_spaces: str = "_",
                      remove_duplicates: bool = True) -> Dict[str, int]:
        """ファイル名のクリーンアップ"""
        stats = {'total': 0, 'matched': 0, 'renamed': 0, 'failed': 0}
        
        # デフォルトの削除文字
        if remove_chars is None:
            remove_chars = r'<>:"/\|?*'
        
        for file_path in self.folder_path.iterdir():
            if file_path.is_file():
                stats['total'] += 1
                filename = file_path.name
                name_part = file_path.stem
                ext_part = file_path.suffix
                
                # 無効な文字を削除
                cleaned_name = name_part
                for char in remove_chars:
                    cleaned_name = cleaned_name.replace(char, '')
                
                # スペースの置換
                if replace_spaces:
                    cleaned_name = cleaned_name.replace(' ', replace_spaces)
                
                # 重複文字の削除
                if remove_duplicates and replace_spaces:
                    cleaned_name = re.sub(f'{re.escape(replace_spaces)}+', replace_spaces, cleaned_name)
                
                # 先頭末尾のトリミング
                cleaned_name = cleaned_name.strip('._-')
                
                new_filename = cleaned_name + ext_part
                
                if new_filename != filename and cleaned_name:
                    stats['matched'] += 1
                    new_path = file_path.parent / new_filename
                    
                    if self._safe_rename(file_path, new_path):
                        stats['renamed'] += 1
                        self.operations_log.append({
                            'operation': 'clean',
                            'old_name': filename,
                            'new_name': new_filename,
                            'status': 'success'
                        })
                    else:
                        stats['failed'] += 1
        
        return stats
    
    def save_operations_log(self, log_file: str = None) -> None:
        """操作ログの保存"""
        if log_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = f"rename_operations_{timestamp}.json"
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'folder_path': str(self.folder_path),
                'dry_run': self.dry_run,
                'operations': self.operations_log
            }, f, ensure_ascii=False, indent=2)
        
        logging.info(f"操作ログを保存しました: {log_file}")


def preview_files(folder_path: str, limit: int = 10) -> None:
    """ファイル一覧のプレビュー"""
    path = Path(folder_path)
    if not path.exists():
        print(f"フォルダが見つかりません: {folder_path}")
        return
    
    files = [f for f in path.iterdir() if f.is_file()]
    
    print(f"\nフォルダ: {folder_path}")
    print(f"ファイル数: {len(files)}")
    print("\nファイル一覧 (最初の{}個):".format(min(limit, len(files))))
    print("-" * 50)
    
    for i, file_path in enumerate(sorted(files)[:limit]):
        print(f"{i+1:3d}. {file_path.name}")
    
    if len(files) > limit:
        print(f"... 他 {len(files) - limit} 個のファイル")


def create_sample_files(folder_path: str, count: int = 10) -> None:
    """テスト用のサンプルファイルを作成"""
    path = Path(folder_path)
    path.mkdir(exist_ok=True)
    
    sample_names = [
        "Document 1.txt", "IMG_001.jpg", "data-file.csv",
        "My Photo (2).png", "report_final_v2.pdf", "temp123.tmp",
        "FILE NAME WITH SPACES.docx", "backup.old.txt",
        "test!@#$%file.txt", "UPPERCASE_FILE.TXT"
    ]
    
    for i in range(min(count, len(sample_names))):
        file_path = path / sample_names[i]
        file_path.write_text(f"Sample content {i+1}")
    
    print(f"{min(count, len(sample_names))}個のサンプルファイルを作成しました: {folder_path}")


def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(description='ファイル名一括変更ツール')
    parser.add_argument('folder', help='対象フォルダのパス')
    parser.add_argument('--dry-run', action='store_true', help='実際の変更を行わずプレビューのみ')
    parser.add_argument('--no-backup', action='store_true', help='バックアップを作成しない')
    parser.add_argument('--extensions', nargs='+', help='対象ファイルの拡張子')
    parser.add_argument('--preview', action='store_true', help='ファイル一覧をプレビュー')
    parser.add_argument('--create-samples', type=int, help='指定数のサンプルファイルを作成')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細ログ出力')
    
    # 操作タイプ
    operation_group = parser.add_mutually_exclusive_group(required=False)
    operation_group.add_argument('--replace', nargs=2, metavar=('OLD', 'NEW'), 
                                help='文字列置換: 古い文字列 新しい文字列')
    operation_group.add_argument('--regex', nargs=2, metavar=('PATTERN', 'REPLACEMENT'),
                                help='正規表現置換: パターン 置換文字列')
    operation_group.add_argument('--sequential', nargs='*', 
                                help='連番リネーム: [prefix] [suffix] [start_num] [digits]')
    operation_group.add_argument('--case', choices=['upper', 'lower', 'title', 'capitalize'],
                                help='大文字小文字変更')
    operation_group.add_argument('--timestamp', choices=['prefix', 'suffix'],
                                help='タイムスタンプ追加')
    operation_group.add_argument('--clean', action='store_true',
                                help='ファイル名クリーンアップ')
    
    # オプション
    parser.add_argument('--case-sensitive', action='store_true', help='大文字小文字を区別')
    parser.add_argument('--regex-flags', choices=['ignorecase', 'multiline', 'dotall'],
                       nargs='+', help='正規表現フラグ')
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    try:
        # サンプルファイル作成
        if args.create_samples:
            create_sample_files(args.folder, args.create_samples)
            return
        
        # プレビュー表示
        if args.preview:
            preview_files(args.folder)
            return
        
        # 操作が指定されていない場合
        if not any([args.replace, args.regex, args.sequential is not None, 
                   args.case, args.timestamp, args.clean]):
            preview_files(args.folder)
            print("\n操作を指定してください。--help でヘルプを確認してください。")
            return
        
        # リネーマーの初期化
        renamer = FileRenamer(
            folder_path=args.folder,
            dry_run=args.dry_run,
            create_backup=not args.no_backup
        )
        
        stats = None
        
        # 操作の実行
        if args.replace:
            old_text, new_text = args.replace
            stats = renamer.simple_replace(
                old_text, new_text,
                case_sensitive=args.case_sensitive,
                file_extensions=args.extensions
            )
        
        elif args.regex:
            pattern, replacement = args.regex
            flags = 0
            if args.regex_flags:
                flag_map = {
                    'ignorecase': re.IGNORECASE,
                    'multiline': re.MULTILINE,
                    'dotall': re.DOTALL
                }
                for flag_name in args.regex_flags:
                    flags |= flag_map[flag_name]
            
            stats = renamer.regex_replace(pattern, replacement, flags)
        
        elif args.sequential is not None:
            seq_args = args.sequential
            prefix = seq_args[0] if len(seq_args) > 0 else ""
            suffix = seq_args[1] if len(seq_args) > 1 else ""
            start_num = int(seq_args[2]) if len(seq_args) > 2 else 1
            digits = int(seq_args[3]) if len(seq_args) > 3 else 3
            
            stats = renamer.sequential_rename(
                prefix=prefix, suffix=suffix,
                start_number=start_num, digits=digits,
                file_extensions=args.extensions
            )
        
        elif args.case:
            stats = renamer.case_change(args.case, args.extensions)
        
        elif args.timestamp:
            stats = renamer.add_timestamp(position=args.timestamp)
        
        elif args.clean:
            stats = renamer.clean_filename()
        
        # 結果表示
        if stats:
            print("\n" + "="*50)
            mode_text = "[DRY RUN] " if args.dry_run else ""
            print(f"{mode_text}処理結果:")
            print(f"総ファイル数: {stats['total']}")
            print(f"対象ファイル数: {stats['matched']}")
            print(f"変更成功: {stats['renamed']}")
            print(f"変更失敗: {stats['failed']}")
            
            if args.dry_run and stats['matched'] > 0:
                print("\n実際に変更するには --dry-run オプションを外してください。")
            
            # 操作ログの保存
            if not args.dry_run and stats['renamed'] > 0:
                renamer.save_operations_log()
            
            print("="*50)
        
        logging.info("処理が完了しました。")
        
    except KeyboardInterrupt:
        logging.info("処理が中断されました。")
        sys.exit(1)
    except Exception as e:
        logging.error(f"エラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
