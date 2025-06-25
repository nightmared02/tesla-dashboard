import os
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone
import json
import requests
from sqlalchemy import desc
import plotly.graph_objs as go
import plotly.utils

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
            return jsonify(latest.to_dict())
        else:
            # Return a message indicating no data is available
            return jsonify({
                "message": "No data available",
                "timestamp": datetime.now().isoformat(),
                "database_url": app.config['SQLALCHEMY_DATABASE_URI'].replace('://', '://***:***@') if '://' in app.config['SQLALCHEMY_DATABASE_URI'] else app.config['SQLALCHEMY_DATABASE_URI']
            })
    except Exception as e:
        return jsonify({
            "error": str(e),
            "message": "Database connection error",
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/api/data/history')
def get_history_data():
    days = request.args.get('days', 7, type=int)
    since = datetime.utcnow() - timedelta(days=days)
    data = TeslaData.query.filter(TeslaData.timestamp >= since).order_by(TeslaData.timestamp).all()
    return jsonify([item.to_dict() for item in data])

@app.route('/api/charts/battery')
def battery_chart():
    days = request.args.get('days', 7, type=int)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    data = db.session.query(TeslaData.timestamp, TeslaData.battery_level, TeslaData.battery_range).filter(
        TeslaData.timestamp >= since, 
        TeslaData.battery_level.isnot(None)
    ).order_by(TeslaData.timestamp).all()
    
    timestamps = [item[0] for item in data]
    battery_levels = [item[1] for item in data]
    battery_ranges_km = [miles_to_km(item[2]) for item in data]
    
    fig = go.Figure()
    
    # Battery Level trace with detailed hover
    fig.add_trace(go.Scatter(
        x=timestamps, 
        y=battery_levels, 
        mode='lines+markers', 
        name='Battery Level (%)', 
        yaxis='y',
        hovertemplate='<b>Time:</b> %{x}<br>' +
                     '<b>Battery Level:</b> %{y:.1f}%<br>' +
                     '<extra></extra>',
        hoverinfo='all'
    ))
    
    # Battery Range trace with detailed hover
    fig.add_trace(go.Scatter(
        x=timestamps, 
        y=battery_ranges_km, 
        mode='lines+markers', 
        name='Battery Range (km)', 
        yaxis='y2',
        hovertemplate='<b>Time:</b> %{x}<br>' +
                     '<b>Range:</b> %{y:.1f} km<br>' +
                     '<extra></extra>',
        hoverinfo='all'
    ))
    
    fig.update_layout(
        title='Battery Level and Range Over Time',
        xaxis_title='Time',
        yaxis=dict(title='Battery Level (%)', side='left'),
        yaxis2=dict(title='Battery Range (km)', side='right', overlaying='y'),
        hovermode='x unified',
        hoverlabel=dict(bgcolor="white", font_size=12)
    )
    
    return jsonify(json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig)))

@app.route('/api/charts/temperature')
def temperature_chart():
    days = request.args.get('days', 7, type=int)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    data = db.session.query(TeslaData.timestamp, TeslaData.inside_temp, TeslaData.outside_temp).filter(
        TeslaData.timestamp >= since,
        TeslaData.inside_temp.isnot(None)
    ).order_by(TeslaData.timestamp).all()
    
    timestamps = [item[0] for item in data]
    inside_temps_c = [item[1] for item in data]  # Already in Celsius
    outside_temps_c = [item[2] for item in data]  # Already in Celsius
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=timestamps, 
        y=inside_temps_c, 
        mode='lines+markers', 
        name='Inside Temperature (°C)',
        hovertemplate='<b>Time:</b> %{x}<br>' +
                     '<b>Inside Temp:</b> %{y:.1f}°C<br>' +
                     '<extra></extra>',
        hoverinfo='all'
    ))
    
    fig.add_trace(go.Scatter(
        x=timestamps, 
        y=outside_temps_c, 
        mode='lines+markers', 
        name='Outside Temperature (°C)',
        hovertemplate='<b>Time:</b> %{x}<br>' +
                     '<b>Outside Temp:</b> %{y:.1f}°C<br>' +
                     '<extra></extra>',
        hoverinfo='all'
    ))
    
    fig.update_layout(
        title='Temperature Monitoring',
        xaxis_title='Time',
        yaxis_title='Temperature (°C)',
        hovermode='x unified',
        hoverlabel=dict(bgcolor="white", font_size=12)
    )
    
    return jsonify(json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig)))

@app.route('/api/charts/charging')
def charging_chart():
    days = request.args.get('days', 30, type=int)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    data = db.session.query(TeslaData.timestamp, TeslaData.charge_rate, TeslaData.charger_power).filter(
        TeslaData.timestamp >= since,
        TeslaData.charging_state == 'Charging'
    ).order_by(TeslaData.timestamp).all()
    
    timestamps = [item[0] for item in data]
    charge_rates_kmh = [mph_to_kmh(item[1]) for item in data]
    charger_powers = [item[2] for item in data]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=timestamps, 
        y=charge_rates_kmh, 
        mode='markers', 
        name='Charge Rate (km/h)',
        hovertemplate='<b>Time:</b> %{x}<br>' +
                     '<b>Charge Rate:</b> %{y:.1f} km/h<br>' +
                     '<extra></extra>',
        hoverinfo='all'
    ))
    
    fig.add_trace(go.Scatter(
        x=timestamps, 
        y=charger_powers, 
        mode='markers', 
        name='Charger Power (kW)', 
        yaxis='y2',
        hovertemplate='<b>Time:</b> %{x}<br>' +
                     '<b>Charger Power:</b> %{y:.1f} kW<br>' +
                     '<extra></extra>',
        hoverinfo='all'
    ))
    
    fig.update_layout(
        title='Charging Sessions',
        xaxis_title='Time',
        yaxis=dict(title='Charge Rate (km/h)', side='left'),
        yaxis2=dict(title='Charger Power (kW)', side='right', overlaying='y'),
        hovermode='x unified',
        hoverlabel=dict(bgcolor="white", font_size=12)
    )
    
    return jsonify(json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig)))

@app.route('/api/charts/tire_pressure')
def tire_pressure_chart():
    days = request.args.get('days', 30, type=int)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    data = db.session.query(
        TeslaData.timestamp, 
        TeslaData.tpms_front_left, 
        TeslaData.tpms_front_right,
        TeslaData.tpms_rear_left,
        TeslaData.tpms_rear_right
    ).filter(
        TeslaData.timestamp >= since,
        TeslaData.tpms_front_left.isnot(None)
    ).order_by(TeslaData.timestamp).all()
    
    timestamps = [item[0] for item in data]
    fl_pressure_bar = [psi_to_bar(item[1]) for item in data]
    fr_pressure_bar = [psi_to_bar(item[2]) for item in data]
    rl_pressure_bar = [psi_to_bar(item[3]) for item in data]
    rr_pressure_bar = [psi_to_bar(item[4]) for item in data]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=timestamps, 
        y=fl_pressure_bar, 
        mode='lines+markers', 
        name='Front Left',
        hovertemplate='<b>Time:</b> %{x}<br>' +
                     '<b>Front Left:</b> %{y:.2f} bar<br>' +
                     '<extra></extra>',
        hoverinfo='all'
    ))
    
    fig.add_trace(go.Scatter(
        x=timestamps, 
        y=fr_pressure_bar, 
        mode='lines+markers', 
        name='Front Right',
        hovertemplate='<b>Time:</b> %{x}<br>' +
                     '<b>Front Right:</b> %{y:.2f} bar<br>' +
                     '<extra></extra>',
        hoverinfo='all'
    ))
    
    fig.add_trace(go.Scatter(
        x=timestamps, 
        y=rl_pressure_bar, 
        mode='lines+markers', 
        name='Rear Left',
        hovertemplate='<b>Time:</b> %{x}<br>' +
                     '<b>Rear Left:</b> %{y:.2f} bar<br>' +
                     '<extra></extra>',
        hoverinfo='all'
    ))
    
    fig.add_trace(go.Scatter(
        x=timestamps, 
        y=rr_pressure_bar, 
        mode='lines+markers', 
        name='Rear Right',
        hovertemplate='<b>Time:</b> %{x}<br>' +
                     '<b>Rear Right:</b> %{y:.2f} bar<br>' +
                     '<extra></extra>',
        hoverinfo='all'
    ))
    
    fig.update_layout(
        title='Tire Pressure Monitoring',
        xaxis_title='Time',
        yaxis_title='Pressure (bar)',
        hovermode='x unified',
        hoverlabel=dict(bgcolor="white", font_size=12)
    )
    
    return jsonify(json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig)))

@app.route('/api/test')
def test_system():
    """Test endpoint to check system status and manually trigger data ingestion"""
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        
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
        return
    
    try:
        # TeslaFi API endpoint (adjust URL based on your actual API endpoint)
        url = f"https://www.teslafi.com/feed.php?token={TESLAFI_API_TOKEN}&command=lastGood"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            
            # Post to our ingest endpoint
            ingest_response = requests.post('http://localhost:5000/api/ingest', json=data)
            print(f"Data ingestion response: {ingest_response.json()}")
        else:
            print(f"Failed to fetch data: {response.status_code}")
            
    except Exception as e:
        print(f"Error fetching data: {e}")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # Uncomment the line below to test data ingestion
    # fetch_and_store_tesla_data()
    
    app.run(debug=True, host='0.0.0.0', port=5001)
