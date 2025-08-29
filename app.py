#!/usr/bin/env python3
"""
Flask Network Ping Monitor
Backend with parallel processing and background monitoring
"""

from flask import Flask, render_template, jsonify, request
import yaml
import subprocess
import platform
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from flask_cors import CORS # Import CORS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

class PingMonitor:
    def __init__(self, hosts_file='hosts.yaml'):
        self.hosts_file = hosts_file
        self.hosts = []
        self.host_info = {}  # Store host metadata (type, color, known_offline)
        self.results = {}
        self.config = {}
        self.is_running = False
        self.background_thread = None
        self.lock = threading.Lock()  # Thread safety for results
        
        # Load configuration
        self.load_config()
        
        # Start background monitoring
        self.start_background_monitoring()
        
    def load_config(self):
        """Load hosts and configuration from YAML file"""
        try:
            with open(self.hosts_file, 'r') as f:
                data = yaml.safe_load(f)
                logger.info(f"Raw YAML data: {data}")
                
                if data is None:
                    logger.error("YAML file is empty or contains only comments")
                    self.hosts = []
                    return
                    
                if not isinstance(data, dict):
                    logger.error(f"YAML data is not a dictionary, got: {type(data)}")
                    self.hosts = []
                    return
                
                # Parse hosts - support both old and new format
                hosts_data = data.get('hosts', [])
                self.hosts = []
                self.host_info = {}
                
                if hosts_data and isinstance(hosts_data[0], dict) and 'type' in hosts_data[0]:
                    # New format with tags and support known_offline
                    for group in hosts_data:
                        group_type = group.get('type', 'Unknown')
                        group_color = group.get('color', '#6c757d')
                        group_ips_entries = group.get('ips', [])
                        
                        for ip_entry in group_ips_entries:
                            ip = None
                            known_offline = False
                            
                            if isinstance(ip_entry, str):
                                ip = ip_entry
                                known_offline = False
                            elif isinstance(ip_entry, dict):
                                # Assuming dictionary format is {ip: {known_offline: true/false}}
                                # Take the first key as the IP
                                ip = list(ip_entry.keys())[0] 
                                ip_details = ip_entry[ip]
                                if isinstance(ip_details, dict):
                                    known_offline = ip_details.get('known_offline', False)
                            
                            if ip: # Only add if IP was successfully extracted
                                self.hosts.append(ip)
                                self.host_info[ip] = {
                                    'type': group_type,
                                    'color': group_color,
                                    'known_offline': known_offline
                                }
                        logger.info(f"Loaded {len(group_ips_entries)} hosts for type '{group_type}'")
                else:
                    # Old format - simple list (also supports mixed, where some ips are dicts)
                    for host_item in hosts_data:
                        ip = None
                        known_offline = False
                        if isinstance(host_item, str):
                            ip = host_item
                            known_offline = False
                        elif isinstance(host_item, dict):
                            # This handles the case where the top-level 'hosts' list directly contains dicts
                            # like - 10.48.9.61: {known_offline: true}
                            ip = list(host_item.keys())[0]
                            ip_details = host_item[ip]
                            if isinstance(ip_details, dict):
                                known_offline = ip_details.get('known_offline', False)
                                
                        if ip:
                            self.hosts.append(ip)
                            self.host_info[ip] = {
                                'type': 'Unknown', # Default type for old/mixed format if not specified
                                'color': '#6c757d', # Default color
                                'known_offline': known_offline
                            }
                
                self.config = data.get('config', {})
                logger.info(f"Total loaded {len(self.hosts)} hosts from {self.hosts_file}")
                
                # Initialize results with unknown status
                with self.lock:
                    for host in self.hosts:
                        if host not in self.results:
                            self.results[host] = {
                                'status': 'unknown',
                                'latency': None,
                                'timestamp': None,
                                'type': self.host_info[host]['type'],
                                'color': self.host_info[host]['color'],
                                'known_offline': self.host_info[host]['known_offline']
                            }
                
        except FileNotFoundError:
            logger.error(f"Configuration file {self.hosts_file} not found")
            self.hosts = []
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file: {e}")
            self.hosts = []
        except Exception as e:
            logger.error(f"Error loading hosts file: {e}")
            self.hosts = []
    
    def ping_host(self, host: str) -> Dict:
        """Ping a single host and return result"""
        system = platform.system().lower()
        
        # Get known_offline status from host_info
        known_offline_flag = self.host_info.get(host, {}).get('known_offline', False)
        
        try:
            if system == 'windows':
                cmd = ['ping', '-n', '1', '-w', '3000', host]  # 3 second timeout
            else:
                cmd = ['ping', '-c', '1', '-W', '3', host]    # 3 second timeout
            
            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                # Parse latency from output
                latency = self._parse_latency(result.stdout, system)
                
                # Determine status based on latency
                if latency is not None and latency <= 50:
                    status = 'green'
                elif latency is not None and latency > 50:
                    status = 'yellow'
                else:
                    status = 'green'  # Default if we can't parse latency but ping succeeded
                
                return {
                    'status': status,
                    'latency': latency,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'type': self.host_info.get(host, {}).get('type', 'Unknown'),
                    'color': self.host_info.get(host, {}).get('color', '#6c757d'),
                    'known_offline': known_offline_flag # Include known_offline in results
                }
            else:
                return {
                    'status': 'red',
                    'latency': None,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'type': self.host_info.get(host, {}).get('type', 'Unknown'),
                    'color': self.host_info.get(host, {}).get('color', '#6c757d'),
                    'known_offline': known_offline_flag # Include known_offline in results
                }
                
        except subprocess.TimeoutExpired:
            return {
                'status': 'red',
                'latency': None,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'type': self.host_info.get(host, {}).get('type', 'Unknown'),
                'color': self.host_info.get(host, {}).get('color', '#6c757d'),
                'known_offline': known_offline_flag # Include known_offline in results
            }
        except Exception as e:
            logger.debug(f"Error pinging {host}: {e}")
            return {
                'status': 'red',
                'latency': None,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'type': self.host_info.get(host, {}).get('type', 'Unknown'),
                'color': self.host_info.get(host, {}).get('color', '#6c757d'),
                'known_offline': known_offline_flag # Include known_offline in results
            }
    
    def _parse_latency(self, output: str, system: str) -> Optional[float]:
        """Parse latency from ping output"""
        try:
            output_lower = output.lower()
            
            if system == 'windows':
                # Look for "time=XXXms" or "time<1ms"
                lines = output_lower.split('\n')
                for line in lines:
                    if 'time=' in line:
                        time_part = line.split('time=')[1].split()[0]
                        if 'ms' in time_part:
                            return float(time_part.replace('ms', ''))
                    elif 'time<' in line:
                        # Handle "time<1ms"
                        return 1.0
            else:
                # Linux/macOS: look for "time=XX.X ms"
                lines = output_lower.split('\n')
                for line in lines:
                    if 'time=' in line:
                        time_part = line.split('time=')[1].split()[0]
                        return float(time_part)
        except (IndexError, ValueError) as e:
            logger.debug(f"Could not parse latency from output: {e}")
        
        return None
    
    def ping_all_hosts_parallel(self):
        """Ping all hosts in parallel using ThreadPoolExecutor"""
        if not self.hosts:
            return
        
        max_workers = min(30, len(self.hosts))  # Limit concurrent pings
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all ping tasks
            future_to_host = {executor.submit(self.ping_host, host): host for host in self.hosts}
            
            # Collect results as they complete
            for future in as_completed(future_to_host):
                host = future_to_host[future]
                try:
                    result = future.result()
                    with self.lock:
                        self.results[host] = result
                    logger.debug(f"{host}: {result['status']} ({result['latency']}ms)")
                except Exception as e:
                    logger.error(f"Error pinging {host}: {e}")
                    # Ensure known_offline is still present even on error
                    known_offline_flag = self.host_info.get(host, {}).get('known_offline', False)
                    with self.lock:
                        self.results[host] = {
                            'status': 'red',
                            'latency': None,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'type': self.host_info.get(host, {}).get('type', 'Unknown'),
                            'color': self.host_info.get(host, {}).get('color', '#6c757d'),
                            'known_offline': known_offline_flag
                        }
    
    def background_monitor(self):
        """Background thread function that continuously pings hosts"""
        logger.info("Background monitoring started")
        
        # Initial ping check
        self.ping_all_hosts_parallel()
        logger.info("Initial ping check completed")
        
        while self.is_running:
            try:
                time.sleep(30)  # Wait 30 seconds
                if self.is_running:  # Check again after sleep
                    logger.info("Running scheduled ping check...")
                    start_time = time.time()
                    self.ping_all_hosts_parallel()
                    elapsed = time.time() - start_time
                    logger.info(f"Ping check completed in {elapsed:.2f} seconds")
            except Exception as e:
                logger.error(f"Error in background monitoring: {e}")
                time.sleep(30)  # Wait before retrying
    
    def start_background_monitoring(self):
        """Start the background monitoring thread"""
        if not self.background_thread or not self.background_thread.is_alive():
            self.is_running = True
            self.background_thread = threading.Thread(target=self.background_monitor, daemon=True)
            self.background_thread.start()
            logger.info("Background monitoring thread started")
    
    def stop_background_monitoring(self):
        """Stop the background monitoring thread"""
        self.is_running = False
        if self.background_thread and self.background_thread.is_alive():
            self.background_thread.join(timeout=5)
            logger.info("Background monitoring thread stopped")
    
    def get_results_copy(self):
        """Get a thread-safe copy of current results"""
        with self.lock:
            results_copy = {}
            for host, result in self.results.items():
                result_copy = result.copy()
                
                is_known_offline_configured = result_copy.get('known_offline', False)

                # Determine if 'known' tag should be shown
                if result_copy['status'] == 'red' and is_known_offline_configured:
                    result_copy['show_known_tag'] = True
                    result_copy['show_unknown_tag'] = False # Ensure only one tag is shown
                # Determine if 'unknown' tag should be shown (offline but not known_offline)
                elif result_copy['status'] == 'red' and not is_known_offline_configured:
                    result_copy['show_known_tag'] = False
                    result_copy['show_unknown_tag'] = True 
                else:
                    result_copy['show_known_tag'] = False
                    result_copy['show_unknown_tag'] = False
                results_copy[host] = result_copy
            return results_copy
    
    def force_ping_all(self):
        """Force an immediate ping check (for manual triggers)"""
        logger.info("Manual ping check triggered")
        self.ping_all_hosts_parallel()

# Initialize monitor
monitor = PingMonitor()

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/api/hosts')
def get_hosts():
    """Return list of all hosts with their metadata"""
    hosts_with_info = []
    for host in monitor.hosts:
        host_data = {
            'ip': host,
            'type': monitor.host_info.get(host, {}).get('type', 'Unknown'),
            'color': monitor.host_info.get(host, {}).get('color', '#6c757d'),
            'known_offline': monitor.host_info.get(host, {}).get('known_offline', False) # Include known_offline
        }
        hosts_with_info.append(host_data)
    return jsonify(hosts_with_info)

@app.route('/api/ping-all')
def ping_all():
    """Force ping all hosts and return results"""
    monitor.force_ping_all()
    return jsonify(monitor.get_results_copy())

@app.route('/api/ping/<host>')
def ping_single(host):
    """Ping a single host"""
    if host in monitor.hosts:
        result = monitor.ping_host(host)
        with monitor.lock:
            monitor.results[host] = result
        return jsonify({host: result})
    else:
        return jsonify({'error': 'Host not found'}), 404

@app.route('/api/status')
def get_status():
    """Get current cached status of all hosts"""
    return jsonify(monitor.get_results_copy())

@app.route('/api/reload')
def reload_hosts():
    """Reload hosts from YAML file"""
    monitor.load_config()
    return jsonify({'message': f'Reloaded {len(monitor.hosts)} hosts'})

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'hosts_count': len(monitor.hosts),
        'monitoring_active': monitor.is_running,
        'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

# Cleanup on app shutdown
import atexit
atexit.register(monitor.stop_background_monitoring)

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=30500, debug=False)  # Turn off debug for production
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        monitor.stop_background_monitoring()
