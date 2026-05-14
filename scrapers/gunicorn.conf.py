import os
workers     = 1
threads     = 2
timeout     = 120
bind        = f"0.0.0.0:{os.environ.get('PORT', '10000')}"
worker_class = "sync"
accesslog   = "-"
errorlog    = "-"
loglevel    = "info"
preload_app = False
