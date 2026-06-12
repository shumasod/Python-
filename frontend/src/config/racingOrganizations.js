/**
 * 競馬団体の設定
 */

export const racingOrganizations = {
  jra: {
    id: 'jra',
    name: 'JRA',
    fullName: '日本中央競馬会',
    description: 'Japan Racing Association - 中央競馬',
    colors: {
      primary: '#006937',      // JRAグリーン
      primaryLight: '#00a968',
      primaryDark: '#005028',
      secondary: '#ffffff',
      accent: '#f0f9ff',
    },
    logo: '🏇',
    website: 'https://www.jra.go.jp/',
  },

  nar: {
    id: 'nar',
    name: 'NAR',
    fullName: '地方競馬',
    description: '地方競馬全国協会 - 地方競馬',
    colors: {
      primary: '#e60012',      // 地方競馬レッド
      primaryLight: '#ff4d4d',
      primaryDark: '#b30000',
      secondary: '#ffffff',
      accent: '#fff5f5',
    },
    logo: '🐴',
    website: 'https://www.keiba.go.jp/',
  },

  hongkong: {
    id: 'hongkong',
    name: 'HKJC',
    fullName: '香港ジョッキークラブ',
    description: 'Hong Kong Jockey Club',
    colors: {
      primary: '#00539f',      // HKJCブルー
      primaryLight: '#0066cc',
      primaryDark: '#003d75',
      secondary: '#ffffff',
      accent: '#f0f7ff',
    },
    logo: '🏆',
    website: 'https://racing.hkjc.com/',
  },

  singapore: {
    id: 'singapore',
    name: 'STC',
    fullName: 'シンガポールターフクラブ',
    description: 'Singapore Turf Club',
    colors: {
      primary: '#8b0000',      // STCダークレッド
      primaryLight: '#b30000',
      primaryDark: '#660000',
      secondary: '#ffffff',
      accent: '#fff5f5',
    },
    logo: '🎯',
    website: 'https://www.turfclub.com.sg/',
  },

  australia: {
    id: 'australia',
    name: 'Racing Australia',
    fullName: 'オーストラリア競馬',
    description: 'Racing Australia',
    colors: {
      primary: '#006600',      // オーストラリアグリーン
      primaryLight: '#009900',
      primaryDark: '#004d00',
      secondary: '#ffcc00',
      accent: '#f5fff5',
    },
    logo: '🦘',
    website: 'https://www.racingaustralia.horse/',
  },

  uk: {
    id: 'uk',
    name: 'British Racing',
    fullName: 'イギリス競馬',
    description: 'British Horseracing Authority',
    colors: {
      primary: '#003366',      // ブリティッシュブルー
      primaryLight: '#004d99',
      primaryDark: '#002244',
      secondary: '#ffffff',
      accent: '#f0f5ff',
    },
    logo: '👑',
    website: 'https://www.britishhorseracing.com/',
  },

  usa: {
    id: 'usa',
    name: 'US Racing',
    fullName: 'アメリカ競馬',
    description: 'United States Racing',
    colors: {
      primary: '#002868',      // アメリカンブルー
      primaryLight: '#003d99',
      primaryDark: '#001a44',
      secondary: '#bf0a30',
      accent: '#f0f5ff',
    },
    logo: '🇺🇸',
    website: 'https://www.tjcis.com/',
  },

  france: {
    id: 'france',
    name: 'France Galop',
    fullName: 'フランス競馬',
    description: 'France Galop',
    colors: {
      primary: '#002395',      // フレンチブルー
      primaryLight: '#003db3',
      primaryDark: '#001a66',
      secondary: '#ffffff',
      accent: '#f0f3ff',
    },
    logo: '🥖',
    website: 'https://www.france-galop.com/',
  },

  dubai: {
    id: 'dubai',
    name: 'Dubai Racing',
    fullName: 'ドバイ競馬',
    description: 'Dubai Racing Club',
    colors: {
      primary: '#c9a961',      // ゴールド
      primaryLight: '#d4b876',
      primaryDark: '#b8964d',
      secondary: '#000000',
      accent: '#fffbf0',
    },
    logo: '🏜️',
    website: 'https://www.dubairacingclub.com/',
  },
}

/**
 * デフォルトの競馬団体
 */
export const defaultOrganization = 'jra'

/**
 * 競馬団体のリストを取得
 */
export const getOrganizationList = () => {
  return Object.values(racingOrganizations)
}

/**
 * IDから競馬団体を取得
 */
export const getOrganizationById = (id) => {
  return racingOrganizations[id] || racingOrganizations[defaultOrganization]
}
