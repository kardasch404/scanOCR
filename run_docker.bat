@echo off
echo Building Docker image...
docker build -t paddleocr-scanner .

echo.
echo Running OCR on cni.jpeg...
docker run --rm -v "%cd%:/app" paddleocr-scanner cni.jpeg

echo.
echo Done! Check cni_ocr.json for results.
pause
