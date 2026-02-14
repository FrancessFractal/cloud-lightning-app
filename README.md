# Weather App

A React frontend + Python (Flask) backend starter project.

## Project Structure

```
weather-app/
├── backend/          # Python Flask API
│   ├── app.py
│   ├── requirements.txt
│   └── venv/
├── frontend/         # React (Vite) app
│   ├── src/
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## Getting Started

### Backend

```bash
cd backend
source venv/bin/activate
python app.py
```

The API runs on **http://localhost:5000**.

### Frontend

```bash
cd frontend
npm run dev
```

The app runs on **http://localhost:3000** and proxies `/api` requests to the backend.

## API Endpoints

| Method | Path         | Description          |
|--------|--------------|----------------------|
| GET    | `/api/hello` | Returns a greeting   |
