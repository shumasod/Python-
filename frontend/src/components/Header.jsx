const Header = () => {
  return (
    <header className="bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-lg">
      <div className="container mx-auto px-4 py-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="text-4xl">🏇</div>
            <div>
              <h1 className="text-3xl font-bold">
                JRA競馬予測システム
              </h1>
              <p className="text-blue-100 text-sm mt-1">
                AI機械学習による着順予測
              </p>
            </div>
          </div>
          <div className="hidden md:flex items-center space-x-2 bg-white/10 px-4 py-2 rounded-lg">
            <span className="text-sm">Powered by</span>
            <span className="font-bold">Random Forest ML</span>
          </div>
        </div>
      </div>
    </header>
  )
}

export default Header
