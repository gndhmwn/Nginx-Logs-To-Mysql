-- Create tables if they don't exist
USE nginx_logs;

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

-- Create additional indexes if needed
ALTER TABLE access_logs ADD INDEX idx_remote_addr (remote_addr);
ALTER TABLE error_logs ADD INDEX idx_client (client);