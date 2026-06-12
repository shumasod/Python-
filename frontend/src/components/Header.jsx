import { useTheme } from '../contexts/ThemeContext'
import OrganizationSelector from './OrganizationSelector'

const Header = () => {
  const { organization } = useTheme()

  return (
    <header className="bg-jra-green text-white shadow-md">
      <div className="container mx-auto px-4 py-5">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center space-x-3 md:space-x-4">
            <div className="text-3xl md:text-4xl">{organization.logo}</div>
            <div>
              <h1 className="text-xl md:text-2xl lg:text-3xl font-bold tracking-tight">
                {organization.name} 競馬予測システム
              </h1>
              <p className="text-green-100 text-xs md:text-sm mt-0.5">
                AI機械学習による着順予測
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-3 md:space-x-6">
            <nav className="hidden lg:flex items-center space-x-4 text-sm">
              <a href="#" className="hover:text-green-200 transition-colors">ニュース</a>
              <a href="#" className="hover:text-green-200 transition-colors">レース情報</a>
            </nav>
            <OrganizationSelector />
          </div>
        </div>
      </div>
    </header>
  )
}

export default Header
