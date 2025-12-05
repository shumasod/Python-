import React, { useState, useEffect } from 'react';
import { Trash2, Plus, Shuffle, Heart, Zap, Sparkles, Flame } from 'lucide-react';

export default function EroticLotterySystem() {
  const [participants, setParticipants] = useState([]);
  const [newName, setNewName] = useState('');
  const [winnerCount, setWinnerCount] = useState(1);
  const [winners, setWinners] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [showResult, setShowResult] = useState(false);
  const [orgasmMode, setOrgasmMode] = useState(false); // 新機能：絶頂モード♡
  const [apiUrl] = useState('http://localhost');

  // ポーリングはそのまま（でもちょっとドキドキさせる）
  useEffect(() => {
    if (!jobId) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${apiUrl}/api/status?jobId=${jobId}`);
        const data = await res.json();
        setJobStatus(data.status);

        if (data.status === 'completed') {
          setWinners(data.winners);
          setShowResult(true);
          setOrgasmMode(true);
          setTimeout(() => setOrgasmMode(false), 8000);
          setJobId(null);
          setIsSubmitting(false);
          clearInterval(interval);
        }
      } catch (e) { console.error(e); }
    }, 800);

    return () => clearInterval(interval);
  }, [jobId, apiUrl]);

  const addParticipant = () => {
    if (!newName.trim()) return;
    setParticipants([...participants, { id: Date.now(), name: newName.trim() }]);
    setNewName('');
  };

  const removeParticipant = (id) => {
    setParticipants(participants.filter(p => p.id !== id));
  };

  const drawLottery = async () => {
    if (participants.length === 0) return alert("ねぇ…誰もいないと寂しいよ？♡");
    if (winnerCount > participants.length) return alert("そんなにたくさんイカせたいの…？無理だよぉ♡");

    setIsSubmitting(true);
    setShowResult(false);
    setJobStatus('queued');

    try {
      const res = await fetch(`${apiUrl}/api/lottery`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ participants, winnerCount: parseInt(winnerCount) })
      });

      const data = await res.json();
      setJobId(data.jobId);
    } catch (err) {
      alert("あぁん…サーバーが感じすぎちゃって応答できないみたい…♡");
      setIsSubmitting(false);
    }
  };

  return (
    <div className={`min-h-screen overflow-hidden relative ${orgasmMode ? 'animate-pulse' : ''}`}
      style={{
        background: orgasmMode 
          ? 'linear-gradient(45deg, #ff006e, #ff8c00, #ff006e, #8a2be2)' 
          : 'linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab)',
        backgroundSize: '400% 400%',
        animation: orgasmMode ? 'none' : 'gradient 15s ease infinite'
      }}
    >
      {/* 背景に揺れるハート */}
      {orgasmMode && (
        <div className="fixed inset-0 pointer-events-none">
          {[...Array(30)].map((_, i) => (
            <Heart
              key={i}
              className="absolute text-pink-300 opacity-60 animate-ping"
              style={{
                top: `${Math.random() * 100}%`,
                left: `${Math.random() * 100}%`,
                animationDelay: `${i * 0.1}s`,
                fontSize: `${30 + Math.random() * 40}px`
              }}
              fill="currentColor"
            />
          ))}
        </div>
      )}

      <div className="relative z-10 max-w-6xl mx-auto p-4 md:p-8">
        <div className="text-center mb-10">
          <h1 className="text-5xl md:text-7xl font-black text-white drop-shadow-2xl mb-4 animate-glow">
            ♡ 絶頂抽選システム ♡
          </h1>
          <p className="text-xl text-pink-100 font-medium tracking-widest">
            あなたの一票で、誰かがイっちゃう…♡
          </p>
          <div className="mt-4 flex justify-center gap-4">
            <Flame className="text-red-400 animate-pulse" size={32} />
            <Sparkles className="text-yellow-300 animate-spin-slow" size={32} />
            <Flame className="text-red-400 animate-pulse" size={32} />
          </div>
        </div>

        <div className="grid lg:grid-cols-2 gap-8 mt-12">
          {/* 左：参加者（誘惑のリスト） */}
          <div className="bg-white/10 backdrop-blur-xl rounded-3xl shadow-2xl p-8 border border-pink-300/30">
            <h2 className="text-3xl font-bold text-white mb-6 flex items-center gap-3">
              <Heart fill="pink" className="text-pink-400" /> 参加者たち
            </h2>

            <div className="flex gap-3 mb-6">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && addParticipant()}
                placeholder="あなたの名前…教えて♡"
                className="flex-1 px-6 py-4 rounded-2xl bg-white/20 border border-pink-300/50 text-white placeholder-pink-200 focus:outline-none focus:border-pink-400 transition"
              />
              <button
                onClick={addParticipant}
                className="bg-gradient-to-r from-pink-500 to-purple-600 px-6 py-4 rounded-2xl text-white font-bold hover:scale-105 transition flex items-center gap-2"
              >
                <Plus /> 参加する♡
              </button>
            </div>

            <div className="space-y-3 max-h-96 overflow-y-auto">
              {participants.map((p) => (
                <div key={p.id} className="group flex items-center justify-between bg-white/15 rounded-2xl p-4 hover:bg-white/25 transition">
                  <span className="text-white font-medium text-lg">{p.name}</span>
                  <button
                    onClick={() => removeParticipant(p.id)}
                    className="opacity-0 group-hover:opacity-100 transition text-pink-300 hover:text-red-400"
                  >
                    <Trash2 size={20} />
                  </button>
                </div>
              ))}
              {participants.length === 0 && (
                <p className="text-center text-pink-200 py-16 text-xl">まだ誰も…あなたが最初？♡</p>
              )}
            </div>

            <div className="mt-6 text-white text-center">
              <p className="text-4xl font-black">{participants.length.toLocaleString()}</p>
              <p className="text-pink-200">人があなたを待ってる…♡</p>
            </div>
          </div>

          {/* 右：抽選ボタン（絶頂スイッチ） */}
          <div className="bg-white/10 backdrop-blur-xl rounded-3xl shadow-2xl p-8 border border-purple-300/30">
            <h2 className="text-3xl font-bold text-white mb-6 text-center">
              <Zap className="inline mr-3 text-yellow-400" /> 当選者数を選んで…
            </h2>

            <input
              type="range"
              min="1"
              max={Math.min(10, participants.length)}
              value={winnerCount}
              onChange={(e) => setWinnerCount(e.target.value)}
              className="w-full h-4 bg-pink-900/50 rounded-full appearance-none cursor-pointer slider-pink mb-8"
            />
            <p className="text-center text-5xl font-black text-pink-300 mb-8">
              {winnerCount}人 イカせる♡
            </p>

            <button
              onClick={drawLottery}
              disabled={isSubmitting || participants.length === 0}
              className={`w-full py-8 rounded-3xl font-black text-3xl transition-all transform ${
                isSubmitting
                  ? 'bg-gray-600 text-gray-300 cursor-not-allowed'
                  : 'bg-gradient-to-br from-red-500 via-pink-500 to-purple-700 text-white hover:scale-105 active:scale-95 shadow-2xl hover:shadow-pink-500/50'
              }`}
            >
              {isSubmitting ? (
                <span className="flex items-center gap-4">
                  <div className="animate-spin h-10 w-10 border-4 border-white rounded-full border-t-transparent"></div>
                  感じてる…待ってて♡
                </span>
              ) : (
                <span className="flex items-center justify-center gap-4">
                  <Heart fill="red" className="animate-pulse" size={40} />
                  今すぐイカせる！
                  <Heart fill="red" className="animate-pulse" size={40} />
                </span>
              )}
            </button>

            {/* 結果発表（絶頂演出） */}
            {showResult && winners.length > 0 && (
              <div className="mt-10 animate__animated animate__jackInTheBox">
                <h3 className="text-4xl font-black text-center text-yellow-300 mb-8 drop-shadow-lg">
                  ♡♡♡ イッちゃった人たち ♡♡♡
                </h3>
                <div className="space-y-4">
                  {winners.map((winner, i) => (
                    <div
                      key={winner.id}
                      className="bg-gradient-to-r from-pink-600 to-purple-700 text-white p-6 rounded-2xl text-center transform hover:scale-105 transition shadow-xl"
                      style={{ animation: `bounceIn 0.8s ${i * 0.2}s both` }}
                    >
                      <p className="text-5xl mb-2">♡</p>
                      <p className="text-3xl font-black">{winner.name}</p>
                      <p className="text-yellow-300 mt-2 text-xl">第{i + 1}位で絶頂♡</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="text-center mt-12 text-pink-200 text-sm">
          Powered by 欲望とReactとRedis | 100,000人同時絶頂対応済み♡
        </div>
      </div>

      <style jsx>{`
        @keyframes gradient {
          0% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }
        @keyframes glow {
          0%, 100% { text-shadow: 0 0 20px #fff, 0 0 40px #ff00e6, 0 0 60px #ff00e6; }
          50% { text-shadow: 0 0 30px #fff, 0 0 60px #ff00e6, 0 0 90px #ff00e6; }
        }
        .animate-glow { animation: glow 2s ease-in-out infinite; }
        .slider-pink::-webkit-slider-thumb {
          appearance: none;
          height: 32px;
          width: 32px;
          border-radius: 50%;
          background: #ff006e;
          cursor: pointer;
          box-shadow: 0 0 20px #ff006e;
        }
      `}</style>
    </div>
  );
}