import React, { useState, useCallback, useRef } from 'react';

const FIELD_WIDTH = 800;
const FIELD_HEIGHT = 520;

const FORMATIONS = {
  '4-4-2': {
    name: '4-4-2',
    positions: [
      { id: 'GK', name: 'ゴールキーパー', x: 400, y: 480, color: '#F39C12' },
      { id: 'LB', name: '左サイドバック', x: 120, y: 400, color: '#3498DB' },
      { id: 'CB1', name: 'センターバック左', x: 300, y: 420, color: '#3498DB' },
      { id: 'CB2', name: 'センターバック右', x: 500, y: 420, color: '#3498DB' },
      { id: 'RB', name: '右サイドバック', x: 680, y: 400, color: '#3498DB' },
      { id: 'LM', name: '左ミッドフィルダー', x: 120, y: 280, color: '#9B59B6' },
      { id: 'CM1', name: 'センターMF左', x: 300, y: 300, color: '#9B59B6' },
      { id: 'CM2', name: 'センターMF右', x: 500, y: 300, color: '#9B59B6' },
      { id: 'RM', name: '右ミッドフィルダー', x: 680, y: 280, color: '#9B59B6' },
      { id: 'ST1', name: 'ストライカー左', x: 320, y: 150, color: '#E74C3C' },
      { id: 'ST2', name: 'ストライカー右', x: 480, y: 150, color: '#E74C3C' },
    ],
  },
  '4-3-3': {
    name: '4-3-3',
    positions: [
      { id: 'GK', name: 'ゴールキーパー', x: 400, y: 480, color: '#F39C12' },
      { id: 'LB', name: '左サイドバック', x: 120, y: 400, color: '#3498DB' },
      { id: 'CB1', name: 'センターバック左', x: 300, y: 420, color: '#3498DB' },
      { id: 'CB2', name: 'センターバック右', x: 500, y: 420, color: '#3498DB' },
      { id: 'RB', name: '右サイドバック', x: 680, y: 400, color: '#3498DB' },
      { id: 'DM', name: '守備的MF', x: 400, y: 320, color: '#9B59B6' },
      { id: 'CM1', name: 'センターMF左', x: 280, y: 260, color: '#9B59B6' },
      { id: 'CM2', name: 'センターMF右', x: 520, y: 260, color: '#9B59B6' },
      { id: 'LW', name: '左ウイング', x: 150, y: 150, color: '#E74C3C' },
      { id: 'ST', name: 'センターFW', x: 400, y: 120, color: '#E74C3C' },
      { id: 'RW', name: '右ウイング', x: 650, y: 150, color: '#E74C3C' },
    ],
  },
  '3-5-2': {
    name: '3-5-2',
    positions: [
      { id: 'GK', name: 'ゴールキーパー', x: 400, y: 480, color: '#F39C12' },
      { id: 'CB1', name: 'センターバック左', x: 250, y: 420, color: '#3498DB' },
      { id: 'CB2', name: 'センターバック中', x: 400, y: 430, color: '#3498DB' },
      { id: 'CB3', name: 'センターバック右', x: 550, y: 420, color: '#3498DB' },
      { id: 'LWB', name: '左ウイングバック', x: 100, y: 320, color: '#1ABC9C' },
      { id: 'CM1', name: 'センターMF左', x: 280, y: 300, color: '#9B59B6' },
      { id: 'DM', name: '守備的MF', x: 400, y: 330, color: '#9B59B6' },
      { id: 'CM2', name: 'センターMF右', x: 520, y: 300, color: '#9B59B6' },
      { id: 'RWB', name: '右ウイングバック', x: 700, y: 320, color: '#1ABC9C' },
      { id: 'ST1', name: 'ストライカー左', x: 320, y: 140, color: '#E74C3C' },
      { id: 'ST2', name: 'ストライカー右', x: 480, y: 140, color: '#E74C3C' },
    ],
  },
  '4-2-3-1': {
    name: '4-2-3-1',
    positions: [
      { id: 'GK', name: 'ゴールキーパー', x: 400, y: 480, color: '#F39C12' },
      { id: 'LB', name: '左サイドバック', x: 120, y: 400, color: '#3498DB' },
      { id: 'CB1', name: 'センターバック左', x: 300, y: 420, color: '#3498DB' },
      { id: 'CB2', name: 'センターバック右', x: 500, y: 420, color: '#3498DB' },
      { id: 'RB', name: '右サイドバック', x: 680, y: 400, color: '#3498DB' },
      { id: 'DM1', name: '守備的MF左', x: 320, y: 320, color: '#9B59B6' },
      { id: 'DM2', name: '守備的MF右', x: 480, y: 320, color: '#9B59B6' },
      { id: 'LAM', name: '左攻撃的MF', x: 200, y: 220, color: '#E67E22' },
      { id: 'CAM', name: 'トップ下', x: 400, y: 200, color: '#E67E22' },
      { id: 'RAM', name: '右攻撃的MF', x: 600, y: 220, color: '#E67E22' },
      { id: 'ST', name: 'ストライカー', x: 400, y: 110, color: '#E74C3C' },
    ],
  },
  '5-3-2': {
    name: '5-3-2',
    positions: [
      { id: 'GK', name: 'ゴールキーパー', x: 400, y: 480, color: '#F39C12' },
      { id: 'LWB', name: '左ウイングバック', x: 80, y: 360, color: '#1ABC9C' },
      { id: 'CB1', name: 'センターバック左', x: 220, y: 420, color: '#3498DB' },
      { id: 'CB2', name: 'センターバック中', x: 400, y: 430, color: '#3498DB' },
      { id: 'CB3', name: 'センターバック右', x: 580, y: 420, color: '#3498DB' },
      { id: 'RWB', name: '右ウイングバック', x: 720, y: 360, color: '#1ABC9C' },
      { id: 'CM1', name: 'センターMF左', x: 280, y: 280, color: '#9B59B6' },
      { id: 'CM2', name: 'センターMF中', x: 400, y: 300, color: '#9B59B6' },
      { id: 'CM3', name: 'センターMF右', x: 520, y: 280, color: '#9B59B6' },
      { id: 'ST1', name: 'ストライカー左', x: 320, y: 140, color: '#E74C3C' },
      { id: 'ST2', name: 'ストライカー右', x: 480, y: 140, color: '#E74C3C' },
    ],
  },
};

const OPPONENT_FORMATIONS = {
  '4-4-2': [
    { id: 'OGK', x: 400, y: 40 },
    { id: 'OLB', x: 680, y: 120 },
    { id: 'OCB1', x: 500, y: 100 },
    { id: 'OCB2', x: 300, y: 100 },
    { id: 'ORB', x: 120, y: 120 },
    { id: 'OLM', x: 680, y: 240 },
    { id: 'OCM1', x: 500, y: 220 },
    { id: 'OCM2', x: 300, y: 220 },
    { id: 'ORM', x: 120, y: 240 },
    { id: 'OST1', x: 480, y: 370 },
    { id: 'OST2', x: 320, y: 370 },
  ],
  '4-3-3': [
    { id: 'OGK', x: 400, y: 40 },
    { id: 'OLB', x: 680, y: 120 },
    { id: 'OCB1', x: 500, y: 100 },
    { id: 'OCB2', x: 300, y: 100 },
    { id: 'ORB', x: 120, y: 120 },
    { id: 'ODM', x: 400, y: 200 },
    { id: 'OCM1', x: 520, y: 260 },
    { id: 'OCM2', x: 280, y: 260 },
    { id: 'OLW', x: 650, y: 370 },
    { id: 'OST', x: 400, y: 400 },
    { id: 'ORW', x: 150, y: 370 },
  ],
  '5-4-1': [
    { id: 'OGK', x: 400, y: 40 },
    { id: 'OLWB', x: 720, y: 140 },
    { id: 'OCB1', x: 560, y: 100 },
    { id: 'OCB2', x: 400, y: 90 },
    { id: 'OCB3', x: 240, y: 100 },
    { id: 'ORWB', x: 80, y: 140 },
    { id: 'OLM', x: 640, y: 240 },
    { id: 'OCM1', x: 480, y: 220 },
    { id: 'OCM2', x: 320, y: 220 },
    { id: 'ORM', x: 160, y: 240 },
    { id: 'OST', x: 400, y: 380 },
  ],
};

const TACTICAL_PATTERNS = {
  'ビルドアップ': {
    description: 'GKからのショートパスで後方からボールを繋ぐ',
    routes: {
      'GK': [{ x: 400, y: 450 }],
      'CB1': [{ x: 250, y: 380 }],
      'CB2': [{ x: 550, y: 380 }],
    },
  },
  'サイドアタック左': {
    description: '左サイドを崩してクロス',
    routes: {
      'LB': [{ x: 80, y: 300 }, { x: 60, y: 150 }],
      'LM': [{ x: 150, y: 200 }, { x: 200, y: 120 }],
      'ST1': [{ x: 350, y: 80 }],
    },
  },
  'サイドアタック右': {
    description: '右サイドを崩してクロス',
    routes: {
      'RB': [{ x: 720, y: 300 }, { x: 740, y: 150 }],
      'RM': [{ x: 650, y: 200 }, { x: 600, y: 120 }],
      'ST2': [{ x: 450, y: 80 }],
    },
  },
  'カウンター': {
    description: '素早い縦パスで一気にゴールを狙う',
    routes: {
      'CM1': [{ x: 350, y: 250 }],
      'ST1': [{ x: 300, y: 80 }],
      'ST2': [{ x: 500, y: 80 }],
    },
  },
  'ポゼッション': {
    description: 'ボールを保持して相手を動かす',
    routes: {
      'CB1': [{ x: 200, y: 380 }],
      'CB2': [{ x: 600, y: 380 }],
      'CM1': [{ x: 250, y: 280 }],
      'CM2': [{ x: 550, y: 280 }],
    },
  },
  'ハイプレス': {
    description: '高い位置からプレッシャーをかける',
    routes: {
      'ST1': [{ x: 350, y: 100 }],
      'ST2': [{ x: 450, y: 100 }],
      'CM1': [{ x: 280, y: 180 }],
      'CM2': [{ x: 520, y: 180 }],
    },
  },
};

const SET_PIECES = {
  'コーナーキック左': {
    ballPosition: { x: 20, y: 20 },
    description: '左コーナーからのセットプレー',
  },
  'コーナーキック右': {
    ballPosition: { x: 780, y: 20 },
    description: '右コーナーからのセットプレー',
  },
  'フリーキック中央': {
    ballPosition: { x: 400, y: 120 },
    description: 'ゴール正面からのFK',
  },
};

export default function SoccerAnalytics() {
  const [formation, setFormation] = useState('4-4-2');
  const [players, setPlayers] = useState(FORMATIONS['4-4-2'].positions);
  const [opponents, setOpponents] = useState(OPPONENT_FORMATIONS['4-4-2']);
  const [opponentFormation, setOpponentFormation] = useState('4-4-2');
  const [showOpponents, setShowOpponents] = useState(true);
  const [selectedPlayer, setSelectedPlayer] = useState(null);
  const [routes, setRoutes] = useState({});
  const [isDrawing, setIsDrawing] = useState(false);
  const [currentRoute, setCurrentRoute] = useState([]);
  const [analysisLog, setAnalysisLog] = useState([]);
  const [ballPosition, setBallPosition] = useState({ x: 400, y: 260 });
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [showPassingLanes, setShowPassingLanes] = useState(false);
  const [selectedPattern, setSelectedPattern] = useState(null);
  const [gameStats, setGameStats] = useState({
    possession: 50,
    passes: 0,
    shots: 0,
    corners: 0,
    attacks: { left: 0, center: 0, right: 0 },
  });
  const canvasRef = useRef(null);

  const addLog = useCallback((message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString('ja-JP');
    setAnalysisLog(prev => [...prev.slice(-19), { message, type, timestamp }]);
  }, []);

  const calculateDistance = (p1, p2) => {
    return Math.sqrt(Math.pow(p2.x - p1.x, 2) + Math.pow(p2.y - p1.y, 2));
  };

  const changeFormation = useCallback((newFormation) => {
    setFormation(newFormation);
    setPlayers(FORMATIONS[newFormation].positions);
    setRoutes({});
    addLog(`フォーメーション変更: ${FORMATIONS[newFormation].name}`, 'info');
  }, [addLog]);

  const changeOpponentFormation = useCallback((newFormation) => {
    setOpponentFormation(newFormation);
    setOpponents(OPPONENT_FORMATIONS[newFormation]);
    addLog(`相手フォーメーション: ${newFormation}`, 'info');
  }, [addLog]);

  const applyTacticalPattern = useCallback((patternName) => {
    const pattern = TACTICAL_PATTERNS[patternName];
    if (!pattern) return;
    
    setRoutes(pattern.routes);
    setSelectedPattern(patternName);
    addLog(`戦術パターン適用: ${patternName}`, 'info');
    addLog(pattern.description, 'info');
  }, [addLog]);

  const runAnalysis = useCallback(() => {
    addLog('=== 戦術分析開始 ===', 'header');
    
    // スペース分析
    addLog('【スペース分析】', 'section');
    
    const zones = [
      { name: '左サイド', xMin: 0, xMax: 267, attackers: 0, defenders: 0 },
      { name: '中央', xMin: 267, xMax: 533, attackers: 0, defenders: 0 },
      { name: '右サイド', xMin: 533, xMax: 800, attackers: 0, defenders: 0 },
    ];
    
    const attackingPlayers = players.filter(p => p.y < 300);
    const opponentDefenders = opponents.filter(o => o.y < 200);
    
    zones.forEach(zone => {
      zone.attackers = attackingPlayers.filter(p => p.x >= zone.xMin && p.x < zone.xMax).length;
      zone.defenders = opponentDefenders.filter(o => o.x >= zone.xMin && o.x < zone.xMax).length;
    });
    
    zones.forEach(zone => {
      const advantage = zone.attackers - zone.defenders;
      if (advantage > 0) {
        addLog(`${zone.name}: 数的優位 (+${advantage}) - 攻撃チャンス！`, 'success');
      } else if (advantage < 0) {
        addLog(`${zone.name}: 数的不利 (${advantage}) - サポート必要`, 'warning');
      } else {
        addLog(`${zone.name}: 均衡状態 - 個の力で突破を`, 'caution');
      }
    });
    
    // パスコース分析
    addLog('【パスコース分析】', 'section');
    
    const ballHolder = players.reduce((closest, player) => {
      const dist = calculateDistance(ballPosition, player);
      return dist < calculateDistance(ballPosition, closest) ? player : closest;
    }, players[0]);
    
    addLog(`ボール保持者: ${ballHolder.name}`, 'info');
    
    const passingOptions = players
      .filter(p => p.id !== ballHolder.id)
      .map(p => {
        const distance = calculateDistance(ballHolder, p);
        const blocked = opponents.some(opp => {
          const d1 = calculateDistance(ballHolder, opp);
          const d2 = calculateDistance(p, opp);
          return d1 < distance && d2 < distance && d1 + d2 < distance * 1.3;
        });
        return { player: p, distance, blocked };
      })
      .sort((a, b) => a.distance - b.distance);
    
    const openPasses = passingOptions.filter(p => !p.blocked).slice(0, 3);
    const blockedPasses = passingOptions.filter(p => p.blocked).slice(0, 2);
    
    if (openPasses.length > 0) {
      addLog('オープンパスコース:', 'recommendation');
      openPasses.forEach(p => {
        addLog(`  → ${p.player.name} (${(p.distance / 8).toFixed(1)}m)`, 'success');
      });
    }
    
    if (blockedPasses.length > 0) {
      addLog('ブロックされているコース:', 'info');
      blockedPasses.forEach(p => {
        addLog(`  × ${p.player.name}`, 'warning');
      });
    }
    
    // 守備ライン分析
    addLog('【守備ライン分析】', 'section');
    const defenderYPositions = opponents.filter(o => o.y < 150).map(o => o.y);
    const avgDefenseLine = defenderYPositions.reduce((a, b) => a + b, 0) / defenderYPositions.length;
    
    if (avgDefenseLine < 100) {
      addLog('相手守備ラインが高い - ロングボールでの裏狙いが有効', 'recommendation');
    } else if (avgDefenseLine > 140) {
      addLog('相手が引いている - サイド攻撃かミドルシュートを', 'recommendation');
    } else {
      addLog('相手守備ラインは標準的 - コンビネーションで崩す', 'info');
    }
    
    // 攻撃推奨
    addLog('【攻撃推奨】', 'section');
    const bestZone = zones.reduce((best, zone) => 
      (zone.attackers - zone.defenders) > (best.attackers - best.defenders) ? zone : best
    );
    addLog(`推奨攻撃エリア: ${bestZone.name}`, 'recommendation');
    
    addLog('=== 分析完了 ===', 'header');
  }, [players, opponents, ballPosition, addLog]);

  const handlePlayerDrag = useCallback((e, playerId, isOpponent = false) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.max(20, Math.min(FIELD_WIDTH - 20, e.clientX - rect.left));
    const y = Math.max(20, Math.min(FIELD_HEIGHT - 20, e.clientY - rect.top));
    
    if (isOpponent) {
      setOpponents(prev => prev.map(p => p.id === playerId ? { ...p, x, y } : p));
    } else {
      setPlayers(prev => prev.map(p => p.id === playerId ? { ...p, x, y } : p));
    }
  }, []);

  const handleCanvasClick = useCallback((e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    if (isDrawing && selectedPlayer) {
      setCurrentRoute(prev => [...prev, { x, y }]);
    } else if (e.shiftKey) {
      setBallPosition({ x, y });
      addLog(`ボール位置更新: (${x.toFixed(0)}, ${y.toFixed(0)})`, 'info');
    }
  }, [isDrawing, selectedPlayer, addLog]);

  const finishRoute = useCallback(() => {
    if (selectedPlayer && currentRoute.length > 0) {
      setRoutes(prev => ({ ...prev, [selectedPlayer]: currentRoute }));
      addLog(`${selectedPlayer}のランニングコース設定完了`, 'success');
    }
    setIsDrawing(false);
    setCurrentRoute([]);
  }, [selectedPlayer, currentRoute, addLog]);

  const resetField = useCallback(() => {
    setPlayers(FORMATIONS[formation].positions);
    setOpponents(OPPONENT_FORMATIONS[opponentFormation]);
    setRoutes({});
    setSelectedPlayer(null);
    setSelectedPattern(null);
    setBallPosition({ x: 400, y: 260 });
    addLog('フィールドをリセットしました', 'info');
  }, [formation, opponentFormation, addLog]);

  const simulateAction = useCallback((action) => {
    const success = Math.random() > 0.4;
    setGameStats(prev => ({
      ...prev,
      passes: action === 'pass' ? prev.passes + 1 : prev.passes,
      shots: action === 'shot' ? prev.shots + 1 : prev.shots,
      possession: Math.max(30, Math.min(70, prev.possession + (success ? 2 : -2))),
    }));
    addLog(`${action === 'pass' ? 'パス' : 'シュート'}: ${success ? '成功 ✓' : '失敗 ✗'}`, success ? 'success' : 'warning');
  }, [addLog]);

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0d1f0d 0%, #1a331a 50%, #0d2615 100%)',
      fontFamily: '"Noto Sans JP", "Helvetica Neue", sans-serif',
      color: '#e8f5e8',
      padding: '20px',
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&family=Rajdhani:wght@600;700&display=swap');
        
        .title-glow {
          text-shadow: 0 0 30px rgba(46, 204, 113, 0.5), 0 0 60px rgba(46, 204, 113, 0.3);
        }
        
        .card {
          background: linear-gradient(145deg, rgba(30, 60, 30, 0.85), rgba(20, 45, 20, 0.9));
          border: 1px solid rgba(46, 204, 113, 0.2);
          border-radius: 16px;
          backdrop-filter: blur(10px);
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05);
        }
        
        .btn {
          padding: 10px 16px;
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
          background: linear-gradient(135deg, #2ECC71, #27AE60);
          color: white;
        }
        
        .btn-secondary {
          background: linear-gradient(135deg, #3498DB, #2980B9);
          color: white;
        }
        
        .btn-danger {
          background: linear-gradient(135deg, #E74C3C, #C0392B);
          color: white;
        }
        
        .btn-outline {
          background: transparent;
          border: 2px solid rgba(46, 204, 113, 0.4);
          color: #2ECC71;
        }
        
        .btn-outline:hover {
          border-color: #2ECC71;
          background: rgba(46, 204, 113, 0.1);
        }
        
        .btn-outline.active {
          background: rgba(46, 204, 113, 0.2);
          border-color: #2ECC71;
        }
        
        .player-marker {
          cursor: grab;
          transition: transform 0.15s ease;
        }
        
        .player-marker:hover {
          transform: scale(1.15);
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
        
        .log-info { background: rgba(46, 204, 113, 0.1); }
        .log-success { background: rgba(46, 204, 113, 0.2); color: #2ecc71; }
        .log-warning { background: rgba(231, 76, 60, 0.2); color: #e74c3c; }
        .log-caution { background: rgba(241, 196, 15, 0.2); color: #f1c40f; }
        .log-header { background: rgba(52, 152, 219, 0.2); color: #3498db; font-weight: 700; }
        .log-section { color: #2ECC71; font-weight: 600; }
        .log-recommendation { background: rgba(155, 89, 182, 0.2); color: #bb6bd9; font-weight: 600; }
        
        .stat-card {
          background: rgba(30, 60, 30, 0.5);
          border-radius: 12px;
          padding: 12px 16px;
          text-align: center;
        }
        
        .stat-value {
          font-family: 'Rajdhani', sans-serif;
          font-size: 26px;
          font-weight: 700;
          color: #2ECC71;
        }
        
        .stat-label {
          font-size: 11px;
          color: rgba(255, 255, 255, 0.6);
          text-transform: uppercase;
          letter-spacing: 1px;
        }

        .possession-bar {
          height: 8px;
          border-radius: 4px;
          background: linear-gradient(90deg, #3498DB ${100 - 50}%, #E74C3C ${50}%);
          position: relative;
        }
      `}</style>
      
      <header style={{ textAlign: 'center', marginBottom: 24 }}>
        <h1 style={{
          fontFamily: '"Rajdhani", sans-serif',
          fontSize: 38,
          fontWeight: 700,
          background: 'linear-gradient(135deg, #2ECC71, #27AE60, #1ABC9C)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          margin: 0,
          letterSpacing: 3,
        }} className="title-glow">
          ⚽ PITCH TACTICS ANALYZER
        </h1>
        <p style={{ color: 'rgba(255,255,255,0.6)', margin: '8px 0 0', fontSize: 14 }}>
          サッカー戦術分析・シミュレーションシステム
        </p>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 20, maxWidth: 1240, margin: '0 auto' }}>
        <div className="card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>フィールドビュー</h2>
            <div style={{ display: 'flex', gap: 8 }}>
              <button 
                className={`btn btn-outline ${showOpponents ? 'active' : ''}`} 
                onClick={() => setShowOpponents(!showOpponents)}
              >
                👥 相手表示
              </button>
              <button 
                className={`btn btn-outline ${showPassingLanes ? 'active' : ''}`}
                onClick={() => setShowPassingLanes(!showPassingLanes)}
              >
                📐 パスレーン
              </button>
              <button 
                className={`btn btn-outline ${showHeatmap ? 'active' : ''}`}
                onClick={() => setShowHeatmap(!showHeatmap)}
              >
                🔥 ヒートマップ
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
              <linearGradient id="fieldGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#2d8a2d"/>
                <stop offset="50%" stopColor="#339933"/>
                <stop offset="100%" stopColor="#2d8a2d"/>
              </linearGradient>
              <filter id="glow">
                <feGaussianBlur stdDeviation="2.5" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
              <pattern id="grassStripes" patternUnits="userSpaceOnUse" width="60" height="520">
                <rect width="30" height="520" fill="#2d8a2d"/>
                <rect x="30" width="30" height="520" fill="#339933"/>
              </pattern>
            </defs>
            
            {/* フィールド背景 */}
            <rect width={FIELD_WIDTH} height={FIELD_HEIGHT} fill="url(#grassStripes)"/>
            
            {/* フィールドライン */}
            <rect x={40} y={20} width={720} height={480} fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth={2}/>
            
            {/* センターライン */}
            <line x1={40} y1={260} x2={760} y2={260} stroke="rgba(255,255,255,0.8)" strokeWidth={2}/>
            
            {/* センターサークル */}
            <circle cx={400} cy={260} r={60} fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth={2}/>
            <circle cx={400} cy={260} r={3} fill="rgba(255,255,255,0.8)"/>
            
            {/* ゴールエリア（上） */}
            <rect x={290} y={20} width={220} height={60} fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth={2}/>
            <rect x={340} y={20} width={120} height={25} fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth={2}/>
            <circle cx={400} cy={56} r={3} fill="rgba(255,255,255,0.8)"/>
            
            {/* ゴールエリア（下） */}
            <rect x={290} y={440} width={220} height={60} fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth={2}/>
            <rect x={340} y={475} width={120} height={25} fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth={2}/>
            <circle cx={400} cy={464} r={3} fill="rgba(255,255,255,0.8)"/>
            
            {/* コーナーアーク */}
            <path d="M 40 30 A 10 10 0 0 0 50 20" fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth={2}/>
            <path d="M 750 20 A 10 10 0 0 0 760 30" fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth={2}/>
            <path d="M 40 490 A 10 10 0 0 1 50 500" fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth={2}/>
            <path d="M 750 500 A 10 10 0 0 1 760 490" fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth={2}/>
            
            {/* ヒートマップ */}
            {showHeatmap && (
              <g opacity={0.25}>
                <ellipse cx={400} cy={150} rx={120} ry={80} fill="#E74C3C"/>
                <ellipse cx={200} cy={200} rx={80} ry={60} fill="#F39C12"/>
                <ellipse cx={600} cy={200} rx={80} ry={60} fill="#F39C12"/>
                <ellipse cx={400} cy={300} rx={150} ry={70} fill="#F1C40F"/>
              </g>
            )}
            
            {/* パスレーン */}
            {showPassingLanes && players.map(player => {
              const nearbyPlayers = players.filter(p => 
                p.id !== player.id && calculateDistance(player, p) < 200
              );
              return nearbyPlayers.map(target => (
                <line
                  key={`lane-${player.id}-${target.id}`}
                  x1={player.x}
                  y1={player.y}
                  x2={target.x}
                  y2={target.y}
                  stroke="rgba(46, 204, 113, 0.3)"
                  strokeWidth={1}
                  strokeDasharray="4,4"
                />
              ));
            })}
            
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
                  <polygon
                    points={`${route[route.length - 1].x},${route[route.length - 1].y - 8} ${route[route.length - 1].x - 6},${route[route.length - 1].y + 4} ${route[route.length - 1].x + 6},${route[route.length - 1].y + 4}`}
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
            
            {/* 相手選手 */}
            {showOpponents && opponents.map(opponent => (
              <g
                key={opponent.id}
                className="player-marker"
                transform={`translate(${opponent.x}, ${opponent.y})`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  const handleMove = (moveE) => handlePlayerDrag(moveE, opponent.id, true);
                  const handleUp = () => {
                    document.removeEventListener('mousemove', handleMove);
                    document.removeEventListener('mouseup', handleUp);
                  };
                  document.addEventListener('mousemove', handleMove);
                  document.addEventListener('mouseup', handleUp);
                }}
              >
                <circle r={14} fill="#C0392B" stroke="rgba(0,0,0,0.4)" strokeWidth={2}/>
                <text y={4} textAnchor="middle" fill="#fff" fontSize={9} fontWeight="bold" style={{ pointerEvents: 'none' }}>
                  {opponent.id.replace('O', '')}
                </text>
              </g>
            ))}
            
            {/* 自チーム選手 */}
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
                  r={selectedPlayer === player.id ? 17 : 14}
                  fill={player.color}
                  stroke={selectedPlayer === player.id ? '#fff' : 'rgba(0,0,0,0.3)'}
                  strokeWidth={selectedPlayer === player.id ? 3 : 2}
                  filter={selectedPlayer === player.id ? 'url(#glow)' : undefined}
                />
                <text
                  y={4}
                  textAnchor="middle"
                  fill="#fff"
                  fontSize={9}
                  fontWeight="bold"
                  style={{ pointerEvents: 'none' }}
                >
                  {player.id}
                </text>
              </g>
            ))}
            
            {/* ボール */}
            <g transform={`translate(${ballPosition.x}, ${ballPosition.y})`}>
              <circle r={8} fill="#fff" stroke="#000" strokeWidth={1}/>
              <circle r={3} fill="#000"/>
            </g>
          </svg>
          
          {/* フォーメーション選択 */}
          <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div>
              <h3 style={{ margin: '0 0 8px', fontSize: 13, color: 'rgba(255,255,255,0.7)' }}>自チーム フォーメーション</h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {Object.keys(FORMATIONS).map(f => (
                  <button
                    key={f}
                    className={`btn btn-outline ${formation === f ? 'active' : ''}`}
                    onClick={() => changeFormation(f)}
                    style={{ fontSize: 12, padding: '8px 12px' }}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <h3 style={{ margin: '0 0 8px', fontSize: 13, color: 'rgba(255,255,255,0.7)' }}>相手 フォーメーション</h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {Object.keys(OPPONENT_FORMATIONS).map(f => (
                  <button
                    key={f}
                    className={`btn btn-outline ${opponentFormation === f ? 'active' : ''}`}
                    onClick={() => changeOpponentFormation(f)}
                    style={{ fontSize: 12, padding: '8px 12px' }}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>
          </div>
          
          {/* 戦術パターン */}
          <div style={{ marginTop: 16 }}>
            <h3 style={{ margin: '0 0 8px', fontSize: 13, color: 'rgba(255,255,255,0.7)' }}>戦術パターン</h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {Object.keys(TACTICAL_PATTERNS).map(pattern => (
                <button
                  key={pattern}
                  className={`btn btn-outline ${selectedPattern === pattern ? 'active' : ''}`}
                  onClick={() => applyTacticalPattern(pattern)}
                  style={{ fontSize: 12, padding: '8px 12px' }}
                >
                  {pattern}
                </button>
              ))}
            </div>
          </div>
        </div>
        
        {/* 右サイドパネル */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* ゲーム統計 */}
          <div className="card" style={{ padding: 16 }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 14 }}>📊 マッチ統計</h3>
            
            {/* ポゼッション */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 12 }}>
                <span style={{ color: '#3498DB' }}>自チーム {gameStats.possession}%</span>
                <span style={{ color: '#E74C3C' }}>{100 - gameStats.possession}% 相手</span>
              </div>
              <div style={{
                height: 8,
                borderRadius: 4,
                background: `linear-gradient(90deg, #3498DB ${gameStats.possession}%, #E74C3C ${gameStats.possession}%)`,
              }}/>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
              <div className="stat-card">
                <div className="stat-value">{gameStats.passes}</div>
                <div className="stat-label">パス</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{gameStats.shots}</div>
                <div className="stat-label">シュート</div>
              </div>
            </div>
            
            {/* 攻撃方向 */}
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)', marginBottom: 6 }}>攻撃方向</div>
              <div style={{ display: 'flex', gap: 4 }}>
                <div style={{ flex: 1, background: 'rgba(231, 76, 60, 0.3)', height: 20, borderRadius: 4 }}/>
                <div style={{ flex: 2, background: 'rgba(46, 204, 113, 0.3)', height: 20, borderRadius: 4 }}/>
                <div style={{ flex: 1, background: 'rgba(231, 76, 60, 0.3)', height: 20, borderRadius: 4 }}/>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginTop: 4, color: 'rgba(255,255,255,0.5)' }}>
                <span>左</span>
                <span>中央</span>
                <span>右</span>
              </div>
            </div>
          </div>
          
          {/* コントロール */}
          <div className="card" style={{ padding: 16 }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 14 }}>🎮 コントロール</h3>
            
            {selectedPlayer && (
              <div style={{ 
                background: 'rgba(46, 204, 113, 0.15)', 
                borderRadius: 8, 
                padding: 10, 
                marginBottom: 12,
                border: '1px solid rgba(46, 204, 113, 0.3)'
              }}>
                <div style={{ fontSize: 12, color: '#2ECC71', marginBottom: 4 }}>選択中</div>
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
                    addLog(`${selectedPlayer}のランニングコース描画開始`, 'info');
                  }
                }}
                disabled={!selectedPlayer}
              >
                ✏️ ランニングコース描画
              </button>
              
              {isDrawing && (
                <button className="btn btn-primary" onClick={finishRoute}>
                  ✓ コース確定
                </button>
              )}
              
              <button className="btn btn-primary" onClick={runAnalysis}>
                🔍 戦術分析実行
              </button>
              
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <button className="btn btn-secondary" onClick={() => simulateAction('pass')}>
                  ⚡ パス
                </button>
                <button className="btn btn-danger" onClick={() => simulateAction('shot')}>
                  🎯 シュート
                </button>
              </div>
            </div>
            
            <div style={{ marginTop: 12, padding: 10, background: 'rgba(0,0,0,0.2)', borderRadius: 8, fontSize: 11, color: 'rgba(255,255,255,0.6)' }}>
              💡 Shift + クリックでボール位置を移動
            </div>
          </div>
          
          {/* 分析ログ */}
          <div className="card" style={{ padding: 16, flex: 1, minHeight: 200, maxHeight: 320, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 14 }}>📋 分析ログ</h3>
            <div style={{ flex: 1, overflowY: 'auto', paddingRight: 8 }}>
              {analysisLog.length === 0 ? (
                <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12, textAlign: 'center', padding: 20 }}>
                  「戦術分析実行」をクリックして分析開始
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
                <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#F39C12' }}/>
                <span>GK</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#3498DB' }}/>
                <span>DF</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#9B59B6' }}/>
                <span>MF</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#E74C3C' }}/>
                <span>FW</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#1ABC9C' }}/>
                <span>WB</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#C0392B' }}/>
                <span>相手</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* 使い方 */}
      <div className="card" style={{ maxWidth: 1240, margin: '20px auto', padding: 16 }}>
        <h3 style={{ margin: '0 0 12px', fontSize: 14 }}>📖 使い方</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, fontSize: 13, color: 'rgba(255,255,255,0.7)' }}>
          <div>
            <strong style={{ color: '#2ECC71' }}>1. 選手配置</strong>
            <p style={{ margin: '4px 0 0' }}>選手をドラッグして位置調整。クリックで選択。</p>
          </div>
          <div>
            <strong style={{ color: '#3498DB' }}>2. フォーメーション</strong>
            <p style={{ margin: '4px 0 0' }}>自チーム・相手のフォーメーションを選択。</p>
          </div>
          <div>
            <strong style={{ color: '#9B59B6' }}>3. 戦術パターン</strong>
            <p style={{ margin: '4px 0 0' }}>ビルドアップ、サイドアタック等をワンクリック適用。</p>
          </div>
          <div>
            <strong style={{ color: '#E74C3C' }}>4. 分析実行</strong>
            <p style={{ margin: '4px 0 0' }}>スペース・パスコース・守備ラインを自動分析。</p>
          </div>
        </div>
      </div>
    </div>
  );
}
