import { useState } from 'react'
import VideoPlayer from './VideoPlayer'
import { useTheme } from '../contexts/ThemeContext'

/**
 * ライブレースセクション
 */
const LiveRaceSection = () => {
  const { organization } = useTheme()
  const [selectedVideo, setSelectedVideo] = useState(null)

  // 競馬団体ごとのライブ配信情報
  const liveStreams = {
    jra: [
      {
        id: 'jra-live-1',
        title: 'JRA 中山競馬場 ライブ配信',
        type: 'youtube',
        url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', // デモ用URL
        thumbnail: 'https://via.placeholder.com/640x360/006937/ffffff?text=JRA+Live',
        isLive: true,
        track: '中山競馬場',
        raceNumber: '11R',
      },
      {
        id: 'jra-live-2',
        title: 'JRA 阪神競馬場 ライブ配信',
        type: 'youtube',
        url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        thumbnail: 'https://via.placeholder.com/640x360/006937/ffffff?text=JRA+Live+2',
        isLive: false,
        track: '阪神競馬場',
        raceNumber: '10R',
      },
    ],
    nar: [
      {
        id: 'nar-live-1',
        title: '大井競馬場 ライブ配信',
        type: 'youtube',
        url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        thumbnail: 'https://via.placeholder.com/640x360/e60012/ffffff?text=NAR+Live',
        isLive: true,
        track: '大井競馬場',
        raceNumber: '12R',
      },
    ],
    hongkong: [
      {
        id: 'hkjc-live-1',
        title: 'Happy Valley Racecourse Live',
        type: 'youtube',
        url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        thumbnail: 'https://via.placeholder.com/640x360/00539f/ffffff?text=HKJC+Live',
        isLive: true,
        track: 'Happy Valley',
        raceNumber: 'Race 8',
      },
    ],
  }

  const currentStreams = liveStreams[organization.id] || []

  if (currentStreams.length === 0) {
    return (
      <div className="card bg-gray-50">
        <div className="text-center py-12">
          <div className="text-6xl mb-4">📺</div>
          <p className="text-gray-500 font-medium">
            {organization.name} のライブ配信は現在準備中です
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* メインプレーヤー */}
      {selectedVideo && (
        <div className="card">
          <VideoPlayer
            src={selectedVideo.url}
            type={selectedVideo.type}
            title={selectedVideo.title}
            isLive={selectedVideo.isLive}
            poster={selectedVideo.thumbnail}
          />
          <div className="mt-4 p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-bold text-gray-800">{selectedVideo.title}</h3>
                <p className="text-sm text-gray-600 mt-1">
                  {selectedVideo.track} - {selectedVideo.raceNumber}
                </p>
              </div>
              {selectedVideo.isLive && (
                <div className="flex items-center space-x-2">
                  <span className="relative flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                  </span>
                  <span className="text-sm font-bold text-red-600">LIVE配信中</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ライブ配信一覧 */}
      <div className="card">
        <h2 className="section-title">
          {organization.logo} ライブ配信
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {currentStreams.map((stream) => (
            <button
              key={stream.id}
              onClick={() => setSelectedVideo(stream)}
              className={`text-left transition-all hover:scale-105 ${
                selectedVideo?.id === stream.id
                  ? 'ring-2 ring-jra-green'
                  : ''
              }`}
            >
              <div className="relative rounded-lg overflow-hidden bg-gray-900 group">
                <img
                  src={stream.thumbnail}
                  alt={stream.title}
                  className="w-full aspect-video object-cover group-hover:opacity-75 transition-opacity"
                />
                {stream.isLive && (
                  <div className="absolute top-3 left-3">
                    <span className="bg-red-600 text-white text-xs px-3 py-1 rounded-full font-bold animate-pulse flex items-center space-x-1">
                      <span className="w-2 h-2 bg-white rounded-full"></span>
                      <span>LIVE</span>
                    </span>
                  </div>
                )}
                <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                  <div className="bg-white/90 rounded-full p-4">
                    <svg
                      className="w-8 h-8 text-jra-green"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z" />
                    </svg>
                  </div>
                </div>
              </div>
              <div className="mt-2 p-3 bg-gray-50 rounded-lg">
                <h3 className="font-bold text-gray-800 text-sm mb-1 line-clamp-2">
                  {stream.title}
                </h3>
                <div className="flex items-center justify-between text-xs text-gray-600">
                  <span>{stream.track}</span>
                  <span className="font-semibold">{stream.raceNumber}</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* 使い方 */}
      <div className="card bg-blue-50/50 border-l-4 border-blue-500">
        <h3 className="font-bold text-gray-800 mb-3 flex items-center">
          <span className="mr-2">💡</span>
          ライブ配信について
        </h3>
        <ul className="text-sm text-gray-700 space-y-2">
          <li className="flex items-start">
            <span className="text-blue-600 mr-2">•</span>
            <span>
              サムネイルをクリックすると、上部のプレーヤーで動画が再生されます
            </span>
          </li>
          <li className="flex items-start">
            <span className="text-blue-600 mr-2">•</span>
            <span>
              <span className="bg-red-600 text-white text-xs px-2 py-0.5 rounded-full font-bold">
                LIVE
              </span>{' '}
              マークが付いている配信はリアルタイムで視聴できます
            </span>
          </li>
          <li className="flex items-start">
            <span className="text-blue-600 mr-2">•</span>
            <span>プレーヤーの操作は動画コントロールから行えます</span>
          </li>
        </ul>
      </div>
    </div>
  )
}

export default LiveRaceSection
