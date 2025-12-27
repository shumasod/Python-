import { useState } from 'react'

const PredictionForm = ({ onSubmit, loading }) => {
  const [formData, setFormData] = useState({
    枠番: '',
    馬番: '',
    斤量: '',
    人気: '',
    単勝: '',
    馬体重: '',
    増減: '',
    性齢: '',
    騎手: '',
  })

  const [errors, setErrors] = useState({})

  // 性齢の選択肢
  const sexAgeOptions = [
    '牡2', '牡3', '牡4', '牡5', '牡6',
    '牝2', '牝3', '牝4', '牝5', '牝6',
    'セ3', 'セ4', 'セ5', 'セ6',
  ]

  // 騎手の選択肢（例）
  const jockeyOptions = [
    '川田将雅', '福永祐一', 'デムーロ', '武豊', '戸崎圭太',
    'ルメール', '横山武史', '松山弘平', '岩田望来', '坂井瑠星',
    'その他',
  ]

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: value
    }))
    // エラーをクリア
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: null
      }))
    }
  }

  const validateForm = () => {
    const newErrors = {}

    // 枠番のバリデーション
    if (!formData.枠番 || formData.枠番 < 1 || formData.枠番 > 8) {
      newErrors.枠番 = '枠番は1〜8の範囲で入力してください'
    }

    // 馬番のバリデーション
    if (!formData.馬番 || formData.馬番 < 1 || formData.馬番 > 18) {
      newErrors.馬番 = '馬番は1〜18の範囲で入力してください'
    }

    // 斤量のバリデーション
    if (!formData.斤量 || formData.斤量 < 40 || formData.斤量 > 65) {
      newErrors.斤量 = '斤量は40〜65kgの範囲で入力してください'
    }

    // 人気のバリデーション
    if (!formData.人気 || formData.人気 < 1 || formData.人気 > 18) {
      newErrors.人気 = '人気は1〜18の範囲で入力してください'
    }

    // 単勝のバリデーション
    if (!formData.単勝 || formData.単勝 < 1) {
      newErrors.単勝 = '単勝オッズは1.0以上で入力してください'
    }

    // 馬体重のバリデーション
    if (!formData.馬体重 || formData.馬体重 < 300 || formData.馬体重 > 600) {
      newErrors.馬体重 = '馬体重は300〜600kgの範囲で入力してください'
    }

    // 増減のバリデーション
    if (formData.増減 === '' || formData.増減 < -50 || formData.増減 > 50) {
      newErrors.増減 = '増減は-50〜50kgの範囲で入力してください'
    }

    // 性齢のバリデーション
    if (!formData.性齢) {
      newErrors.性齢 = '性齢を選択してください'
    }

    // 騎手のバリデーション
    if (!formData.騎手) {
      newErrors.騎手 = '騎手を選択してください'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = (e) => {
    e.preventDefault()

    if (validateForm()) {
      // 数値型に変換して送信
      const submitData = {
        枠番: parseInt(formData.枠番),
        馬番: parseInt(formData.馬番),
        斤量: parseFloat(formData.斤量),
        人気: parseInt(formData.人気),
        単勝: parseFloat(formData.単勝),
        馬体重: parseInt(formData.馬体重),
        増減: parseInt(formData.増減),
        性齢: formData.性齢,
        騎手: formData.騎手,
      }
      onSubmit(submitData)
    }
  }

  return (
    <div className="card">
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* 枠番 */}
        <div>
          <label className="label">枠番 (1-8)</label>
          <input
            type="number"
            name="枠番"
            value={formData.枠番}
            onChange={handleChange}
            className={`input ${errors.枠番 ? 'border-red-500' : ''}`}
            placeholder="例: 3"
            min="1"
            max="8"
          />
          {errors.枠番 && (
            <p className="text-red-500 text-sm mt-1">{errors.枠番}</p>
          )}
        </div>

        {/* 馬番 */}
        <div>
          <label className="label">馬番 (1-18)</label>
          <input
            type="number"
            name="馬番"
            value={formData.馬番}
            onChange={handleChange}
            className={`input ${errors.馬番 ? 'border-red-500' : ''}`}
            placeholder="例: 5"
            min="1"
            max="18"
          />
          {errors.馬番 && (
            <p className="text-red-500 text-sm mt-1">{errors.馬番}</p>
          )}
        </div>

        {/* 斤量 */}
        <div>
          <label className="label">斤量 (kg)</label>
          <input
            type="number"
            name="斤量"
            value={formData.斤量}
            onChange={handleChange}
            className={`input ${errors.斤量 ? 'border-red-500' : ''}`}
            placeholder="例: 55.0"
            min="40"
            max="65"
            step="0.5"
          />
          {errors.斤量 && (
            <p className="text-red-500 text-sm mt-1">{errors.斤量}</p>
          )}
        </div>

        {/* 人気 */}
        <div>
          <label className="label">人気順位 (1-18)</label>
          <input
            type="number"
            name="人気"
            value={formData.人気}
            onChange={handleChange}
            className={`input ${errors.人気 ? 'border-red-500' : ''}`}
            placeholder="例: 2"
            min="1"
            max="18"
          />
          {errors.人気 && (
            <p className="text-red-500 text-sm mt-1">{errors.人気}</p>
          )}
        </div>

        {/* 単勝オッズ */}
        <div>
          <label className="label">単勝オッズ</label>
          <input
            type="number"
            name="単勝"
            value={formData.単勝}
            onChange={handleChange}
            className={`input ${errors.単勝 ? 'border-red-500' : ''}`}
            placeholder="例: 3.5"
            min="1.0"
            step="0.1"
          />
          {errors.単勝 && (
            <p className="text-red-500 text-sm mt-1">{errors.単勝}</p>
          )}
        </div>

        {/* 馬体重 */}
        <div>
          <label className="label">馬体重 (kg)</label>
          <input
            type="number"
            name="馬体重"
            value={formData.馬体重}
            onChange={handleChange}
            className={`input ${errors.馬体重 ? 'border-red-500' : ''}`}
            placeholder="例: 480"
            min="300"
            max="600"
          />
          {errors.馬体重 && (
            <p className="text-red-500 text-sm mt-1">{errors.馬体重}</p>
          )}
        </div>

        {/* 増減 */}
        <div>
          <label className="label">馬体重増減 (kg)</label>
          <input
            type="number"
            name="増減"
            value={formData.増減}
            onChange={handleChange}
            className={`input ${errors.増減 ? 'border-red-500' : ''}`}
            placeholder="例: 2 (増加の場合は正、減少の場合は負)"
            min="-50"
            max="50"
          />
          {errors.増減 && (
            <p className="text-red-500 text-sm mt-1">{errors.増減}</p>
          )}
        </div>

        {/* 性齢 */}
        <div>
          <label className="label">性齢</label>
          <select
            name="性齢"
            value={formData.性齢}
            onChange={handleChange}
            className={`input ${errors.性齢 ? 'border-red-500' : ''}`}
          >
            <option value="">選択してください</option>
            {sexAgeOptions.map(option => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          {errors.性齢 && (
            <p className="text-red-500 text-sm mt-1">{errors.性齢}</p>
          )}
        </div>

        {/* 騎手 */}
        <div>
          <label className="label">騎手</label>
          <select
            name="騎手"
            value={formData.騎手}
            onChange={handleChange}
            className={`input ${errors.騎手 ? 'border-red-500' : ''}`}
          >
            <option value="">選択してください</option>
            {jockeyOptions.map(option => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          {errors.騎手 && (
            <p className="text-red-500 text-sm mt-1">{errors.騎手}</p>
          )}
        </div>

        {/* 送信ボタン */}
        <button
          type="submit"
          disabled={loading}
          className={`w-full btn btn-primary py-3 text-lg font-bold ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? (
            <span className="flex items-center justify-center">
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              予測中...
            </span>
          ) : (
            '🎯 予測を実行'
          )}
        </button>
      </form>
    </div>
  )
}

export default PredictionForm
