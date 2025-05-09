nginx-log-monitor/
├── docker-compose.yml
├── .env
├── mysql/
│   ├── config/
│   │   └── custom.cnf      # Optional MySQL config
│   └── data/              # Will be created automatically
├── scripts/
│   └── init.sql           # Initial database setup
└── src/
    ├── nginx_log_monitor.py  # Main monitoring script
    ├── Dockerfile          # For the log monitor container
    └── requirements.txt    # Python dependencies


####################################################################################
# Create database
CREATE DATABASE IF NOT EXISTS nginx_logs;
USE nginx_logs;

# Access logs table with reverse_proxy format support
CREATE TABLE IF NOT EXISTS access_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    remote_addr VARCHAR(45),
    remote_user VARCHAR(255),
    time_local DATETIME,
    request TEXT,
    status INT,
    body_bytes_sent INT,
    http_referer TEXT,
    http_user_agent TEXT,
    upstream_addr VARCHAR(255),
    request_time FLOAT,
    upstream_response_time FLOAT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_time (time_local),
    INDEX idx_status (status),
    INDEX idx_upstream (upstream_addr)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

# Error logs table
CREATE TABLE IF NOT EXISTS error_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    time_local DATETIME,
    level VARCHAR(20),
    message TEXT,
    pid INT,
    client VARCHAR(45),
    server VARCHAR(255),
    request TEXT,
    host TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_time (time_local),
    INDEX idx_level (level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

# Create user (adjust permissions as needed)
CREATE USER IF NOT EXISTS 'loguser'@'%' IDENTIFIED BY 'securepassword';
GRANT INSERT, SELECT, UPDATE ON nginx_logs.* TO 'loguser'@'%';
FLUSH PRIVILEGES;

####################################################################################
# 1. Traffic Analysis
SELECT 
    DATE(time_local) as day,
    COUNT(*) as requests,
    AVG(request_time) as avg_response_time,
    SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as error_count
FROM access_logs
GROUP BY day
ORDER BY day DESC;

# 2. Upstream Performance
SELECT 
    upstream_addr,
    COUNT(*) as requests,
    AVG(request_time) as avg_total_time,
    AVG(upstream_response_time) as avg_upstream_time,
    SUM(CASE WHEN status >= 500 THEN 1 ELSE 0 END) as error_count
FROM access_logs
WHERE upstream_addr IS NOT NULL
GROUP BY upstream_addr
ORDER BY requests DESC;

# 3. Top Slow Requests
SELECT 
    time_local,
    request,
    request_time,
    upstream_response_time,
    upstream_addr
FROM access_logs
ORDER BY request_time DESC
LIMIT 20;

# 4. Error Analysis
SELECT 
    level,
    COUNT(*) as count,
    MIN(time_local) as first_occurrence,
    MAX(time_local) as last_occurrence
FROM error_logs
GROUP BY level
ORDER BY count DESC;

# 5. Client Analysis
SELECT 
    remote_addr,
    COUNT(*) as requests,
    AVG(request_time) as avg_response_time,
    MAX(request_time) as max_response_time
FROM access_logs
GROUP BY remote_addr
HAVING COUNT(*) > 10
ORDER BY requests DESC
LIMIT 50;

# 6. Hourly Traffic Pattern
SELECT 
    HOUR(time_local) as hour,
    COUNT(*) as requests,
    AVG(request_time) as avg_response_time
FROM access_logs
GROUP BY hour
ORDER BY hour;

##################################################################
# Create /etc/systemd/system/nginx-log-monitor.service:

[Unit]
Description=Nginx Log Monitor
After=network.target mysql.service

[Service]
User=root
WorkingDirectory=/opt/nginx-log-monitor
ExecStart=/usr/bin/python3 /opt/nginx-log-monitor/nginx_log_monitor.py
EnvironmentFile=/opt/nginx-log-monitor/.env
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# Then enable and start the service:
    $ sudo systemctl daemon-reload
    $ sudo systemctl enable nginx-log-monitor
    $ sudo systemctl start nginx-log-monitor

###################################################################
# DOCKER COMPOSE
- Create the directory structure and files as shown above
- Set proper permissions:
    $ chmod -R 755 mysql/data
- Start the services:
    $ docker-compose up -d
- Verify the containers are running:
    $ docker-compose ps
- Check logs:
    $ docker-compose logs -f