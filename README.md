# Prop-Porter

NBA Player Stat Predictor - AI-powered basketball analytics platform.

## 🏗️ Project Structure

```
Prop-Porter/
├── backend/               # Python Backend API
│   ├── api/              # Flask API code
│   │   ├── __init__.py   # Flask app initialization
│   │   ├── routes.py     # API endpoints
│   │   ├── server.py     # Server entry point
│   │   └── utils.py      # Database utilities
│   ├── core/             # Core backend modules
│   ├── data/             # Data handling modules
│   ├── ml/               # Machine learning code
│   ├── requirements.txt  # Python dependencies
│   ├── schema.sql       # Database schema
│   └── venv/            # Virtual environment
├── frontend-nextjs/       # Next.js React Frontend
│   ├── src/
│   │   ├── app/         # Next.js app router
│   │   ├── components/  # React components
│   │   └── lib/         # Utility libraries
│   ├── package.json     # Frontend dependencies
│   └── ...              # Next.js configuration files
├── docs/                 # Documentation and notes
├── scripts/              # Utility scripts
├── tests/                # Test files
├── player_points_predictor.pkl  # ML model file
└── venv/                 # Project virtual environment
```

## 🚀 Quick Start

### Frontend (Next.js)
```bash
cd frontend-nextjs
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000)

### Backend (Python)
```bash
cd backend
pip install -r requirements.txt
python api/server.py
```

## 🔧 Development

- **Frontend**: React + Next.js + TypeScript + Tailwind CSS
- **Backend**: Python API with ML models
- **Database**: SQL database with NBA player/team data

## 📚 Documentation

- See `docs/` folder for detailed migration notes and development guides
- API documentation available in backend code

## 🤝 Contributing

1. Frontend changes: Work in `frontend-nextjs/`
2. Backend changes: Work in `backend/`
3. Keep documentation updated in `docs/`

## 📝 License

[Your License Here]
