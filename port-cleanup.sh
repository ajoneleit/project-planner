#!/bin/bash
# Port cleanup script for development environment
# Kills processes running on common development ports

set -e

echo "🧹 Cleaning up development ports..."

# Common development ports
PORTS=(3000 8000 8080 3001 5000 5173 4000)

for port in "${PORTS[@]}"; do
    echo "Checking port $port..."
    
    # Find processes using the port
    PIDS=$(lsof -ti :$port 2>/dev/null || true)
    
    if [ -n "$PIDS" ]; then
        echo "  🔥 Killing processes on port $port: $PIDS"
        echo $PIDS | xargs -r kill -9
        sleep 1
        
        # Verify the port is free
        if ! lsof -ti :$port >/dev/null 2>&1; then
            echo "  ✅ Port $port is now free"
        else
            echo "  ⚠️  Some processes may still be running on port $port"
        fi
    else
        echo "  ✅ Port $port is already free"
    fi
done

echo ""
echo "🎉 Port cleanup complete!"
echo ""
echo "Common development commands:"
echo "  Backend:  poetry run uvicorn app.main:app --reload --port 8000"
echo "  Frontend: cd web && npm run dev"
echo "  Docker:   docker run -p 8000:8000 planner-bot"