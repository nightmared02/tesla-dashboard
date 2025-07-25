import os
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone
import json
import requests
from sqlalchemy import desc, text
import pytz
import threading
import time
from flask_wtf.csrf import CSRFProtect

# Force rebuild - 2025-06-26 00:15:00
app = Flask(__name__)

# Database configuration
# For local development, use SQLite
# For production, you can switch to PostgreSQL or MySQL
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///tesla_data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Set secret key for CSRF protection
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

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
    start_time = request.args.get('start_time', '00:00:00')
    end_time = request.args.get('end_time', '23:59:59')
    
    # Default to last hour if no dates provided
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        # Parse date strings and combine with time for precise filtering
        start_dt = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp <= end_dt
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
    start_time = request.args.get('start_time', '00:00:00')
    end_time = request.args.get('end_time', '23:59:59')
    
    # Default to last hour if no dates provided
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        # Parse date strings and combine with time for precise filtering
        start_dt = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp <= end_dt
        ).order_by(TeslaData.timestamp).all()
    
    if not data:
        return jsonify({'success': True, 'data': {'labels': [], 'outside': [], 'inside': []}})
    
    # Convert UTC timestamps to Europe/Sofia timezone
    sofia_tz = pytz.timezone('Europe/Sofia')
    labels = [d.timestamp.replace(tzinfo=timezone.utc).astimezone(sofia_tz).strftime('%Y-%m-%d %H:%M') for d in data]
    outside = [d.outside_temp for d in data]
    inside = [d.inside_temp for d in data]
    
    return jsonify({'success': True, 'data': {'labels': labels, 'outside': outside, 'inside': inside}})

@app.route('/api/charts/charging')
def charging_chart():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    start_time = request.args.get('start_time', '00:00:00')
    end_time = request.args.get('end_time', '23:59:59')
    
    # Default to last hour if no dates provided
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        # Parse date strings and combine with time for precise filtering
        start_dt = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp <= end_dt
        ).order_by(TeslaData.timestamp).all()
    
    if not data:
        return jsonify({'success': True, 'data': {'labels': [], 'charging_state': [], 'charge_rate': [], 'charger_power': []}})
    
    # Convert UTC timestamps to Europe/Sofia timezone
    sofia_tz = pytz.timezone('Europe/Sofia')
    labels = [d.timestamp.replace(tzinfo=timezone.utc).astimezone(sofia_tz).strftime('%Y-%m-%d %H:%M') for d in data]
    
    # Charging state (0/1), charge rate (kW), and charger power (kW)
    charging_state = []
    charge_rate = []
    charger_power = []
    
    for d in data:
        # Convert charging state to 0/1 - more robust logic
        charging_state_value = 0
        if d.charging_state:
            charging_state_lower = d.charging_state.lower()
            # Check for various charging states
            if any(state in charging_state_lower for state in ['charging', 'connected', 'complete']):
                charging_state_value = 1
            # Explicitly check for disconnected states
            elif any(state in charging_state_lower for state in ['disconnected', 'stopped']):
                charging_state_value = 0
            else:
                # If it's not a known charging state, default to 0
                charging_state_value = 0
        else:
            charging_state_value = 0
        
        charging_state.append(charging_state_value)
        
        # Use charge_rate (actual charging power in kW)
        charge_rate.append(d.charge_rate if d.charge_rate is not None else 0)
        
        # Use charger_power (maximum power capability in kW)
        charger_power.append(d.charger_power if d.charger_power is not None else 0)
    
    return jsonify({
        'success': True, 
        'data': {
            'labels': labels, 
            'charging_state': charging_state, 
            'charge_rate': charge_rate,
            'charger_power': charger_power
        }
    })

@app.route('/api/charts/tire_pressure')
def tire_pressure_chart():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    start_time = request.args.get('start_time', '00:00:00')
    end_time = request.args.get('end_time', '23:59:59')
    
    # Default to last hour if no dates provided
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        # Parse date strings and combine with time for precise filtering
        start_dt = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp <= end_dt
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
    start_time = request.args.get('start_time', '00:00:00')
    end_time = request.args.get('end_time', '23:59:59')
    
    # Default to last hour if no dates provided
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        # Parse date strings and combine with time for precise filtering
        start_dt = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp <= end_dt
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

@app.route('/api/ingest', methods=['POST'])
def ingest_data():
    """Handle data ingestion from both internal scheduler and external scripts"""
    print(f"[{datetime.now()}] /api/ingest endpoint called")
    print(f"[{datetime.now()}] Request method: {request.method}")
    print(f"[{datetime.now()}] Request headers: {dict(request.headers)}")
    print(f"[{datetime.now()}] Request is_json: {request.is_json}")
    
    try:
        # Check if data was sent in the request
        if request.is_json and request.get_json():
            print(f"[{datetime.now()}] External script sending data")
            # External script is sending data
            data = request.get_json()
            print(f"[{datetime.now()}] Received data_id: {data.get('data_id')}")
            
            # Check if data_id already exists to avoid duplicates
            existing = TeslaData.query.filter_by(data_id=data.get('data_id')).first()
            if existing:
                print(f"[{datetime.now()}] Data already exists (duplicate)")
                return jsonify({"status": "duplicate", "message": "Data already exists"})
            
            print(f"[{datetime.now()}] Creating new TeslaData record")
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
            print(f"[{datetime.now()}] Data stored successfully")
            
            return jsonify({"status": "success", "message": "Data stored successfully", "data_id": data.get('data_id')})
        else:
            print(f"[{datetime.now()}] Internal call - fetching from TeslaFi")
            # Internal call - fetch data from TeslaFi
            result = fetch_and_store_tesla_data()
            return jsonify({"success": True, "message": "Data ingestion completed", "result": result})
            
    except Exception as e:
        print(f"[{datetime.now()}] Error in ingest_data: {e}")
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/ingest/manual', methods=['GET'])
def manual_ingest():
    """Manual data ingestion endpoint (GET request for easy testing)"""
    try:
        print(f"[{datetime.now()}] Manual ingestion triggered")
        result = fetch_and_store_tesla_data()
        return jsonify({
            "success": True, 
            "message": "Manual data ingestion completed", 
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        print(f"[{datetime.now()}] Manual ingestion failed: {e}")
        return jsonify({
            "success": False, 
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/api/ingest/status', methods=['GET'])
def ingest_status():
    """Check the status of automatic data ingestion"""
    global scheduler_running, last_run_time, next_run_time, scheduler_thread
    
    try:
        status_info = {
            "status": "running" if scheduler_running else "stopped",
            "next_run": next_run_time.isoformat() if next_run_time else None,
            "last_run": last_run_time.isoformat() if last_run_time else None,
            "interval": "5 minutes",
            "thread_alive": scheduler_thread.is_alive() if scheduler_thread else False,
            "current_time": datetime.now().isoformat()
        }
        return jsonify(status_info)
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/api/ingest/start', methods=['POST'])
def start_ingestion():
    """Start the automatic data ingestion scheduler"""
    try:
        start_scheduler()
        return jsonify({
            "success": True,
            "message": "Scheduler started",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/api/ingest/stop', methods=['POST'])
def stop_ingestion():
    """Stop the automatic data ingestion scheduler"""
    try:
        stop_scheduler()
        return jsonify({
            "success": True,
            "message": "Scheduler stopped",
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

@app.route('/api/test-post', methods=['POST'])
def test_post():
    """Test endpoint to verify POST requests work"""
    print(f"[{datetime.now()}] Test POST endpoint called")
    print(f"[{datetime.now()}] Request headers: {dict(request.headers)}")
    print(f"[{datetime.now()}] Request data: {request.get_data()}")
    return jsonify({"status": "success", "message": "POST request received"})

@app.route('/api/ingest/test-scheduler', methods=['GET'])
def test_scheduler():
    """Test the scheduler function directly"""
    try:
        print(f"[{datetime.now()}] Testing scheduler function directly...")
        result = automatic_data_ingestion()
        return jsonify({
            "success": True,
            "message": "Scheduler function test completed",
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        print(f"[{datetime.now()}] ERROR in scheduler test: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/widget/<widget_name>')
def widget_detail(widget_name):
    """Render the detailed graph view for a specific widget"""
    # You can add logic here to validate widget_name or customize the page
    return render_template('widget_detail.html', widget_name=widget_name)

@app.route('/api/charts/climate')
def climate_chart():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    start_time = request.args.get('start_time', '00:00:00')
    end_time = request.args.get('end_time', '23:59:59')
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        start_dt = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp <= end_dt
        ).order_by(TeslaData.timestamp).all()
    sofia_tz = pytz.timezone('Europe/Sofia')
    labels = [d.timestamp.replace(tzinfo=timezone.utc).astimezone(sofia_tz).strftime('%Y-%m-%d %H:%M') for d in data]
    values = [1 if d.is_climate_on else 0 for d in data]
    return jsonify({'success': True, 'data': {'labels': labels, 'values': values}})

@app.route('/api/charts/vehicle_state')
def vehicle_state_chart():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    start_time = request.args.get('start_time', '00:00:00')
    end_time = request.args.get('end_time', '23:59:59')
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        start_dt = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp <= end_dt
        ).order_by(TeslaData.timestamp).all()
    sofia_tz = pytz.timezone('Europe/Sofia')
    labels = [d.timestamp.replace(tzinfo=timezone.utc).astimezone(sofia_tz).strftime('%Y-%m-%d %H:%M') for d in data]
    values = [1 if d.locked else 0 for d in data]
    return jsonify({'success': True, 'data': {'labels': labels, 'values': values}})

@app.route('/api/charts/sentry')
def sentry_chart():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    start_time = request.args.get('start_time', '00:00:00')
    end_time = request.args.get('end_time', '23:59:59')
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        start_dt = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp <= end_dt
        ).order_by(TeslaData.timestamp).all()
    sofia_tz = pytz.timezone('Europe/Sofia')
    labels = [d.timestamp.replace(tzinfo=timezone.utc).astimezone(sofia_tz).strftime('%Y-%m-%d %H:%M') for d in data]
    values = [1 if d.sentry_mode else 0 for d in data]
    return jsonify({'success': True, 'data': {'labels': labels, 'values': values}})

@app.route('/api/charts/valet')
def valet_chart():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    start_time = request.args.get('start_time', '00:00:00')
    end_time = request.args.get('end_time', '23:59:59')
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        start_dt = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp <= end_dt
        ).order_by(TeslaData.timestamp).all()
    sofia_tz = pytz.timezone('Europe/Sofia')
    labels = [d.timestamp.replace(tzinfo=timezone.utc).astimezone(sofia_tz).strftime('%Y-%m-%d %H:%M') for d in data]
    values = [1 if d.valet_mode else 0 for d in data]
    return jsonify({'success': True, 'data': {'labels': labels, 'values': values}})

@app.route('/api/charts/odometer')
def odometer_chart():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    start_time = request.args.get('start_time', '00:00:00')
    end_time = request.args.get('end_time', '23:59:59')
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        start_dt = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp <= end_dt
        ).order_by(TeslaData.timestamp).all()
    sofia_tz = pytz.timezone('Europe/Sofia')
    labels = [d.timestamp.replace(tzinfo=timezone.utc).astimezone(sofia_tz).strftime('%Y-%m-%d %H:%M') for d in data]
    values = [miles_to_km(d.odometer) for d in data]
    return jsonify({'success': True, 'data': {'labels': labels, 'values': values}})

@app.route('/api/charts/speed')
def speed_chart():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    start_time = request.args.get('start_time', '00:00:00')
    end_time = request.args.get('end_time', '23:59:59')
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        start_dt = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp <= end_dt
        ).order_by(TeslaData.timestamp).all()
    sofia_tz = pytz.timezone('Europe/Sofia')
    labels = [d.timestamp.replace(tzinfo=timezone.utc).astimezone(sofia_tz).strftime('%Y-%m-%d %H:%M') for d in data]
    values = [mph_to_kmh(d.speed) for d in data]
    return jsonify({'success': True, 'data': {'labels': labels, 'values': values}})

@app.route('/api/charts/location')
def location_chart():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    start_time = request.args.get('start_time', '00:00:00')
    end_time = request.args.get('end_time', '23:59:59')
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        start_dt = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp <= end_dt
        ).order_by(TeslaData.timestamp).all()
    sofia_tz = pytz.timezone('Europe/Sofia')
    labels = [d.timestamp.replace(tzinfo=timezone.utc).astimezone(sofia_tz).strftime('%Y-%m-%d %H:%M') for d in data]
    latitudes = [d.latitude for d in data]
    longitudes = [d.longitude for d in data]
    return jsonify({'success': True, 'data': {'labels': labels, 'latitudes': latitudes, 'longitudes': longitudes}})

@app.route('/api/charts/battery_range')
def battery_range_chart():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    start_time = request.args.get('start_time', '00:00:00')
    end_time = request.args.get('end_time', '23:59:59')
    
    # Default to last hour if no dates provided
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        # Parse date strings and combine with time for precise filtering
        start_dt = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp <= end_dt
        ).order_by(TeslaData.timestamp).all()
    
    if not data:
        return jsonify({'success': True, 'data': {'labels': [], 'battery_range': [], 'ideal_battery_range': [], 'est_battery_range': []}})
    
    # Convert UTC timestamps to Europe/Sofia timezone
    sofia_tz = pytz.timezone('Europe/Sofia')
    labels = [d.timestamp.replace(tzinfo=timezone.utc).astimezone(sofia_tz).strftime('%Y-%m-%d %H:%M') for d in data]
    
    # Convert battery ranges from miles to kilometers
    battery_range = [miles_to_km(d.battery_range) for d in data]
    ideal_battery_range = [miles_to_km(d.ideal_battery_range) for d in data]
    est_battery_range = [miles_to_km(d.est_battery_range) for d in data]
    
    return jsonify({
        'success': True, 
        'data': {
            'labels': labels,
            'battery_range': battery_range,
            'ideal_battery_range': ideal_battery_range,
            'est_battery_range': est_battery_range
        }
    })

@app.route('/api/charts/charging_details')
def charging_details_chart():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    start_time = request.args.get('start_time', '00:00:00')
    end_time = request.args.get('end_time', '23:59:59')
    
    # Default to last hour if no dates provided
    if not start_date or not end_date:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    else:
        # Parse date strings and combine with time for precise filtering
        start_dt = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        data = TeslaData.query.filter(
            TeslaData.timestamp >= start_dt,
            TeslaData.timestamp <= end_dt
        ).order_by(TeslaData.timestamp).all()
    
    if not data:
        return jsonify({'success': True, 'data': {'labels': [], 'charge_rate': [], 'charger_power': [], 'charger_voltage': [], 'charger_current': [], 'time_to_full': [], 'energy_added': []}})
    
    # Convert UTC timestamps to Europe/Sofia timezone
    sofia_tz = pytz.timezone('Europe/Sofia')
    labels = [d.timestamp.replace(tzinfo=timezone.utc).astimezone(sofia_tz).strftime('%Y-%m-%d %H:%M') for d in data]
    
    # Extract charging details
    charge_rate = [d.charge_rate if d.charge_rate is not None else 0 for d in data]
    charger_power = [d.charger_power if d.charger_power is not None else 0 for d in data]
    charger_voltage = [d.charger_voltage if d.charger_voltage is not None else 0 for d in data]
    charger_current = [d.charger_actual_current if d.charger_actual_current is not None else 0 for d in data]
    time_to_full = [d.time_to_full_charge if d.time_to_full_charge is not None else 0 for d in data]
    energy_added = [d.charge_energy_added if d.charge_energy_added is not None else 0 for d in data]
    
    return jsonify({
        'success': True, 
        'data': {
            'labels': labels,
            'charge_rate': charge_rate,
            'charger_power': charger_power,
            'charger_voltage': charger_voltage,
            'charger_current': charger_current,
            'time_to_full': time_to_full,
            'energy_added': energy_added
        }
    })

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
    with app.app_context():
        # You'll need to set your TeslaFi API token as an environment variable
        TESLAFI_API_TOKEN = os.environ.get('TESLAFI_API_TOKEN')
        
        if not TESLAFI_API_TOKEN:
            print(f"[{datetime.now()}] ERROR: TESLAFI_API_TOKEN not set")
            return {"status": "error", "message": "TESLAFI_API_TOKEN not set"}
        
        try:
            print(f"[{datetime.now()}] Fetching data from TeslaFi API...")
            # TeslaFi API endpoint (adjust URL based on your actual API endpoint)
            url = f"https://www.teslafi.com/feed.php?token={TESLAFI_API_TOKEN}&command=lastGood"
            response = requests.get(url, timeout=30)
            
            print(f"[{datetime.now()}] TeslaFi API response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"[{datetime.now()}] Successfully fetched data from TeslaFi (data_id: {data.get('data_id', 'unknown')})")
                
                # Check if data_id already exists to avoid duplicates
                existing = TeslaData.query.filter_by(data_id=data.get('data_id')).first()
                if existing:
                    print(f"[{datetime.now()}] Data already exists (duplicate data_id: {data.get('data_id')})")
                    return {"status": "duplicate", "message": "Data already exists"}
                
                print(f"[{datetime.now()}] Creating new TeslaData record...")
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
                
                print(f"[{datetime.now()}] SUCCESS: Data stored successfully with data_id: {data.get('data_id')}")
                return {"status": "success", "message": "Data stored successfully", "data_id": data.get('data_id')}
            else:
                print(f"[{datetime.now()}] ERROR: Failed to fetch data from TeslaFi API: HTTP {response.status_code}")
                print(f"[{datetime.now()}] Response text: {response.text}")
                return {"status": "error", "message": f"Failed to fetch data: {response.status_code}"}
                
        except requests.RequestException as e:
            print(f"[{datetime.now()}] ERROR: Request exception when fetching TeslaFi data: {e}")
            return {"status": "error", "message": f"Request error: {str(e)}"}
        except json.JSONDecodeError as e:
            print(f"[{datetime.now()}] ERROR: JSON decode error from TeslaFi API: {e}")
            return {"status": "error", "message": f"JSON decode error: {str(e)}"}
        except Exception as e:
            print(f"[{datetime.now()}] CRITICAL ERROR in fetch_and_store_tesla_data: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return {"status": "error", "message": str(e)}

# Global variables for scheduling
scheduler_thread = None
scheduler_running = False
last_run_time = None
next_run_time = None

def automatic_data_ingestion():
    """Automatically fetch and store Tesla data every 5 minutes"""
    try:
        print(f"[{datetime.now()}] Starting automatic data ingestion on Railway...")
        
        # Check if TESLAFI_API_TOKEN is set
        teslafi_token = os.environ.get('TESLAFI_API_TOKEN')
        if not teslafi_token:
            print(f"[{datetime.now()}] ERROR: TESLAFI_API_TOKEN not set")
            return {"status": "error", "message": "TESLAFI_API_TOKEN not set"}
        
        print(f"[{datetime.now()}] TeslaFi token available, fetching data...")
        result = fetch_and_store_tesla_data()
        print(f"[{datetime.now()}] Automatic data ingestion completed: {result}")
        
        # Log the result for debugging
        if result.get('status') == 'success':
            print(f"[{datetime.now()}] SUCCESS: Data ingested with data_id: {result.get('data_id')}")
        elif result.get('status') == 'duplicate':
            print(f"[{datetime.now()}] INFO: Data already exists (duplicate)")
        else:
            print(f"[{datetime.now()}] ERROR: Ingestion failed - {result}")
        
        return result
    except Exception as e:
        print(f"[{datetime.now()}] CRITICAL ERROR in automatic data ingestion: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

def scheduler_worker():
    """Background thread that runs data ingestion at exact 5-minute intervals"""
    global scheduler_running, last_run_time, next_run_time
    
    print(f"[{datetime.now()}] Scheduler worker started")
    scheduler_running = True
    
    with app.app_context():
        while scheduler_running:
            try:
                now = datetime.now()
                
                # Calculate next run time (at exact 5-minute boundaries)
                # Find the next 5-minute mark from now
                current_minute = now.minute
                current_second = now.second
                
                # Calculate minutes to next 5-minute boundary
                minutes_to_next = 5 - (current_minute % 5)
                if minutes_to_next == 5:
                    minutes_to_next = 0
                
                # If we're at the exact minute boundary and seconds are 0, run immediately
                if current_minute % 5 == 0 and current_second < 10:
                    print(f"[{datetime.now()}] At exact minute boundary, running immediately")
                    next_run = now
                else:
                    # Set next run time to exact minute boundary
                    next_run = now.replace(second=0, microsecond=0) + timedelta(minutes=minutes_to_next)
                
                next_run_time = next_run
                
                print(f"[{datetime.now()}] Current time: {now}")
                print(f"[{datetime.now()}] Next scheduled run: {next_run}")
                
                # Wait until next run time
                time_to_wait = (next_run - now).total_seconds()
                if time_to_wait > 0:
                    print(f"[{datetime.now()}] Waiting {time_to_wait:.1f} seconds until next run")
                    time.sleep(time_to_wait)
                
                # Execute data ingestion
                print(f"[{datetime.now()}] ===== EXECUTING SCHEDULED DATA INGESTION =====")
                last_run_time = datetime.now()
                
                # Check if TESLAFI_API_TOKEN is available
                teslafi_token = os.environ.get('TESLAFI_API_TOKEN')
                print(f"[{datetime.now()}] TESLAFI_API_TOKEN available: {bool(teslafi_token)}")
                
                result = automatic_data_ingestion()
                print(f"[{datetime.now()}] ===== SCHEDULED INGESTION RESULT: {result} =====")
                
                # Wait a bit before calculating next run time
                time.sleep(10)
                
            except Exception as e:
                print(f"[{datetime.now()}] CRITICAL ERROR in scheduler worker: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(60)  # Wait a minute before retrying

def start_scheduler():
    """Start the background scheduler thread"""
    global scheduler_thread, scheduler_running
    
    if scheduler_thread is None or not scheduler_thread.is_alive():
        scheduler_thread = threading.Thread(target=scheduler_worker, daemon=True)
        scheduler_thread.start()
        print(f"[{datetime.now()}] Scheduler thread started")
    else:
        print(f"[{datetime.now()}] Scheduler already running")

def stop_scheduler():
    """Stop the background scheduler thread"""
    global scheduler_running
    scheduler_running = False
    print(f"[{datetime.now()}] Scheduler stop requested")

# Start the scheduler when the app starts
print(f"[{datetime.now()}] Starting Tesla data ingestion scheduler...")
start_scheduler()

# Also run once immediately on startup
print(f"[{datetime.now()}] Running initial data ingestion...")
try:
    initial_result = automatic_data_ingestion()
    print(f"[{datetime.now()}] Initial data ingestion result: {initial_result}")
except Exception as e:
    print(f"[{datetime.now()}] ERROR in initial data ingestion: {e}")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # Uncomment the line below to test data ingestion
    # fetch_and_store_tesla_data()
    
    app.run(debug=True, host='0.0.0.0', port=5001)
