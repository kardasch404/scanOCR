import os
import json
import logging
import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Import our Elite ID engine
from scan_yolo import AdvancedIDAnalyzer

# Initialize FastAPI
app = FastAPI(
    title="Elite ID Scanner API",
    description="Autonomous Neural ID Extraction Engine",
    version="5.0.0-elite"
)

# 1. CORS Setup: This makes sure anyone from any domain/browser can access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the Analyzer globally so models stay loaded in memory
try:
    print("Initializing Elite ID Engine in API mode...")
    analyzer = AdvancedIDAnalyzer()
except Exception as e:
    print(f"CRITICAL ERROR: Failed to load AdvancedIDAnalyzer. Ensure models are present.\n{str(e)}")
    analyzer = None

# Configure logs directory
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

def setup_request_logger(log_file_path: Path):
    """Sets up a specific logger for a single image request"""
    logger = logging.getLogger(log_file_path.stem)
    logger.setLevel(logging.INFO)
    # Remove existing handlers to avoid duplicates
    if logger.hasHandlers():
        logger.handlers.clear()
        
    fh = logging.FileHandler(log_file_path, encoding='utf-8')
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger

@app.get("/")
def root():
    return {"status": "online", "message": "Elite ID Scanner API is running with Advanced Logging."}

@app.post("/scan", summary="Scan an ID Document Image")
async def scan_document(request: Request, file: UploadFile = File(...)):
    if not analyzer:
        raise HTTPException(status_code=503, detail="OCR Engine is not initialized")
        
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (JPEG/PNG).")
        
    try:
        # Create a unique folder for this request
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(file.filename)[0] if file.filename else "unknown"
        # Make the folder name safe for the file system
        safe_base_name = "".join([c if c.isalnum() else "_" for c in base_name])
        
        # Format: logs/rus_pass7_20260723_105030/
        session_folder = LOGS_DIR / f"{safe_base_name}_{timestamp_str}"
        session_folder.mkdir(parents=True, exist_ok=True)
        
        # Define paths for the 3 files (image, json, log)
        image_ext = os.path.splitext(file.filename)[1] or ".jpg"
        image_path = session_folder / f"{safe_base_name}{image_ext}"
        json_path = session_folder / f"{safe_base_name}.json"
        log_path = session_folder / f"{safe_base_name}.log"
        
        # Setup specific logger for this request
        req_logger = setup_request_logger(log_path)
        client_ip = request.client.host if request.client else "Unknown"
        
        req_logger.info(f"--- New Scan Request ---")
        req_logger.info(f"Client IP: {client_ip}")
        req_logger.info(f"Original File Name: {file.filename}")
        
        # Save uploaded file directly to the log folder
        contents = await file.read()
        with open(image_path, "wb") as f:
            f.write(contents)
        req_logger.info(f"Image saved locally to: {image_path}")
            
        print(f"\n[API] Received scan request for: {file.filename} -> saving to {session_folder}")
        
        # Analyze the image using the saved file path
        req_logger.info(f"Starting Elite ID analysis engine on {image_path.name}...")
        result = analyzer.analyze(str(image_path))
        req_logger.info(f"Analysis complete. Status: Success.")
        
        # Try to find a person's name in the result to log it
        extracted_name = "Unknown"
        if isinstance(result, dict):
            # Best guess for name fields (checks for common JSON keys)
            first_name = result.get('first_name', result.get('prenom', result.get('Given Names', result.get('nom_prenom', ''))))
            last_name = result.get('last_name', result.get('nom', result.get('Surname', '')))
            if first_name or last_name:
                extracted_name = f"{first_name} {last_name}".strip()
                req_logger.info(f"Extracted Person Name: {extracted_name}")
        
        # Save the JSON result locally
        with open(json_path, "w", encoding='utf-8') as jf:
            json.dump(result, jf, indent=4, ensure_ascii=False)
        req_logger.info(f"Extracted data successfully saved to: {json_path}")
        
        # Return the JSON result to the client
        return JSONResponse(content=result)
        
    except Exception as e:
        error_msg = f"Internal Server Error during scanning: {str(e)}"
        print(f"[API ERROR] {error_msg}")
        if 'req_logger' in locals():
            req_logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

if __name__ == "__main__":
    # Start the Uvicorn server on all network interfaces (0.0.0.0) at port 8000
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
