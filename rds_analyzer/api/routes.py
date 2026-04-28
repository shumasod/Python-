"""
FastAPI ルーター定義

設計意図:
- RESTful API エンドポイントを定義
- 依存性注入パターン（Depends）でサービス層を分離
- 非同期処理（async/await）でレスポンス時間 5 秒以内を達成
- エラーハンドリングとログを統一

エンドポイント:
- GET /health              ヘルスチェック
- GET /rds/summary         全インスタンス概要
- POST /rds                インスタンス登録
- GET /rds/{id}/analysis   詳細分析
- GET /rds/{id}/recommendations 改善提案
- POST /rds/{id}/metrics   メトリクス手動入力
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .schemas import (
    AnalysisResponse,
    CostSummaryResponse,
    HealthCheckResponse,
    InstanceSummaryItem,
    MetricsInputRequest,
    PerformanceSummaryResponse,
    RDSInstanceRequest,
    RDSSummaryResponse,
    RecommendationItem,
    RecommendationResponse,
)
from ..analyzers.cost_analyzer import CostAnalyzer
from ..analyzers.performance_analyzer import PerformanceAnalyzer
from ..analyzers.recommendation_engine import RecommendationEngine
from ..analyzers.ml_anomaly_detector import MLAnomalyDetector, CostForecast
from ..models.costs import CostBreakdown
from ..models.metrics import (
    MetricsHistory,
    MetricsStatistics,
    PerformanceAnalysisResult,
)
from ..models.rds import EngineType, RDSInstance, StorageType
from ..notifications.slack_notifier import SlackNotifier
from rds_analyzer import __version__

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================
# インメモリストア（本番では DynamoDB / PostgreSQL を使用）
# ============================================================
_instance_store: dict[str, RDSInstance] = {}
_metrics_store: dict[str, MetricsHistory] = {}
# 月次コスト履歴 {instance_id: [(YYYY-MM, cost_usd), ...]}
_cost_history_store: dict[str, list[tuple[str, float]]] = {}


# ============================================================
# 依存性注入
# ============================================================

def get_cost_analyzer() -> CostAnalyzer:
    return CostAnalyzer()


def get_performance_analyzer() -> PerformanceAnalyzer:
    return PerformanceAnalyzer()


def get_recommendation_engine() -> RecommendationEngine:
    return RecommendationEngine()


def get_ml_detector() -> MLAnomalyDetector:
    return MLAnomalyDetector()


def get_slack_notifier() -> SlackNotifier:
    return SlackNotifier()


def get_instance_or_404(instance_id: str) -> RDSInstance:
    """インスタンスを取得（存在しない場合は 404）"""
    instance = _instance_store.get(instance_id)
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"インスタンス '{instance_id}' が見つかりません",
        )
    return instance


def get_metrics_or_404(instance_id: str) -> MetricsHistory:
    """メトリクスを取得（存在しない場合は 404）"""
    metrics = _metrics_store.get(instance_id)
    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"インスタンス '{instance_id}' のメトリクスデータがありません。先にメトリクスを投入してください。",
        )
    return metrics


# ============================================================
# ルート定義
# ============================================================

@router.get("/health", response_model=HealthCheckResponse, tags=["system"])
async def health_check() -> HealthCheckResponse:
    """サービスのヘルスチェック"""
    return HealthCheckResponse(version=__version__)


@router.post(
    "/rds",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    tags=["instances"],
    summary="RDS インスタンスを登録",
)
async def register_instance(request: RDSInstanceRequest) -> dict:
    """
    RDS インスタンス設定を登録する

    CloudWatch / Cost Explorer から自動収集できない設定情報を手動で登録
    """
    try:
        engine = EngineType(request.engine)
        storage_type = StorageType(request.storage_type)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    instance = RDSInstance(
        instance_id=request.instance_id,
        engine=engine,
        engine_version=request.engine_version,
        instance_class=request.instance_class,
        region=request.region,
        multi_az=request.multi_az,
        storage_type=storage_type,
        allocated_storage_gb=request.allocated_storage_gb,
        provisioned_iops=request.provisioned_iops,
        read_replica_count=request.read_replica_count,
        backup_retention_days=request.backup_retention_days,
        snapshot_storage_gb=request.snapshot_storage_gb,
        tags=request.tags,
    )

    _instance_store[request.instance_id] = instance
    logger.info("インスタンス登録: %s (%s)", instance.instance_id, instance.engine)

    return {"message": "登録しました", "instance_id": instance.instance_id}


@router.post(
    "/rds/{instance_id}/metrics",
    response_model=dict,
    tags=["metrics"],
    summary="メトリクスデータを手動投入",
)
async def submit_metrics(
    instance_id: str,
    request: MetricsInputRequest,
) -> dict:
    """
    メトリクスデータを手動投入する

    CloudWatch API にアクセスできない開発環境や
    テスト用にメトリクスを直接投入できる
    """
    # インスタンスの存在確認
    get_instance_or_404(instance_id)

    now = datetime.utcnow()
    period_start = now - timedelta(hours=request.period_hours)

    def make_stats(avg: float, max_val: float, min_val: Optional[float] = None) -> MetricsStatistics:
        """統計オブジェクトを生成するヘルパー"""
        return MetricsStatistics(
            avg=avg,
            max=max_val,
            min=min_val if min_val is not None else avg * 0.5,
            p95=max_val * 0.95,
            p99=max_val * 0.99,
            sample_count=request.period_hours * 12,  # 5分間隔
        )

    gb_to_bytes = 1024 ** 3

    metrics = MetricsHistory(
        instance_id=instance_id,
        period_start=period_start,
        period_end=now,
        cpu_utilization=make_stats(request.cpu_avg_pct, request.cpu_max_pct),
        freeable_memory_bytes=MetricsStatistics(
            avg=request.freeable_memory_avg_gb * gb_to_bytes,
            max=request.freeable_memory_avg_gb * gb_to_bytes * 1.2,
            min=request.freeable_memory_min_gb * gb_to_bytes,
            p95=request.freeable_memory_min_gb * gb_to_bytes * 1.1,
            p99=request.freeable_memory_min_gb * gb_to_bytes,
            sample_count=request.period_hours * 12,
        ),
        read_iops=make_stats(request.read_iops_avg, request.read_iops_max),
        write_iops=make_stats(request.write_iops_avg, request.write_iops_max),
        read_latency_ms=make_stats(request.read_latency_avg_ms, request.read_latency_avg_ms * 2),
        write_latency_ms=make_stats(request.write_latency_avg_ms, request.write_latency_avg_ms * 2),
        disk_queue_depth=make_stats(request.disk_queue_depth_avg, request.disk_queue_depth_avg * 3),
        database_connections=make_stats(request.connections_avg, request.connections_max),
        network_receive_bps=make_stats(1_000_000, 5_000_000),   # デフォルト値
        network_transmit_bps=make_stats(1_000_000, 5_000_000),
        free_storage_bytes=make_stats(
            request.free_storage_gb * gb_to_bytes,
            request.free_storage_gb * gb_to_bytes * 1.1,
        ),
    )

    _metrics_store[instance_id] = metrics
    logger.info("メトリクス投入: %s (期間: %dh)", instance_id, request.period_hours)

    return {"message": "メトリクスを登録しました", "instance_id": instance_id}


@router.get(
    "/rds/summary",
    response_model=RDSSummaryResponse,
    tags=["analysis"],
    summary="全インスタンスの概要を取得",
)
async def get_rds_summary(
    cost_analyzer: CostAnalyzer = Depends(get_cost_analyzer),
    perf_analyzer: PerformanceAnalyzer = Depends(get_performance_analyzer),
    rec_engine: RecommendationEngine = Depends(get_recommendation_engine),
) -> RDSSummaryResponse:
    """
    登録済み全 RDS インスタンスのコストとスコアの概要を返す

    - 月次合計コスト
    - 推定削減可能額
    - 各インスタンスのスコアサマリー
    """
    if not _instance_store:
        return RDSSummaryResponse(
            total_instances=0,
            total_monthly_cost_usd=0.0,
            total_potential_savings_usd=0.0,
            instances=[],
        )

    items: list[InstanceSummaryItem] = []
    total_cost = 0.0
    total_savings = 0.0

    for instance_id, instance in _instance_store.items():
        # コスト計算
        breakdown, _ = cost_analyzer.calculate_monthly_cost(instance)
        total_cost += breakdown.total_cost_usd

        # スコア計算
        health_score = 75  # メトリクスなしのデフォルト
        cost_eff_score = 75

        metrics = _metrics_store.get(instance_id)
        top_recommendation = None

        if metrics:
            perf_result = perf_analyzer.analyze(instance, metrics)
            health_score = perf_result.health_score

            eff_score = cost_analyzer.calculate_efficiency_score(
                instance=instance,
                breakdown=breakdown,
                avg_cpu_pct=metrics.cpu_utilization.avg,
                avg_iops_used=metrics.avg_total_iops,
                storage_used_gb=(
                    instance.allocated_storage_gb
                    - metrics.free_storage_bytes.avg / (1024 ** 3)
                ),
            )
            cost_eff_score = eff_score.score

            # 上位の提案を取得
            recs = rec_engine.generate_recommendations(instance, perf_result, breakdown)
            if recs:
                top_recommendation = recs[0].title
                total_savings += max(0, recs[0].estimated_monthly_savings_usd)

        items.append(
            InstanceSummaryItem(
                instance_id=instance_id,
                engine=instance.engine.value,
                instance_class=instance.instance_class,
                region=instance.region,
                monthly_cost_usd=round(breakdown.total_cost_usd, 2),
                cost_efficiency_score=cost_eff_score,
                health_score=health_score,
                top_recommendation=top_recommendation,
            )
        )

    return RDSSummaryResponse(
        total_instances=len(_instance_store),
        total_monthly_cost_usd=round(total_cost, 2),
        total_potential_savings_usd=round(total_savings, 2),
        instances=items,
    )


@router.get(
    "/rds/{instance_id}/analysis",
    response_model=AnalysisResponse,
    tags=["analysis"],
    summary="インスタンスの詳細分析を取得",
)
async def get_instance_analysis(
    instance_id: str,
    analysis_period_hours: int = Query(default=24, ge=1, le=720),
    data_transfer_gb: float = Query(default=0.0, ge=0),
    cost_analyzer: CostAnalyzer = Depends(get_cost_analyzer),
    perf_analyzer: PerformanceAnalyzer = Depends(get_performance_analyzer),
) -> AnalysisResponse:
    """
    特定インスタンスのコスト + パフォーマンス詳細分析を返す

    - コスト内訳（コンピュート/ストレージ/IOPS/転送）
    - パフォーマンス各指標の状態
    - 総合スコア
    """
    instance = get_instance_or_404(instance_id)
    metrics = get_metrics_or_404(instance_id)

    # コスト分析
    breakdown, _ = cost_analyzer.calculate_monthly_cost(
        instance, data_transfer_gb=data_transfer_gb
    )

    # ストレージ使用量
    storage_used_gb = (
        instance.allocated_storage_gb
        - metrics.free_storage_bytes.avg / (1024 ** 3)
    )

    eff_score = cost_analyzer.calculate_efficiency_score(
        instance=instance,
        breakdown=breakdown,
        avg_cpu_pct=metrics.cpu_utilization.avg,
        avg_iops_used=metrics.avg_total_iops,
        storage_used_gb=storage_used_gb,
    )

    # パフォーマンス分析
    perf_result = perf_analyzer.analyze(instance, metrics)

    # 月次コストの前月比（サンプルとして 10% 増加を仮定）
    from datetime import date
    current_month = date.today().strftime("%Y-%m")

    cost_response = CostSummaryResponse(
        instance_id=instance_id,
        month=current_month,
        total_cost_usd=round(breakdown.total_cost_usd, 2),
        breakdown={
            "compute": round(breakdown.compute_cost_usd + breakdown.replica_compute_cost_usd, 2),
            "storage": round(breakdown.storage_cost_usd, 2),
            "iops": round(breakdown.iops_cost_usd, 2),
            "transfer": round(breakdown.transfer_cost_usd, 2),
            "backup": round(breakdown.backup_cost_usd, 2),
        },
        cost_efficiency_score=eff_score.score,
        grade=eff_score.grade,
        potential_savings_usd=round(
            cost_analyzer.estimate_gp3_savings(instance), 2
        ),
    )

    perf_response = PerformanceSummaryResponse(
        instance_id=instance_id,
        health_score=perf_result.health_score,
        status_summary=_build_status_summary(perf_result),
        bottlenecks=perf_result.critical_issues,
        cpu_avg_pct=round(perf_result.cpu_avg_pct, 1),
        memory_free_gb=round(perf_result.freeable_memory_avg_gb, 2),
        avg_total_iops=round(perf_result.avg_total_iops, 0),
        avg_connections=round(perf_result.avg_connections, 0),
    )

    warnings = []
    if perf_result.storage_utilization_pct >= 80:
        warnings.append(f"ストレージ使用率が {perf_result.storage_utilization_pct:.0f}% に達しています")
    if not instance.multi_az:
        warnings.append("シングルAZ構成です。本番環境ではマルチAZを推奨します")

    return AnalysisResponse(
        instance_id=instance_id,
        analyzed_at=datetime.utcnow(),
        cost=cost_response,
        performance=perf_response,
        analysis_period_hours=analysis_period_hours,
        warnings=warnings,
    )


@router.get(
    "/rds/{instance_id}/recommendations",
    response_model=RecommendationResponse,
    tags=["recommendations"],
    summary="インスタンスの改善提案を取得",
)
async def get_recommendations(
    instance_id: str,
    data_transfer_gb: float = Query(default=0.0, ge=0),
    cost_analyzer: CostAnalyzer = Depends(get_cost_analyzer),
    perf_analyzer: PerformanceAnalyzer = Depends(get_performance_analyzer),
    rec_engine: RecommendationEngine = Depends(get_recommendation_engine),
) -> RecommendationResponse:
    """
    改善提案リストを返す

    優先度（CRITICAL > HIGH > MEDIUM > LOW）順に、
    コスト削減・パフォーマンス改善の提案を返す
    """
    instance = get_instance_or_404(instance_id)
    metrics = get_metrics_or_404(instance_id)

    breakdown, _ = cost_analyzer.calculate_monthly_cost(
        instance, data_transfer_gb=data_transfer_gb
    )
    perf_result = perf_analyzer.analyze(instance, metrics)
    recommendations = rec_engine.generate_recommendations(instance, perf_result, breakdown)

    total_savings = sum(
        max(0, r.estimated_monthly_savings_usd) for r in recommendations
    )

    rec_items = [
        RecommendationItem(
            id=r.recommendation_id,
            type=r.type.value,
            priority=r.priority.value,
            title=r.title,
            description=r.description,
            current_config=r.current_config,
            recommended_config=r.recommended_config,
            estimated_monthly_savings_usd=round(r.estimated_monthly_savings_usd, 2),
            estimated_performance_improvement_pct=r.estimated_performance_improvement_pct,
            implementation_complexity=r.implementation_complexity,
            action_steps=r.action_steps,
            impact_summary=r.impact_summary,
        )
        for r in recommendations
    ]

    return RecommendationResponse(
        instance_id=instance_id,
        generated_at=datetime.utcnow(),
        total_recommendations=len(recommendations),
        total_potential_savings_usd=round(total_savings, 2),
        recommendations=rec_items,
    )


# ============================================================
# ヘルパー関数
# ============================================================

def _build_status_summary(perf: PerformanceAnalysisResult) -> str:
    """パフォーマンス分析結果から概要文を生成"""
    if perf.health_score >= 90:
        return "パフォーマンスは良好です"
    elif perf.health_score >= 70:
        return "パフォーマンスは概ね良好ですが、一部改善の余地があります"
    elif perf.health_score >= 50:
        return "複数のパフォーマンス問題を検知しています"
    else:
        return "重大なパフォーマンス問題を検知しています。即時対応を推奨します"


# ============================================================
# 拡張エンドポイント（ML 異常検知 / コスト予測 / レポート / Slack）
# ============================================================

@router.post(
    "/rds/{instance_id}/cost-history",
    response_model=dict,
    tags=["analysis"],
    summary="月次コスト履歴を登録（予測用）",
)
async def add_cost_history(
    instance_id: str,
    history: list[dict],
) -> dict:
    """
    月次コスト履歴を登録する（コスト予測 API で使用）

    body: [{"month": "2024-01", "cost_usd": 450.0}, ...]
    """
    get_instance_or_404(instance_id)
    entries = [(item["month"], float(item["cost_usd"])) for item in history]
    _cost_history_store[instance_id] = sorted(entries, key=lambda x: x[0])
    return {"message": f"{len(entries)} 件の履歴を登録しました"}


@router.get(
    "/rds/{instance_id}/forecast",
    response_model=dict,
    tags=["analysis"],
    summary="コスト予測（ML）",
)
async def get_cost_forecast(
    instance_id: str,
    months: int = Query(default=3, ge=1, le=12),
    ml_detector: MLAnomalyDetector = Depends(get_ml_detector),
) -> dict:
    """
    過去の月次コスト履歴から将来コストを予測する（線形回帰ベース）

    先に POST /rds/{id}/cost-history でデータを登録してください
    """
    get_instance_or_404(instance_id)
    history = _cost_history_store.get(instance_id, [])

    if len(history) < 3:
        raise HTTPException(
            status_code=400,
            detail="予測には 3 ヶ月以上のコスト履歴が必要です",
        )

    forecasts = ml_detector.forecast_monthly_costs(history, forecast_months=months)
    trend_info = ml_detector.calculate_cost_trend(history)

    return {
        "instance_id": instance_id,
        "history_months": len(history),
        "trend": trend_info,
        "forecasts": [
            {
                "month": f.month,
                "predicted_cost_usd": f.predicted_cost_usd,
                "lower_bound_usd": f.lower_bound_usd,
                "upper_bound_usd": f.upper_bound_usd,
                "confidence_pct": f.confidence_pct,
                "trend": f.trend,
            }
            for f in forecasts
        ],
    }


@router.get(
    "/rds/{instance_id}/report",
    response_model=dict,
    tags=["reports"],
    summary="Markdown レポート生成",
)
async def generate_report(
    instance_id: str,
    data_transfer_gb: float = Query(default=0.0, ge=0),
    cost_analyzer: CostAnalyzer = Depends(get_cost_analyzer),
    perf_analyzer: PerformanceAnalyzer = Depends(get_performance_analyzer),
    rec_engine: RecommendationEngine = Depends(get_recommendation_engine),
) -> dict:
    """
    インスタンスの分析結果を Markdown レポートとして返す
    """
    instance = get_instance_or_404(instance_id)
    metrics = get_metrics_or_404(instance_id)

    breakdown, _ = cost_analyzer.calculate_monthly_cost(instance, data_transfer_gb=data_transfer_gb)
    storage_used_gb = (
        instance.allocated_storage_gb
        - metrics.free_storage_bytes.avg / (1024 ** 3)
    )
    cost_score = cost_analyzer.calculate_efficiency_score(
        instance=instance,
        breakdown=breakdown,
        avg_cpu_pct=metrics.cpu_utilization.avg,
        avg_iops_used=metrics.avg_total_iops,
        storage_used_gb=storage_used_gb,
    )
    perf_result = perf_analyzer.analyze(instance, metrics)
    recommendations = rec_engine.generate_recommendations(instance, perf_result, breakdown)

    from ..report_generator import ReportGenerator
    gen = ReportGenerator()
    markdown = gen.generate(instance, breakdown, cost_score, perf_result, recommendations)

    return {
        "instance_id": instance_id,
        "generated_at": datetime.utcnow().isoformat(),
        "markdown": markdown,
    }


@router.post(
    "/rds/{instance_id}/notify",
    response_model=dict,
    tags=["notifications"],
    summary="Slack へ分析結果を通知",
)
async def notify_slack(
    instance_id: str,
    data_transfer_gb: float = Query(default=0.0, ge=0),
    cost_analyzer: CostAnalyzer = Depends(get_cost_analyzer),
    perf_analyzer: PerformanceAnalyzer = Depends(get_performance_analyzer),
    rec_engine: RecommendationEngine = Depends(get_recommendation_engine),
    notifier: SlackNotifier = Depends(get_slack_notifier),
) -> dict:
    """
    インスタンスの分析結果を Slack に通知する

    環境変数 SLACK_WEBHOOK_URL が設定されている必要があります
    """
    if not notifier.is_configured:
        raise HTTPException(
            status_code=400,
            detail="SLACK_WEBHOOK_URL が設定されていません",
        )

    instance = get_instance_or_404(instance_id)
    metrics = get_metrics_or_404(instance_id)

    breakdown, _ = cost_analyzer.calculate_monthly_cost(instance, data_transfer_gb=data_transfer_gb)
    perf_result = perf_analyzer.analyze(instance, metrics)
    recommendations = rec_engine.generate_recommendations(instance, perf_result, breakdown)
    total_savings = sum(max(0, r.estimated_monthly_savings_usd) for r in recommendations)

    sent = []
    # パフォーマンスアラート
    if notifier.notify_performance_alert(instance_id, perf_result, instance.region):
        sent.append("performance_alert")
    # 改善提案
    if notifier.notify_recommendations(instance_id, recommendations, total_savings):
        sent.append("recommendations")

    return {
        "instance_id": instance_id,
        "notifications_sent": sent,
        "total": len(sent),
    }
