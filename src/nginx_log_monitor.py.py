import os
import re
from datetime import datetime
import mysql.connector
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Load environment variables
load_dotenv()

class NginxLogHandler(FileSystemEventHandler):
    def __init__(self):
        # MySQL connection setup
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '3306'),
            'database': os.getenv('DB_NAME', 'nginx_logs'),
            'user': os.getenv('DB_USER', 'loguser'),
            'password': os.getenv('DB_PASSWORD', 'securepassword'),
            'autocommit': False
        }
        self.connect_db()
        
        # Regex patterns
        self.access_log_pattern = re.compile(
            r'(?P<remote_addr>\S+) - (?P<remote_user>\S+) \[(?P<time_local>[^\]]+)\] '
            r'"(?P<request>[^"]*)" (?P<status>\d+) (?P<body_bytes_sent>\d+) '
            r'"(?P<http_referer>[^"]*)" "(?P<http_user_agent>[^"]*)" '
            r'(?P<upstream_addr>\S+) (?P<request_time>\S+) (?P<upstream_response_time>\S+)'
        )
        
        self.error_log_pattern = re.compile(
            r'^(?P<time_local>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) \[(?P<level>\w+)\] '
            r'(?P<pid>\d+)#(?P<tid>\d+): (?:\*(?P<cid>\d+))? ?'
            r'(?P<message>.*?)(?:, client: (?P<client>[^,]+))?'
            r'(?:, server: (?P<server>[^,]+))?'
            r'(?:, request: "(?P<request>[^"]+)")?'
            r'(?:, host: "(?P<host>[^"]+)")?$'
        )

    def connect_db(self):
        """Establish database connection with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.db_connection = mysql.connector.connect(**self.db_config)
                self.cursor = self.db_connection.cursor()
                return
            except mysql.connector.Error as err:
                if attempt == max_retries - 1:
                    raise
                print(f"DB connection failed (attempt {attempt + 1}): {err}")
                time.sleep(5)

    def on_modified(self, event):
        if not event.is_directory:
            try:
                if 'access.log' in event.src_path:
                    self.process_access_log(event.src_path)
                elif 'error.log' in event.src_path:
                    self.process_error_log(event.src_path)
            except Exception as e:
                print(f"Error processing {event.src_path}: {str(e)}")

    def process_access_log(self, file_path):
        """Process new lines in access log file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Go to end of file
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if not line:
                        break
                    self.parse_and_store_access_line(line.strip())
        except IOError as e:
            print(f"Error reading access log: {str(e)}")

    def process_error_log(self, file_path):
        """Process new lines in error log file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Go to end of file
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if not line:
                        break
                    self.parse_and_store_error_line(line.strip())
        except IOError as e:
            print(f"Error reading error log: {str(e)}")

    def parse_and_store_access_line(self, line):
        """Parse and store a single access log line"""
        match = self.access_log_pattern.match(line)
        if not match:
            print(f"Failed to parse access log line: {line[:100]}...")
            return

        data = match.groupdict()
        
        try:
            # Parse and format timestamp
            time_local = datetime.strptime(data['time_local'], '%d/%b/%Y:%H:%M:%S %z')
            time_local_str = time_local.strftime('%Y-%m-%d %H:%M:%S')
            
            # Parse numeric fields
            request_time = float(data['request_time'])
            upstream_response_time = float(data['upstream_response_time']) if data['upstream_response_time'] != '-' else None
            
            # Prepare and execute SQL
            query = """
            INSERT INTO access_logs 
            (remote_addr, remote_user, time_local, request, status, body_bytes_sent, 
             http_referer, http_user_agent, upstream_addr, request_time, upstream_response_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            values = (
                data['remote_addr'],
                data['remote_user'] if data['remote_user'] != '-' else None,
                time_local_str,
                data['request'],
                int(data['status']),
                int(data['body_bytes_sent']),
                data['http_referer'] if data['http_referer'] != '-' else None,
                data['http_user_agent'],
                data['upstream_addr'] if data['upstream_addr'] != '-' else None,
                request_time,
                upstream_response_time
            )
            
            self.cursor.execute(query, values)
            self.db_connection.commit()
            
        except ValueError as e:
            print(f"Value error parsing line: {str(e)}")
            self.db_connection.rollback()
        except mysql.connector.Error as e:
            print(f"Database error: {str(e)}")
            self.db_connection.rollback()
            self.connect_db()  # Reconnect on error

    def parse_and_store_error_line(self, line):
        """Parse and store a single error log line"""
        match = self.error_log_pattern.match(line)
        if not match:
            print(f"Failed to parse error log line: {line[:100]}...")
            return

        data = match.groupdict()
        
        try:
            # Parse and format timestamp
            time_local = datetime.strptime(data['time_local'], '%Y/%m/%d %H:%M:%S')
            time_local_str = time_local.strftime('%Y-%m-%d %H:%M:%S')
            
            # Prepare and execute SQL
            query = """
            INSERT INTO error_logs 
            (time_local, level, message, pid, client, server, request, host)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            values = (
                time_local_str,
                data['level'],
                data['message'],
                int(data['pid']) if data['pid'] else None,
                data.get('client'),
                data.get('server'),
                data.get('request'),
                data.get('host')
            )
            
            self.cursor.execute(query, values)
            self.db_connection.commit()
            
        except ValueError as e:
            print(f"Value error parsing line: {str(e)}")
            self.db_connection.rollback()
        except mysql.connector.Error as e:
            print(f"Database error: {str(e)}")
            self.db_connection.rollback()
            self.connect_db()  # Reconnect on error

    def __del__(self):
        """Clean up resources"""
        if hasattr(self, 'cursor'):
            self.cursor.close()
        if hasattr(self, 'db_connection'):
            self.db_connection.close()

def main():
    access_log_path = os.getenv('ACCESS_LOG_PATH', '/var/log/nginx/*-access.log')
    error_log_path = os.getenv('ERROR_LOG_PATH', '/var/log/nginx/*-error.log')
    
    # Get directory from path pattern
    access_log_dir = os.path.dirname(access_log_path)
    
    event_handler = NginxLogHandler()
    observer = Observer()
    observer.schedule(event_handler, access_log_dir, recursive=False)
    
    print(f"Starting Nginx log monitor for directory: {access_log_dir}")
    observer.start()
    
    try:
        while True:
            pass
    except KeyboardInterrupt:
        observer.stop()
        print("\nLog monitoring stopped")
    
    observer.join()

if __name__ == "__main__":
    main()