import { useState } from 'react'
import { useTheme } from '../contexts/ThemeContext'
import { getOrganizationList } from '../config/racingOrganizations'

const OrganizationSelector = () => {
  const { organization, changeOrganization } = useTheme()
  const [isOpen, setIsOpen] = useState(false)
  const organizations = getOrganizationList()

  const handleSelect = (orgId) => {
    changeOrganization(orgId)
    setIsOpen(false)
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-2 bg-white/10 hover:bg-white/20 px-4 py-2 rounded-lg transition-colors"
      >
        <span className="text-2xl">{organization.logo}</span>
        <div className="text-left hidden sm:block">
          <div className="text-sm font-bold">{organization.name}</div>
          <div className="text-xs opacity-90">{organization.fullName}</div>
        </div>
        <svg
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <>
          {/* オーバーレイ */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />

          {/* ドロップダウンメニュー */}
          <div className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-2xl z-20 border border-gray-200 max-h-96 overflow-y-auto">
            <div className="p-3 border-b border-gray-200 bg-gray-50">
              <h3 className="text-sm font-bold text-gray-700">競馬団体を選択</h3>
            </div>

            <div className="py-2">
              {organizations.map((org) => (
                <button
                  key={org.id}
                  onClick={() => handleSelect(org.id)}
                  className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors flex items-center space-x-3 ${
                    organization.id === org.id ? 'bg-gray-100' : ''
                  }`}
                >
                  <span className="text-3xl">{org.logo}</span>
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-gray-800">{org.name}</span>
                      {organization.id === org.id && (
                        <span className="text-green-600">✓</span>
                      )}
                    </div>
                    <div className="text-sm text-gray-600">{org.fullName}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{org.description}</div>
                  </div>
                  <div
                    className="w-4 h-4 rounded-full"
                    style={{ backgroundColor: org.colors.primary }}
                  />
                </button>
              ))}
            </div>

            <div className="p-3 bg-gray-50 border-t border-gray-200">
              <p className="text-xs text-gray-600 text-center">
                団体を切り替えるとテーマカラーが変更されます
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default OrganizationSelector
