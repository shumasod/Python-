import React, { useState, useCallback, useEffect, useRef } from 'react';

const FIELD_WIDTH = 800;
const FIELD_HEIGHT = 500;
const YARD_LINE_SPACING = FIELD_WIDTH / 100;

const POSITIONS = {
  offense: [
    { id: 'QB', name: 'クォーターバック', x: 400, y: 300, color: '#FFD700' },
    { id: 'RB', name: 'ランニングバック', x: 400, y: 340, color: '#FF6B35' },
    { id: 'WR1', name: 'ワイドレシーバー1', x: 150, y: 250, color: '#4ECDC4' },
    { id: 'WR2', name: 'ワイドレシーバー2', x: 650, y: 250, color: '#4ECDC4' },
    { id: 'TE', name: 'タイトエンド', x: 550, y: 270, color: '#95E1D3' },
    { id: 'LT', name: '左タックル', x: 320, y: 270, color: '#A8E6CF' },
    { id: 'LG', name: '左ガード', x: 360, y: 270, color: '#A8E6CF' },
    { id: 'C', name: 'センター', x: 400, y: 270, color: '#A8E6CF' },
    { id: 'RG', name: '右ガード', x: 440, y: 270, color: '#A8E6CF' },
    { id: 'RT', name: '右タックル', x: 480, y: 270, color: '#A8E6CF' },
    { id: 'FB', name: 'フルバック', x: 400, y: 320, color: '#FF6B35' },
  ],
  defense: [
    { id: 'DE1', name: '左ディフェンシブエンド', x: 300, y: 240, color: '#E74C3C' },
    { id: 'DT1', name: '左ディフェンシブタックル', x: 370, y: 240, color: '#C0392B' },
    { id: 'DT2', name: '右ディフェンシブタックル', x: 430, y: 240, color: '#C0392B' },
    { id: 'DE2', name: '右ディフェンシブエンド', x: 500, y: 240, color: '#E74C3C' },
    { id: 'MLB', name: 'ミドルラインバッカー', x: 400, y: 200, color: '#9B59B6' },
    { id: 'OLB1', name: '左アウトサイドLB', x: 280, y: 200, color: '#8E44AD' },
    { id: 'OLB2', name: '右アウトサイドLB', x: 520, y: 200, color: '#8E44AD' },
    { id: 'CB1', name: '左コーナーバック', x: 150, y: 180, color: '#3498DB' },
    { id: 'CB2', name: '右コーナーバック', x: 650, y: 180, color: '#3498DB' },
    { id: 'FS', name: 'フリーセーフティ', x: 350, y: 130, color: '#2980B9' },
    { id: 'SS', name: 'ストロングセーフティ', x: 450, y: 130, color: '#2980B9' },
  ],
};

const PLAY_TEMPLATES = {
  'スラント': {
    routes: { WR1: [{ x: 250, y: 200 }], WR2: [{ x: 550, y: 200 }] },
    description: 'WRが斜め内側にカット。素早いパスで短いゲインを狙う。',
  },
  'ゴーディープ': {
    routes: { WR1: [{ x: 150, y: 80 }], WR2: [{ x: 650, y: 80 }] },
    description: 'WRがエンドゾーンに向けて全速力で走る。ビッグプレー狙い。',
  },
  'アウトルート': {
    routes: { WR1: [{ x: 150, y: 180 }, { x: 80, y: 180 }], WR2: [{ x: 650, y: 180 }, { x: 720, y: 180 }] },
    description: 'WRがサイドラインに向かってカット。サイドラインストップ。',
  },
  'HBダイブ': {
    routes: { RB: [{ x: 400, y: 220 }] },
    description: 'RBが中央を突く。ショートヤーデージ向き。',
  },
  'スクリーンパス': {
    routes: { RB: [{ x: 300, y: 300 }], WR1: [{ x: 200, y: 280 }] },
    description: 'RBにショートパス。OLがブロッカーとなり前進。',
  },
  'プレイアクション': {
    routes: { RB: [{ x: 420, y: 300 }], TE: [{ x: 600, y: 150 }], WR1: [{ x: 200, y: 120 }] },
    description: 'ラン偽装からのパス。ディフェンスを欺く。',
  },
};

const DEFENSIVE_FORMATIONS = {
  '4-3': { name: '4-3ベース', adjustments: {} },
  '3-4': { name: '3-4', adjustments: { DT1: { x: 400, y: 240 }, DE1: { x: 320, y: 240 }, DE2: { x: 480, y: 240 } } },
  'ニッケル': { name: 'ニッケル', adjustments: { OLB1: { x: 200, y: 200 } } },
  'ダイム': { name: 'ダイム', adjustments: { MLB: { x: 400, y: 160 } } },
  'ブリッツ': { name: 'ブリッツ', adjustments: { MLB: { x: 400, y: 250 }, OLB1: { x: 250, y: 250 } } },
};

export default function FootballAnalytics() {
  const [players, setPlayers] = useState([...POSITIONS.offense, ...POSITIONS.defense]);
  const [selectedPlayer, setSelectedPlayer] = useState(null);
  const [routes, setRoutes] = useState({});
  const [isDrawing, setIsDrawing] = useState(false);
  const [currentRoute, setCurrentRoute] = useState([]);
  const [analysisLog, setAnalysisLog] = useState([]);
  const [selectedPlay, setSelectedPlay] = useState(null);
  const [defensiveFormation, setDefensiveFormation] = useState('4-3');
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [playHistory, setPlayHistory] = useState([]);
  const [gameStats, setGameStats] = useState({
    totalPlays: 0,
    passPlays: 0,
    runPlays: 0,
    yardsGained: 0,
    successRate: 0,
  });
  const canvasRef = useRef(null);

  const addLog = useCallback((message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString('ja-JP');
    setAnalysisLog(prev => [...prev.slice(-19), { message, type, timestamp }]);
  }, []);

  const calculateDistance = (p1, p2) => {
    return Math.sqrt(Math.pow(p2.x - p1.x, 2) + Math.pow(p2.y - p1.y, 2));
  };

  const analyzeMatchup = useCallback((offensePlayer, defensePlayer) => {
    const distance = calculateDistance(offensePlayer, defensePlayer);
    const yardDistance = (distance / YARD_LINE_SPACING).toFixed(1);
    
    let threat = 'LOW';
    let advice = '';
    
    if (distance < 30) {
      threat = 'HIGH';
      advice = `${defensePlayer.id}が${offensePlayer.id}を密着マーク中。ダブルムーブやモーションを検討。`;
    } else if (distance < 60) {
      threat = 'MEDIUM';
      advice = `${defensePlayer.id}が${offensePlayer.id}をゾーンカバー。クイックパスが有効。`;
    } else {
      advice = `${offensePlayer.id}がオープン。パスターゲットとして最適。`;
    }
    
    return { distance: yardDistance, threat, advice };
  }, []);

  const runAnalysis = useCallback(() => {
    addLog('=== 戦術分析開始 ===', 'header');
    
    const offensePlayers = players.filter(p => POSITIONS.offense.some(o => o.id === p.id));
    const defensePlayers = players.filter(p => POSITIONS.defense.some(d => d.id === p.id));
    
    // マッチアップ分析
    const qb = offensePlayers.find(p => p.id === 'QB');
    const receivers = offensePlayers.filter(p => ['WR1', 'WR2', 'TE', 'RB'].includes(p.id));
    const coverageDB = defensePlayers.filter(p => ['CB1', 'CB2', 'FS', 'SS'].includes(p.id));
    
    addLog('【レシーバーマッチアップ分析】', 'section');
    
    let bestTarget = null;
    let maxSeparation = 0;
    
    receivers.forEach(receiver => {
      let closestDefender = null;
      let minDistance = Infinity;
      
      coverageDB.forEach(defender => {
        const dist = calculateDistance(receiver, defender);
        if (dist < minDistance) {
          minDistance = dist;
          closestDefender = defender;
        }
      });
      
      if (closestDefender) {
        const analysis = analyzeMatchup(receiver, closestDefender);
        addLog(`${receiver.name}: ${closestDefender.name}から${analysis.distance}yd - 脅威度:${analysis.threat}`, 
          analysis.threat === 'HIGH' ? 'warning' : analysis.threat === 'MEDIUM' ? 'caution' : 'success');
        
        if (minDistance > maxSeparation) {
          maxSeparation = minDistance;
          bestTarget = receiver;
        }
      }
    });
    
    if (bestTarget) {
      addLog(`【推奨ターゲット】 ${bestTarget.name} - 最大セパレーション`, 'recommendation');
    }
    
    // ブリッツ検知
    addLog('【ブリッツ分析】', 'section');
    const linebackers = defensePlayers.filter(p => ['MLB', 'OLB1', 'OLB2'].includes(p.id));
    const blitzingLBs = linebackers.filter(lb => lb.y > 220);
    
    if (blitzingLBs.length > 0) {
      addLog(`警告: ${blitzingLBs.length}人のLBがブリッツ位置！`, 'warning');
      addLog('対策: クイックパス、スクリーン、ホットルートを検討', 'recommendation');
    } else {
      addLog('ブリッツの兆候なし。通常のパスプロテクションで対応可能。', 'success');
    }
    
    // ランvs パス推奨
    addLog('【プレー選択推奨】', 'section');
    const boxCount = defensePlayers.filter(p => 
      p.x > 300 && p.x < 500 && p.y > 180 && p.y < 280
    ).length;
    
    if (boxCount >= 7) {
      addLog(`ボックス内${boxCount}人検知 - パスプレー推奨`, 'recommendation');
    } else if (boxCount <= 5) {
      addLog(`ボックス内${boxCount}人のみ - ランプレーが有効`, 'recommendation');
    } else {
      addLog(`ボックス内${boxCount}人 - バランス攻撃が最適`, 'info');
    }
    
    addLog('=== 分析完了 ===', 'header');
  }, [players, addLog, analyzeMatchup]);

  const applyPlayTemplate = useCallback((playName) => {
    const play = PLAY_TEMPLATES[playName];
    if (!play) return;
    
    setRoutes(play.routes);
    setSelectedPlay(playName);
    addLog(`プレー適用: ${playName}`, 'info');
    addLog(play.description, 'info');
  }, [addLog]);

  const applyDefensiveFormation = useCallback((formation) => {
    setDefensiveFormation(formation);
    const formationData = DEFENSIVE_FORMATIONS[formation];
    
    setPlayers(prev => prev.map(player => {
      if (formationData.adjustments[player.id]) {
        return { ...player, ...formationData.adjustments[player.id] };
      }
      const original = POSITIONS.defense.find(p => p.id === player.id);
      if (original && POSITIONS.defense.some(d => d.id === player.id)) {
        return { ...player, x: original.x, y: original.y };
      }
      return player;
    }));
    
    addLog(`ディフェンス隊形変更: ${formationData.name}`, 'info');
  }, [addLog]);

  const handlePlayerDrag = useCallback((e, playerId) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.max(20, Math.min(FIELD_WIDTH - 20, e.clientX - rect.left));
    const y = Math.max(20, Math.min(FIELD_HEIGHT - 20, e.clientY - rect.top));
    
    setPlayers(prev => prev.map(p => 
      p.id === playerId ? { ...p, x, y } : p
    ));
  }, []);

  const handleCanvasClick = useCallback((e) => {
    if (!selectedPlayer || !isDrawing) return;
    
    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    setCurrentRoute(prev => [...prev, { x, y }]);
  }, [selectedPlayer, isDrawing]);

  const finishRoute = useCallback(() => {
    if (selectedPlayer && currentRoute.length > 0) {
      setRoutes(prev => ({ ...prev, [selectedPlayer]: currentRoute }));
      addLog(`${selectedPlayer}のルート設定完了 (${currentRoute.length}ポイント)`, 'success');
    }
    setIsDrawing(false);
    setCurrentRoute([]);
  }, [selectedPlayer, currentRoute, addLog]);

  const simulatePlay = useCallback(() => {
    const yards = Math.floor(Math.random() * 15) - 2;
    const success = yards > 0;
    
    setPlayHistory(prev => [...prev, {
      play: selectedPlay || 'カスタム',
      defense: defensiveFormation,
      yards,
      success,
      timestamp: new Date(),
    }]);
    
    setGameStats(prev => ({
      totalPlays: prev.totalPlays + 1,
      passPlays: selectedPlay && !selectedPlay.includes('ダイブ') ? prev.passPlays + 1 : prev.passPlays,
      runPlays: selectedPlay && selectedPlay.includes('ダイブ') ? prev.runPlays + 1 : prev.runPlays,
      yardsGained: prev.yardsGained + Math.max(0, yards),
      successRate: ((prev.successRate * prev.totalPlays) + (success ? 100 : 0)) / (prev.totalPlays + 1),
    }));
    
    addLog(`プレー結果: ${yards > 0 ? '+' : ''}${yards}ヤード ${success ? '✓' : '✗'}`, success ? 'success' : 'warning');
  }, [selectedPlay, defensiveFormation, addLog]);

  const resetField = useCallback(() => {
    setPlayers([...POSITIONS.offense, ...POSITIONS.defense]);
    setRoutes({});
    setSelectedPlayer(null);
    setSelectedPlay(null);
    setCurrentRoute([]);
    setIsDrawing(false);
    addLog('フィールドをリセットしました', 'info');
  }, [addLog]);

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0a1628 0%, #1a2744 50%, #0d1f3c 100%)',
      fontFamily: '"Noto Sans JP", "Helvetica Neue", sans-serif',
      color: '#e8eef5',
      padding: '20px',
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&family=Orbitron:wght@700;900&display=swap');
        
        .title-glow {
          text-shadow: 0 0 30px rgba(255, 200, 87, 0.5), 0 0 60px rgba(255, 200, 87, 0.3);
        }
        
        .card {
          background: linear-gradient(145deg, rgba(30, 50, 80, 0.8), rgba(20, 35, 60, 0.9));
          border: 1px solid rgba(100, 150, 200, 0.2);
          border-radius: 16px;
          backdrop-filter: blur(10px);
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05);
        }
        
        .btn {
          padding: 10px 18px;
          border: none;
          border-radius: 8px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s ease;
          font-size: 13px;
        }
        
        .btn:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        
        .btn-primary {
          background: linear-gradient(135deg, #FFD700, #FFA500);
          color: #1a2744;
        }
        
        .btn-secondary {
          background: linear-gradient(135deg, #4ECDC4, #44A08D);
          color: white;
        }
        
        .btn-danger {
          background: linear-gradient(135deg, #E74C3C, #C0392B);
          color: white;
        }
        
        .btn-outline {
          background: transparent;
          border: 2px solid rgba(100, 150, 200, 0.4);
          color: #8ab4f8;
        }
        
        .btn-outline:hover {
          border-color: #8ab4f8;
          background: rgba(138, 180, 248, 0.1);
        }
        
        .btn-outline.active {
          background: rgba(138, 180, 248, 0.2);
          border-color: #8ab4f8;
        }
        
        .player-marker {
          cursor: grab;
          transition: transform 0.15s ease;
        }
        
        .player-marker:hover {
          transform: scale(1.2);
        }
        
        .log-entry {
          padding: 6px 10px;
          border-radius: 6px;
          font-size: 12px;
          margin-bottom: 4px;
          animation: slideIn 0.3s ease;
        }
        
        @keyframes slideIn {
          from { opacity: 0; transform: translateX(-10px); }
          to { opacity: 1; transform: translateX(0); }
        }
        
        .log-info { background: rgba(100, 150, 200, 0.15); }
        .log-success { background: rgba(46, 204, 113, 0.2); color: #2ecc71; }
        .log-warning { background: rgba(231, 76, 60, 0.2); color: #e74c3c; }
        .log-caution { background: rgba(241, 196, 15, 0.2); color: #f1c40f; }
        .log-header { background: rgba(155, 89, 182, 0.2); color: #bb6bd9; font-weight: 700; }
        .log-section { color: #8ab4f8; font-weight: 600; }
        .log-recommendation { background: rgba(78, 205, 196, 0.2); color: #4ecdc4; font-weight: 600; }
        
        .stat-card {
          background: rgba(30, 50, 80, 0.5);
          border-radius: 12px;
          padding: 12px 16px;
          text-align: center;
        }
        
        .stat-value {
          font-family: 'Orbitron', monospace;
          font-size: 24px;
          font-weight: 700;
          color: #FFD700;
        }
        
        .stat-label {
          font-size: 11px;
          color: rgba(255, 255, 255, 0.6);
          text-transform: uppercase;
          letter-spacing: 1px;
        }
        
        .field-grass {
          background: linear-gradient(180deg, 
            #2d5016 0%, #3a6b1e 10%, #2d5016 10%, #3a6b1e 20%,
            #2d5016 20%, #3a6b1e 30%, #2d5016 30%, #3a6b1e 40%,
            #2d5016 40%, #3a6b1e 50%, #2d5016 50%, #3a6b1e 60%,
            #2d5016 60%, #3a6b1e 70%, #2d5016 70%, #3a6b1e 80%,
            #2d5016 80%, #3a6b1e 90%, #2d5016 90%, #3a6b1e 100%
          );
        }
      `}</style>
      
      <header style={{ textAlign: 'center', marginBottom: 24 }}>
        <h1 style={{
          fontFamily: '"Orbitron", monospace',
          fontSize: 36,
          fontWeight: 900,
          background: 'linear-gradient(135deg, #FFD700, #FFA500, #FF6B35)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          margin: 0,
          letterSpacing: 2,
        }} className="title-glow">
          🏈 GRIDIRON ANALYTICS
        </h1>
        <p style={{ color: 'rgba(255,255,255,0.6)', margin: '8px 0 0', fontSize: 14 }}>
          アメリカンフットボール戦術分析システム
        </p>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 20, maxWidth: 1200, margin: '0 auto' }}>
        <div className="card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>フィールドビュー</h2>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-outline" onClick={() => setShowHeatmap(!showHeatmap)}>
                {showHeatmap ? '📊 ヒートマップOFF' : '📊 ヒートマップON'}
              </button>
              <button className="btn btn-danger" onClick={resetField}>リセット</button>
            </div>
          </div>
          
          <svg
            ref={canvasRef}
            width={FIELD_WIDTH}
            height={FIELD_HEIGHT}
            style={{ 
              borderRadius: 12, 
              cursor: isDrawing ? 'crosshair' : 'default',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
            }}
            onClick={handleCanvasClick}
          >
            <defs>
              <pattern id="grassPattern" patternUnits="userSpaceOnUse" width="80" height="50">
                <rect width="80" height="25" fill="#2d5016"/>
                <rect y="25" width="80" height="25" fill="#3a6b1e"/>
              </pattern>
              <filter id="glow">
                <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
            </defs>
            
            <rect width={FIELD_WIDTH} height={FIELD_HEIGHT} fill="url(#grassPattern)"/>
            
            {/* ヤードライン */}
            {Array.from({ length: 11 }, (_, i) => (
              <g key={i}>
                <line
                  x1={80 + i * 64}
                  y1={0}
                  x2={80 + i * 64}
                  y2={FIELD_HEIGHT}
                  stroke="rgba(255,255,255,0.3)"
                  strokeWidth={2}
                />
                <text
                  x={80 + i * 64}
                  y={20}
                  fill="rgba(255,255,255,0.5)"
                  fontSize={12}
                  textAnchor="middle"
                  fontWeight="bold"
                >
                  {i === 0 || i === 10 ? 'G' : i * 10}
                </text>
              </g>
            ))}
            
            {/* ハッシュマーク */}
            {Array.from({ length: 50 }, (_, i) => (
              <g key={`hash-${i}`}>
                <line x1={16 + i * 16} y1={165} x2={16 + i * 16} y2={175} stroke="rgba(255,255,255,0.4)" strokeWidth={1}/>
                <line x1={16 + i * 16} y1={325} x2={16 + i * 16} y2={335} stroke="rgba(255,255,255,0.4)" strokeWidth={1}/>
              </g>
            ))}
            
            {/* ライン・オブ・スクリメージ */}
            <line x1={0} y1={270} x2={FIELD_WIDTH} y2={270} stroke="#FFD700" strokeWidth={3} strokeDasharray="10,5" opacity={0.7}/>
            
            {/* ヒートマップ */}
            {showHeatmap && (
              <g opacity={0.3}>
                <ellipse cx={400} cy={200} rx={100} ry={60} fill="red"/>
                <ellipse cx={250} cy={220} rx={60} ry={40} fill="orange"/>
                <ellipse cx={550} cy={220} rx={60} ry={40} fill="orange"/>
                <ellipse cx={400} cy={300} rx={80} ry={50} fill="yellow"/>
              </g>
            )}
            
            {/* ルート描画 */}
            {Object.entries(routes).map(([playerId, route]) => {
              const player = players.find(p => p.id === playerId);
              if (!player || route.length === 0) return null;
              
              const pathData = `M ${player.x} ${player.y} ` + route.map(p => `L ${p.x} ${p.y}`).join(' ');
              return (
                <g key={`route-${playerId}`}>
                  <path
                    d={pathData}
                    fill="none"
                    stroke={player.color}
                    strokeWidth={3}
                    strokeDasharray="8,4"
                    filter="url(#glow)"
                  />
                  <circle
                    cx={route[route.length - 1].x}
                    cy={route[route.length - 1].y}
                    r={6}
                    fill={player.color}
                  />
                </g>
              );
            })}
            
            {/* 描画中のルート */}
            {isDrawing && currentRoute.length > 0 && selectedPlayer && (
              <path
                d={`M ${players.find(p => p.id === selectedPlayer)?.x} ${players.find(p => p.id === selectedPlayer)?.y} ` + 
                   currentRoute.map(p => `L ${p.x} ${p.y}`).join(' ')}
                fill="none"
                stroke="#fff"
                strokeWidth={2}
                strokeDasharray="5,5"
                opacity={0.7}
              />
            )}
            
            {/* 選手マーカー */}
            {players.map(player => (
              <g
                key={player.id}
                className="player-marker"
                transform={`translate(${player.x}, ${player.y})`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  const handleMove = (moveE) => handlePlayerDrag(moveE, player.id);
                  const handleUp = () => {
                    document.removeEventListener('mousemove', handleMove);
                    document.removeEventListener('mouseup', handleUp);
                  };
                  document.addEventListener('mousemove', handleMove);
                  document.addEventListener('mouseup', handleUp);
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedPlayer(player.id);
                }}
              >
                <circle
                  r={selectedPlayer === player.id ? 18 : 15}
                  fill={player.color}
                  stroke={selectedPlayer === player.id ? '#fff' : 'rgba(0,0,0,0.3)'}
                  strokeWidth={selectedPlayer === player.id ? 3 : 2}
                  filter={selectedPlayer === player.id ? 'url(#glow)' : undefined}
                />
                <text
                  y={4}
                  textAnchor="middle"
                  fill="#fff"
                  fontSize={10}
                  fontWeight="bold"
                  style={{ pointerEvents: 'none' }}
                >
                  {player.id}
                </text>
              </g>
            ))}
          </svg>
          
          {/* プレーテンプレート */}
          <div style={{ marginTop: 16 }}>
            <h3 style={{ margin: '0 0 10px', fontSize: 14, color: 'rgba(255,255,255,0.7)' }}>プレーテンプレート</h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {Object.keys(PLAY_TEMPLATES).map(play => (
                <button
                  key={play}
                  className={`btn btn-outline ${selectedPlay === play ? 'active' : ''}`}
                  onClick={() => applyPlayTemplate(play)}
                >
                  {play}
                </button>
              ))}
            </div>
          </div>
          
          {/* ディフェンス隊形 */}
          <div style={{ marginTop: 16 }}>
            <h3 style={{ margin: '0 0 10px', fontSize: 14, color: 'rgba(255,255,255,0.7)' }}>ディフェンス隊形</h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {Object.keys(DEFENSIVE_FORMATIONS).map(formation => (
                <button
                  key={formation}
                  className={`btn btn-outline ${defensiveFormation === formation ? 'active' : ''}`}
                  onClick={() => applyDefensiveFormation(formation)}
                >
                  {DEFENSIVE_FORMATIONS[formation].name}
                </button>
              ))}
            </div>
          </div>
        </div>
        
        {/* 右サイドパネル */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* ゲーム統計 */}
          <div className="card" style={{ padding: 16 }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 14 }}>📈 ゲーム統計</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
              <div className="stat-card">
                <div className="stat-value">{gameStats.totalPlays}</div>
                <div className="stat-label">総プレー数</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{gameStats.yardsGained}</div>
                <div className="stat-label">獲得ヤード</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{gameStats.passPlays}</div>
                <div className="stat-label">パスプレー</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{gameStats.successRate.toFixed(0)}%</div>
                <div className="stat-label">成功率</div>
              </div>
            </div>
          </div>
          
          {/* コントロール */}
          <div className="card" style={{ padding: 16 }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 14 }}>🎮 コントロール</h3>
            
            {selectedPlayer && (
              <div style={{ 
                background: 'rgba(78, 205, 196, 0.15)', 
                borderRadius: 8, 
                padding: 10, 
                marginBottom: 12,
                border: '1px solid rgba(78, 205, 196, 0.3)'
              }}>
                <div style={{ fontSize: 12, color: '#4ECDC4', marginBottom: 4 }}>選択中</div>
                <div style={{ fontWeight: 600 }}>
                  {players.find(p => p.id === selectedPlayer)?.name} ({selectedPlayer})
                </div>
              </div>
            )}
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <button
                className="btn btn-secondary"
                onClick={() => {
                  if (selectedPlayer) {
                    setIsDrawing(true);
                    setCurrentRoute([]);
                    addLog(`${selectedPlayer}のルート描画開始`, 'info');
                  }
                }}
                disabled={!selectedPlayer}
              >
                ✏️ ルート描画開始
              </button>
              
              {isDrawing && (
                <button className="btn btn-primary" onClick={finishRoute}>
                  ✓ ルート確定
                </button>
              )}
              
              <button className="btn btn-primary" onClick={runAnalysis}>
                🔍 戦術分析実行
              </button>
              
              <button className="btn btn-secondary" onClick={simulatePlay}>
                ▶️ プレーシミュレート
              </button>
            </div>
          </div>
          
          {/* 分析ログ */}
          <div className="card" style={{ padding: 16, flex: 1, minHeight: 200, maxHeight: 350, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 14 }}>📋 分析ログ</h3>
            <div style={{ flex: 1, overflowY: 'auto', paddingRight: 8 }}>
              {analysisLog.length === 0 ? (
                <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12, textAlign: 'center', padding: 20 }}>
                  「戦術分析実行」をクリックして分析を開始
                </div>
              ) : (
                analysisLog.map((entry, i) => (
                  <div key={i} className={`log-entry log-${entry.type}`}>
                    <span style={{ opacity: 0.5, marginRight: 8 }}>{entry.timestamp}</span>
                    {entry.message}
                  </div>
                ))
              )}
            </div>
          </div>
          
          {/* 凡例 */}
          <div className="card" style={{ padding: 12 }}>
            <h3 style={{ margin: '0 0 8px', fontSize: 12, color: 'rgba(255,255,255,0.6)' }}>凡例</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6, fontSize: 11 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#FFD700' }}/>
                <span>QB</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#4ECDC4' }}/>
                <span>WR</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#FF6B35' }}/>
                <span>RB</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#A8E6CF' }}/>
                <span>OL</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#E74C3C' }}/>
                <span>DL</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#9B59B6' }}/>
                <span>LB</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#3498DB' }}/>
                <span>DB</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* 使い方 */}
      <div className="card" style={{ maxWidth: 1200, margin: '20px auto', padding: 16 }}>
        <h3 style={{ margin: '0 0 12px', fontSize: 14 }}>📖 使い方</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, fontSize: 13, color: 'rgba(255,255,255,0.7)' }}>
          <div>
            <strong style={{ color: '#FFD700' }}>1. 選手配置</strong>
            <p style={{ margin: '4px 0 0' }}>選手をドラッグして位置を調整。クリックで選択。</p>
          </div>
          <div>
            <strong style={{ color: '#4ECDC4' }}>2. ルート設定</strong>
            <p style={{ margin: '4px 0 0' }}>選手を選択後「ルート描画」でフィールドをクリック。</p>
          </div>
          <div>
            <strong style={{ color: '#E74C3C' }}>3. 隊形変更</strong>
            <p style={{ margin: '4px 0 0' }}>ディフェンス隊形ボタンで守備配置を変更。</p>
          </div>
          <div>
            <strong style={{ color: '#9B59B6' }}>4. 分析実行</strong>
            <p style={{ margin: '4px 0 0' }}>「戦術分析実行」でマッチアップと推奨を確認。</p>
          </div>
        </div>
      </div>
    </div>
  );
}
