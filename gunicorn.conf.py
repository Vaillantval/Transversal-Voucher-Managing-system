"""
Gunicorn configuration — BonNet production.

Cible : 1000 users simultanés.
Modèle : gthread (workers × threads) → concurrent sans async.

Sur Railway (2 vCPU / 1 GB RAM typique) :
  workers=4, threads=4 → 16 slots concurrents
  Chaque requête cache-chaude ≈ 50ms → ~320 req/s théorique
"""
import multiprocessing
import os

# ─── Binding ──────────────────────────────────────────────────────────────────
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# ─── Workers ──────────────────────────────────────────────────────────────────
# Railway PostgreSQL Hobby = 25 connexions max.
# Budget : 4 workers × 1 connexion persistante (conn_max_age) = 4 connexions
#          + threads partagent la même connexion dans un worker gthread
# WEB_CONCURRENCY peut être surchargé via variable Railway si besoin
workers = int(os.getenv('WEB_CONCURRENCY', 4))
worker_class = 'gthread'   # threads I/O-safe dans chaque worker (idéal avec Redis/DB)
threads = int(os.getenv('GUNICORN_THREADS', 4))  # 4 workers × 4 threads = 16 slots concurrents

# ─── Timeouts ─────────────────────────────────────────────────────────────────
timeout = 60          # worker tué après 60s (évite les workers bloqués sur UniFi)
graceful_timeout = 30 # délai pour finir les requêtes en cours avant arrêt
keepalive = 5         # connexions HTTP keep-alive (réduit overhead TCP)

# ─── Stabilité long-terme ─────────────────────────────────────────────────────
max_requests = 1000         # redémarre le worker après N requêtes (évite les fuites mémoire)
max_requests_jitter = 100   # étale les redémarrages (évite que tous redémarrent en même temps)

# ─── Logging ──────────────────────────────────────────────────────────────────
accesslog = '-'       # stdout → Railway logs
errorlog  = '-'       # stderr → Railway logs
loglevel  = os.getenv('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(D)sµs'
