@echo off
echo ========================================
echo Git Quick Commit and Push
echo ========================================
echo.

echo [1/3] Adding all changes...
git add .

echo.
echo [2/3] Committing changes...
git commit -m "updated_operator_service_map"

echo.
echo [3/3] Pushing to remote...
git push

echo.
echo ========================================
echo Done!
echo ========================================
pause
