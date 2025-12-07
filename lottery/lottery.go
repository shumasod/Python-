// かなり長いので途中で省略はしません。
// 高可読・高品質な Go サーバーコードとして再構築済みです。

package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"math/rand"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"sync"
	"syscall"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
)

/* ============================================================
 *                      Constants / Types
 * ============================================================*/

const (
	defaultQueueSize     = 10000
	defaultWorkerCount   = 20
	jobCacheTTL          = 10 * time.Minute
	rateLimitMaxRequests = 100
	rateLimitWindow      = time.Minute
)

/* ----------------------- Request / Response ------------------------ */

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

/* ============================================================
 *                      Worker Pool
 * ============================================================*/

type WorkerPool struct {
	workerCount int
	jobs        map[string]*LotteryJob
	jobMu       sync.RWMutex
	wg          sync.WaitGroup
	jobQueue    chan *LotteryJob
}

func NewWorkerPool(count int, queue chan *LotteryJob) *WorkerPool {
	return &WorkerPool{
		workerCount: count,
		jobs:        make(map[string]*LotteryJob),
		jobQueue:    queue,
	}
}

func (wp *WorkerPool) Start(redis *redis.Client) {
	for i := 0; i < wp.workerCount; i++ {
		wp.wg.Add(1)
		go wp.worker(i, redis)
	}
	log.Printf("Worker pool started: %d workers", wp.workerCount)
}

func (wp *WorkerPool) worker(id int, redis *redis.Client) {
	defer wp.wg.Done()

	r := rand.New(rand.NewSource(time.Now().UnixNano() + int64(id)))

	for job := range wp.jobQueue {
		job.Status = "processing"
		wp.updateJob(job)

		// 擬似処理時間
		time.Sleep(80 * time.Millisecond)

		// Fisher-Yates shuffle
		shuffled := make([]Participant, len(job.Participants))
		copy(shuffled, job.Participants)
		for i := len(shuffled) - 1; i > 0; i-- {
			j := r.Intn(i + 1)
			shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
		}

		job.Winners = shuffled[:job.WinnerCount]
		job.Status = "completed"
		job.CompletedAt = time.Now()
		wp.updateJob(job)

		if redis != nil {
			data, err := json.Marshal(job)
			if err == nil {
				redis.Set(context.Background(), "job:"+job.JobID, data, jobCacheTTL)
			}
		}

		log.Printf("Worker %d completed job %s", id, job.JobID)
	}
}

func (wp *WorkerPool) updateJob(job *LotteryJob) {
	wp.jobMu.Lock()
	defer wp.jobMu.Unlock()
	wp.jobs[job.JobID] = job
}

func (wp *WorkerPool) GetJob(jobID string) (*LotteryJob, bool) {
	wp.jobMu.RLock()
	defer wp.jobMu.RUnlock()
	job, ok := wp.jobs[jobID]
	return job, ok
}

func (wp *WorkerPool) Stop() {
	close(wp.jobQueue)
	wp.wg.Wait()
}

/* ============================================================
 *                      Rate Limiter
 * ============================================================*/

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
	list := rl.requests[ip]

	// 古いものを削除
	valid := list[:0]
	for _, t := range list {
		if now.Sub(t) < rl.window {
			valid = append(valid, t)
		}
	}

	// 制限チェック
	if len(valid) >= rl.limit {
		return false
	}

	rl.requests[ip] = append(valid, now)
	return true
}

/* ============================================================
 *                      Application Struct
 * ============================================================*/

type App struct {
	ctx         context.Context
	redis       *redis.Client
	workerPool  *WorkerPool
	jobQueue    chan *LotteryJob
	rateLimiter *RateLimiter
}

/* ============================================================
 *                      Helpers
 * ============================================================*/

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

func enableCORS(w http.ResponseWriter) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
}

func (app *App) rateLimit(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ip, _, _ := net.SplitHostPort(r.RemoteAddr)
		if !app.rateLimiter.Allow(ip) {
			writeJSON(w, http.StatusTooManyRequests, ErrorResponse{
				Error: "Too many requests",
			})
			return
		}
		next(w, r)
	}
}

/* ============================================================
 *                      Handlers
 * ============================================================*/

func (app *App) submitLottery(w http.ResponseWriter, r *http.Request) {
	enableCORS(w)

	if r.Method == http.MethodOptions {
		w.WriteHeader(http.StatusOK)
		return
	}
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, ErrorResponse{Error: "Method not allowed"})
		return
	}

	var req LotteryRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, ErrorResponse{Error: "Invalid JSON"})
		return
	}

	if len(req.Participants) == 0 {
		writeJSON(w, http.StatusBadRequest, ErrorResponse{Error: "Participants required"})
		return
	}
	if req.WinnerCount < 1 || req.WinnerCount > len(req.Participants) {
		writeJSON(w, http.StatusBadRequest, ErrorResponse{Error: "Invalid winnerCount"})
		return
	}

	job := &LotteryJob{
		JobID:        uuid.NewString(),
		Status:       "queued",
		Participants: req.Participants,
		WinnerCount:  req.WinnerCount,
		CreatedAt:    time.Now(),
	}

	select {
	case app.jobQueue <- job:
		app.workerPool.updateJob(job)
		writeJSON(w, http.StatusAccepted, LotteryResponse{
			JobID:   job.JobID,
			Status:  "queued",
			Message: "Job accepted.",
		})
	default:
		writeJSON(w, http.StatusServiceUnavailable, ErrorResponse{
			Error: "Server busy",
		})
	}
}

func (app *App) getStatus(w http.ResponseWriter, r *http.Request) {
	enableCORS(w)

	jobID := r.URL.Query().Get("jobId")
	if jobID == "" {
		writeJSON(w, http.StatusBadRequest, ErrorResponse{Error: "jobId required"})
		return
	}

	// Redis check
	if app.redis != nil {
		val, err := app.redis.Get(app.ctx, "job:"+jobID).Result()
		if err == nil {
			var job LotteryJob
			if json.Unmarshal([]byte(val), &job) == nil {
				writeJSON(w, http.StatusOK, JobStatusResponse{
					JobID:       job.JobID,
					Status:      job.Status,
					Winners:     job.Winners,
					CompletedAt: job.CompletedAt.Format(time.RFC3339),
				})
				return
			}
		}
	}

	// Memory
	job, ok := app.workerPool.GetJob(jobID)
	if !ok {
		writeJSON(w, http.StatusNotFound, ErrorResponse{Error: "Job not found"})
		return
	}

	writeJSON(w, http.StatusOK, JobStatusResponse{
		JobID:       job.JobID,
		Status:      job.Status,
		Winners:     job.Winners,
		CompletedAt: job.CompletedAt.Format(time.RFC3339),
	})
}

func (app *App) health(w http.ResponseWriter, r *http.Request) {
	enableCORS(w)

	redisStatus := "disconnected"
	if app.redis != nil {
		if err := app.redis.Ping(app.ctx).Err(); err == nil {
			redisStatus = "connected"
		}
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"status":      "ok",
		"time":        time.Now().Format(time.RFC3339),
		"queueSize":   len(app.jobQueue),
		"queueCap":    cap(app.jobQueue),
		"workers":     app.workerPool.workerCount,
		"redisStatus": redisStatus,
	})
}

/* ============================================================
 *                      Redis Init
 * ============================================================*/

func initRedis() (*redis.Client, error) {
	addr := os.Getenv("REDIS_ADDR")
	if addr == "" {
		addr = "localhost:6379"
	}

	client := redis.NewClient(&redis.Options{
		Addr: addr,
		DB:   0,
	})

	if err := client.Ping(context.Background()).Err(); err != nil {
		return nil, err
	}

	return client, nil
}

/* ============================================================
 *                      Main
 * ============================================================*/

func main() {
	ctx := context.Background()

	redis, err := initRedis()
	if err != nil {
		log.Printf("Redis disabled: %v", err)
		redis = nil
	}

	// Worker count
	workers := defaultWorkerCount
	if v := os.Getenv("WORKER_COUNT"); v != "" {
		if parsed, err := strconv.Atoi(v); err == nil && parsed > 0 {
			workers = parsed
		}
	}

	jobQueue := make(chan *LotteryJob, defaultQueueSize)
	pool := NewWorkerPool(workers, jobQueue)
	pool.Start(redis)

	app := &App{
		ctx:         ctx,
		redis:       redis,
		workerPool:  pool,
		jobQueue:    jobQueue,
		rateLimiter: NewRateLimiter(rateLimitMaxRequests, rateLimitWindow),
	}

	http.HandleFunc("/api/lottery", app.rateLimit(app.submitLottery))
	http.HandleFunc("/api/status", app.getStatus)
	http.HandleFunc("/api/health", app.health)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	server := &http.Server{
		Addr:         ":" + port,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
	}

	// Graceful shutdown
	go func() {
		sig := make(chan os.Signal, 1)
		signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
		<-sig

		log.Println("Shutting down...")

		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
		defer cancel()

		server.Shutdown(ctx)
		pool.Stop()
		if app.redis != nil {
			app.redis.Close()
		}
		log.Println("Shutdown complete")
	}()

	fmt.Printf("🚀 Server running at http://localhost:%s (workers=%d)\n", port, workers)
	server.ListenAndServe()
}
