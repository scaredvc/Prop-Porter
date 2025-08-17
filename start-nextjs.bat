@echo off
echo Starting Prop-Porter Next.js Development Server...
echo.
echo This will:
echo 1. Navigate to the frontend-nextjs directory
echo 2. Install dependencies (if not already installed)
echo 3. Start the development server
echo.
echo Press any key to continue...
pause >nul

echo.
echo Navigating to frontend-nextjs directory...
cd frontend-nextjs

echo.
echo Installing dependencies...
npm install

echo.
echo Starting development server...
echo The app will be available at: http://localhost:3000
echo.
echo Press Ctrl+C to stop the server
echo.
npm run dev 