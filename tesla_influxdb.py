#!/usr/bin/env python3
"""
Tesla InfluxDB Integration
Handles time series data storage for Tesla metrics
"""

import os
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import logging

class TeslaInfluxDB:
    def __init__(self):
        self.url = os.environ.get('INFLUXDB_URL', 'http://localhost:8086')
        self.token = os.environ.get('INFLUXDB_TOKEN', 'tesla_token_123456')
        self.org = os.environ.get('INFLUXDB_ORG', 'tesla_org')
        self.bucket = os.environ.get('INFLUXDB_BUCKET', 'tesla_data')
        
        self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def store_tesla_data(self, data):
        """Store Tesla data as time series points"""
        try:
            # Create measurement point
            point = Point("tesla_vehicle") \
                .tag("vehicle_id", "tesla_001") \
                .tag("data_id", str(data.get('data_id', ''))) \
                .field("battery_level", data.get('battery_level')) \
                .field("battery_range_km", data.get('battery_range_km')) \
                .field("inside_temp_c", data.get('inside_temp_c')) \
                .field("outside_temp_c", data.get('outside_temp_c')) \
                .field("speed_kmh", data.get('speed_kmh')) \
                .field("odometer_km", data.get('odometer_km')) \
                .field("charge_rate_kmh", data.get('charge_rate_kmh')) \
                .field("charger_power_kw", data.get('charger_power')) \
                .field("tpms_fl_bar", data.get('tpms_front_left_bar')) \
                .field("tpms_fr_bar", data.get('tpms_front_right_bar')) \
                .field("tpms_rl_bar", data.get('tpms_rear_left_bar')) \
                .field("tpms_rr_bar", data.get('tpms_rear_right_bar')) \
                .field("state", data.get('state', '')) \
                .field("charging_state", data.get('charging_state', '')) \
                .field("location", data.get('location', '')) \
                .time(datetime.now(timezone.utc))
            
            # Write to InfluxDB
            self.write_api.write(bucket=self.bucket, record=point)
            self.logger.info(f"Data stored in InfluxDB: {data.get('data_id', 'unknown')}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error storing data in InfluxDB: {e}")
            return False
    
    def get_latest_data(self):
        """Get the latest Tesla data point"""
        try:
            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: -1h)
                |> filter(fn: (r) => r["_measurement"] == "tesla_vehicle")
                |> last()
            '''
            
            result = self.query_api.query(query)
            
            if result:
                # Convert Flux result to dictionary
                data = {}
                for table in result:
                    for record in table.records:
                        field = record.get_field()
                        value = record.get_value()
                        data[field] = value
                
                return data
            return None
            
        except Exception as e:
            self.logger.error(f"Error querying InfluxDB: {e}")
            return None
    
    def get_history_data(self, hours=24):
        """Get historical data for charts"""
        try:
            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: -{hours}h)
                |> filter(fn: (r) => r["_measurement"] == "tesla_vehicle")
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            '''
            
            result = self.query_api.query(query)
            
            if result:
                data_points = []
                for table in result:
                    for record in table.records:
                        data_points.append({
                            'timestamp': record.get_time(),
                            'battery_level': record.values.get('battery_level'),
                            'battery_range_km': record.values.get('battery_range_km'),
                            'inside_temp_c': record.values.get('inside_temp_c'),
                            'outside_temp_c': record.values.get('outside_temp_c'),
                            'speed_kmh': record.values.get('speed_kmh'),
                            'charge_rate_kmh': record.values.get('charge_rate_kmh'),
                            'charger_power_kw': record.values.get('charger_power_kw'),
                            'tpms_fl_bar': record.values.get('tpms_fl_bar'),
                            'tpms_fr_bar': record.values.get('tpms_fr_bar'),
                            'tpms_rl_bar': record.values.get('tpms_rl_bar'),
                            'tpms_rr_bar': record.values.get('tpms_rr_bar'),
                        })
                
                return data_points
            return []
            
        except Exception as e:
            self.logger.error(f"Error querying historical data: {e}")
            return []
    
    def close(self):
        """Close InfluxDB connection"""
        self.client.close() 