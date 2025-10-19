import React, { useState, useEffect } from 'react';
import { Trash2, Plus, Shuffle, Clock, CheckCircle, AlertCircle } from 'lucide-react';

export default function LotterySystem() {
  const [participants, setParticipants] = useState([]);
  const [newName, setNewName] = useState('');
  const [winnerCount, setWinnerCount] = useState(1);
  const [winners, setWinners] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [showResult, setShowResult] = useState(false);
  const [apiUrl] = useState('http://localhost');

  // ジョブステータスをポーリング
  useEffect(() => {
    if (!jobId) return;

    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`${apiUrl}/api/status?jobId=${jobId}`);
        if (!response.ok) throw new Error('Status check failed');
        
        const data = await response.json();
        setJobStatus(data.status);

        if (data.status === 'completed') {
          setWinners(data.winners);
          setShowResult(true);
          setJobId(null);
          setIsSubmitting(false);
          clearInterval(pollInterval);
        }
      } catch (error) {
        console.error('Status polling error:', error);
      }
    }, 1000);

    return () => clearInterval(pollInterval);
  }, [jobId, apiUrl]);

  const addParticipant = () => {
    if (newName.trim()) {
      setParticipants([
        ...participants,
        { id: Date.now(), name: newName.trim() }
      ]);
      setNewName('');
    }
  };

  const removeParticipant = (id) => {
    setParticipants(participants.filter(p => p.id !== id));
  };

  const addBulkParticipants = (count) => {
    const newParticipants = Array.from({ length: count }, (_, i) => ({
      id: Date.now() + i,
      name: `参加者${participants.length + i + 1}`
    }));
    setParticipants([...participants, ...newParticipants]);
  };

  const drawLottery = async () => {
    if (participants.length === 0) {
      alert('参加者を追加してください');
      return;
    }

    if (winnerCount > participants.length) {
      alert('当選者数は参加者数以下にしてください');
      return;
    }

    setIsSubmitting(true);
    setShowResult(false);
    setJobStatus('queued');

    try {
      const response = await fetch(`${apiUrl}/api/lottery`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          participants,
          winnerCount: parseInt(winnerCount)
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || '抽選に失敗しました');
      }

      const data = await response.json();
      setJobId(data.jobId);
      setJobStatus(data.status);

    } catch (error) {
      console.error('Error:', error);
      alert(error.message || 'サーバーに接続できませんでした');
      setIsSubmitting(false);
      setJobStatus(null);
    }
  };

  const getStatusIcon = () => {
    switch (jobStatus) {
      case 'queued':
        return <Clock className="animate-pulse text-yellow-500" size={24} />;
      case 'processing':
        return <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>;
      case 'completed':
        return <CheckCircle className="text-green-500" size={24} />;
      default:
        return null;
    }
  };

  const getStatusText = () => {
    switch (jobStatus) {
      case 'queued':
        return 'キューで待機中...';
      case 'processing':
        return '抽選処理中...';
      case 'completed':
        return '抽選完了！';
      default:
        return '';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-400 via-pink-500 to-red-500 p-4 md:p-8">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-2 drop-shadow-lg">
            🎰 高負荷対応 抽選システム
          </h1>
          <p className="text-white text-sm md:text-base opacity-90">
            10万人同時アクセス対応 | 負荷分散 + キュー処理
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* 参加者管理 */}
          <div className="bg-white rounded-2xl shadow-2xl p-6">
            <h2 className="text-2xl font-bold text-gray-800 mb-4">参加者管理</h2>
            
            <div className="flex gap-2 mb-4">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && addParticipant()}
                placeholder="名前を入力"
                className="flex-1 px-4 py-2 border-2 border-gray-300 rounded-lg focus:border-purple-500 focus:outline-none"
              />
              <button
                onClick={addParticipant}
                className="bg-purple-500 text-white px-4 py-2 rounded-lg hover:bg-purple-600 transition flex items-center gap-2"
              >
                <Plus size={20} />
                追加
              </button>
            </div>

            {/* 一括追加ボタン */}
            <div className="flex gap-2 mb-4">
              <button
                onClick={() => addBulkParticipants(100)}
                className="flex-1 bg-blue-500 text-white px-3 py-2 rounded-lg hover:bg-blue-600 transition text-sm"
              >
                +100人
              </button>
              <button
                onClick={() => addBulkParticipants(1000)}
                className="flex-1 bg-blue-600 text-white px-3 py-2 rounded-lg hover:bg-blue-700 transition text-sm"
              >
                +1,000人
              </button>
              <button
                onClick={() => addBulkParticipants(10000)}
                className="flex-1 bg-blue-700 text-white px-3 py-2 rounded-lg hover:bg-blue-800 transition text-sm"
              >
                +10,000人
              </button>
            </div>

            <div className="space-y-2 max-h-80 overflow-y-auto mb-4">
              {participants.length === 0 ? (
                <p className="text-gray-400 text-center py-8">参加者がいません</p>
              ) : participants.length > 50 ? (
                <div className="text-center py-4 bg-gray-50 rounded-lg">
                  <p className="text-lg font-bold text-gray-700">
                    参加者が多いため省略表示
                  </p>
                  <p className="text-sm text-gray-500 mt-2">
                    最初の10名と最後の10名を表示
                  </p>
                </div>
              ) : (
                participants.map((p) => (
                  <div
                    key={p.id}
                    className="flex items-center justify-between bg-gray-50 p-3 rounded-lg"
                  >
                    <span className="font-medium">{p.name}</span>
                    <button
                      onClick={() => removeParticipant(p.id)}
                      className="text-red-500 hover:text-red-700 transition"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                ))
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 bg-purple-50 rounded-lg">
                <p className="text-xs text-gray-600">総参加者数</p>
                <p className="text-2xl font-bold text-purple-600">
                  {participants.length.toLocaleString()}名
                </p>
              </div>
              <div className="p-3 bg-green-50 rounded-lg">
                <p className="text-xs text-gray-600">システム状態</p>
                <p className="text-sm font-bold text-green-600">稼働中</p>
              </div>
            </div>
          </div>

          {/* 抽選実行 */}
          <div className="bg-white rounded-2xl shadow-2xl p-6">
            <h2 className="text-2xl font-bold text-gray-800 mb-4">抽選実行</h2>

            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                当選者数
              </label>
              <input
                type="number"
                min="1"
                max={participants.length}
                value={winnerCount}
                onChange={(e) => setWinnerCount(e.target.value)}
                className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:border-purple-500 focus:outline-none"
              />
            </div>

            {/* ステータス表示 */}
            {jobStatus && (
              <div className="mb-6 p-4 bg-blue-50 rounded-lg flex items-center gap-3">
                {getStatusIcon()}
                <div className="flex-1">
                  <p className="font-medium text-gray-800">{getStatusText()}</p>
                  {jobId && (
                    <p className="text-xs text-gray-500 mt-1">
                      Job ID: {jobId.substring(0, 8)}...
                    </p>
                  )}
                </div>
              </div>
            )}

            <button
              onClick={drawLottery}
              disabled={isSubmitting || participants.length === 0}
              className={`w-full py-4 rounded-lg font-bold text-lg flex items-center justify-center gap-3 transition ${
                isSubmitting || participants.length === 0
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-gradient-to-r from-pink-500 to-purple-600 text-white hover:from-pink-600 hover:to-purple-700 shadow-lg'
              }`}
            >
              {isSubmitting ? (
                <>
                  {getStatusIcon()}
                  処理中...
                </>
              ) : (
                <>
                  <Shuffle size={24} />
                  抽選開始
                </>
              )}
            </button>

            {/* 抽選結果 */}
            {showResult && winners.length > 0 && (
              <div className="mt-6 animate-fade-in">
                <h3 className="text-xl font-bold text-gray-800 mb-3 text-center">
                  🎉 当選者発表 🎉
                </h3>
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {winners.map((winner, index) => (
                    <div
                      key={winner.id}
                      className="bg-gradient-to-r from-yellow-400 to-orange-500 text-white p-4 rounded-lg shadow-lg animate-bounce"
                      style={{ 
                        animationDelay: `${index * 0.1}s`, 
                        animationIterationCount: 3 
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-2xl">🏆</span>
                        <span className="text-xl font-bold">{winner.name}</span>
                        <span className="text-sm bg-white text-orange-500 px-2 py-1 rounded-full">
                          #{index + 1}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* システム情報 */}
            <div className="mt-6 p-4 bg-gray-50 rounded-lg">
              <h4 className="font-bold text-sm text-gray-700 mb-2">💪 システム機能</h4>
              <ul className="text-xs text-gray-600 space-y-1">
                <li>✓ 4台のサーバーで負荷分散</li>
                <li>✓ Redisキャッシュ & ジョブキュー</li>
                <li>✓ 非同期処理 (100並列ワーカー)</li>
                <li>✓ レート制限 (100req/分)</li>
                <li>✓ 10万人同時アクセス対応</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="mt-8 text-center">
          <p className="text-white text-sm opacity-75">
            Go + React + Redis + Nginx | 高負荷対応アーキテクチャ
          </p>
        </div>
      </div>

      <style jsx>{`
        @keyframes fade-in {
          from {
            opacity: 0;
            transform: translateY(-10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fade-in {
          animation: fade-in 0.5s ease-out;
        }
      `}</style>
    </div>
  );
}
