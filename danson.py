import random
import time
from typing import List, Optional
from dataclasses import dataclass
import argparse
import signal
import sys
import logging

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class DansonConfig:
    """ダンソンジェネレーターの設定"""
    min_repeat: int = 1
    max_repeat: int = 8
    interval: float = 1.0
    max_iterations: Optional[int] = None
    pattern: str = "ダンソン！"

class DansonGenerator:
    """ダンソンのフレーズを生成するクラス"""
    
    def __init__(self, config: DansonConfig):
        """
        初期化
        
        Args:
            config: 生成の設定
        """
        self.config = config
        self._validate_config()
        self.running = True
        self._setup_signal_handler()
        
    def _validate_config(self) -> None:
        """設定の妥当性検証"""
        if self.config.min_repeat < 1:
            raise ValueError("min_repeatは1以上である必要があります")
        if self.config.max_repeat < self.config.min_repeat:
            raise ValueError("max_repeatはmin_repeat以上である必要があります")
        if self.config.interval <= 0:
            raise ValueError("intervalは正の値である必要があります")
            
    def _setup_signal_handler(self) -> None:
        """シグナルハンドラーの設定"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum: int, frame) -> None:
        """
        シグナルハンドラー
        
        Args:
            signum: シグナル番号
            frame: 現在のスタックフレーム
        """
        self.running = False
        logger.info("\nプログラムを終了します。お疲れ様でした！")
        
    def generate_pattern(self) -> str:
        """
        ダンソンのパターンを生成
        
        Returns:
            str: 生成されたパターン
        """
        repeat_count = random.randint(
            self.config.min_repeat,
            self.config.max_repeat
        )
        return "".join([self.config.pattern] * repeat_count)
        
    def run(self) -> None:
        """ダンソンジェネレーターを実行"""
        iteration = 0
        
        try:
            while self.running:
                # 最大繰り返し回数のチェック
                if (self.config.max_iterations is not None and 
                    iteration >= self.config.max_iterations):
                    logger.info("指定された繰り返し回数に達しました")
                    break
                    
                # パターンの生成と出力
                pattern = self.generate_pattern()
                print(pattern, flush=True)
                
                # 待機
                time.sleep(self.config.interval)
                iteration += 1
                
        except Exception as e:
            logger.error(f"実行中にエラーが発生しました: {e}")
            raise

def parse_arguments() -> argparse.Namespace:
    """コマンドライン引数のパース"""
    parser = argparse.ArgumentParser(description='ダンソンジェネレーター')
    parser.add_argument(
        '--min',
        type=int,
        default=1,
        help='最小繰り返し回数 (デフォルト: 1)'
    )
    parser.add_argument(
        '--max',
        type=int,
        default=8,
        help='最大繰り返し回数 (デフォルト: 8)'
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=1.0,
        help='出力間隔（秒） (デフォルト: 1.0)'
    )
    parser.add_argument(
        '--iterations',
        type=int,
        default=None,
        help='最大実行回数 (デフォルト: 無制限)'
    )
    parser.add_argument(
        '--pattern',
        type=str,
        default="ダンソン！",
        help='基本パターン (デフォルト: ダンソン！)'
    )
    
    return parser.parse_args()

def main() -> None:
    """メイン実行関数"""
    try:
        # コマンドライン引数のパース
        args = parse_arguments()
        
        # 設定の作成
        config = DansonConfig(
            min_repeat=args.min,
            max_repeat=args.max,
            interval=args.interval,
            max_iterations=args.iterations,
            pattern=args.pattern
        )
        
        # ジェネレーターの作成と実行
        generator = DansonGenerator(config)
        generator.run()
        
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
