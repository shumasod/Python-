const HealthStatus = ({ status }) => {
  if (!status) {
    return (
      <div className="card bg-gray-100">
        <div className="flex items-center space-x-3">
          <div className="w-3 h-3 bg-gray-400 rounded-full animate-pulse"></div>
          <span className="text-gray-600">サーバーステータスを確認中...</span>
        </div>
      </div>
    )
  }

  const isHealthy = status.status === 'healthy' && status.model_loaded
  const statusColor = isHealthy ? 'bg-green-500' : 'bg-yellow-500'
  const statusText = isHealthy ? '正常稼働中' : 'モデル準備中'

  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className={`w-3 h-3 ${statusColor} rounded-full animate-pulse`}></div>
          <div>
            <span className="font-semibold text-gray-800">
              システムステータス: {statusText}
            </span>
            {status.version && (
              <span className="text-sm text-gray-500 ml-3">
                v{status.version}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center space-x-4 text-sm">
          <div className="flex items-center space-x-2">
            <span className="text-gray-600">モデル:</span>
            <span className={`font-semibold ${status.model_loaded ? 'text-green-600' : 'text-red-600'}`}>
              {status.model_loaded ? '✓ 読込済' : '✗ 未読込'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default HealthStatus
