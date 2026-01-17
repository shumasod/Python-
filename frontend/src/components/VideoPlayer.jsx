import { useEffect, useRef, useState } from 'react'

/**
 * リアルタイム動画プレーヤーコンポーネント
 * HLS、MP4、YouTube、Twitchなどに対応
 */
const VideoPlayer = ({
  src,
  type = 'auto',
  poster,
  title,
  isLive = false,
  autoplay = false,
  muted = false,
  controls = true,
}) => {
  const videoRef = useRef(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [error, setError] = useState(null)
  const [isLoading, setIsLoading] = useState(true)

  // 動画タイプを自動検出
  const detectVideoType = (url) => {
    if (!url) return 'unknown'

    if (url.includes('youtube.com') || url.includes('youtu.be')) {
      return 'youtube'
    }
    if (url.includes('twitch.tv')) {
      return 'twitch'
    }
    if (url.includes('.m3u8')) {
      return 'hls'
    }
    if (url.includes('.mp4') || url.includes('.webm')) {
      return 'native'
    }
    return 'unknown'
  }

  const videoType = type === 'auto' ? detectVideoType(src) : type

  // YouTube IDを抽出
  const getYouTubeId = (url) => {
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/
    const match = url.match(regExp)
    return match && match[2].length === 11 ? match[2] : null
  }

  // HLS動画の読み込み
  useEffect(() => {
    if (videoType === 'hls' && videoRef.current) {
      // HLS.jsの動的読み込み
      if (window.Hls && window.Hls.isSupported()) {
        const hls = new window.Hls({
          enableWorker: true,
          lowLatencyMode: isLive,
        })

        hls.loadSource(src)
        hls.attachMedia(videoRef.current)

        hls.on(window.Hls.Events.MANIFEST_PARSED, () => {
          setIsLoading(false)
          if (autoplay) {
            videoRef.current.play()
          }
        })

        hls.on(window.Hls.Events.ERROR, (event, data) => {
          if (data.fatal) {
            setError('動画の読み込みに失敗しました')
            setIsLoading(false)
          }
        })

        return () => {
          hls.destroy()
        }
      } else if (videoRef.current.canPlayType('application/vnd.apple.mpegurl')) {
        // Safari ネイティブHLS対応
        videoRef.current.src = src
        setIsLoading(false)
      } else {
        setError('このブラウザはHLS再生に対応していません')
        setIsLoading(false)
      }
    } else if (videoType === 'native' && videoRef.current) {
      setIsLoading(false)
    }
  }, [src, videoType, isLive, autoplay])

  // 再生状態の管理
  const handlePlay = () => setIsPlaying(true)
  const handlePause = () => setIsPlaying(false)

  // YouTubeプレーヤー
  if (videoType === 'youtube') {
    const videoId = getYouTubeId(src)
    if (!videoId) {
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <p className="text-red-600">無効なYouTube URLです</p>
        </div>
      )
    }

    return (
      <div className="relative w-full" style={{ paddingBottom: '56.25%' }}>
        {title && (
          <div className="absolute top-0 left-0 right-0 bg-gradient-to-b from-black/70 to-transparent p-4 z-10">
            <h3 className="text-white font-bold flex items-center space-x-2">
              {isLive && (
                <span className="bg-red-600 text-white text-xs px-2 py-1 rounded-full animate-pulse">
                  ● LIVE
                </span>
              )}
              <span>{title}</span>
            </h3>
          </div>
        )}
        <iframe
          className="absolute top-0 left-0 w-full h-full rounded-lg"
          src={`https://www.youtube.com/embed/${videoId}?autoplay=${autoplay ? 1 : 0}&mute=${muted ? 1 : 0}`}
          title={title || 'YouTube video player'}
          frameBorder="0"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
        ></iframe>
      </div>
    )
  }

  // Twitchプレーヤー
  if (videoType === 'twitch') {
    const channel = src.split('twitch.tv/')[1]
    return (
      <div className="relative w-full" style={{ paddingBottom: '56.25%' }}>
        {title && (
          <div className="absolute top-0 left-0 right-0 bg-gradient-to-b from-black/70 to-transparent p-4 z-10">
            <h3 className="text-white font-bold flex items-center space-x-2">
              <span className="bg-purple-600 text-white text-xs px-2 py-1 rounded-full animate-pulse">
                ● LIVE
              </span>
              <span>{title}</span>
            </h3>
          </div>
        )}
        <iframe
          className="absolute top-0 left-0 w-full h-full rounded-lg"
          src={`https://player.twitch.tv/?channel=${channel}&parent=${window.location.hostname}`}
          frameBorder="0"
          allowFullScreen
          scrolling="no"
        ></iframe>
      </div>
    )
  }

  // エラー表示
  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-8 text-center">
        <div className="text-5xl mb-4">⚠️</div>
        <p className="text-red-600 font-semibold mb-2">動画エラー</p>
        <p className="text-red-500 text-sm">{error}</p>
      </div>
    )
  }

  // ネイティブビデオプレーヤー（HLS、MP4など）
  return (
    <div className="relative w-full bg-black rounded-lg overflow-hidden">
      {title && (
        <div className="absolute top-0 left-0 right-0 bg-gradient-to-b from-black/70 to-transparent p-4 z-10">
          <h3 className="text-white font-bold flex items-center space-x-2">
            {isLive && (
              <span className="bg-red-600 text-white text-xs px-2 py-1 rounded-full animate-pulse">
                ● LIVE
              </span>
            )}
            <span>{title}</span>
          </h3>
        </div>
      )}

      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-20">
          <div className="text-center">
            <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-white mb-4 mx-auto"></div>
            <p className="text-white">動画を読み込み中...</p>
          </div>
        </div>
      )}

      <video
        ref={videoRef}
        poster={poster}
        autoPlay={autoplay}
        muted={muted}
        controls={controls}
        playsInline
        onPlay={handlePlay}
        onPause={handlePause}
        onLoadedData={() => setIsLoading(false)}
        onError={(e) => {
          setError('動画の読み込みに失敗しました')
          setIsLoading(false)
        }}
        className="w-full"
        style={{ maxHeight: '70vh' }}
      >
        {videoType === 'native' && (
          <source src={src} type="video/mp4" />
        )}
        お使いのブラウザは動画タグをサポートしていません。
      </video>

      {!controls && (
        <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/70 to-transparent">
          <button
            onClick={() => {
              if (isPlaying) {
                videoRef.current.pause()
              } else {
                videoRef.current.play()
              }
            }}
            className="bg-white/20 hover:bg-white/30 text-white p-3 rounded-full transition-colors"
          >
            {isPlaying ? '⏸' : '▶'}
          </button>
        </div>
      )}
    </div>
  )
}

export default VideoPlayer
