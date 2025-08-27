# Network Ping Monitor

A Flask-based web application for real-time network monitoring with parallel ping processing and advanced filtering capabilities.

## Features

- **Real-time Monitoring**: Automatic background ping checks every 30 seconds
- **Parallel Processing**: Concurrent ping execution for fast results
- **Color-coded Status**: Visual indicators for network health
  - Green: Online (≤50ms latency)
  - Yellow: Slow (>50ms latency) 
  - Red: Offline/Unreachable
- **Advanced Filtering**: Filter hosts by type, status, or combinations
- **Host Categorization**: Organized host groups with custom colors and labels
- **Responsive Design**: Works on desktop and mobile devices

## Quick Start

### Prerequisites
- Python 3.7+
- pip package manager

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ping-monitoring-status-page
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure hosts in `hosts.yaml` (see Configuration section)

4. Run the application:
```bash
python app.py
```

5. Open your browser to `http://localhost:30500`

## Configuration

### Host Configuration (`hosts.yaml`)

Configure your network hosts using the following format:

```yaml
hosts:
  - type: "Proxmox"
    color: "#4CAF50"
    ips:
      - 10.49.9.18
      - 10.49.9.19
      # ... more IPs

  - type: "IPMI-R2" 
    color: "#2196F3"
    ips:
      - 10.48.9.16
      - 10.48.9.32
      # ... more IPs
```

**Configuration Options:**
- `type`: Display name for the host group
- `color`: Hex color code for the group tag
- `ips`: List of IP addresses to monitor

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main web interface |
| `/api/hosts` | GET | Get all configured hosts with metadata |
| `/api/ping-all` | GET | Force ping all hosts and return results |
| `/api/ping/<host>` | GET | Ping a specific host |
| `/api/status` | GET | Get cached status of all hosts |
| `/api/reload` | GET | Reload hosts from YAML file |
| `/api/health` | GET | Application health check |

## Filtering System

The web interface includes an advanced filtering system:

### Filter Types
1. **All**: Shows all hosts (default)
2. **Host Types**: Filter by configured host types (Proxmox, IPMI-R2, etc.)
3. **Status**: Filter by connection status (Online, Slow, Offline)
4. **Logic**: Choose AND/OR logic for combining filters

### Filter Behavior
- **"All" enabled**: Shows everything, disables other filters
- **"All" disabled**: Apply selected type and status filters
- **AND Logic**: Show hosts matching selected types AND selected statuses
- **OR Logic**: Show hosts matching selected types OR selected statuses
- **No filters selected**: Shows no hosts when "All" is disabled

## Technical Details

### Architecture
- **Backend**: Flask web server with background monitoring
- **Frontend**: Vanilla JavaScript with real-time updates
- **Concurrency**: ThreadPoolExecutor for parallel ping processing
- **Thread Safety**: Mutex locks for shared data structures

### Performance
- Maximum 30 concurrent ping operations
- 3-second timeout per ping operation
- Background monitoring every 30 seconds
- Real-time web updates without page refresh

### Platform Support
- **Linux/macOS**: Uses `ping -c 1 -W 3`
- **Windows**: Uses `ping -n 1 -w 3000`
- Cross-platform latency parsing

## File Structure

```
lweye/
├── app.py                 # Main Flask application
├── hosts.yaml           # Host configuration file
├── requirements.txt     # Python dependencies
├── templates/
│   └── index.html      # Web interface template
├── Dockerfile          # Docker container config
└── docker-compose.yml  # Docker Compose config
```

## Dependencies

```
Flask==2.3.3
PyYAML==6.0.1
```

## Docker Support

Build and run using Docker:

```bash
# Using docker-compose
docker-compose up -d

# Or build manually
docker build -t network-monitor .
docker run -p 30500:30500 network-monitor
```

## Usage Examples

### Manual Operations
- **Ping All**: Click "Start Ping Check" to force immediate ping of all hosts
- **Reload Configuration**: Click "Reload Hosts" to refresh from `hosts.yaml`
- **Filter by Type**: Disable "All", select specific host types
- **Filter by Status**: Choose Online/Slow/Offline status filters
- **Combine Filters**: Use AND/OR logic with multiple filter selections

### API Usage
```bash
# Get current status
curl http://localhost:30500/api/status

# Force ping all hosts  
curl http://localhost:30500/api/ping-all

# Check application health
curl http://localhost:30500/api/health
```

## Troubleshooting

### Common Issues

1. **No hosts loaded**
   - Check `hosts.yaml` syntax and file permissions
   - View logs for YAML parsing errors

2. **Ping failures**
   - Verify network connectivity
   - Check firewall rules for ICMP traffic
   - Ensure proper DNS resolution

3. **Performance issues**
   - Reduce number of concurrent hosts
   - Adjust ping timeout values
   - Check system resource usage

### Logs
Application logs are output to stdout with INFO level by default.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source. See license file for details.