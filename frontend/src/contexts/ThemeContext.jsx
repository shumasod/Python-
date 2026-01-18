import { createContext, useContext, useState, useEffect } from 'react'
import { getOrganizationById, defaultOrganization } from '../config/racingOrganizations'

const ThemeContext = createContext()

export const useTheme = () => {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}

export const ThemeProvider = ({ children }) => {
  const [organizationId, setOrganizationId] = useState(() => {
    // ローカルストレージから保存された設定を読み込み
    return localStorage.getItem('selectedOrganization') || defaultOrganization
  })

  const organization = getOrganizationById(organizationId)

  // 競馬団体を変更
  const changeOrganization = (newOrgId) => {
    setOrganizationId(newOrgId)
    localStorage.setItem('selectedOrganization', newOrgId)
  }

  // CSS変数を更新してテーマカラーを適用
  useEffect(() => {
    const root = document.documentElement
    root.style.setProperty('--color-primary', organization.colors.primary)
    root.style.setProperty('--color-primary-light', organization.colors.primaryLight)
    root.style.setProperty('--color-primary-dark', organization.colors.primaryDark)
    root.style.setProperty('--color-secondary', organization.colors.secondary)
    root.style.setProperty('--color-accent', organization.colors.accent)
  }, [organization])

  const value = {
    organization,
    organizationId,
    changeOrganization,
  }

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
