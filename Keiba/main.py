import React, { useState, useEffect, useRef, useCallback } from 'react';
import { AlertCircle, Bluetooth, Power, Battery, Wifi, WifiOff } from 'lucide-react';

// ===== 定数定義 =====
const BLUETOOTH_CONFIG = {
  SERVICE_UUID: '12345678-1234-1234-1234-123456789abc',
  CHARACTERISTIC_UUID: '87654321-4321-4321-4321-cba987654321',
  DEVICE_NAME_PREFIX: 'SetsubunDetector',
};

const SystemState = {
  STANDBY: 0,
  WARNING: 1,
  ALERT: 2,
  LOW_BATTERY: 3,
};

const STATE_NAMES = {
  [SystemState.STANDBY]: '待機中',
  [SystemState.WARNING]: '警戒モード',
  [SystemState.ALERT]: '警報モード',
  [SystemState.LOW_BATTERY]: '電池残量低下',
};

const LOG_TYPES = {
  INFO: 'info',
  SUCCESS: 'success',
  WARNING: 'warning',
  ERROR: 'error',
};

const DISTANCE_THRESHOLDS = {
  DANGER: 200,
  WARNING: 300,
  MAX: 300,
};

const BATTERY_THRESHOLDS = {
  HIGH: 50,
  LOW: 20,
};

const MAX_LOGS = 50;

// ===== ユーティリティ関数 =====
const convertMetersTocentimeters = (meters) => meters * 100;

const getBatteryColorClass = (percentage) => {
  if (percentage > BATTERY_THRESHOLDS.HIGH) return 'text-green-500';
  if (percentage > BATTERY_THRESHOLDS.LOW) return 'text-yellow-500';
  return 'text-red-500';
};

const getStateColorClass = (state) => {
  const colorMap = {
    [SystemState.STANDBY]: 'bg-green-500',
    [SystemState.WARNING]: 'bg-yellow-500',
    [SystemState.ALERT]: 'bg-red-500',
    [SystemState.LOW_BATTERY]: 'bg-blue-500',
  };
  return colorMap[state] || 'bg-gray-500';
};

const getDistanceWarning = (distance) => {
  if (distance > DISTANCE_THRESHOLDS.MAX || distance === 0) return null;
  if (distance < DISTANCE_THRESHOLDS.DANGER) {
    return { level: 'danger', message: '緊急警報！' };
  }
  if (distance < DISTANCE_THRESHOLDS.WARNING) {
    return { level: 'warning', message: '警戒中' };
  }
  return null;
};

// ===== カスタムフック: ログ管理 =====
const useLogManager = () => {
  const [logs, setLogs] = useState([]);

  const addLog = useCallback((message, type = LOG_TYPES.INFO) => {
    const newLog = {
      id: Date.now() + Math.random(),
      timestamp: new Date().toLocaleTimeString('ja-JP'),
      message,
      type,
    };
    setLogs((prev) => [newLog, ...prev.slice(0, MAX_LOGS - 1)]);
  }, []);

  const clearLogs = useCallback(() => setLogs([]), []);

  return { logs, addLog, clearLogs };
};

// ===== カスタムフック: Bluetooth接続管理 =====
const useBluetoothConnection = (addLog) => {
  const [device, setDevice] = useState(null);
  const [characteristic, setCharacteristic] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('未接続');

  const handleDisconnect = useCallback(() => {
    setIsConnected(false);
    setDevice(null);
    setCharacteristic(null);
    setConnectionStatus('切断されました');
    addLog('Bluetoothデバイスが切断されました', LOG_TYPES.WARNING);
  }, [addLog]);

  const connect = useCallback(async () => {
    try {
      setConnectionStatus('接続中...');
      addLog('Bluetoothデバイスを検索中...', LOG_TYPES.INFO);

      const bluetoothDevice = await navigator.bluetooth.requestDevice({
        filters: [
          { namePrefix: BLUETOOTH_CONFIG.DEVICE_NAME_PREFIX },
          { services: [BLUETOOTH_CONFIG.SERVICE_UUID] },
        ],
        optionalServices: [BLUETOOTH_CONFIG.SERVICE_UUID],
      });

      addLog(`デバイス発見: ${bluetoothDevice.name}`, LOG_TYPES.SUCCESS);

      const server = await bluetoothDevice.gatt.connect();
      const service = await server.getPrimaryService(BLUETOOTH_CONFIG.SERVICE_UUID);
      const char = await service.getCharacteristic(BLUETOOTH_CONFIG.CHARACTERISTIC_UUID);

      setDevice(bluetoothDevice);
      setCharacteristic(char);
      setIsConnected(true);
      setConnectionStatus('接続済み');

      addLog('Bluetooth接続完了', LOG_TYPES.SUCCESS);

      bluetoothDevice.addEventListener('gattserverdisconnected', handleDisconnect);

      return char;
    } catch (error) {
      console.error('Bluetooth接続エラー:', error);
      addLog(`接続エラー: ${error.message}`, LOG_TYPES.ERROR);
      setConnectionStatus('接続失敗');
      throw error;
    }
  }, [addLog, handleDisconnect]);

  const disconnect = useCallback(() => {
    device?.gatt?.disconnect();
  }, [device]);

  const sendCommand = useCallback(
    async (command) => {
      if (!characteristic) {
        addLog('デバイスが接続されていません', LOG_TYPES.ERROR);
        return false;
      }

      try {
        const encoder = new TextEncoder();
        const data = encoder.encode(`${command}\n`);
        await characteristic.writeValue(data);
        addLog(`コマンド送信: ${command}`, LOG_TYPES.INFO);
        return true;
      } catch (error) {
        console.error('コマンド送信エラー:', error);
        addLog(`コマンド送信エラー: ${error.message}`, LOG_TYPES.ERROR);
        return false;
      }
    },
    [characteristic, addLog]
  );

  return {
    device,
    characteristic,
    isConnected,
    connectionStatus,
    connect,
    disconnect,
    sendCommand,
  };
};

// ===== カスタムフック: センサーデータ管理 =====
const useSensorData = () => {
  const [data, setData] = useState({
    distance: 0,
    motionDetected: false,
    batteryPercentage: 100,
    currentState: SystemState.STANDBY,
    systemActive: true,
    lastUpdate: new Date(),
  });

  const updateData = useCallback((newData) => {
    setData({
      distance: convertMetersTocentimeters(newData.distance),
      motionDetected: newData.motion,
      batteryPercentage: newData.battery,
      currentState: newData.state,
      systemActive: newData.active,
      lastUpdate: new Date(),
    });
  }, []);

  return { data, updateData };
};

// ===== サブコンポーネント =====
const ConnectionStatus = ({ isConnected, connectionStatus, onConnect, onDisconnect }) => (
  <div className="bg-gray-800 rounded-lg p-4 mb-6 border-2 border-gray-700">
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center space-x-3">
        <div
          className={`w-4 h-4 rounded-full ${
            isConnected ? 'bg-green-500' : 'bg-red-500'
          } animate-pulse`}
        />
        <span className="font-semibold">接続状態: {connectionStatus}</span>
        {isConnected ? (
          <Wifi className="w-5 h-5 text-green-500" />
        ) : (
          <WifiOff className="w-5 h-5 text-red-500" />
        )}
      </div>
      <button
        onClick={isConnected ? onDisconnect : onConnect}
        className={`px-4 py-2 rounded-lg font-medium ${
          isConnected ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'
        } transition-colors duration-200`}
      >
        <Bluetooth className="w-4 h-4 inline mr-2" />
        {isConnected ? '切断' : '接続'}
      </button>
    </div>
  </div>
);

const SystemStateDisplay = ({ state, lastUpdate }) => (
  <div className="bg-gray-800 rounded-lg p-6 border-2 border-gray-700">
    <h3 className="text-xl font-bold mb-4 text-center">システム状態</h3>
    <div className="flex flex-col items-center space-y-4">
      <div className={`w-16 h-16 rounded-full ${getStateColorClass(state)} animate-pulse shadow-lg`} />
      <div className="text-center">
        <p className="text-lg font-semibold">{STATE_NAMES[state]}</p>
        <p className="text-sm text-gray-400">
          最終更新: {lastUpdate.toLocaleTimeString('ja-JP')}
        </p>
      </div>
    </div>
  </div>
);

const DistanceSensor = ({ distance, motionDetected }) => {
  const warning = getDistanceWarning(distance);

  return (
    <div className="bg-gray-800 rounded-lg p-6 border-2 border-gray-700">
      <h3 className="text-xl font-bold mb-4 text-center">距離センサー</h3>
      <div className="text-center">
        <div className="text-4xl font-bold mb-2">
          {distance > 0 ? `${distance.toFixed(1)}cm` : '---'}
        </div>
        {warning && (
          <div
            className={`mt-3 p-2 rounded-lg ${
              warning.level === 'danger' ? 'bg-red-600 text-white' : 'bg-yellow-600 text-white'
            }`}
          >
            <AlertCircle className="w-4 h-4 inline mr-2" />
            {warning.message}
          </div>
        )}
        {motionDetected && <div className="mt-2 text-yellow-400">🚶 動きを検知中</div>}
      </div>
    </div>
  );
};

const BatteryDisplay = ({ percentage }) => {
  const colorClass = getBatteryColorClass(percentage);

  return (
    <div className="bg-gray-800 rounded-lg p-6 border-2 border-gray-700">
      <h3 className="text-xl font-bold mb-4 text-center">バッテリー</h3>
      <div className="text-center">
        <Battery className={`w-12 h-12 mx-auto mb-3 ${colorClass}`} />
        <div className="text-3xl font-bold mb-2">{percentage.toFixed(1)}%</div>
        <div className="w-full bg-gray-600 rounded-full h-3">
          <div
            className={`h-3 rounded-full transition-all duration-500 ${colorClass.replace(
              'text-',
              'bg-'
            )}`}
            style={{ width: `${Math.max(percentage, 0)}%` }}
          />
        </div>
      </div>
    </div>
  );
};

const ControlPanel = ({ systemActive, isConnected, onToggle, onRequestStatus }) => (
  <div className="bg-gray-800 rounded-lg p-6 border-2 border-gray-700 mb-6">
    <h3 className="text-xl font-bold mb-4 text-center">システム制御</h3>
    <div className="flex flex-wrap gap-4 justify-center">
      <button
        onClick={onToggle}
        disabled={!isConnected}
        className={`px-6 py-3 rounded-lg font-medium transition-colors duration-200 ${
          systemActive ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'
        } disabled:bg-gray-600 disabled:cursor-not-allowed`}
      >
        <Power className="w-5 h-5 inline mr-2" />
        {systemActive ? 'システム停止' : 'システム開始'}
      </button>

      <button
        onClick={onRequestStatus}
        disabled={!isConnected}
        className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium transition-colors duration-200 disabled:bg-gray-600 disabled:cursor-not-allowed"
      >
        ステータス更新
      </button>
    </div>
  </div>
);

const LogDisplay = ({ logs }) => {
  const getLogColorClass = (type) => {
    const colorMap = {
      [LOG_TYPES.ERROR]: 'text-red-400',
      [LOG_TYPES.SUCCESS]: 'text-green-400',
      [LOG_TYPES.WARNING]: 'text-yellow-400',
      [LOG_TYPES.INFO]: 'text-gray-300',
    };
    return colorMap[type] || 'text-gray-300';
  };

  return (
    <div className="bg-gray-800 rounded-lg p-6 border-2 border-gray-700">
      <h3 className="text-xl font-bold mb-4">システムログ</h3>
      <div className="bg-black rounded-lg p-4 h-64 overflow-y-auto font-mono text-sm">
        {logs.length === 0 ? (
          <p className="text-gray-500">ログがありません</p>
        ) : (
          logs.map((log) => (
            <div key={log.id} className={`mb-1 ${getLogColorClass(log.type)}`}>
              <span className="text-gray-500">[{log.timestamp}]</span> {log.message}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

// ===== メインコンポーネント =====
const SetsubunDetectorApp = () => {
  const { logs, addLog } = useLogManager();
  const { data, updateData } = useSensorData();
  const { isConnected, connectionStatus, characteristic, connect, disconnect, sendCommand } =
    useBluetoothConnection(addLog);

  // Bluetoothデータ受信処理
  const handleBluetoothData = useCallback(
    (event) => {
      try {
        const decoder = new TextDecoder();
        const jsonString = decoder.decode(event.target.value);
        const parsedData = JSON.parse(jsonString);

        updateData(parsedData);
        addLog(
          `データ受信: 距離=${convertMetersTocentimeters(parsedData.distance).toFixed(
            1
          )}cm, バッテリー=${parsedData.battery.toFixed(1)}%`,
          LOG_TYPES.INFO
        );
      } catch (error) {
        console.error('データ解析エラー:', error);
        addLog(`データ解析エラー: ${error.message}`, LOG_TYPES.ERROR);
      }
    },
    [updateData, addLog]
  );

  // Bluetooth接続とデータ受信設定
  const handleConnect = useCallback(async () => {
    try {
      const char = await connect();
      await char.startNotifications();
      char.addEventListener('characteristicvaluechanged', handleBluetoothData);
    } catch (error) {
      // エラーは connect 内で処理済み
    }
  }, [connect, handleBluetoothData]);

  // システムトグル
  const handleSystemToggle = useCallback(() => {
    const command = data.systemActive ? 'STOP' : 'START';
    sendCommand(command);
  }, [data.systemActive, sendCommand]);

  // ステータス要求
  const requestStatus = useCallback(() => {
    sendCommand('STATUS');
  }, [sendCommand]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-blue-900 to-indigo-900 text-white">
      <div className="container mx-auto px-4 py-6">
        {/* ヘッダー */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-yellow-400 to-red-500 bg-clip-text text-transparent">
            🎌 節分鬼検知システム v1.3 🎌
          </h1>
          <p className="text-lg text-gray-300">Bluetooth対応版 - Web制御インターフェース</p>
        </div>

        {/* 接続ステータス */}
        <ConnectionStatus
          isConnected={isConnected}
          connectionStatus={connectionStatus}
          onConnect={handleConnect}
          onDisconnect={disconnect}
        />

        {/* メイン制御パネル */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-6">
          <SystemStateDisplay state={data.currentState} lastUpdate={data.lastUpdate} />
          <DistanceSensor distance={data.distance} motionDetected={data.motionDetected} />
          <BatteryDisplay percentage={data.batteryPercentage} />
        </div>

        {/* 制御ボタン */}
        <ControlPanel
          systemActive={data.systemActive}
          isConnected={isConnected}
          onToggle={handleSystemToggle}
          onRequestStatus={requestStatus}
        />

        {/* ログ表示 */}
        <LogDisplay logs={logs} />

        {/* フッター */}
        <div className="text-center mt-8 text-gray-400">
          <p>節分鬼検知システム - Web Bluetooth API対応</p>
          <p className="text-sm">豆まきの効果を科学的に測定します 🫘👹</p>
        </div>
      </div>
    </div>
  );
};

export default SetsubunDetectorApp;
