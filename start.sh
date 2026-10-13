#!/bin/bash
# DIGIARMOR AI - Quick Start Script

echo "🛡️  DIGIARMOR AI - Starting..."
echo ""

# Check if MongoDB is running
if ! pgrep -x "mongod" > /dev/null; then
    echo "⚠️  MongoDB is not running. Start it with: mongod"
    echo "   Or use Atlas and set MONGO_URI in backend/.env"
    echo ""
fi

# Start Backend
echo "🔧 Starting Flask Backend..."
cd backend
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "📝 Created .env from template. Edit backend/.env with your settings."
fi

# Check virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
fi

python app.py &
BACKEND_PID=$!
echo "   Backend running on http://localhost:5000 (PID: $BACKEND_PID)"

# Start Frontend
cd ../frontend
echo ""
echo "⚛️  Starting React Frontend..."
npm start &
FRONTEND_PID=$!
echo "   Frontend running on http://localhost:3000 (PID: $FRONTEND_PID)"

echo ""
echo "✅ DIGIARMOR AI is running!"
echo "   Open: http://localhost:3000"
echo ""
echo "   Press Ctrl+C to stop all services"

# Wait and cleanup
trap "echo ''; echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
