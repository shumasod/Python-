-- ============================================================
-- ローカル開発用 PostgreSQL 初期スキーマ
-- ============================================================

-- レース結果テーブル
CREATE TABLE IF NOT EXISTS race_results (
    id          SERIAL PRIMARY KEY,
    race_date   DATE NOT NULL,
    jyo_code    CHAR(2) NOT NULL,
    race_no     SMALLINT NOT NULL,
    rank        SMALLINT NOT NULL,
    boat_number SMALLINT NOT NULL,
    racer_no    VARCHAR(10),
    racer_name  VARCHAR(50),
    time        VARCHAR(10),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_race_results_date ON race_results(race_date);
CREATE INDEX IF NOT EXISTS idx_race_results_jyo  ON race_results(jyo_code, race_date);

-- 選手マスタ
CREATE TABLE IF NOT EXISTS racers (
    racer_no    VARCHAR(10) PRIMARY KEY,
    racer_name  VARCHAR(50),
    rank        CHAR(2),
    win_rate    NUMERIC(5,2),
    rate_2      NUMERIC(5,2),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 予測ログ（APIリクエスト記録）
CREATE TABLE IF NOT EXISTS prediction_logs (
    id              SERIAL PRIMARY KEY,
    race_id         VARCHAR(50),
    request_body    JSONB,
    response_body   JSONB,
    latency_ms      INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pred_logs_created ON prediction_logs(created_at);
