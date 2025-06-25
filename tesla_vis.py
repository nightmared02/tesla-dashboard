import os
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone
import json
import requests
from sqlalchemy import desc, text
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from flask_wtf.csrf import CSRFProtect

# Force rebuild - 2025-06-26 00:15:00
app = Flask(__name__)

# Database configuration
# For local development, use SQLite
# For production, you can switch to PostgreSQL or MySQL
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///tesla_data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Initialize database on startup
with app.app_context():
    try:
        db.create_all()
        print("Database tables created successfully!")
    except Exception as e:
        print(f"Database initialization error: {e}")

# Unit conversion functions
def miles_to_km(miles):
    """Convert miles to kilometers"""
    if miles is None:
        return None
    return miles * 1.60934

def fahrenheit_to_celsius(fahrenheit):
    """Convert Fahrenheit to Celsius"""
    if fahrenheit is None:
        return None
    return (fahrenheit - 32) * 5/9

def psi_to_bar(psi):
    """Convert PSI to bar"""
    if psi is None:
        return None
    return psi * 0.0689476

def kw_to_kw(kw):
    """Keep kW as is (already metric)"""
    return kw

def mph_to_kmh(mph):
    """Convert mph to km/h"""
    if mph is None:
        return None
    return mph * 1.60934

# Database Model
class TeslaData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_id = db.Column(db.Integer, unique=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    date = db.Column(db.String(50))
    state = db.Column(db.String(20))
    battery_level = db.Column(db.Float)
    battery_range = db.Column(db.Float)
    ideal_battery_range = db.Column(db.Float)
    est_battery_range = db.Column(db.Float)
    usable_battery_level = db.Column(db.Float)
    charge_limit_soc = db.Column(db.Float)
    charging_state = db.Column(db.String(20))
    charge_rate = db.Column(db.Float)
    charger_power = db.Column(db.Float)
    charger_voltage = db.Column(db.Float)
    charger_actual_current = db.Column(db.Float)
    time_to_full_charge = db.Column(db.Float)
    charge_energy_added = db.Column(db.Float)
    charge_miles_added_rated = db.Column(db.Float)
    inside_temp = db.Column(db.Float)
    outside_temp = db.Column(db.Float)
    driver_temp_setting = db.Column(db.Float)
    passenger_temp_setting = db.Column(db.Float)
    is_climate_on = db.Column(db.Boolean)
    is_preconditioning = db.Column(db.Boolean)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    speed = db.Column(db.Float)
    heading = db.Column(db.Float)
    odometer = db.Column(db.Float)
    shift_state = db.Column(db.String(10))
    locked = db.Column(db.Boolean)
    sentry_mode = db.Column(db.Boolean)
    valet_mode = db.Column(db.Boolean)
    car_version = db.Column(db.String(50))
    tpms_front_left = db.Column(db.Float)
    tpms_front_right = db.Column(db.Float)
    tpms_rear_left = db.Column(db.Float)
    tpms_rear_right = db.Column(db.Float)
    location = db.Column(db.String(100))
    car_state = db.Column(db.String(20))
    max_range = db.Column(db.Float)
    sleep_number = db.Column(db.Integer)
    drive_number = db.Column(db.Integer)
    charge_number = db.Column(db.Integer)
    idle_number = db.Column(db.Integer)
    
    def to_dict(self):
        """Convert to dictionary with metric units"""
        base_dict = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        
        # Convert to metric units
        base_dict['battery_range_km'] = miles_to_km(self.battery_range)
        base_dict['ideal_battery_range_km'] = miles_to_km(self.ideal_battery_range)
        base_dict['est_battery_range_km'] = miles_to_km(self.est_battery_range)
        base_dict['charge_miles_added_rated_km'] = miles_to_km(self.charge_miles_added_rated)
        base_dict['inside_temp_c'] = self.inside_temp  # Already in Celsius
        base_dict['outside_temp_c'] = self.outside_temp  # Already in Celsius
        base_dict['driver_temp_setting_c'] = self.driver_temp_setting  # Already in Celsius
        base_dict['passenger_temp_setting_c'] = self.passenger_temp_setting  # Already in Celsius
        base_dict['speed_kmh'] = mph_to_kmh(self.speed)
        base_dict['odometer_km'] = miles_to_km(self.odometer)
        base_dict['max_range_km'] = miles_to_km(self.max_range)
        base_dict['tpms_front_left_bar'] = psi_to_bar(self.tpms_front_left)
        base_dict['tpms_front_right_bar'] = psi_to_bar(self.tpms_front_right)
        base_dict['tpms_rear_left_bar'] = psi_to_bar(self.tpms_rear_left)
        base_dict['tpms_rear_right_bar'] = psi_to_bar(self.tpms_rear_right)
        
        return base_dict

# Routes
@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/data/latest')
def get_latest_data():
    try:
        latest = TeslaData.query.order_by(desc(TeslaData.timestamp)).first()
        if latest:
            data_dict = latest.to_dict()
            # Add debugging info
            data_dict['debug'] = {
                'record_count': TeslaData.query.count(),
                'timestamp': datetime.now().isoformat(),
                'teslafi_token_set': bool(os.environ.get('TESLAFI_API_TOKEN'))
            }
            return jsonify(data_dict)
        else:
            # Return a message indicating no data is available
            return jsonify({
                "message": "No data available",
                "timestamp": datetime.now().isoformat(),
                "database_url": app.config['SQLALCHEMY_DATABASE_URI'].replace('://', '://***:***@') if '://' in app.config['SQLALCHEMY_DATABASE_URI'] else app.config['SQLALCHEMY_DATABASE_URI'],
                "debug": {
                    "record_count": 0,
                    "teslafi_token_set": bool(os.environ.get('TESLAFI_API_TOKEN'))
                }
            })
    except Exception as e:
        print(f"Error in get_latest_data: {e}")
        return jsonify({
            "error": str(e),
            "message": "Database connection error",
            "timestamp": datetime.now().isoformat(),
            "debug": {
                "exception_type": type(e).__name__,
                "teslafi_token_set": bool(os.environ.get('TESLAFI_API_TOKEN'))
            }
        }), 500

@app.route('/api/data/history')
def get_history_data():
    days = request.args.get('days', 7, type=int)
    since = datetime.utcnow() - timedelta(days=days)
    data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    return jsonify([item.to_dict() for item in data])

@app.route('/api/charts/battery')
def battery_chart():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Default to last hour if no dates provided
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        # Parse date strings and filter by date range
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=timezone.utc) + timedelta(days=1)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp < end_dt
        ).order_by(TeslaData.timestamp).all()
    
    if not data:
        return jsonify({'success': True, 'data': {'labels': [], 'values': []}})
    
    # Convert UTC timestamps to Europe/Sofia timezone
    sofia_tz = pytz.timezone('Europe/Sofia')
    labels = [d.timestamp.replace(tzinfo=timezone.utc).astimezone(sofia_tz).strftime('%Y-%m-%d %H:%M') for d in data]
    values = [d.battery_level for d in data]
    
    return jsonify({'success': True, 'data': {'labels': labels, 'values': values}})

@app.route('/api/charts/temperature')
def temperature_chart():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Default to last hour if no dates provided
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        # Parse date strings and filter by date range
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=timezone.utc) + timedelta(days=1)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp < end_dt
        ).order_by(TeslaData.timestamp).all()
    
    if not data:
        return jsonify({'success': True, 'data': {'labels': [], 'values': []}})
    
    # Convert UTC timestamps to Europe/Sofia timezone
    sofia_tz = pytz.timezone('Europe/Sofia')
    labels = [d.timestamp.replace(tzinfo=timezone.utc).astimezone(sofia_tz).strftime('%Y-%m-%d %H:%M') for d in data]
    values = [d.outside_temp for d in data]
    
    return jsonify({'success': True, 'data': {'labels': labels, 'values': values}})

@app.route('/api/charts/charging')
def charging_chart():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Default to last hour if no dates provided
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        # Parse date strings and filter by date range
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=timezone.utc) + timedelta(days=1)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp < end_dt
        ).order_by(TeslaData.timestamp).all()
    
    if not data:
        return jsonify({'success': True, 'data': {'labels': [], 'values': []}})
    
    # Convert UTC timestamps to Europe/Sofia timezone
    sofia_tz = pytz.timezone('Europe/Sofia')
    labels = [d.timestamp.replace(tzinfo=timezone.utc).astimezone(sofia_tz).strftime('%Y-%m-%d %H:%M') for d in data]
    values = [d.charge_rate for d in data]
    
    return jsonify({'success': True, 'data': {'labels': labels, 'values': values}})

@app.route('/api/charts/tire_pressure')
def tire_pressure_chart():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Default to last hour if no dates provided
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        # Parse date strings and filter by date range
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=timezone.utc) + timedelta(days=1)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp < end_dt
        ).order_by(TeslaData.timestamp).all()
    
    if not data:
        return jsonify({'success': True, 'data': {'labels': [], 'values': []}})
    
    # Convert UTC timestamps to Europe/Sofia timezone
    sofia_tz = pytz.timezone('Europe/Sofia')
    labels = [d.timestamp.replace(tzinfo=timezone.utc).astimezone(sofia_tz).strftime('%Y-%m-%d %H:%M') for d in data]
    
    # Convert tire pressures from psi to bar
    front_left = [psi_to_bar(d.tpms_front_left) for d in data]
    front_right = [psi_to_bar(d.tpms_front_right) for d in data]
    rear_left = [psi_to_bar(d.tpms_rear_left) for d in data]
    rear_right = [psi_to_bar(d.tpms_rear_right) for d in data]
    
    return jsonify({
        'success': True, 
        'data': {
            'labels': labels,
            'front_left': front_left,
            'front_right': front_right,
            'rear_left': rear_left,
            'rear_right': rear_right
        }
    })

@app.route('/api/charts/usage_stats')
def usage_stats_chart():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Default to last hour if no dates provided
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        # Parse date strings and filter by date range
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=timezone.utc) + timedelta(days=1)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp < end_dt
        ).order_by(TeslaData.timestamp).all()
    
    if not data:
        return jsonify({'success': True, 'data': {'labels': [], 'datasets': []}})
    
    # Analyze the data to detect sessions
    drive_sessions = 0
    charge_sessions = 0
    idle_sessions = 0
    sleep_sessions = 0
    
    # Group data by day to count sessions
    from collections import defaultdict
    daily_sessions = defaultdict(lambda: {'drive': 0, 'charge': 0, 'idle': 0, 'sleep': 0})
    
    for record in data:
        date_key = record.date
        if record.date:
            # Count based on state and charging status
            if record.charging_state and 'charging' in record.charging_state.lower():
                daily_sessions[date_key]['charge'] += 1
            elif record.shift_state and record.shift_state in ['D', 'R']:
                daily_sessions[date_key]['drive'] += 1
            elif record.state and 'sleep' in record.state.lower():
                daily_sessions[date_key]['sleep'] += 1
            else:
                daily_sessions[date_key]['idle'] += 1
    
    # Sum up all sessions
    for day_sessions in daily_sessions.values():
        drive_sessions += day_sessions['drive']
        charge_sessions += day_sessions['charge']
        idle_sessions += day_sessions['idle']
        sleep_sessions += day_sessions['sleep']
    
    # Calculate percentages
    total = drive_sessions + charge_sessions + idle_sessions + sleep_sessions
    if total > 0:
        drive_pct = (drive_sessions / total) * 100
        charge_pct = (charge_sessions / total) * 100
        idle_pct = (idle_sessions / total) * 100
        sleep_pct = (sleep_sessions / total) * 100
    else:
        drive_pct = charge_pct = idle_pct = sleep_pct = 0
    
    return jsonify({
        'success': True, 
        'data': {
            'labels': ['Drive', 'Charge', 'Idle', 'Sleep'],
            'datasets': [{
                'data': [drive_pct, charge_pct, idle_pct, sleep_pct],
                'backgroundColor': ['#3B82F6', '#10B981', '#F59E0B', '#6B7280'],
                'borderColor': ['#2563EB', '#059669', '#D97706', '#4B5563'],
                'borderWidth': 2
            }],
            'totals': {
                'drive': drive_sessions,
                'charge': charge_sessions,
                'idle': idle_sessions,
                'sleep': sleep_sessions
            }
        }
    })

@app.route('/api/test')
def test_system():
    """Test endpoint to check system status and manually trigger data ingestion"""
    try:
        # Check database connection using proper SQLAlchemy syntax
        db.session.execute(text('SELECT 1'))
        
        # Count existing records
        record_count = TeslaData.query.count()
        
        # Try to fetch latest data
        latest = TeslaData.query.order_by(desc(TeslaData.timestamp)).first()
        
        return jsonify({
            "status": "healthy",
            "database_connected": True,
            "record_count": record_count,
            "latest_record": latest.to_dict() if latest else None,
            "timestamp": datetime.now().isoformat(),
            "teslafi_token_set": bool(os.environ.get('TESLAFI_API_TOKEN'))
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "database_connected": False,
            "timestamp": datetime.now().isoformat()
        }), 500

csrf = CSRFProtect(app)

@csrf.exempt
@app.route('/api/ingest', methods=['POST'])
def ingest_data():
    """Manually trigger data ingestion"""
    try:
        result = fetch_and_store_tesla_data()
        return jsonify({"success": True, "message": "Data ingestion completed", "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/ingest/manual', methods=['GET'])
def manual_ingest():
    """Manual data ingestion endpoint (GET request for easy testing)"""
    try:
        result = fetch_and_store_tesla_data()
        return jsonify({
            "success": True, 
            "message": "Manual data ingestion completed", 
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False, 
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/api/add-test-data', methods=['GET'])
def add_test_data():
    """Add some test data for demonstration"""
    try:
        # Check if we already have data
        existing_count = TeslaData.query.count()
        if existing_count > 0:
            return jsonify({
                "success": True,
                "message": f"Database already has {existing_count} records",
                "timestamp": datetime.now().isoformat()
            })
        
        # Create test data
        test_data = TeslaData(
            data_id=999999,
            date="2025-06-25",
            state="online",
            battery_level=85.5,
            battery_range=280.0,
            ideal_battery_range=300.0,
            est_battery_range=275.0,
            usable_battery_level=85.0,
            charge_limit_soc=90.0,
            charging_state="Disconnected",
            charge_rate=0.0,
            charger_power=0.0,
            charger_voltage=0.0,
            charger_actual_current=0.0,
            time_to_full_charge=0.0,
            charge_energy_added=0.0,
            charge_miles_added_rated=0.0,
            inside_temp=22.0,
            outside_temp=25.0,
            driver_temp_setting=21.0,
            passenger_temp_setting=21.0,
            is_climate_on=False,
            is_preconditioning=False,
            latitude=40.7128,
            longitude=-74.0060,
            speed=0.0,
            heading=0.0,
            odometer=74565.0,
            shift_state="P",
            locked=True,
            sentry_mode=False,
            valet_mode=False,
            car_version="2024.20.1",
            tpms_front_left=42.0,
            tpms_front_right=42.0,
            tpms_rear_left=40.0,
            tpms_rear_right=40.0,
            location="New York, NY",
            car_state="online",
            max_range=350.0,
            sleep_number=1,
            drive_number=1,
            charge_number=1,
            idle_number=1
        )
        
        db.session.add(test_data)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Test data added successfully",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/api/init-db', methods=['GET'])
def init_database():
    """Initialize database tables manually"""
    try:
        with app.app_context():
            db.create_all()
            return jsonify({
                "success": True,
                "message": "Database tables created successfully",
                "timestamp": datetime.now().isoformat()
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

def safe_float(value):
    """Safely convert value to float, return None if not possible"""
    if value is None or value == '' or value == 'null':
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def safe_int(value):
    """Safely convert value to int, return None if not possible"""
    if value is None or value == '' or value == 'null':
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

def safe_bool(value):
    """Safely convert value to bool, return None if not possible"""
    if value is None or value == '' or value == 'null':
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on')
    return bool(value)

# Data ingestion script (can be run separately)
def fetch_and_store_tesla_data():
    """Function to fetch data from TeslaFi API and store in database"""
    # You'll need to set your TeslaFi API token as an environment variable
    TESLAFI_API_TOKEN = os.environ.get('TESLAFI_API_TOKEN')
    
    if not TESLAFI_API_TOKEN:
        print("Please set TESLAFI_API_TOKEN environment variable")
        return {"error": "TESLAFI_API_TOKEN not set"}
    
    try:
        # TeslaFi API endpoint (adjust URL based on your actual API endpoint)
        url = f"https://www.teslafi.com/feed.php?token={TESLAFI_API_TOKEN}&command=lastGood"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check if data_id already exists to avoid duplicates
            existing = TeslaData.query.filter_by(data_id=data.get('data_id')).first()
            if existing:
                return {"status": "duplicate", "message": "Data already exists"}
            
            # Create new record
            tesla_record = TeslaData(
                data_id=data.get('data_id'),
                date=data.get('Date'),
                state=data.get('state'),
                battery_level=safe_float(data.get('battery_level')),
                battery_range=safe_float(data.get('battery_range')),
                ideal_battery_range=safe_float(data.get('ideal_battery_range')),
                est_battery_range=safe_float(data.get('est_battery_range')),
                usable_battery_level=safe_float(data.get('usable_battery_level')),
                charge_limit_soc=safe_float(data.get('charge_limit_soc')),
                charging_state=data.get('charging_state'),
                charge_rate=safe_float(data.get('charge_rate')),
                charger_power=safe_float(data.get('charger_power')),
                charger_voltage=safe_float(data.get('charger_voltage')),
                charger_actual_current=safe_float(data.get('charger_actual_current')),
                time_to_full_charge=safe_float(data.get('time_to_full_charge')),
                charge_energy_added=safe_float(data.get('charge_energy_added')),
                charge_miles_added_rated=safe_float(data.get('charge_miles_added_rated')),
                inside_temp=safe_float(data.get('inside_temp')),
                outside_temp=safe_float(data.get('outside_temp')),
                driver_temp_setting=safe_float(data.get('driver_temp_setting')),
                passenger_temp_setting=safe_float(data.get('passenger_temp_setting')),
                is_climate_on=safe_bool(data.get('is_climate_on')),
                is_preconditioning=safe_bool(data.get('is_preconditioning')),
                latitude=safe_float(data.get('latitude')),
                longitude=safe_float(data.get('longitude')),
                speed=safe_float(data.get('speed')),
                heading=safe_float(data.get('heading')),
                odometer=safe_float(data.get('odometer')),
                shift_state=data.get('shift_state'),
                locked=safe_bool(data.get('locked')),
                sentry_mode=safe_bool(data.get('sentry_mode')),
                valet_mode=safe_bool(data.get('valet_mode')),
                car_version=data.get('car_version'),
                tpms_front_left=safe_float(data.get('tpms_front_left')),
                tpms_front_right=safe_float(data.get('tpms_front_right')),
                tpms_rear_left=safe_float(data.get('tpms_rear_left')),
                tpms_rear_right=safe_float(data.get('tpms_rear_right')),
                location=data.get('location'),
                car_state=data.get('carState'),
                max_range=safe_float(data.get('maxRange')),
                sleep_number=safe_int(data.get('sleepNumber')),
                drive_number=safe_int(data.get('driveNumber')),
                charge_number=safe_int(data.get('chargeNumber')),
                idle_number=safe_int(data.get('idleNumber'))
            )
            
            db.session.add(tesla_record)
            db.session.commit()
            
            return {"status": "success", "message": "Data stored successfully", "data_id": data.get('data_id')}
        else:
            return {"status": "error", "message": f"Failed to fetch data: {response.status_code}"}
            
    except Exception as e:
        db.session.rollback()
        return {"status": "error", "message": str(e)}

# Initialize scheduler for automatic data ingestion
scheduler = BackgroundScheduler()
scheduler.start()

def automatic_data_ingestion():
    """Automatically fetch and store Tesla data every minute"""
    try:
        # Use the local function instead of importing from separate module
        result = fetch_and_store_tesla_data()
        print(f"[{datetime.now()}] Automatic data ingestion completed: {result}")
    except Exception as e:
        print(f"[{datetime.now()}] Automatic data ingestion failed: {e}")

# Schedule automatic data ingestion every 1 minute
scheduler.add_job(
    func=automatic_data_ingestion,
    trigger=IntervalTrigger(minutes=1),
    id='tesla_data_ingestion',
    name='Fetch Tesla data every minute',
    replace_existing=True
)

print("Automatic data ingestion scheduled every 1 minute")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # Uncomment the line below to test data ingestion
    # fetch_and_store_tesla_data()
    
    app.run(debug=True, host='0.0.0.0', port=5001)
