# Anomaly Detection Service

## Project Structure
```
📦 Anomaly Detection Service
├── 📄 main.py              # 🆕 FastAPI application entry point (moved from app/)
├── 📄 requirements.txt     # Python dependencies
├── 📄 start.sh            # 🔄 Updated startup script
├── 📁 app/
│   ├── 📁 api/
│   │   └── 📁 v1/
│   │       └── 📄 endpoints.py
│   ├── 📁 config/
│   │   ├── 📄 logs.py
│   │   └── 📄 redis.py
│   ├── 📁 models/
│   │   └── 📄 anomaly.py
│   └── 📁 services/
│       └── 📄 anomalyDetector.py
└── 📁 venv/               # Virtual environment
```

## ✅ Changes Made

### 🔄 Merged run.py → main.py
- **Before**: Separate `run.py` and `app/main.py` files
- **After**: Single `main.py` at project root with all functionality

### 📁 Moved main.py to Root
- **Before**: `app/main.py` (required `python -m app.main`)
- **After**: `main.py` (simple `python main.py`)

### 🔧 Fixed Import Paths
- ✅ `app.core.config` → `app.config.logs`
- ✅ `app.core.redisClient` → `app.config.redis`

## 🚀 How to Run

### Method 1: Direct
```bash
python main.py
```

### Method 2: Startup Script
```bash
./start.sh
```

### Method 3: With Virtual Environment
```bash
source venv/bin/activate
python main.py
```

## 🎯 Benefits of the Move

1. **Simpler Execution** - No module syntax needed
2. **Industry Standard** - Common FastAPI pattern
3. **Better DX** - Easier for development and deployment
4. **Cleaner Root** - Single entry point at project root
