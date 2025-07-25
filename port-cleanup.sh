#\!/bin/bash

# Function to show what's using ports
show_ports() {
    echo "=== Ports in use ==="
    netstat -tulpn  < /dev/null |  grep -E ':(3000|3001|8000|8001)\s' || echo "No processes found on common ports"
    echo ""
    echo "=== Detailed port info ==="
    lsof -i :3000,3001,8000,8001 2>/dev/null || echo "No detailed info available"
}

# Function to kill processes on specific ports
kill_port() {
    local port=$1
    echo "Killing processes on port $port..."
    fuser -k ${port}/tcp 2>/dev/null || echo "No processes found on port $port"
}

# Show current usage
show_ports

echo ""
echo "Commands you can use:"
echo "  ./port-cleanup.sh show     - Show current port usage"
echo "  ./port-cleanup.sh kill 3000 - Kill processes on port 3000"
echo "  ./port-cleanup.sh killall   - Kill processes on all common ports"

case "$1" in
    "show")
        show_ports
        ;;
    "kill")
        if [ -n "$2" ]; then
            kill_port $2
        else
            echo "Usage: $0 kill <port_number>"
        fi
        ;;
    "killall")
        echo "Killing all processes on development ports..."
        kill_port 3000
        kill_port 3001
        kill_port 8000
        kill_port 8001
        echo "Done\!"
        ;;
    *)
        echo "Usage: $0 {show|kill <port>|killall}"
        ;;
esac
