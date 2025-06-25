# Tesla Dashboard Setup Guide

This guide will help you set up a comprehensive Tesla data visualization dashboard with Flask and your choice of database.

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.8+
- TeslaFi account and API token
- Git (optional)

### 1. Environment Setup

```bash
# Clone or create project directory
mkdir tesla-dashboard
cd tesla-dashboard

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in your project root:

```env
# TeslaFi API Configuration
TESLAFI_API_TOKEN=your_teslafi_api_token_here

# Flask Configuration
FLASK_ENV=development
FLASK_APP=app.py
SECRET_KEY=your-secret-key-here

# Database Configuration
DATABASE_TYPE=sqlite
# For PostgreSQL: DATABASE_URL=postgresql://user:pass@localhost:5432/tesla_dashboard
# For TimescaleDB: TIMESCALEDB_URL=postgresql://user:pass@localhost:5432/tesla_timeseries

# Data Ingestion
INGESTION_INTERVAL_MINUTES=5
FLASK_APP_URL=http://localhost:5000
```

### 3. Run the Application

```bash
# Start the Flask application
python app.py

# In another terminal, start data ingestion (optional)
python tesla_ingestion.py schedule
```

The dashboard will be available at `http://localhost:5000`

## 🗄️ Database Options

### SQLite (Default - Local Development)
- **Pros**: No setup required, perfect for testing
- **Cons**: Single-user, not suitable for production
- **Configuration**: Default, no additional setup needed

### PostgreSQL (Recommended for Production)
```bash
# Install PostgreSQL
# Ubuntu/Debian:
sudo apt-get install postgresql postgresql-contrib

# macOS:
brew install postgresql

# Create database
sudo -u postgres createdb tesla_dashboard

# Set environment variable
export DATABASE_TYPE=postgresql
export DATABASE_URL=postgresql://username:password@localhost:5432/tesla_dashboard
```

### TimescaleDB (Best for Time-Series Data)
```bash
# Install TimescaleDB (extends PostgreSQL)
# Ubuntu/Debian:
sudo apt-get install timescaledb-postgresql

# Enable TimescaleDB extension
sudo -u postgres psql -d tesla_dashboard -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# Set environment variable
export DATABASE_TYPE=timescaledb
export TIMESCALEDB_URL=postgresql://username:password@localhost:5432/tesla_timeseries
```

### MongoDB (Alternative NoSQL Option)
```bash
# Install MongoDB
# Ubuntu:
sudo apt-get install mongodb

# macOS:
brew install mongodb-community

# You'll need to modify the app to use MongoDB instead of SQLAlchemy
```

## ☁️ Cloud Deployment Options

### 1. Heroku (Easy Deployment)

```bash
# Install Heroku CLI
# Create Procfile
echo "web: gunicorn app:app" > Procfile

# Initialize git repository
git init
git add .
git commit -m "Initial commit"

# Create Heroku app
heroku create your-tesla-dashboard

# Add PostgreSQL addon
heroku addons:create heroku-postgresql:hobby-dev

# Set environment variables
heroku config:set TESLAFI_API_TOKEN=your_token_here
heroku config:set FLASK_ENV=production
heroku config:set DATABASE_TYPE=postgresql

# Deploy
git push heroku main
```

### 2. DigitalOcean App Platform

```yaml
# app.yaml
name: tesla-dashboard
services:
- name: web
  source_dir: /
  github:
    repo: your-username/tesla-dashboard
    branch: main
  run_command: gunicorn app:app
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  env:
  - key: FLASK_ENV
    value: production
  - key: TESLAFI_API_TOKEN
    value: your_token_here
databases:
- name: tesla-db
  engine: PG
  size: db-s-dev-database
```

### 3. AWS (Advanced)

#### Using AWS RDS + Elastic Beanstalk:
```bash
# Create RDS PostgreSQL instance
aws rds create-db-instance \
    --db-name tesla_dashboard \
    --db-instance-identifier tesla-dashboard-db \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --master-username admin \
    --master-user-password your_password

# Deploy to Elastic Beanstalk
eb init tesla-dashboard
eb create production
eb deploy
```

## 📊 Database Schema Optimization

### For Time-Series Workloads (TimescaleDB)

```sql
-- Create hypertable for better performance
SELECT create_hypertable('tesla_data', 'timestamp');

-- Create useful indexes
CREATE INDEX idx_tesla_battery ON tesla_data (timestamp, battery_level);
CREATE INDEX idx_tesla_location ON tesla_data (timestamp, location);
CREATE INDEX idx_tesla_charging ON tesla_data (timestamp, charging_state);

-- Create continuous aggregates for dashboards
CREATE MATERIALIZED VIEW tesla_hourly_avg
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', timestamp) AS hour,
    AVG(battery_level) as avg_battery,
    AVG(outside_temp) as avg_temp,
    COUNT(*) as readings
FROM tesla_data
GROUP BY hour;
```

### For Regular PostgreSQL

```sql
-- Create indexes for common queries
CREATE INDEX idx_tesla_timestamp ON tesla_data (timestamp DESC);
CREATE INDEX idx_tesla_battery_level ON tesla_data (battery_level) WHERE battery_level IS NOT NULL;
CREATE INDEX idx_tesla_charging_state ON tesla_data (charging_state) WHERE charging_state IS NOT NULL;

-- Partition table by month for better performance (PostgreSQL 10+)
CREATE TABLE tesla_data_y2025m01 PARTITION OF tesla_data
FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
```

## 🔧 Data Ingestion Strategies

### 1. Scheduled Script (Recommended)
```bash
# Run data ingestion every 5 minutes
python tesla_ingestion.py schedule
```

### 2. Cron Job (Linux/macOS)
```bash
# Add to crontab
crontab -e

# Add this line for every 5 minutes
*/5 * * * * /path/to/venv/bin/python /path/to/tesla_ingestion.py once
```

### 3. Systemd Service (Linux)
```ini
# /etc/systemd/system/tesla-ingestion.service
[Unit]
Description=Tesla Data Ingestion Service
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/tesla-dashboard
Environment=PATH=/path/to/venv/bin
ExecStart=/path/to/venv/bin/python tesla_ingestion.py schedule
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable tesla-ingestion.service
sudo systemctl start tesla-ingestion.service
```

## 📈 Monitoring and Maintenance

### Log Monitoring
```bash
# View ingestion logs
tail -f tesla_ingestion.log

# View Flask app logs
tail -f flask_app.log
```

### Database Maintenance
```sql
-- For PostgreSQL/TimescaleDB
-- Check database size
SELECT pg_size_pretty(pg_database_size('tesla_dashboard'));

-- Vacuum old data (run weekly)
VACUUM ANALYZE tesla_data;

-- For TimescaleDB: Drop old data chunks (optional)
SELECT drop_chunks('tesla_data', INTERVAL '1 year');
```

### Backup Strategy
```bash
# PostgreSQL backup
pg_dump tesla_dashboard > backup_$(date +%Y%m%d).sql

# Automated daily backup
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump tesla_dashboard | gzip > /backups/tesla_backup_$DATE.sql.gz

# Keep only last 30 days
find /backups -name "tesla_backup_*.sql.gz" -mtime +30 -delete
```

## 🎨 Customization

### Adding New Charts
1. Add API endpoint in `app.py`
2. Add chart container in HTML template
3. Add JavaScript function to load chart data
4. Update dashboard initialization

### Adding New Metrics
1. Add columns to `TeslaData` model
2. Update `ingest_data` function to handle new fields
3. Add display elements to dashboard template
4. Update `updateStatusCards` or `updateAdditionalMetrics` functions

### Styling Customization
- Modify CSS classes in the HTML template
- Customize Plotly chart themes
- Add custom color schemes
- Implement dark/light mode toggle

## 🔒 Security Considerations

### Production Security
```python
# In production, use strong secret key
import secrets
app.config['SECRET_KEY'] = secrets.token_urlsafe(32)

# Use environment variables for sensitive data
app.config['TESLAFI_TOKEN'] = os.environ.get('TESLAFI_API_TOKEN')

# Enable CSRF protection
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect(app)

# Add rate limiting
from flask_limiter import Limiter
limiter = Limiter(app, key_func=lambda: 'global')
```

### API Security
- Use HTTPS in production
- Implement API rate limiting
- Add authentication for sensitive endpoints
- Validate and sanitize all inputs

## 🐛 Troubleshooting

### Common Issues

1. **TeslaFi API Rate Limits**
   - Check rate limit headers in API responses
   - Adjust ingestion frequency if needed
   - Implement exponential backoff

2. **Database Connection Issues**
   - Verify database credentials
   - Check firewall settings
   - Ensure database service is running

3. **Missing Data in Charts**
   - Check data ingestion logs
   - Verify database has data
   - Check for null values in queries

4. **Performance Issues**
   - Add database indexes
   - Implement query caching
   - Consider data archiving strategy

### Debug Mode
```bash
# Enable debug logging
export FLASK_DEBUG=1
python app.py
```

## 📚 Additional Resources

- [TeslaFi API Documentation](https://teslafi.com/api.php)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Plotly Documentation](https://plotly.com/python/)
- [TimescaleDB Documentation](https://docs.timescale.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is open source and available under the MIT License.
