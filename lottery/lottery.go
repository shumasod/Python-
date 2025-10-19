package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
)

var (
	ctx        = context.Background()
	redisClient *redis.Client
	jobQueue   = make(chan *LotteryJob, 10000)
	workerPool *WorkerPool
)

type Participant struct {
	ID   int    `json:"id"`
	Name string `json:"name"`
}

type LotteryRequest struct {
	Participants []Participant `json:"participants"`
	WinnerCount  int           `json:"winnerCount"`
}

type LotteryJob struct {
	JobID        string
	Participants []Participant
	WinnerCount  int
	Status       string
	Winners      []Participant
	CreatedAt    time.Time
	CompletedAt  time.Time
}

type LotteryResponse struct {
	JobID   string `json:"jobId"`
	Status  string `json:"status"`
	Message string `json:"message"`
}

type JobStatusResponse struct {
	JobID       string        `json:"jobId"`
	Status      string        `json:"status"`
	Winners     []Participant `json:"winners,omitempty"`
	CompletedAt string        `json:"completedAt,omitempty"`
}

type ErrorResponse struct {
	Error string `json:"error"`
}

// ワーカープール
type WorkerPool struct {
	workerCount int
	wg          sync.WaitGroup
	mu          sync.RWMutex
	jobs        map[string]*LotteryJob
}

func NewWorkerPool(count int) *WorkerPool {
	return &WorkerPool{
		workerCount: count,
		jobs:        make(map[string]*LotteryJob),
	}
}

func (wp *WorkerPool) Start() {
	for i := 0; i < wp.workerCount; i++ {
		wp.wg.Add(1)
		go wp.worker(i)
	}
	log.Printf("ワーカープール起動: %d workers", wp.workerCount)
}

func (wp *WorkerPool) worker(id int) {
	defer wp.wg.Done()
	log.Printf("Worker %d 起動", id)

	for job := range jobQueue {
		log.Printf("Worker %d: Job %s 処理開始", id, job.JobID)
		
		// 抽選処理実行
		job.Status = "processing"
		wp.updateJob(job)

		// シミュレーション: 大量データの処理
		time.Sleep(100 * time.Millisecond)

		// Fisher-Yatesシャッフル
		rand.Seed(time.Now().UnixNano() + int64(id))
		shuffled := make([]Participant, len(job.Participants))
		copy(shuffled, job.Participants)

		for i := len(shuffled) - 1; i > 0; i-- {
			j := rand.Intn(i + 1)
			shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
		}

		job.Winners = shuffled[:job.WinnerCount]
		job.Status = "completed"
		job.CompletedAt = time.Now()
		
		wp.updateJob(job)
		
		// Redisにキャッシュ
		if redisClient != nil {
			data, _ := json.Marshal(job)
			redisClient.Set(ctx, "job:"+job.JobID, data, 10*time.Minute)
		}

		log.Printf("Worker %d: Job %s 完了 (%d winners)", id, job.JobID, len(job.Winners))
	}
}

func (wp *WorkerPool) updateJob(job *LotteryJob) {
	wp.mu.Lock()
	defer wp.mu.Unlock()
	wp.jobs[job.JobID] = job
}

func (wp *WorkerPool) getJob(jobID string) (*LotteryJob, bool) {
	wp.mu.RLock()
	defer wp.mu.RUnlock()
	job, ok := wp.jobs[jobID]
	return job, ok
}

func (wp *WorkerPool) Stop() {
	close(jobQueue)
	wp.wg.Wait()
}

// レート制限用のミドルウェア
type RateLimiter struct {
	requests map[string][]time.Time
	mu       sync.Mutex
	limit    int
	window   time.Duration
}

func NewRateLimiter(limit int, window time.Duration) *RateLimiter {
	return &RateLimiter{
		requests: make(map[string][]time.Time),
		limit:    limit,
		window:   window,
	}
}

func (rl *RateLimiter) Allow(ip string) bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	now := time.Now()
	if _, exists := rl.requests[ip]; !exists {
		rl.requests[ip] = []time.Time{}
	}

	// 古いリクエストを削除
	var validRequests []time.Time
	for _, t := range rl.requests[ip] {
		if now.Sub(t) < rl.window {
			validRequests = append(validRequests, t)
		}
	}

	if len(validRequests) >= rl.limit {
		return false
	}

	rl.requests[ip] = append(validRequests, now)
	return true
}

var rateLimiter *RateLimiter

func enableCORS(w http.ResponseWriter) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
}

func rateLimitMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ip := r.RemoteAddr
		if !rateLimiter.Allow(ip) {
			enableCORS(w)
			w.WriteHeader(http.StatusTooManyRequests)
			json.NewEncoder(w).Encode(ErrorResponse{
				Error: "レート制限: リクエストが多すぎます。しばらく待ってから再試行してください。",
			})
			return
		}
		next(w, r)
	}
}

func submitLottery(w http.ResponseWriter, r *http.Request) {
	enableCORS(w)

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	if r.Method != "POST" {
		w.WriteHeader(http.StatusMethodNotAllowed)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "Method not allowed"})
		return
	}

	var req LotteryRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "Invalid request body"})
		return
	}

	if len(req.Participants) == 0 {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "No participants provided"})
		return
	}

	if req.WinnerCount <= 0 || req.WinnerCount > len(req.Participants) {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "Invalid winner count"})
		return
	}

	// ジョブ作成
	jobID := uuid.New().String()
	job := &LotteryJob{
		JobID:        jobID,
		Participants: req.Participants,
		WinnerCount:  req.WinnerCount,
		Status:       "queued",
		CreatedAt:    time.Now(),
	}

	// キューに追加（非ブロッキング）
	select {
	case jobQueue <- job:
		workerPool.updateJob(job)
		log.Printf("Job %s キューに追加 (参加者: %d, 当選者: %d)", jobID, len(req.Participants), req.WinnerCount)
		
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusAccepted)
		json.NewEncoder(w).Encode(LotteryResponse{
			JobID:   jobID,
			Status:  "queued",
			Message: "抽選リクエストを受け付けました。ステータスを確認してください。",
		})
	default:
		w.WriteHeader(http.StatusServiceUnavailable)
		json.NewEncoder(w).Encode(ErrorResponse{
			Error: "サーバーが混雑しています。しばらく待ってから再試行してください。",
		})
	}
}

func getJobStatus(w http.ResponseWriter, r *http.Request) {
	enableCORS(w)

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	jobID := r.URL.Query().Get("jobId")
	if jobID == "" {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "Job ID required"})
		return
	}

	// まずRedisをチェック
	if redisClient != nil {
		val, err := redisClient.Get(ctx, "job:"+jobID).Result()
		if err == nil {
			var job LotteryJob
			if err := json.Unmarshal([]byte(val), &job); err == nil {
				w.Header().Set("Content-Type", "application/json")
				json.NewEncoder(w).Encode(JobStatusResponse{
					JobID:       job.JobID,
					Status:      job.Status,
					Winners:     job.Winners,
					CompletedAt: job.CompletedAt.Format("2006-01-02 15:04:05"),
				})
				return
			}
		}
	}

	// メモリから取得
	job, ok := workerPool.getJob(jobID)
	if !ok {
		w.WriteHeader(http.StatusNotFound)
		json.NewEncoder(w).Encode(ErrorResponse{Error: "Job not found"})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(JobStatusResponse{
		JobID:       job.JobID,
		Status:      job.Status,
		Winners:     job.Winners,
		CompletedAt: job.CompletedAt.Format("2006-01-02 15:04:05"),
	})
}

func healthCheck(w http.ResponseWriter, r *http.Request) {
	enableCORS(w)
	
	redisStatus := "disconnected"
	if redisClient != nil {
		if err := redisClient.Ping(ctx).Err(); err == nil {
			redisStatus = "connected"
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":      "ok",
		"time":        time.Now().Format("2006-01-02 15:04:05"),
		"queueSize":   len(jobQueue),
		"queueCap":    cap(jobQueue),
		"workers":     workerPool.workerCount,
		"redisStatus": redisStatus,
	})
}

func initRedis() {
	redisAddr := os.Getenv("REDIS_ADDR")
	if redisAddr == "" {
		redisAddr = "localhost:6379"
	}

	redisClient = redis.NewClient(&redis.Options{
		Addr:     redisAddr,
		Password: "",
		DB:       0,
	})

	if err := redisClient.Ping(ctx).Err(); err != nil {
		log.Printf("警告: Redisに接続できません: %v (キャッシュなしで続行)", err)
		redisClient = nil
	} else {
		log.Printf("Redis接続成功: %s", redisAddr)
	}
}

func main() {
	// Redis初期化
	initRedis()

	// ワーカープール初期化（CPU数に応じて調整）
	workerCount := 20
	if val := os.Getenv("WORKER_COUNT"); val != "" {
		fmt.Sscanf(val, "%d", &workerCount)
	}
	workerPool = NewWorkerPool(workerCount)
	workerPool.Start()

	// レート制限初期化（1分間に100リクエスト）
	rateLimiter = NewRateLimiter(100, time.Minute)

	// ルーティング
	http.HandleFunc("/api/lottery", rateLimitMiddleware(submitLottery))
	http.HandleFunc("/api/status", getJobStatus)
	http.HandleFunc("/api/health", healthCheck)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	server := &http.Server{
		Addr:         ":" + port,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// グレースフルシャットダウン
	go func() {
		sigChan := make(chan os.Signal, 1)
		signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
		<-sigChan

		log.Println("シャットダウン開始...")
		
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()

		if err := server.Shutdown(ctx); err != nil {
			log.Printf("シャットダウンエラー: %v", err)
		}

		workerPool.Stop()
		
		if redisClient != nil {
			redisClient.Close()
		}
		
		log.Println("シャットダウン完了")
	}()

	fmt.Printf("🚀 高負荷対応サーバー起動: http://localhost:%s\n", port)
	fmt.Printf("   Workers: %d\n", workerCount)
	fmt.Printf("   Queue Cap: %d\n", cap(jobQueue))
	
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
