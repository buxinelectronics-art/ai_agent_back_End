# gunicorn.conf.py
# Render reads this automatically when using gunicorn

workers    = 2
threads    = 4
timeout    = 120
bind       = "0.0.0.0:10000"
worker_class = "sync"
accesslog  = "-"
errorlog   = "-"
loglevel   = "info"
