import React, { useState, useEffect, useCallback, useRef } from 'react';

const SushiTypingGame = () => {
  const [gameState, setGameState] = useState('menu'); // 'menu', 'playing', 'gameOver'
  const [score, setScore] = useState(0);
  const [timeLeft, setTimeLeft] = useState(60);
  const [currentWord, setCurrentWord] = useState('');
  const [typedText, setTypedText] = useState('');
  const [sushiPosition, setSushiPosition] = useState(100);
  const [combo, setCombo] = useState(0);
  const [accuracy, setAccuracy] = useState(100);
  const [totalTyped, setTotalTyped] = useState(0);
  const [correctTyped, setCorrectTyped] = useState(0);
  const [gameSpeed, setGameSpeed] = useState(1);
  
  const inputRef = useRef(null);
  const gameLoopRef = useRef(null);
  
  // 寿司メニューと読み方
  const sushiMenu = [
    { name: 'まぐろ', romaji: 'maguro' },
    { name: 'さーもん', romaji: 'sa-mon' },
    { name: 'えび', romaji: 'ebi' },
    { name: 'いか', romaji: 'ika' },
    { name: 'たこ', romaji: 'tako' },
    { name: 'うに', romaji: 'uni' },
    { name: 'いくら', romaji: 'ikura' },
    { name: 'あなご', romaji: 'anago' },
    { name: 'かっぱまき', romaji: 'kappamaki' },
    { name: 'てっかまき', romaji: 'tekkamaki' },
    { name: 'ちらし', romaji: 'chirashi' },
    { name: 'かんぱち', romaji: 'kanpachi' },
    { name: 'はまち', romaji: 'hamachi' },
    { name: 'あじ', romaji: 'aji' },
    { name: 'さば', romaji: 'saba' }
  ];

  const getRandomSushi = useCallback(() => {
    return sushiMenu[Math.floor(Math.random() * sushiMenu.length)];
  }, []);

  const startGame = () => {
    setGameState('playing');
    setScore(0);
    setTimeLeft(60);
    setCombo(0);
    setAccuracy(100);
    setTotalTyped(0);
    setCorrectTyped(0);
    setGameSpeed(1);
    const newSushi = getRandomSushi();
    setCurrentWord(newSushi.romaji);
    setTypedText('');
    setSushiPosition(100);
    
    setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus();
      }
    }, 100);
  };

  const nextSushi = useCallback(() => {
    const newSushi = getRandomSushi();
    setCurrentWord(newSushi.romaji);
    setTypedText('');
    setSushiPosition(100);
  }, [getRandomSushi]);

  const endGame = useCallback(() => {
    setGameState('gameOver');
    if (gameLoopRef.current) {
      clearInterval(gameLoopRef.current);
    }
  }, []);

  // ゲームループ
  useEffect(() => {
    if (gameState === 'playing') {
      gameLoopRef.current = setInterval(() => {
        setSushiPosition(prev => {
          const newPos = prev - gameSpeed;
          if (newPos <= -20) {
            // 寿司が画面外に出た場合、次の寿司
            setCombo(0);
            setTimeout(() => {
              const newSushi = getRandomSushi();
              setCurrentWord(newSushi.romaji);
              setTypedText('');
              setSushiPosition(100);
            }, 0);
            return 100;
          }
          return newPos;
        });

        setTimeLeft(prev => {
          if (prev <= 1) {
            endGame();
            return 0;
          }
          return prev - 1;
        });

        // ゲーム速度を徐々に上げる
        setGameSpeed(prev => Math.min(prev + 0.001, 3));
      }, 100);

      return () => {
        if (gameLoopRef.current) {
          clearInterval(gameLoopRef.current);
        }
      };
    }
  }, [gameState, gameSpeed, getRandomSushi, endGame]);

  const handleInputChange = (e) => {
    const value = e.target.value;
    setTypedText(value);
    setTotalTyped(prev => prev + 1);

    if (currentWord.startsWith(value)) {
      setCorrectTyped(prev => prev + 1);
      
      if (value === currentWord) {
        // 正解！
        const basePoints = 100;
        const comboBonus = combo * 10;
        const speedBonus = Math.max(0, Math.floor((100 - sushiPosition) * 2));
        const totalPoints = basePoints + comboBonus + speedBonus;
        
        setScore(prev => prev + totalPoints);
        setCombo(prev => prev + 1);
        nextSushi();
      }
    } else {
      // 間違い
      setCombo(0);
    }

    // 正確性の計算
    if (totalTyped > 0) {
      setAccuracy(Math.round((correctTyped / totalTyped) * 100));
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === ' ') {
      e.preventDefault();
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getSushiForWord = (romaji) => {
    return sushiMenu.find(item => item.romaji === romaji)?.name || '🍣';
  };

  if (gameState === 'menu') {
    return (
      <div className="min-h-screen bg-gradient-to-b from-blue-400 to-blue-600 flex items-center justify-center">
        <div className="bg-white rounded-2xl shadow-2xl p-8 text-center max-w-md w-full mx-4">
          <div className="text-6xl mb-4">🍣</div>
          <h1 className="text-4xl font-bold text-gray-800 mb-2">寿司タイピング</h1>
          <p className="text-gray-600 mb-8">流れる寿司をタイピングでキャッチしよう！</p>
          <button
            onClick={startGame}
            className="bg-red-500 hover:bg-red-600 text-white font-bold py-4 px-8 rounded-full text-xl transition-colors duration-200 shadow-lg hover:shadow-xl transform hover:scale-105"
          >
            ゲーム開始
          </button>
          <div className="mt-6 text-sm text-gray-500">
            <p>制限時間: 60秒</p>
            <p>正確にタイピングしてスコアを稼ごう！</p>
          </div>
        </div>
      </div>
    );
  }

  if (gameState === 'gameOver') {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-700 to-gray-900 flex items-center justify-center">
        <div className="bg-white rounded-2xl shadow-2xl p-8 text-center max-w-md w-full mx-4">
          <div className="text-6xl mb-4">🏁</div>
          <h1 className="text-4xl font-bold text-gray-800 mb-6">ゲーム終了</h1>
          
          <div className="space-y-4 mb-8">
            <div className="bg-yellow-100 rounded-lg p-4">
              <div className="text-2xl font-bold text-yellow-800">スコア</div>
              <div className="text-4xl font-bold text-yellow-900">{score.toLocaleString()}</div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-blue-100 rounded-lg p-3">
                <div className="text-sm text-blue-700">最高コンボ</div>
                <div className="text-xl font-bold text-blue-800">{combo}</div>
              </div>
              <div className="bg-green-100 rounded-lg p-3">
                <div className="text-sm text-green-700">正確性</div>
                <div className="text-xl font-bold text-green-800">{accuracy}%</div>
              </div>
            </div>
          </div>

          <button
            onClick={startGame}
            className="bg-red-500 hover:bg-red-600 text-white font-bold py-3 px-6 rounded-full text-lg transition-colors duration-200 shadow-lg hover:shadow-xl transform hover:scale-105 mr-4"
          >
            もう一度
          </button>
          <button
            onClick={() => setGameState('menu')}
            className="bg-gray-500 hover:bg-gray-600 text-white font-bold py-3 px-6 rounded-full text-lg transition-colors duration-200 shadow-lg hover:shadow-xl transform hover:scale-105"
          >
            メニューへ
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-400 to-blue-600 p-4">
      {/* ヘッダー情報 */}
      <div className="flex justify-between items-center mb-4 bg-white/20 rounded-lg p-4 backdrop-blur-sm">
        <div className="text-white">
          <div className="text-lg font-bold">スコア: {score.toLocaleString()}</div>
          <div className="text-sm">コンボ: {combo}x</div>
        </div>
        <div className="text-white text-center">
          <div className="text-2xl font-bold">{formatTime(timeLeft)}</div>
          <div className="text-sm">残り時間</div>
        </div>
        <div className="text-white text-right">
          <div className="text-lg font-bold">正確性: {accuracy}%</div>
          <div className="text-sm">速度: {gameSpeed.toFixed(1)}x</div>
        </div>
      </div>

      {/* ゲームエリア */}
      <div className="bg-white rounded-2xl shadow-2xl p-6 min-h-96 relative overflow-hidden">
        {/* 寿司レーン */}
        <div className="h-32 bg-gradient-to-r from-amber-100 to-amber-200 rounded-lg mb-6 relative border-4 border-amber-300">
          <div className="absolute inset-0 bg-wood-pattern opacity-20"></div>
          
          {/* 流れる寿司 */}
          <div 
            className="absolute top-1/2 transform -translate-y-1/2 transition-all duration-100 ease-linear text-6xl"
            style={{ 
              left: `${sushiPosition}%`,
              filter: sushiPosition < 20 ? 'brightness(0.7)' : 'none'
            }}
          >
            🍣
          </div>
          
          {/* 寿司の名前表示 */}
          <div 
            className="absolute top-2 left-0 transform transition-all duration-100 ease-linear"
            style={{ left: `${sushiPosition}%` }}
          >
            <div className="bg-white/90 rounded-lg px-3 py-1 shadow-lg whitespace-nowrap">
              <div className="text-lg font-bold text-gray-800">{getSushiForWord(currentWord)}</div>
            </div>
          </div>
        </div>

        {/* タイピングエリア */}
        <div className="text-center">
          <div className="text-3xl font-bold text-gray-800 mb-4">
            {currentWord.split('').map((char, index) => (
              <span
                key={index}
                className={
                  index < typedText.length
                    ? typedText[index] === char
                      ? 'text-green-600 bg-green-100 rounded px-1'
                      : 'text-red-600 bg-red-100 rounded px-1'
                    : 'text-gray-400'
                }
              >
                {char}
              </span>
            ))}
          </div>

          <input
            ref={inputRef}
            type="text"
            value={typedText}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            className="w-full max-w-md px-4 py-3 text-2xl text-center border-2 border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none bg-gray-50"
            placeholder="ここにタイピング..."
            autoComplete="off"
            spellCheck="false"
          />

          {/* プログレスバー */}
          <div className="mt-4 w-full bg-gray-200 rounded-full h-3">
            <div
              className="bg-gradient-to-r from-green-400 to-blue-500 h-3 rounded-full transition-all duration-300"
              style={{ width: `${(typedText.length / currentWord.length) * 100}%` }}
            ></div>
          </div>
        </div>

        {/* 危険ゾーン */}
        {sushiPosition < 20 && (
          <div className="absolute inset-0 border-4 border-red-500 rounded-2xl animate-pulse pointer-events-none">
            <div className="absolute top-4 left-4 bg-red-500 text-white px-3 py-1 rounded-full text-sm font-bold">
              危険！
            </div>
          </div>
        )}
      </div>

      {/* インストラクション */}
      <div className="mt-4 text-center text-white/80 text-sm">
        <p>寿司が右端に到達する前にローマ字でタイピングしよう！</p>
        <p>連続で成功するとコンボボーナスがもらえます</p>
      </div>
    </div>
  );
};

export default SushiTypingGame;
