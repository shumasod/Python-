const Header = () => {
  return (
    <header className="bg-jra-green text-white shadow-md">
      <div className="container mx-auto px-4 py-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="text-4xl">🏇</div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
                JRA競馬予測システム
              </h1>
              <p className="text-green-100 text-xs md:text-sm mt-0.5">
                AI機械学習による着順予測
              </p>
            </div>
          </div>
          <nav className="hidden md:flex items-center space-x-6 text-sm">
            <a href="#" className="hover:text-green-200 transition-colors">ニュース</a>
            <a href="#" className="hover:text-green-200 transition-colors">レース情報</a>
            <button className="bg-white text-jra-green px-4 py-2 rounded hover:bg-green-50 transition-colors font-medium">
              検索
            </button>
          </nav>
        </div>
      </div>
    </header>
  )
}

export default Header
