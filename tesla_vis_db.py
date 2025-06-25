# database_config.py
"""
Database configuration options for Tesla Dashboard
Choose the appropriate configuration based on your needs
"""

import os

class DatabaseConfig:
    """Base database configuration"""
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class SQLiteConfig(DatabaseConfig):
    """SQLite configuration - good for local development and testing"""
    SQLALCHEMY_DATABASE_URI = 'sqlite:///tesla_data.db'

class PostgreSQLConfig(DatabaseConfig):
    """PostgreSQL configuration - recommended for production"""
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 
        'postgresql://username:password@localhost:5432/tesla_dashboard'
    )

class TimescaleDBConfig(DatabaseConfig):
    """TimescaleDB configuration - excellent for time-series data"""
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'TIMESCALEDB_URL',
        'postgresql://username:password@localhost:5432/tesla_timeseries'
    )

class MySQLConfig(DatabaseConfig):
    """MySQL configuration"""
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'MYSQL_URL',
        'mysql+pymysql://username:password@localhost:3306/tesla_dashboard'
    )

# MongoDB alternative (requires separate implementation)
class MongoDBConfig:
    """MongoDB configuration - alternative NoSQL approach"""
    MONGO_URI = os.environ.get(
        'MONGODB_URI',
        'mongodb://localhost:27017/tesla_dashboard'
    )

# Cloud database configurations
class CloudDatabaseConfig:
    """Cloud database options"""
    
    # AWS RDS PostgreSQL
    AWS_RDS_POSTGRESQL = "postgresql://username:password@your-rds-endpoint.amazonaws.com:5432/tesla_dashboard"
    
    # Google Cloud SQL
    GOOGLE_CLOUD_SQL = "postgresql://username:password@your-cloud-sql-ip:5432/tesla_dashboard"
    
    # Azure Database for PostgreSQL
    AZURE_POSTGRESQL = "postgresql://username:password@your-server.postgres.database.azure.com:5432/tesla_dashboard"
    
    # MongoDB Atlas (cloud)
    MONGODB_ATLAS = "mongodb+srv://username:password@cluster.mongodb.net/tesla_dashboard"
    
    # InfluxDB Cloud (time-series optimized)
    INFLUXDB_CLOUD = {
        'url': 'https://your-org.influxdata.io',
        'token': 'your-token',
        'org': 'your-org',
        'bucket': 'tesla-data'
    }

# Environment-based configuration selection
def get_database_config():
    """Get database configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development')
    db_type = os.environ.get('DATABASE_TYPE', 'sqlite')
    
    if env == 'development':
        if db_type == 'postgresql':
            return PostgreSQLConfig
        elif db_type == 'timescaledb':
            return TimescaleDBConfig
        else:
            return SQLiteConfig
    
    elif env == 'production':
        if db_type == 'timescaledb':
            return TimescaleDBConfig
        else:
            return PostgreSQLConfig
    
    return SQLiteConfig

# TimescaleDB specific setup (if using TimescaleDB)
TIMESCALEDB_SETUP_SQL = """
-- Create hypertable for time-series optimization
SELECT create_hypertable('tesla_data', 'timestamp', if_not_exists => TRUE);

-- Create indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_tesla_data_timestamp ON tesla_data (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_tesla_data_battery_level ON tesla_data (battery_level) WHERE battery_level IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tesla_data_charging_state ON tesla_data (charging_state) WHERE charging_state IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tesla_data_location ON tesla_data (location) WHERE location IS NOT NULL;

-- Create continuous aggregates for daily summaries
CREATE MATERIALIZED VIEW IF NOT EXISTS tesla_daily_summary
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', timestamp) AS day,
    AVG(battery_level) as avg_battery_level,
    MIN(battery_level) as min_battery_level,
    MAX(battery_level) as max_battery_level,
    AVG(outside_temp) as avg_outside_temp,
    COUNT(*) as data_points
FROM tesla_data
WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '1 year'
GROUP BY day;

-- Refresh policy for continuous aggregates
SELECT add_continuous_aggregate_policy('tesla_daily_summary',
    start_offset => INTERVAL '1 month',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');
"""
