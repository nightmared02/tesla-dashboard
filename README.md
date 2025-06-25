# 🚗 Tesla Data Visualization Dashboard

A real-time Tesla vehicle data visualization dashboard with time series database storage, built with Flask and InfluxDB.

## ✨ Features

- **Real-time Tesla Data**: Live data from TeslaFi API
- **Metric Units**: European metric system (km, °C, bar)
- **Time Series Storage**: InfluxDB for efficient data storage
- **Interactive Charts**: Battery, temperature, charging, and tire pressure monitoring
- **Auto-refresh**: Real-time updates every 30 seconds
- **Responsive Design**: Works on desktop and mobile
- **Cloud Ready**: Easy deployment to Railway, Render, or any cloud platform

## 🏗️ Architecture

- **Backend**: Flask (Python)
- **Database**: InfluxDB (Time Series)
- **Frontend**: HTML/CSS/JavaScript with Plotly.js
- **Data Source**: TeslaFi API
- **Deployment**: Docker + GitHub Actions

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker (for InfluxDB)
- TeslaFi API token

### Local Development

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/tesla-dashboard.git
cd tesla-dashboard
```

2. **Start InfluxDB**
```bash
docker-compose up -d
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your TeslaFi API token
```

5. **Initialize database**
```bash
python init_db.py
```

6. **Run the application**
```bash
python tesla_vis.py
```

7. **Start data ingestion**
```bash
python tesla_vis_data_ingestion.py schedule
```

Visit `http://localhost:5001` to see your dashboard!

## 🌐 Deployment

### Option 1: Railway (Recommended)

1. Fork this repository
2. Sign up at [Railway.app](https://railway.app)
3. Connect your GitHub repository
4. Add environment variables in Railway dashboard
5. Deploy automatically on push to main

### Option 2: Render

1. Fork this repository
2. Sign up at [Render.com](https://render.com)
3. Create a new Web Service
4. Connect your GitHub repository
5. Set build command: `pip install -r requirements.txt`
6. Set start command: `gunicorn tesla_vis:app --bind 0.0.0.0:$PORT`

### Environment Variables

```bash
# TeslaFi API
TESLAFI_API_TOKEN=your_teslafi_token

# InfluxDB (for cloud deployment)
INFLUXDB_URL=https://your-influxdb-url
INFLUXDB_TOKEN=your_influxdb_token
INFLUXDB_ORG=your_org
INFLUXDB_BUCKET=tesla_data

# Flask
FLASK_APP=tesla_vis.py
FLASK_ENV=production
```

## 📊 Data Storage

This project uses **InfluxDB** for time series data storage, which provides:

- **Efficient Compression**: 90%+ disk space savings
- **Fast Queries**: Optimized for time-based data
- **Scalability**: Handles millions of data points
- **Retention Policies**: Automatic data cleanup

### Data Structure

Each Tesla data point is stored as a measurement with:
- **Tags**: vehicle_id, data_id
- **Fields**: battery_level, temperature, speed, etc.
- **Timestamp**: Automatic time indexing

## 🔧 Configuration

### Data Ingestion Interval
Modify `INGESTION_INTERVAL_MINUTES` in `.env` to change how often data is fetched.

### Chart Time Ranges
Adjust the `days` parameter in chart endpoints:
- Battery: 7 days
- Temperature: 7 days  
- Charging: 30 days
- Tire Pressure: 30 days

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [TeslaFi](https://www.teslafi.com/) for providing Tesla data API
- [InfluxData](https://www.influxdata.com/) for InfluxDB
- [Plotly](https://plotly.com/) for interactive charts

## 📞 Support

If you have questions or need help:
1. Check the [Issues](https://github.com/yourusername/tesla-dashboard/issues) page
2. Create a new issue with your question
3. Join our [Discussions](https://github.com/yourusername/tesla-dashboard/discussions)

---

**Note**: This project is not affiliated with Tesla, Inc. Use at your own risk. 