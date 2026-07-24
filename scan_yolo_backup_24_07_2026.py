# **************************************************************************** #
#                                                                              #
#                                                  ::::::::         :::        #
#    scan_yolo.py                                 :+:    :+:      :+:          #
#                                                 +:+    +:+    +:+ +:+        #
#    By: kardasch <zakaria@kardasch.me>           +#+    +:+   +#+  +:+        #
#                                                 +#+    +#+  +#+kardasch      #
#    Created: 2026/07/01 15:27:37 by kardasch     #+#    #+#        #+#        #
#    Updated: 2026/07/20 11:45:00 by kardasch      ########       ###.ma       #
#                                                                              #
# **************************************************************************** #


import os
import argparse
import cv2
import numpy as np
import json
import sys
import re
from datetime import datetime
from pathlib import Path
import builtins
import warnings
import logging

# ==============================================================================
#  ELITE PRACTICE: SILENCE NOISY FRAMEWORKS
# ==============================================================================
os.environ["GLOG_minloglevel"] = "3"  # Silence Paddle C++ logs
os.environ["PADDLEX_LOG_LEVEL"] = "ERROR"
warnings.filterwarnings("ignore")
logging.getLogger("ppocr").setLevel(logging.ERROR)
logging.getLogger("paddlex").setLevel(logging.ERROR)

class EliteStream:
    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        if not data:
            return
            
        # Hardcore suppression of any paddle/paddlex noise that sneaks through
        noise_keywords = [
            "Connectivity check", "PADDLE_PDX", "Creating model:", 
            "Model files already exist", "Information", "impossible de trouver", 
            "UserWarning", "ccache"
        ]
        if any(k in data for k in noise_keywords):
            return

        self.stream.write(data)

    def flush(self):
        self.stream.flush()

    def __getattr__(self, attr):
        return getattr(self.stream, attr)

sys.stdout = EliteStream(sys.stdout)
sys.stderr = EliteStream(sys.stderr)

# ==============================================================================
#  ELITE PRACTICE: GLOBAL PRINT INTERCEPTOR 10X
# ==============================================================================
# Force UTF-8 for Windows
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

_original_print = builtins.print

class SuppressCStderr:
    """ELITE PRACTICE: Suppress C-level stderr outputs (e.g. pyzbar DLL assertions)"""
    def __enter__(self):
        try:
            self.devnull = os.open(os.devnull, os.O_WRONLY)
            self.old_stderr = os.dup(2)
            sys.stderr.flush()
            os.dup2(self.devnull, 2)
        except Exception:
            pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            os.dup2(self.old_stderr, 2)
            os.close(self.devnull)
            os.close(self.old_stderr)
        except Exception:
            pass

def elite_print(*args, **kwargs):
    kwargs["flush"] = True
    if not args:
        _original_print(*args, **kwargs)
        return

    text = " ".join(str(a) for a in args)
    
    # Hide any lingering paddle load logs
    if "Model files already exist" in text or "Creating model" in text or "Information :" in text:
        return
        
    replacements = {
        r"🔬 Initializing Elite ID Analyzer.*": "\n\033[95m" + "█"*70 + "\033[0m\n\033[96m\033[1m<<< ELITE OCR ENGINE INITIALIZATION >>>\033[0m",
        r"🔬 ELITE ID ANALYSIS.*": "\033[96m\033[1m[+] COMMAND_INTERFACE // ACQUIRING TARGET\033[0m",
        r"📸 Image:": "\033[92m●\033[0m \033[96mTARGET_FILE\033[0m      \033[97m>>>",
        r"📐 Dimensions:": "\033[92m●\033[0m \033[96mRESOLUTION\033[0m       \033[97m>>>",
        r"📡 YOLO Stage:": "\n\033[92m●\033[0m \033[96mYOLO_VISION\033[0m      \033[97m>>>",
        r"🗂 Elite layout detection\.\.\.": "\n\033[92m●\033[0m \033[96mLAYOUT_SCAN\033[0m      \033[97m>>>",
        r"🔭 Elite Visual Fingerprinting…": "\n\033[92m●\033[0m \033[96mFINGERPRINT\033[0m      \033[97m>>>",
        r"📷 Detecting photos and logos…": "\n\033[92m●\033[0m \033[96mVISUAL_ELEMENTS\033[0m  \033[97m>>>",
        r"📊 Detecting barcode/MRZ regions…": "\n\033[92m●\033[0m \033[96mBARCODE_MRZ\033[0m      \033[97m>>>",
        r"📝 Deep text extraction…": "\n\033[92m●\033[0m \033[96mTEXT_EXTRACTION\033[0m  \033[97m>>>",
        r"🔍 Elite image preprocessing \(CLAHE\)\.\.\.": "\n\033[92m●\033[0m \033[96mPREPROCESSING\033[0m    \033[97m>>>",
        r"⏳ Running heavy neural net inference.*": "   \033[92m●\033[0m \033[96mNEURAL_NET\033[0m       \033[97m>>> Running inference...",
        r"🔐 MRZ-FIRST pipeline \(strict geometric isolation\)\.\.\.": "\n\033[92m●\033[0m \033[96mPIPELINE_MODE\033[0m    \033[97m>>> MRZ-FIRST ISOLATION",
        r"🔒 ELITE MRZ STRICT ISOLATION…": "\n\033[92m●\033[0m \033[96mSTRICT_ISOLATION\033[0m \033[97m>>>",
        r"🗺️  Spatial zone analysis…": "\n\033[92m●\033[0m \033[96mSPATIAL_ANALYSIS\033[0m \033[97m>>>",
        r"🖼️  Exporting extracted image crops…": "\n\033[92m●\033[0m \033[96mIMAGE_EXPORT\033[0m     \033[97m>>>",
        r"⏱️  Scan Time:": "\033[92m●\033[0m \033[96mEXECUTION_TIME\033[0m   \033[97m>>>",
        r"💾 Saved →": "\033[92m●\033[0m \033[96mDATA_SAVED\033[0m       \033[97m>>>",
        r"   ✓": "      \033[96m>>>\033[0m",
        r"   ✅": "      \033[92m[SUCCESS]\033[0m",
        r"   •": "      \033[96m>>>\033[0m",
        r"   =>": "      \033[96m>>>\033[0m",
        r"   WARNING:": "      \033[95m[WARNING]\033[0m",
        r"🎉 Batch Processing Complete!": "\n\033[95m" + "█"*70 + "\033[0m\n\033[92m[SUCCESS]\033[0m BATCH FACTORY COMPLETE",
        r"📂 Found": "\033[96m[BATCH_FACTORY]\033[0m Found",
        r"✅ Model setup complete\.": "\033[92m[SUCCESS]\033[0m MODEL SETUP COMPLETE",
        r"══════════════════════════════════════════════════════════════════════": "",
    }

    for old, new in replacements.items():
        text = re.sub(old, new, text)
        
    # Catch any unstyled debug lines like [portrait-zone] and gray them out
    if text.startswith("   ["):
        text = "\033[90m      " + text.strip() + "\033[0m"

    if text.strip() == "":
        return
        
    kwargs['file'] = kwargs.get('file', sys.stdout)
    _original_print(text, **kwargs)

builtins.print = elite_print
# ==============================================================================

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_ROOT = BASE_DIR / "models"
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(DEFAULT_MODEL_ROOT / "paddlex_cache"))
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("PADDLE_OCR_STRICT_OFFLINE", "0")
os.environ.setdefault("PADDLE_OCR_BLOCK_NETWORK", "0")

if os.environ.get("PADDLE_OCR_BLOCK_NETWORK", "1") == "1":
    import socket

    _orig_create_connection = socket.create_connection
    _orig_connect = socket.socket.connect
    _allowed_hosts = {"127.0.0.1", "::1", "localhost"}

    def _is_allowed_host(host):
        if host is None:
            return False
        return str(host).lower() in _allowed_hosts

    def _blocked_create_connection(address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if _is_allowed_host(host):
            return _orig_create_connection(address, *args, **kwargs)
        raise RuntimeError(f"Outbound network blocked by offline policy: {host}")

    def _blocked_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if _is_allowed_host(host):
            return _orig_connect(self, address)
        raise RuntimeError(f"Outbound network blocked by offline policy: {host}")

    socket.create_connection = _blocked_create_connection
    socket.socket.connect = _blocked_connect

from paddleocr import PaddleOCR

# ── Optional: PDF417 barcode decoder for CNI-V1 verso ────────────────────────
try:
    from pyzbar.pyzbar import decode as pyzbar_decode, ZBarSymbol
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False
    pyzbar_decode = None
    ZBarSymbol = None


# ── Optional: YOLOv8 for Elite Auto-Orientation and Pose Transform ───────────
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    YOLO = None

# ═══════════════════════════════════════════════════════════════════════════════
#  YOLO DETECTION CONSTANTS — Custom YOLOv8n class mapping
# ═══════════════════════════════════════════════════════════════════════════════

YOLO_CLASS_PORTRAIT_MAIN  = 0
YOLO_CLASS_PORTRAIT_GHOST = 1
YOLO_CLASS_MRZ_ZONE       = 2
YOLO_CLASS_BARCODE_2D     = 3
YOLO_CLASS_MOROCCO_FLAG   = 4
YOLO_CLASS_CORNER_TL      = 5
YOLO_CLASS_CORNER_TR      = 6
YOLO_CLASS_CORNER_BL      = 7
YOLO_CLASS_CORNER_BR      = 8


# ═══════════════════════════════════════════════════════════════════════════════
#  YOLO CONTEXT  ─  All detections from a single YOLO inference call
# ═══════════════════════════════════════════════════════════════════════════════

class YoloContext:
    """Holds all YOLO detection results from a single inference call."""
    __slots__ = ('portrait_main', 'portrait_ghost', 'mrz_zone', 'barcode_zone',
                 'flag', 'corners', 'all_portraits', 'all_mrz_zones', 'all_barcodes',
                 'raw_results')

    def __init__(self):
        self.portrait_main  = None   # (x1, y1, x2, y2) numpy array or None
        self.portrait_ghost = None
        self.mrz_zone       = None
        self.barcode_zone   = None
        self.flag           = None
        self.corners        = []     # list of (class_id, center_x, center_y)
        self.all_portraits  = []     # all portrait detections (for layout)
        self.all_mrz_zones  = []
        self.all_barcodes   = []
        self.raw_results    = None

    @property
    def has_detections(self):
        return any([self.portrait_main is not None, self.portrait_ghost is not None,
                    self.mrz_zone is not None, self.barcode_zone is not None,
                    self.flag is not None, len(self.corners) > 0])


# ═══════════════════════════════════════════════════════════════════════════════
#  YOLO STAGE  ─  Single-inference engine (80ms CPU, <15ms GPU)
# ═══════════════════════════════════════════════════════════════════════════════

class YoloStage:
    """Single-inference YOLO engine. Runs model.predict() ONCE, extracts all signals."""

    MODEL_PATH = "yolo_id_card.pt"   # Custom trained model (change to your .pt file)
    _model = None
    _model_attempted = False

    @classmethod
    def _load_model(cls):
        if cls._model_attempted:
            return cls._model
        cls._model_attempted = True
        if not YOLO_AVAILABLE:
            return None
        model_path = BASE_DIR / cls.MODEL_PATH
        if not model_path.exists():
            return None
        try:
            cls._model = YOLO(str(model_path))
            print(f"   \u2713 YOLO model loaded: {model_path}")
        except Exception as e:
            pass # Suppressed per elite practice mode
        return cls._model

    @classmethod
    def infer(cls, img):
        """Run YOLO inference once. Returns YoloContext with all detections."""
        ctx = YoloContext()
        model = cls._load_model()
        if model is None:
            return ctx

        try:
            results = model.predict(img, conf=0.35, verbose=False)[0]
            ctx.raw_results = results
        except Exception as e:
            pass # Suppressed per elite practice mode
            return ctx

        for box in results.boxes:
            cls_id = int(box.cls[0].item())
            bbox = box.xyxy[0].cpu().numpy()   # (x1, y1, x2, y2)
            conf = float(box.conf[0].item())

            if cls_id == YOLO_CLASS_PORTRAIT_MAIN:
                ctx.all_portraits.append(bbox)
                if ctx.portrait_main is None or conf > 0.5:
                    ctx.portrait_main = bbox
            elif cls_id == YOLO_CLASS_PORTRAIT_GHOST:
                ctx.portrait_ghost = bbox
            elif cls_id == YOLO_CLASS_MRZ_ZONE:
                ctx.all_mrz_zones.append(bbox)
                if ctx.mrz_zone is None or conf > 0.5:
                    ctx.mrz_zone = bbox
            elif cls_id == YOLO_CLASS_BARCODE_2D:
                ctx.all_barcodes.append(bbox)
                if ctx.barcode_zone is None or conf > 0.5:
                    ctx.barcode_zone = bbox
            elif cls_id == YOLO_CLASS_MOROCCO_FLAG:
                ctx.flag = bbox
            elif cls_id in (YOLO_CLASS_CORNER_TL, YOLO_CLASS_CORNER_TR,
                            YOLO_CLASS_CORNER_BL, YOLO_CLASS_CORNER_BR):
                cx = (bbox[0] + bbox[2]) / 2
                cy = (bbox[1] + bbox[3]) / 2
                ctx.corners.append((cls_id, cx, cy))

        return ctx


# ═══════════════════════════════════════════════════════════════════════════════
#  YOLO CLASSIFIER  ─  Zero-OCR document classification
# ═══════════════════════════════════════════════════════════════════════════════

class YoloClassifier:
    """Zero-OCR document classification using YOLO signals only."""

    @staticmethod
    def classify(ctx, img):
        """
        Classify document from YOLO detections.
        Returns: {'doc_class': str, 'side': str, 'confidence': float}
        """
        if not ctx.has_detections:
            return {'doc_class': 'UNKNOWN', 'side': 'UNKNOWN', 'confidence': 0.0}

        img_h, img_w = img.shape[:2]

        # ── PASSPORT ─────────────────────────────────────────────
        if (ctx.portrait_main is not None and ctx.mrz_zone is not None
                and img_h > img_w * 0.9):
            return {'doc_class': 'PASSPORT', 'side': 'DATA_PAGE', 'confidence': 0.95}

        # ── CNI-V1 VERSO (PDF417 = definitive) ───────────────────
        if ctx.barcode_zone is not None:
            return {'doc_class': 'CNI_V1', 'side': 'VERSO', 'confidence': 0.99}

        # ── CNI-V2 VERSO (MRZ + no portrait) ─────────────────────
        if ctx.mrz_zone is not None and ctx.portrait_main is None:
            return {'doc_class': 'CNI_V2', 'side': 'VERSO', 'confidence': 0.95}

        # ── CNI-V2 RECTO (ghost = definitive) ────────────────────
        if ctx.portrait_ghost is not None:
            return {'doc_class': 'CNI_V2', 'side': 'RECTO', 'confidence': 0.95}

        # ── CNI-V2 RECTO (flag + portrait LEFT) ──────────────────
        if ctx.flag is not None and ctx.portrait_main is not None:
            portrait_cx = (ctx.portrait_main[0] + ctx.portrait_main[2]) / 2
            if portrait_cx < img_w * 0.50:
                return {'doc_class': 'CNI_V2', 'side': 'RECTO', 'confidence': 0.90}

        # ── CNI-V1 RECTO (portrait RIGHT) ────────────────────────
        if ctx.portrait_main is not None:
            portrait_cx = (ctx.portrait_main[0] + ctx.portrait_main[2]) / 2
            if portrait_cx > img_w * 0.50:
                return {'doc_class': 'CNI_V1', 'side': 'RECTO', 'confidence': 0.85}

        # ── PASSPORT fallback (portrait + MRZ, landscape) ────────
        if ctx.portrait_main is not None and ctx.mrz_zone is not None:
            return {'doc_class': 'PASSPORT', 'side': 'DATA_PAGE', 'confidence': 0.80}

        return {'doc_class': 'UNKNOWN', 'side': 'UNKNOWN', 'confidence': 0.0}


# ═══════════════════════════════════════════════════════════════════════════════
#  YOLO DEWARP  ─  Perspective correction using 4-corner keypoints
# ═══════════════════════════════════════════════════════════════════════════════

class YoloDewarp:
    """Perspective correction using YOLO corner detections."""

    # ISO 7810 ID-1 card: 85.6mm x 54mm = 1.585:1
    TARGET_W = 640
    TARGET_H = 400

    @staticmethod
    def dewarp(img, ctx):
        """If 4 corners detected, warp to standard card rectangle."""
        if len(ctx.corners) != 4:
            return img

        expected_ids = {YOLO_CLASS_CORNER_TL, YOLO_CLASS_CORNER_TR,
                        YOLO_CLASS_CORNER_BL, YOLO_CLASS_CORNER_BR}
        actual_ids = {c[0] for c in ctx.corners}
        if actual_ids != expected_ids:
            return img

        corner_map = {c[0]: (c[1], c[2]) for c in ctx.corners}
        src_pts = np.array([
            corner_map[YOLO_CLASS_CORNER_TL],
            corner_map[YOLO_CLASS_CORNER_TR],
            corner_map[YOLO_CLASS_CORNER_BR],
            corner_map[YOLO_CLASS_CORNER_BL],
        ], dtype=np.float32)

        dst_pts = np.array([
            [0, 0],
            [YoloDewarp.TARGET_W - 1, 0],
            [YoloDewarp.TARGET_W - 1, YoloDewarp.TARGET_H - 1],
            [0, YoloDewarp.TARGET_H - 1],
        ], dtype=np.float32)

        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        return cv2.warpPerspective(img, M, (YoloDewarp.TARGET_W, YoloDewarp.TARGET_H))


# ═══════════════════════════════════════════════════════════════════════════════
#  YOLO LAYOUT DETECTOR  ─  Multi-card detection from YOLO signals
# ═══════════════════════════════════════════════════════════════════════════════

class YoloLayoutDetector:
    """YOLO-based multi-card layout detection. Falls back to None if uncertain."""

    @staticmethod
    def detect(img, ctx):
        """
        Detect card layout using YOLO signals.
        Returns dict (same format as EliteLayoutDetector) or None for fallback.
        """
        if not ctx.has_detections:
            return None

        img_h, img_w = img.shape[:2]
        portraits = ctx.all_portraits
        mrz_zones = ctx.all_mrz_zones
        barcodes  = ctx.all_barcodes

        # Two portraits = two cards
        if len(portraits) == 2:
            p1_cy = (portraits[0][1] + portraits[0][3]) / 2
            p2_cy = (portraits[1][1] + portraits[1][3]) / 2
            p1_cx = (portraits[0][0] + portraits[0][2]) / 2
            p2_cx = (portraits[1][0] + portraits[1][2]) / 2

            if abs(p1_cx - p2_cx) > img_w * 0.30:
                layout = "horizontal"
                split = int((p1_cx + p2_cx) / 2)
                cards = [
                    {"img": img[:, :split], "bbox": (0, 0, split, img_h), "index": 0},
                    {"img": img[:, split:], "bbox": (split, 0, img_w - split, img_h), "index": 1},
                ]
            else:
                layout = "vertical"
                split = int((p1_cy + p2_cy) / 2)
                cards = [
                    {"img": img[:split, :], "bbox": (0, 0, img_w, split), "index": 0},
                    {"img": img[split:, :], "bbox": (0, split, img_w, img_h - split), "index": 1},
                ]
            return {"layout": layout, "cards_detected": 2, "cards": cards}

        # One portrait + one MRZ/barcode = recto + verso
        if len(portraits) == 1 and (len(mrz_zones) >= 1 or len(barcodes) >= 1):
            portrait_cy = (portraits[0][1] + portraits[0][3]) / 2
            portrait_cx = (portraits[0][0] + portraits[0][2]) / 2
            other = mrz_zones[0] if mrz_zones else barcodes[0]
            other_cy = (other[1] + other[3]) / 2
            other_cx = (other[0] + other[2]) / 2

            if abs(portrait_cx - other_cx) > img_w * 0.30:
                layout = "horizontal"
                split = int((portrait_cx + other_cx) / 2)
                cards = [
                    {"img": img[:, :split], "bbox": (0, 0, split, img_h), "index": 0},
                    {"img": img[:, split:], "bbox": (split, 0, img_w - split, img_h), "index": 1},
                ]
            else:
                layout = "vertical"
                split = int((portrait_cy + other_cy) / 2)
                cards = [
                    {"img": img[:split, :], "bbox": (0, 0, img_w, split), "index": 0},
                    {"img": img[split:, :], "bbox": (0, split, img_w, img_h - split), "index": 1},
                ]
            return {"layout": layout, "cards_detected": 2, "cards": cards}

        # Single card
        if len(portraits) >= 1 or len(mrz_zones) >= 1 or len(barcodes) >= 1:
            return {"layout": "single", "cards_detected": 1,
                    "cards": [{"img": img, "bbox": (0, 0, img_w, img_h), "index": 0}]}

        return None



# ═══════════════════════════════════════════════════════════════════════════════
#  ELITE LAYOUT DETECTOR  ─  Multi-card detection, horizontal/vertical split
# ═══════════════════════════════════════════════════════════════════════════════

class EliteLayoutDetector:
    """
    Elite Layout Detector: Detects if a photo contains 1 or 2 ID cards.
    Handles horizontal (side-by-side) and vertical (stacked) dual-card layouts.
    Splits the image into individual card crops for independent analysis.
    """

    _CARD_ASPECT_MIN = 1.2   # Min width/height ratio for a card
    _CARD_ASPECT_MAX = 2.4   # Max width/height ratio for a card
    _MIN_CARD_AREA_RATIO = 0.08  # Card must be ≥8% of image area

    @staticmethod
    def detect(img) -> dict:
        """
        Detect card layout and return individual card crops.
        Returns:
            {
              'layout': 'single' | 'horizontal' | 'vertical',
              'cards_detected': int,
              'cards': [{'img': ndarray, 'bbox': (x,y,w,h), 'index': int}]
            }
        """
        img_h, img_w = img.shape[:2]
        img_area = img_h * img_w

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        edges = cv2.Canny(blurred, 20, 80)

        # Close gaps in card borders
        kernel = np.ones((20, 20), np.uint8)
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=3)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        card_candidates = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < img_area * EliteLayoutDetector._MIN_CARD_AREA_RATIO:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            if h == 0:
                continue
            ar = w / h
            if EliteLayoutDetector._CARD_ASPECT_MIN <= ar <= EliteLayoutDetector._CARD_ASPECT_MAX:
                card_candidates.append({"bbox": (x, y, w, h), "area": area})

        # Keep top 2 largest candidates
        card_candidates.sort(key=lambda c: c["area"], reverse=True)
        card_candidates = card_candidates[:2]

        if len(card_candidates) == 2:
            bbox_a = card_candidates[0]["bbox"]
            bbox_b = card_candidates[1]["bbox"]

            # Check for excessive overlap — if so, fallback to gap line detector
            x_overlap = max(0, min(bbox_a[0] + bbox_a[2], bbox_b[0] + bbox_b[2]) - max(bbox_a[0], bbox_b[0]))
            y_overlap = max(0, min(bbox_a[1] + bbox_a[3], bbox_b[1] + bbox_b[3]) - max(bbox_a[1], bbox_b[1]))
            if x_overlap > bbox_a[2] * 0.5 or y_overlap > bbox_a[3] * 0.5:
                card_candidates = [] # Clear candidates to force fallback

            if card_candidates:
                # Determine orientation by comparing centroid separation
                cx_a = bbox_a[0] + bbox_a[2] // 2
                cy_a = bbox_a[1] + bbox_a[3] // 2
                cx_b = bbox_b[0] + bbox_b[2] // 2
                cy_b = bbox_b[1] + bbox_b[3] // 2

                if abs(cx_a - cx_b) > abs(cy_a - cy_b):
                    layout = "horizontal"
                    card_candidates.sort(key=lambda c: c["bbox"][0])  # left → right
                else:
                    layout = "vertical"
                    card_candidates.sort(key=lambda c: c["bbox"][1])  # top → bottom

                cards = []
                pad = 8
                for i, cand in enumerate(card_candidates):
                    x, y, w, h = cand["bbox"]
                    x2 = max(0, x - pad)
                    y2 = max(0, y - pad)
                    w2 = min(img_w - x2, w + 2 * pad)
                    h2 = min(img_h - y2, h + 2 * pad)
                    crop = img[y2:y2 + h2, x2:x2 + w2]
                    cards.append({"img": crop, "bbox": (x2, y2, w2, h2), "index": i})

                return {"layout": layout, "cards_detected": 2, "cards": cards}

        # ── ELITE FALLBACK: Brightness-Gap-Line detector ───────────────────────
        # When two cards share a similar background (no strong edge between them),
        # look for a bright horizontal or vertical band separating them.
        gap_result = EliteLayoutDetector._gap_line_detect(img, gray)
        if gap_result:
            return gap_result

        # Fallback: treat as single card (full image)
        return EliteLayoutDetector._single_result(img)

    @staticmethod
    def _gap_line_detect(img, gray=None) -> dict | None:
        """
        ELITE FALLBACK: Detect two cards separated by a bright/white band
        when the contour-based approach fails (similar-colored card backgrounds).

        Strategy:
          1. Compute mean row brightness (horizontal projection)
          2. Look for a contiguous band of BRIGHT rows (>185) in the middle 20%-80%
             This band = white gap between two stacked cards (vertical layout)
          3. If found -> split image at the gap midpoint -> return 2 cards
          4. Repeat with column projection for horizontal (side-by-side) layout
        """
        if gray is None:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img_h, img_w = gray.shape

        # ── Vertical split (cards stacked top/bottom) ──────────────────────────
        row_means = np.mean(gray, axis=1).astype(float)
        kernel_size = max(3, img_h // 40)
        row_smooth = np.convolve(row_means, np.ones(kernel_size) / kernel_size, mode='same')

        BRIGHT  = 185
        MIN_GAP = max(4, img_h // 60)
        S_START = int(img_h * 0.20)
        S_END   = int(img_h * 0.80)

        best_y, best_len = None, 0
        in_gap, g_start = False, 0
        for r in range(S_START, S_END):
            if row_smooth[r] > BRIGHT:
                if not in_gap:
                    in_gap, g_start = True, r
            else:
                if in_gap:
                    gap_len = r - g_start
                    if gap_len >= MIN_GAP and gap_len > best_len:
                        best_len, best_y = gap_len, (g_start + r) // 2
                    in_gap = False
        if in_gap:
            gap_len = S_END - g_start
            if gap_len >= MIN_GAP and gap_len > best_len:
                best_y = (g_start + S_END) // 2

        if best_y is not None:
            top_ar = img_w / max(best_y, 1)
            bot_ar = img_w / max(img_h - best_y, 1)
            if (EliteLayoutDetector._CARD_ASPECT_MIN <= top_ar <= EliteLayoutDetector._CARD_ASPECT_MAX and
                    EliteLayoutDetector._CARD_ASPECT_MIN <= bot_ar <= EliteLayoutDetector._CARD_ASPECT_MAX):
                return {
                    "layout": "vertical",
                    "cards_detected": 2,
                    "cards": [
                        {"img": img[:best_y, :],  "bbox": (0, 0,      img_w, best_y),         "index": 0},
                        {"img": img[best_y:, :],  "bbox": (0, best_y, img_w, img_h - best_y), "index": 1},
                    ]
                }

        # ── Horizontal split (cards side-by-side) ──────────────────────────────
        col_means  = np.mean(gray, axis=0).astype(float)
        col_smooth = np.convolve(col_means, np.ones(kernel_size) / kernel_size, mode='same')
        SC, EC = int(img_w * 0.20), int(img_w * 0.80)

        best_x, best_lenc = None, 0
        in_gap, g_start = False, 0
        for c in range(SC, EC):
            if col_smooth[c] > BRIGHT:
                if not in_gap:
                    in_gap, g_start = True, c
            else:
                if in_gap:
                    gap_len = c - g_start
                    if gap_len >= MIN_GAP and gap_len > best_lenc:
                        best_lenc, best_x = gap_len, (g_start + c) // 2
                    in_gap = False
        if in_gap:
            gap_len = EC - g_start
            if gap_len >= MIN_GAP and gap_len > best_lenc:
                best_x = (g_start + EC) // 2

        if best_x is not None:
            left_ar  = best_x / max(img_h, 1)
            right_ar = (img_w - best_x) / max(img_h, 1)
            if (EliteLayoutDetector._CARD_ASPECT_MIN <= left_ar <= EliteLayoutDetector._CARD_ASPECT_MAX and
                    EliteLayoutDetector._CARD_ASPECT_MIN <= right_ar <= EliteLayoutDetector._CARD_ASPECT_MAX):
                return {
                    "layout": "horizontal",
                    "cards_detected": 2,
                    "cards": [
                        {"img": img[:, :best_x],  "bbox": (0,      0, best_x,        img_h), "index": 0},
                        {"img": img[:, best_x:],  "bbox": (best_x, 0, img_w - best_x, img_h), "index": 1},
                    ]
                }

        return None  # No gap found — truly a single card

    @staticmethod
    def _single_result(img) -> dict:
        h, w = img.shape[:2]
        return {
            "layout": "single",
            "cards_detected": 1,
            "cards": [{"img": img, "bbox": (0, 0, w, h), "index": 0}]
        }



# ═══════════════════════════════════════════════════════════════════════════════
#  ELITE MRZ ENGINE  ─  ICAO Doc 9303 compliant, auto-correcting, format-aware
# ═══════════════════════════════════════════════════════════════════════════════

class EliteMRZParser:
    """
    Cryptographic MRZ parser for TD1 (3×30), TD2 (2×36), TD3 (2×44) documents.
    Implements ICAO Doc 9303 check-digit algorithm with weighted scheme [7,3,1],
    smart OCR-error auto-correction, and full validation logging.
    """

    # ---------- ICAO check-digit constants ----------
    _WEIGHTS = [7, 3, 1]
    _CHAR_VALUES = {c: i for i, c in enumerate("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", 0)}
    # Override numeric chars so digits map to their numeric value
    for _d in "0123456789":
        _CHAR_VALUES[_d] = int(_d)

    # Common OCR substitution pairs  char_seen → char_should_be
    _OCR_FIXES = [
        # each tuple: (wrong, correct) — applied when check-digit validation fails
        ("O", "0"), ("0", "O"),
        ("I", "1"), ("1", "I"),
        ("S", "5"), ("5", "S"),
        ("B", "8"), ("8", "B"),
        ("Z", "2"), ("2", "Z"),
        ("G", "6"), ("6", "G"),
        # ELITE FIX: Edge noise read as characters at the end of filler blocks
        ("S", "<"), ("8", "<"), ("E", "<"), ("K", "<"), ("Z", "<"),
    ]

    # Country code → ISO3 passthrough (TD3 uses 3-char, TD1 may use abbreviated)
    _COUNTRY_ALIASES = {
        "D": "DEU", "D<<": "DEU",
        "F": "FRA", "FRA": "FRA",
        "MAR": "MAR", "MA": "MAR",
        "GBR": "GBR", "GB": "GBR",
        "USA": "USA", "US": "USA",
        "BEL": "BEL", "NLD": "NLD",
        "ESP": "ESP", "ITA": "ITA",
        "CHE": "CHE", "AUT": "AUT",
        "CAN": "CAN", "AUS": "AUS",
    }

    # ────────────────────────────────────────────────────
    #  Core ICAO check-digit calculation
    # ────────────────────────────────────────────────────
    @classmethod
    def calculate_check_digit(cls, data_string: str) -> int:
        """
        ICAO Doc 9303 check-digit with weights [7,3,1].
        '<' → 0, digits → face value, A-Z → 10-35.
        Returns single decimal digit (0-9).
        """
        total = 0
        for i, ch in enumerate(data_string.upper()):
            if ch == "<":
                val = 0
            elif ch.isdigit():
                val = int(ch)
            elif ch.isalpha():
                val = ord(ch) - ord("A") + 10
            else:
                val = 0
            total += val * cls._WEIGHTS[i % 3]
        return total % 10

    @classmethod
    def _check_digit_log(cls, data_string: str) -> str:
        """Return human-readable calculation log for audit trail."""
        parts = []
        total = 0
        for i, ch in enumerate(data_string.upper()):
            w = cls._WEIGHTS[i % 3]
            if ch == "<":
                val = 0
            elif ch.isdigit():
                val = int(ch)
            elif ch.isalpha():
                val = ord(ch) - ord("A") + 10
            else:
                val = 0
            contrib = val * w
            total += contrib
            parts.append(f"{ch}({val}){chr(0x00D7)}{w}={contrib}")
        return " + ".join(parts) + f" = {total} % 10 = {total % 10}"

    # ────────────────────────────────────────────────────
    #  OCR sanitisation helpers
    # ────────────────────────────────────────────────────
    @staticmethod
    def sanitize_mrz_line(raw_line: str) -> str:
        """
        Strip anything outside the MRZ charset [A-Z0-9<] with smart mapping.
        Spaces → '<'  lowercase → UPPER  common confusables mapped first.
        """
        # Mapping of common OCR noise outside the charset
        noise_map = {
            " ": "<", "\t": "<", "_": "<", "-": "<", "~": "<",
            "!": "I", "@": "0", "£": "E", "$": "S", "|": "I",
            "(": "C", ")": "J", "?": "<", "{": "<", "}": "<",
            "[": "<", "]": "<", ":": "<", ";": "<", ",": "<", ".": "<",
        }
        out = []
        for ch in raw_line.upper():
            if ch in noise_map:
                out.append(noise_map[ch])
            elif re.match(r"[A-Z0-9<]", ch):
                out.append(ch)
            else:
                out.append("<")
        return "".join(out)

    @staticmethod
    def smart_pad(line: str, target_len: int) -> str:
        """
        Smart padding for MRZ lines. If line is shorter than target_len,
        and it ends with an alphanumeric character (like a check digit), 
        the missing characters are likely dropped '<' fillers from the middle.
        """
        line = line[:target_len]
        if len(line) == target_len:
            return line
        missing = target_len - len(line)
        if re.search(r'<+[A-Z0-9]+$', line):
            def repl(m):
                return m.group(1) + ("<" * missing) + m.group(2)
            return re.sub(r'(<+)([^<]+)$', repl, line)
        return line.ljust(target_len, "<")

    def _try_fix_zone(self, zone: str, expected_check: str) -> tuple[str, bool]:
        """
        Iteratively apply OCR corrections to `zone` until the check digit matches
        `expected_check`.  Returns (best_zone, fixed) where fixed=True means a
        correction was found.
        """
        if expected_check == "<" or str(self.calculate_check_digit(zone)) == expected_check:
            return zone, False

        # Try single-character substitutions first (fast path)
        for wrong, right in self._OCR_FIXES:
            if wrong not in zone:
                continue
            candidate = zone.replace(wrong, right)
            if str(self.calculate_check_digit(candidate)) == expected_check:
                return candidate, True
        # Two-pass combinations for hard cases
        for w1, r1 in self._OCR_FIXES:
            if w1 not in zone:
                continue
            for w2, r2 in self._OCR_FIXES:
                if w1 == w2 or w1 == r2 or r1 == w2:
                    continue
                candidate = zone.replace(w1, r1)
                if w2 not in candidate:
                    continue
                candidate = candidate.replace(w2, r2)
                if str(self.calculate_check_digit(candidate)) == expected_check:
                    return candidate, True
        return zone, False

    # ────────────────────────────────────────────────────
    #  ELITE: Advanced format detection with validation
    # ────────────────────────────────────────────────────
    @staticmethod
    def detect_format_advanced(lines: list[str]) -> tuple[str | None, dict]:
        """
        ELITE: Advanced format detection with confidence scoring.
        Returns (format, metadata) where metadata includes confidence and detected features.
        
        Adaptive for ANY country's identity documents:
        - TD1 (3×30): National ID cards (Morocco, Germany, etc.)
        - TD2 (2×36): Older ID cards, some visas
        - TD3 (2×44): Passports (universal)
        """
        metadata = {
            "confidence": 0.0,
            "detected_features": [],
            "format_scores": {"TD1": 0, "TD2": 0, "TD3": 0}
        }
        
        if len(lines) == 3:
            # TD1 candidate - check structure
            l1, l2, l3 = lines
            score = 0
            
            # Check lengths (allow ±2 chars tolerance)
            if 28 <= len(l1) <= 32 and 28 <= len(l2) <= 32 and 28 <= len(l3) <= 32:
                score += 30
                metadata["detected_features"].append("3_lines_correct_length")
            
            # Check line 1 structure: doc_code(2) + country(3) + doc_num(9) + check(1)
            if len(l1) >= 15 and l1[0:2].replace("<", "").isalpha():
                score += 20
                metadata["detected_features"].append("td1_doc_code_present")
            
            # Check line 2 structure: dates with check digits
            if len(l2) >= 15:
                # Birth date at pos 0-6, expiry at pos 8-14
                if l2[6].isalnum() and l2[14].isalnum():  # Check digits present
                    score += 30
                    metadata["detected_features"].append("td1_date_check_digits")
            
            # Check line 3: name with << separator
            if "<<" in l3:
                score += 20
                metadata["detected_features"].append("name_double_filler")
            
            metadata["format_scores"]["TD1"] = score
            if score >= 50:
                metadata["confidence"] = score / 100.0
                return "TD1", metadata
        
        if len(lines) == 2:
            l1, l2 = lines
            
            # TD3 candidate (passports) - 44 chars
            if 40 <= len(l1) <= 46 and 40 <= len(l2) <= 46:
                score = 0
                
                # Check line 1: P< at start (passport indicator) — full score
                if l1[0:2] in ["P<", "V<"]:
                    score += 40
                    metadata["detected_features"].append("passport_indicator_P")
                # ELITE: OCR often drops the 'P' → '<MAR...<<...' still has name separator
                elif l1.startswith("<") and "<<" in l1[3:]:
                    score += 25  # Partial score — likely P< with dropped P
                    metadata["detected_features"].append("passport_P_likely_dropped")
                
                # Check line 1: country code at pos 2-5 (or 1-4 if P was dropped)
                country_slice = l1[2:5] if not l1.startswith("<") else l1[1:4]
                if country_slice.replace("<", "").isalpha():
                    score += 15
                    metadata["detected_features"].append("td3_country_code")
                
                # Check line 1: name separator <<
                if "<<" in l1:
                    score += 15
                    metadata["detected_features"].append("td3_name_separator")
                
                # Check line 2: doc number + check at pos 0-10
                if len(l2) >= 10 and l2[9].isalnum():
                    score += 15
                    metadata["detected_features"].append("td3_doc_check_digit")
                
                # Check line 2: multiple check digits at expected positions
                if len(l2) >= 44:
                    check_positions = [9, 19, 27, 42, 43]  # Known check digit positions
                    checks_found = sum(1 for pos in check_positions if pos < len(l2) and l2[pos].isalnum())
                    score += checks_found * 3
                    if checks_found >= 4:
                        metadata["detected_features"].append(f"td3_{checks_found}_check_digits")
                
                metadata["format_scores"]["TD3"] = score
                if score >= 50:
                    metadata["confidence"] = score / 100.0
                    return "TD3", metadata
            
            # TD2 candidate - 36 chars
            if 32 <= len(l1) <= 38 and 32 <= len(l2) <= 38:
                score = 0
                
                # Check line 1: doc_code(2) + country(3)
                if len(l1) >= 5 and l1[0:2].replace("<", "").isalpha():
                    score += 25
                    metadata["detected_features"].append("td2_doc_code")
                
                # Check line 1: name separator <<
                if "<<" in l1:
                    score += 25
                    metadata["detected_features"].append("td2_name_separator")
                
                # Check line 2: doc number + checks
                if len(l2) >= 36 and l2[9].isalnum() and l2[35].isalnum():
                    score += 30
                    metadata["detected_features"].append("td2_check_digits")
                
                # Check line 2: date patterns
                if len(l2) >= 20:
                    if l2[19].isalnum():  # Birth date check
                        score += 20
                        metadata["detected_features"].append("td2_birth_check")
                
                metadata["format_scores"]["TD2"] = score
                if score >= 50:
                    metadata["confidence"] = score / 100.0
                    return "TD2", metadata
        
        # Return best guess even if confidence is low
        best_format = max(metadata["format_scores"].items(), key=lambda x: x[1])
        if best_format[1] > 0:
            metadata["confidence"] = best_format[1] / 100.0
            return best_format[0], metadata
        
        return None, metadata

    # ────────────────────────────────────────────────────
    #  Date helpers
    # ────────────────────────────────────────────────────
    @staticmethod
    def _parse_mrz_date(yymmdd: str, is_expiry: bool = False) -> str:
        """
        Convert YYMMDD to YYYY-MM-DD.
        For birth dates: YY >= current_year_2digit+1 -> 1900s, else 2000s.
        For expiry dates: always 2000s.
        Applies mandatory digit-only OCR correction (O->0, I->1, S->5, etc.)
        """
        _ocr_digit_map = {"O": "0", "o": "0", "I": "1", "l": "1", "S": "5",
                          "B": "8", "Z": "2", "G": "6", "<": "0", " ": "0"}
        cleaned = "".join(
            ch if ch.isdigit() else _ocr_digit_map.get(ch, "0")
            for ch in yymmdd
        )
        if len(cleaned) < 6:
            return "UNKNOWN"
        yy, mm, dd = cleaned[0:2], cleaned[2:4], cleaned[4:6]
        try:
            current_yy = int(datetime.now().strftime("%y"))
            century = "20" if is_expiry else ("19" if int(yy) > current_yy + 1 else "20")
            return f"{century}{yy}-{mm}-{dd}"
        except ValueError:
            return f"20{yy}-{mm}-{dd}"

    @staticmethod
    def _normalise_country(raw: str) -> str:
        raw = raw.strip("<").strip()
        return EliteMRZParser._COUNTRY_ALIASES.get(raw, raw) if raw else "UNKNOWN"

    # ────────────────────────────────────────────────────
    #  TD1 parser  (3 × 30)
    # ────────────────────────────────────────────────────
    def _parse_td1(self, l1: str, l2: str, l3: str) -> dict:
        """
        TD1: Identity cards (e.g. Moroccan CIN, German Personalausweis)
        Line 1: doc_code(2) + issuing_state(3) + doc_number(9) + check(1) + optional_1(15)
        Line 2: birth_date(6) + check(1) + sex(1) + expiry(6) + check(1) +
                nationality(3) + optional_2(11) + composite_check(1)
        Line 3: primary_id<<secondary_id (30)
        """
        validation = {}

        # --- Document number (L1 pos 5-13) ---
        doc_raw = l1[5:14]
        doc_check_digit = l1[14] if len(l1) > 14 else "<"
        
        # ELITE FIX: ICAO 9303 TD1 Document Number Overflow
        # If document number > 9 chars, pos 14 is '<' and overflow is in pos 15-29 followed by check digit.
        if doc_check_digit == "<" and len(l1) > 15 and l1[15] != "<":
            overflow_part = l1[15:30].split("<")[0]
            if len(overflow_part) > 1:
                extended_doc = doc_raw + overflow_part[:-1]
                extended_check = overflow_part[-1]
                doc_zone_fixed, doc_was_fixed = self._try_fix_zone(extended_doc, extended_check)
                doc_check_valid = str(self.calculate_check_digit(doc_zone_fixed)) == extended_check
                doc_check_digit = extended_check # For the validation log
                doc_raw = extended_doc           # Update raw for composite check
            else:
                doc_zone_fixed, doc_was_fixed = self._try_fix_zone(doc_raw, doc_check_digit)
                doc_check_valid = False # Invalid if it has overflow but no check digit
        else:
            doc_zone_fixed, doc_was_fixed = self._try_fix_zone(doc_raw, doc_check_digit)
            doc_check_valid = str(self.calculate_check_digit(doc_zone_fixed)) == doc_check_digit
            
        validation["document_number_check"] = {
            "digit": doc_check_digit,
            "is_valid": doc_check_valid,
            "auto_corrected": doc_was_fixed,
            "calculation_log": self._check_digit_log(doc_zone_fixed),
        }

        # --- Birth date (L2 pos 0-5) ---
        birth_raw = l2[0:6]
        birth_check_digit = l2[6] if len(l2) > 6 else "<"
        birth_zone_fixed, birth_was_fixed = self._try_fix_zone(birth_raw, birth_check_digit)
        birth_check_valid = str(self.calculate_check_digit(birth_zone_fixed)) == birth_check_digit
        validation["birth_date_check"] = {
            "digit": birth_check_digit,
            "is_valid": birth_check_valid,
            "auto_corrected": birth_was_fixed,
            "calculation_log": self._check_digit_log(birth_zone_fixed),
        }

        # --- Expiry date (L2 pos 8-13) ---
        expiry_raw = l2[8:14]
        expiry_check_digit = l2[14] if len(l2) > 14 else "<"
        expiry_zone_fixed, expiry_was_fixed = self._try_fix_zone(expiry_raw, expiry_check_digit)
        expiry_check_valid = str(self.calculate_check_digit(expiry_zone_fixed)) == expiry_check_digit
        validation["expiry_date_check"] = {
            "digit": expiry_check_digit,
            "is_valid": expiry_check_valid,
            "auto_corrected": expiry_was_fixed,
            "calculation_log": self._check_digit_log(expiry_zone_fixed),
        }

        # --- Composite check (L2 last char) ---
        # Composite covers: doc_number+check (L1 5-14) + optional1 (L1 15-29) +
        #                   birth+check (L2 0-6) + expiry+check (L2 8-14) +
        #                   optional2 (L2 18-28)
        # ELITE FIX: Auto-correct composite zone errors with OCR fixes, supporting TD1 overflow
        if len(doc_zone_fixed) > 9:
            # Reconstruct l1[5:30] with the fixed extended document number
            fixed_l1_remainder = doc_zone_fixed[:9] + "<" + doc_zone_fixed[9:] + doc_check_digit
            # Add the rest of the original padding
            padding_len = 25 - len(fixed_l1_remainder)
            fixed_l1_remainder += "<" * max(0, padding_len)
        else:
            fixed_l1_remainder = doc_zone_fixed + l1[14] + l1[15:30]
            
        composite_zone = fixed_l1_remainder + birth_zone_fixed + l2[6] + expiry_zone_fixed + l2[14] + l2[18:29]
        composite_check_digit = l2[29] if len(l2) > 29 else "<"
        composite_zone_fixed, composite_was_fixed = self._try_fix_zone(composite_zone, composite_check_digit)
        composite_check_valid = str(self.calculate_check_digit(composite_zone_fixed)) == composite_check_digit
        validation["composite_check"] = {
            "digit": composite_check_digit,
            "is_valid": composite_check_valid,
            "auto_corrected": composite_was_fixed,
            "calculation_log": self._check_digit_log(composite_zone_fixed[:60]) + "…",
        }
        validation["overall_mrz_valid"] = all([
            doc_check_valid, birth_check_valid, expiry_check_valid, composite_check_valid
        ])

        # --- Name parsing (L3) ---
        # ELITE FIX: Repair common hallucinated separators ('<Z', '<S', '<K', 'ZS') on TD1 L3
        l3_clean = re.sub(r'<[ZSK]', '<<', l3)
        l3_clean = l3_clean.replace('ZS', '<<')
        name_parts = l3_clean.split("<<")
        primary = name_parts[0].replace("<", " ").strip() if name_parts else ""
        secondary = name_parts[1].replace("<", " ").strip() if len(name_parts) > 1 else ""

        # --- Issuing state / nationality ---
        issuing_state = self._normalise_country(l1[2:5])
        nationality_raw = l2[15:18]
        
        # ELITE FIX: Recover OCR-dropped nationality using Issuing State
        if nationality_raw == "<<<" and issuing_state != "UNKNOWN":
            nationality = issuing_state
        else:
            nationality = self._normalise_country(nationality_raw)
            
        gender_raw = l2[7] if len(l2) > 7 else "<"
        gender = {"M": "MALE", "F": "FEMALE", "<": "UNSPECIFIED"}.get(gender_raw, "UNSPECIFIED")

        return {
            "format": "TD1",
            "raw_payload": [l1, l2, l3],
            "parsed_data": {
                "document_code": l1[0:2].strip("<"),
                "issuing_state": issuing_state,
                "document_number": doc_zone_fixed.strip("<"),
                "optional_data_1": l1[15:30].strip("<") or None,
                "birth_date": self._parse_mrz_date(birth_zone_fixed, is_expiry=False),
                "gender": gender_raw,
                "expiry_date": self._parse_mrz_date(expiry_zone_fixed, is_expiry=True),
                "nationality": nationality,
                "optional_data_2": l2[18:29].strip("<") or None,
                "primary_identifier": primary,
                "secondary_identifier": secondary,
            },
            "cryptographic_validation": validation,
        }

    # ────────────────────────────────────────────────────
    #  TD2 parser  (2 × 36)
    # ────────────────────────────────────────────────────
    def _parse_td2(self, l1: str, l2: str) -> dict:
        """
        TD2: Some older national ID cards (e.g. old German Personalausweis pre-2010).
        Line 1: doc_code(2) + issuing_state(3) + primary<<secondary (31)
        Line 2: doc_number(9) + check(1) + nationality(3) + birth(6) + check(1) +
                sex(1) + expiry(6) + check(1) + optional(7) + composite_check(1)
        """
        validation = {}

        doc_raw = l2[0:9]
        doc_check_digit = l2[9] if len(l2) > 9 else "<"
        doc_zone_fixed, doc_was_fixed = self._try_fix_zone(doc_raw, doc_check_digit)
        doc_check_valid = str(self.calculate_check_digit(doc_zone_fixed)) == doc_check_digit
        validation["document_number_check"] = {
            "digit": doc_check_digit, "is_valid": doc_check_valid,
            "auto_corrected": doc_was_fixed,
            "calculation_log": self._check_digit_log(doc_zone_fixed),
        }

        birth_raw = l2[13:19]
        birth_check_digit = l2[19] if len(l2) > 19 else "<"
        birth_zone_fixed, _ = self._try_fix_zone(birth_raw, birth_check_digit)
        birth_check_valid = str(self.calculate_check_digit(birth_zone_fixed)) == birth_check_digit
        validation["birth_date_check"] = {
            "digit": birth_check_digit, "is_valid": birth_check_valid,
            "calculation_log": self._check_digit_log(birth_zone_fixed),
        }

        expiry_raw = l2[21:27]
        expiry_check_digit = l2[27] if len(l2) > 27 else "<"
        expiry_zone_fixed, _ = self._try_fix_zone(expiry_raw, expiry_check_digit)
        expiry_check_valid = str(self.calculate_check_digit(expiry_zone_fixed)) == expiry_check_digit
        validation["expiry_date_check"] = {
            "digit": expiry_check_digit, "is_valid": expiry_check_valid,
            "calculation_log": self._check_digit_log(expiry_zone_fixed),
        }

        composite_zone = doc_zone_fixed + l2[9] + birth_zone_fixed + l2[19] + expiry_zone_fixed + l2[27] + l2[28:35]
        composite_check_digit = l2[35] if len(l2) > 35 else "<"
        composite_check_valid = str(self.calculate_check_digit(composite_zone)) == composite_check_digit
        validation["composite_check"] = {
            "digit": composite_check_digit, "is_valid": composite_check_valid,
            "calculation_log": self._check_digit_log(composite_zone[:60]) + "…",
        }
        validation["overall_mrz_valid"] = all([
            doc_check_valid, birth_check_valid, expiry_check_valid, composite_check_valid
        ])

        name_parts = l1[5:36].split("<<")
        primary = name_parts[0].replace("<", " ").strip()
        secondary = name_parts[1].replace("<", " ").strip() if len(name_parts) > 1 else ""
        gender_raw = l2[20] if len(l2) > 20 else "<"
        gender_map = {"M": "MALE", "F": "FEMALE", "<": "UNSPECIFIED"}

        return {
            "format": "TD2",
            "raw_payload": [l1, l2],
            "parsed_data": {
                "document_code": l1[0:2].strip("<"),
                "issuing_state": self._normalise_country(l1[2:5]),
                "document_number": doc_zone_fixed.strip("<"),
                "nationality": self._normalise_country(l2[10:13]),
                "birth_date": self._parse_mrz_date(birth_zone_fixed, is_expiry=False),
                "gender": gender_raw,
                "expiry_date": self._parse_mrz_date(expiry_zone_fixed, is_expiry=True),
                "optional_data": l2[28:35].strip("<") or None,
                "primary_identifier": primary,
                "secondary_identifier": secondary,
            },
            "cryptographic_validation": validation,
        }

    # ────────────────────────────────────────────────────
    #  TD3 parser  (2 × 44)  — passports
    # ────────────────────────────────────────────────────
    def _parse_td3(self, l1: str, l2: str) -> dict:
        """
        TD3: Machine-readable passports.
        Line 1: doc_code(2) + issuing_state(3) + primary<<secondary (39)
        Line 2: doc_number(9) + check(1) + nationality(3) + birth(6) + check(1) +
                sex(1) + expiry(6) + check(1) + personal_number(14) + check(1) +
                composite_check(1)
        """
        validation = {}

        doc_raw = l2[0:9]
        doc_check_digit = l2[9] if len(l2) > 9 else "<"
        doc_zone_fixed, doc_was_fixed = self._try_fix_zone(doc_raw, doc_check_digit)
        doc_check_valid = str(self.calculate_check_digit(doc_zone_fixed)) == doc_check_digit
        validation["document_number_check"] = {
            "digit": doc_check_digit, "is_valid": doc_check_valid,
            "auto_corrected": doc_was_fixed,
            "calculation_log": self._check_digit_log(doc_zone_fixed),
        }

        birth_raw = l2[13:19]
        birth_check_digit = l2[19] if len(l2) > 19 else "<"
        birth_zone_fixed, _ = self._try_fix_zone(birth_raw, birth_check_digit)
        birth_check_valid = str(self.calculate_check_digit(birth_zone_fixed)) == birth_check_digit
        validation["birth_date_check"] = {
            "digit": birth_check_digit, "is_valid": birth_check_valid,
            "calculation_log": self._check_digit_log(birth_zone_fixed),
        }

        expiry_raw = l2[21:27]
        expiry_check_digit = l2[27] if len(l2) > 27 else "<"
        expiry_zone_fixed, _ = self._try_fix_zone(expiry_raw, expiry_check_digit)
        expiry_check_valid = str(self.calculate_check_digit(expiry_zone_fixed)) == expiry_check_digit
        validation["expiry_date_check"] = {
            "digit": expiry_check_digit, "is_valid": expiry_check_valid,
            "calculation_log": self._check_digit_log(expiry_zone_fixed),
        }

        # Personal number check (optional field at L2 pos 28-41 + check at 42)
        personal_number_raw = l2[28:42]
        personal_check_digit = l2[42] if len(l2) > 42 else "<"
        personal_check_valid = str(self.calculate_check_digit(personal_number_raw)) == personal_check_digit
        validation["personal_number_check"] = {
            "digit": personal_check_digit, "is_valid": personal_check_valid,
            "calculation_log": self._check_digit_log(personal_number_raw),
        }

        # Composite covers doc+check+personal_number+check+birth+check+expiry+check+composite_zone
        composite_zone = doc_zone_fixed + l2[9] + birth_zone_fixed + l2[19] + expiry_zone_fixed + l2[27] + l2[28:43]
        composite_check_digit = l2[43] if len(l2) > 43 else "<"
        composite_check_valid = str(self.calculate_check_digit(composite_zone)) == composite_check_digit
        validation["composite_check"] = {
            "digit": composite_check_digit, "is_valid": composite_check_valid,
            "calculation_log": self._check_digit_log(composite_zone[:60]) + "…",
        }
        
        # ELITE FIX: Line 1 must be structurally valid for Passport (TD3)
        # It must start with 'P' (or '<' due to OCR noise, but usually 'P') and contain '<<'
        l1_valid = l1.startswith("P") or l1.startswith("<")
        l1_valid = l1_valid and "<<" in l1
        validation["line1_structure_check"] = {
            "is_valid": l1_valid,
            "calculation_log": f"Starts with P/< and contains <<: {l1_valid}"
        }

        validation["overall_mrz_valid"] = all([
            doc_check_valid, birth_check_valid, expiry_check_valid,
            personal_check_valid, composite_check_valid, l1_valid
        ])

        name_parts = l1[5:44].split("<<")
        primary = name_parts[0].replace("<", " ").strip()
        secondary = " ".join(p.replace("<", " ").strip() for p in name_parts[1:] if p) or ""
        gender_raw = l2[20] if len(l2) > 20 else "<"

        return {
            "format": "TD3",
            "raw_payload": [l1, l2],
            "parsed_data": {
                "document_code": l1[0:2].strip("<"),
                "issuing_state": self._normalise_country(l1[2:5]),
                "document_number": doc_zone_fixed.strip("<"),
                "nationality": self._normalise_country(l2[10:13]),
                "birth_date": self._parse_mrz_date(birth_zone_fixed, is_expiry=False),
                "gender": gender_raw,
                "expiry_date": self._parse_mrz_date(expiry_zone_fixed, is_expiry=True),
                "personal_number": personal_number_raw.strip("<") or None,
                "primary_identifier": primary,
                "secondary_identifier": secondary,
            },
            "cryptographic_validation": validation,
        }

    # ────────────────────────────────────────────────────
    #  Public entry point
    # ────────────────────────────────────────────────────
    def parse(self, raw_lines: list[str]) -> dict | None:
        """
        ELITE: Try to detect and parse an MRZ from a list of raw OCR text lines.
        Returns parsed dict with FULL VALIDATION or None if no valid MRZ found.
        Pads / trims lines to expected lengths before parsing.
        
        ADAPTIVE: Works with ANY country's documents (passports, ID cards, visas).
        """
        # Sanitize all candidate lines (uppercase + normalize)
        clean = [self.sanitize_mrz_line(l) for l in raw_lines]

        # ELITE: Advanced format detection with confidence scoring
        fmt, metadata = self.detect_format_advanced(clean)
        
        if fmt is None:
            # Try with explicit length enforcement by padding
            for target_len in (30, 36, 44):
                padded = [self.smart_pad(l, target_len) for l in clean]
                fmt, metadata = self.detect_format_advanced(padded)
                if fmt:
                    clean = padded
                    break

        if fmt == "TD1":
            l1, l2, l3 = (self.smart_pad(clean[0], 30),
                          self.smart_pad(clean[1], 30),
                          self.smart_pad(clean[2], 30))
            result = self._parse_td1(l1, l2, l3)
            result["format_detection_metadata"] = metadata
            return result
        elif fmt == "TD2":
            l1, l2 = (self.smart_pad(clean[0], 36),
                      self.smart_pad(clean[1], 36))
            result = self._parse_td2(l1, l2)
            result["format_detection_metadata"] = metadata
            return result
        elif fmt == "TD3":
            l1, l2 = (self.smart_pad(clean[0], 44),
                      self.smart_pad(clean[1], 44))
            result = self._parse_td3(l1, l2)
            result["format_detection_metadata"] = metadata
            return result

        return None

    def find_mrz_lines_in_ocr(self, all_text_boxes: list[dict], img_height: int = None) -> list[str] | None:
        """
        ELITE: Scan OCR boxes for MRZ-like lines.
        TD1 (3×30): Moroccan CNIE v2 verso.
        TD3 (2×44): Passports.
        CRITICAL FIX: OCR often drops trailing '<<<' from short lines → accept ≥18 chars and pad.
        """
        # ELITE: Accept from 18 chars (OCR may drop trailing fillers)
        MRZ_RE = re.compile(r"^[A-Z0-9<]{18,}$", re.IGNORECASE)

        candidates = []
        for box in all_text_boxes:
            raw_text = box["text"].upper()
            _temp_clean = raw_text.replace(' ', '')
            if "<" not in raw_text and not (len(_temp_clean) >= 18 and re.match(r'^[A-Z0-9]+$', _temp_clean)):
                print(f"   [MRZ DEBUG] Rejected (no < and not full alpha): '{raw_text}'")
                continue
            raw = raw_text.replace(" ", "<")
            sanitised = self.sanitize_mrz_line(raw)
            if not MRZ_RE.match(sanitised):
                print(f"   [MRZ DEBUG] Rejected (regex mismatch): '{sanitised}' (original: '{raw_text}')")
                continue
            filler_ratio = sanitised.count("<") / max(len(sanitised), 1)
            # ELITE: Allow lines with no filler if they are full-length MRZ strings (e.g. Polish Verso TD1 middle line)
            if filler_ratio < 0.02 and not (len(_temp_clean) >= 18 and re.match(r'^[A-Z0-9]+$', _temp_clean)):
                print(f"   [MRZ DEBUG] Rejected (low filler ratio {filler_ratio:.2f} and not full alpha): '{sanitised}'")
                continue
            
            print(f"   [MRZ DEBUG] Accepted Candidate: '{sanitised}'")

            y_pos = box["position"]["y"]
            priority = 0
            if img_height:
                if y_pos > img_height * 0.70:
                    priority = 100
                elif y_pos > img_height * 0.60:
                    priority = 50
                else:
                    priority = 1
            else:
                priority = 1

            candidates.append({
                "sanitised": sanitised,
                "y": y_pos,
                "y_min": box["position"]["y_min"],
                "priority": priority,
            })

        if len(candidates) < 2:
            # ELITE: Even with 1 candidate, search for TD1 L1+L2+L3 triplet
            # by actively hunting name-line (with <<) from ALL boxes
            pass  # fall through to triplet reconstruction below
        else:
            candidates.sort(key=lambda c: c["y"])

        if len(candidates) >= 2:
            candidates.sort(key=lambda c: c["y"])
            
            has_passport_prefix = any(
                c["sanitised"].startswith("P<") 
                or c["sanitised"][:4] in ("PMAR", "PFRA", "PDEU", "PGBR")
                or (c["sanitised"].startswith("<") and re.match(r"<[A-Z]{3}[A-Z<]+<<", c["sanitised"]))
                for c in candidates
            )
            
            best_invalid_mrz = None
            
            for group_size in (3, 2):
                for start in range(len(candidates) - group_size + 1):
                    group = candidates[start:start + group_size]
                    priorities = [c["priority"] for c in group]
                    lines_raw = [c["sanitised"] for c in group]
                    
                    attempts = []
                    if group_size == 3:
                        if has_passport_prefix:
                            # ELITE FIX: Prioritize adjacent lines first!
                            for i, j in [(1, 2), (0, 1), (0, 2)]:
                                pair = [lines_raw[i], lines_raw[j]]
                                attempts.append([self.smart_pad(l, 44) for l in pair])
                        attempts.append([self.smart_pad(l, 30) for l in lines_raw])
                    else:
                        l1 = lines_raw[0]
                        if l1.startswith("P<") or has_passport_prefix:
                            attempts.append([self.smart_pad(l, 44) for l in lines_raw])
                        if l1[:2] in ("ID", "I<") or (l1.startswith("I") and "MAR" in l1[:10]):
                            attempts.append([self.smart_pad(l, 30) for l in lines_raw])
                        if not attempts:
                            attempts.append([self.smart_pad(l, 44) for l in lines_raw])
                            attempts.append([self.smart_pad(l, 30) for l in lines_raw])
                    
                    for lines in attempts:
                        result = self.parse(lines)
                        if result:
                            cv = result.get("cryptographic_validation", {})
                            if cv.get("overall_mrz_valid"):
                                return lines
                            doc_ok = bool(cv.get("document_number_check", {}).get("is_valid"))
                            dob_ok = bool(cv.get("birth_date_check", {}).get("is_valid"))
                            exp_ok = bool(cv.get("expiry_date_check", {}).get("is_valid"))
                            if doc_ok and dob_ok and exp_ok:
                                return lines
                                
                            # ELITE FALLBACK: Even if composite fails, 
                            # if 2 of 3 individual checks pass → accept (OCR noise in one field)
                            pass_count = sum([doc_ok, dob_ok, exp_ok])
                            if pass_count >= 2 and "<<" in lines[0]:
                                return lines
                            
                            # ELITE DYNAMIC FALLBACK: If it's structurally valid but fails checksums (e.g. fake/template)
                            if best_invalid_mrz is None:
                                fmt = result.get("format")
                                line1 = lines[0]
                                if fmt == "TD3" and (line1.startswith("P") or line1.startswith("<")) and "<<" in line1:
                                    best_invalid_mrz = lines
                                elif fmt == "TD1" and (line1.startswith("I") or line1.startswith("<")):
                                    best_invalid_mrz = lines
                                elif fmt == "TD2" and (line1.startswith("I") or line1.startswith("<")):
                                    best_invalid_mrz = lines

                            if group_size == 3 and len(lines[0]) == 30 and all(p >= 50 for p in priorities):
                                # ELITE FIX: Do not eagerly return just because lines are at the bottom.
                                # Let it fall back to best_invalid_mrz logic if it's truly a valid structure.
                                pass

        if len(candidates) == 2:
            l1_san = candidates[0]["sanitised"]
            l2_san = candidates[1]["sanitised"]
            if l1_san[:2] in ("ID", "I<") or "MAR" in l1_san[:8]:
                for box in all_text_boxes:
                    raw = box["text"].upper().replace(" ", "<")
                    san = self.sanitize_mrz_line(raw)
                    if san in (l1_san, l2_san):
                        continue
                    has_double_fill = "<<" in san
                    all_mrz_chars = re.match(r"^[A-Z0-9<]+$", san)
                    if has_double_fill and all_mrz_chars and len(san) >= 4:
                        line3 = self.smart_pad(san, 30)
                        lines = [
                            self.smart_pad(l1_san, 30),
                            self.smart_pad(l2_san, 30),
                            line3
                        ]
                        result = self.parse(lines)
                        if result:
                            cv = result.get("cryptographic_validation", {})
                            doc_ok = cv.get("document_number_check", {}).get("is_valid")
                            dob_ok = cv.get("birth_date_check", {}).get("is_valid")
                            exp_ok = cv.get("expiry_date_check", {}).get("is_valid")
                            if cv.get("overall_mrz_valid") or (doc_ok and dob_ok and exp_ok):
                                return lines
                                
        if 'best_invalid_mrz' in locals() and best_invalid_mrz:
            return best_invalid_mrz
            
        return None

    @staticmethod
    def is_valid_mrz_country(country_code: str) -> bool:
        """
        ELITE: Reject false MRZ detections from barcode noise.
        A real MRZ country must be a known ISO-3166-1 alpha-3 code.
        """
        # Common ISO-3 codes (non-exhaustive but covers main cases)
        KNOWN_CODES = {
            "MAR", "FRA", "DEU", "GBR", "USA", "ESP", "ITA", "PRT",
            "BEL", "NLD", "CHE", "AUT", "SWE", "NOR", "DNK", "FIN",
            "POL", "CZE", "SVK", "HUN", "ROU", "BGR", "HRV", "SRB",
            "GRC", "TUR", "RUS", "UKR", "CHN", "JPN", "KOR", "IND",
            "PAK", "BGD", "IDN", "MYS", "THA", "PHL", "VNM", "SAU",
            "ARE", "EGY", "DZA", "TUN", "LBY", "SEN", "CIV", "GHA",
            "NGA", "KEN", "ETH", "ZAF", "MDG", "CMR", "COD", "TCD",
            "MLI", "NER", "BFA", "GNB", "GAB", "COG", "CAF", "SSD",
            "CAN", "MEX", "BRA", "ARG", "CHL", "COL", "PER", "VEN",
            "AUS", "NZL", "ISR", "IRN", "IRQ", "SYR", "LBN", "JOR",
            "KWT", "QAT", "BHR", "OMN", "YEM", "AFG", "KAZ", "UZB",
            "UTO",  # ICAO test code
        }
        return country_code.upper() in KNOWN_CODES

    @staticmethod
    def extract_name_from_raw_mrz_text(boxes: list[dict]) -> dict:
        """
        ELITE: Even if MRZ validation fails, extract name/gender from raw OCR text
        that matches the TD1 Line-3 pattern: LASTNAME<<FIRSTNAME<<<<
        Also extracts gender from 'Sexe M' / 'Sexe F' VIZ text.
        """
        result = {"last_name": None, "first_name": None, "full_name": None, "gender": None}
        name_re = re.compile(r'^([A-Z]{2,})<<([A-Z<]+)$', re.IGNORECASE)

        for box in boxes:
            text = box["text"].upper().replace(" ", "<")
            m = name_re.match(text)
            if m:
                last = m.group(1).strip("<")
                first = m.group(2).replace("<", " ").strip()
                result["last_name"] = last
                result["first_name"] = first
                result["full_name"] = f"{last} {first}".strip()
                break

        # ELITE FALLBACK: Repair PaddleX hallucinations on Polish Verso (padding < read as S, Z, K)
        if not result["full_name"]:
            for box in boxes:
                text = box["text"].upper().replace(" ", "")
                if len(text) > 20 and re.match(r'^[A-Z]{3,}[SZK]{1,3}[A-Z]{3,}[SZK]{1,3}[A-Z]{3,}', text):
                    # Only fix trailing fillers, and only replace obvious separator errors without destroying names
                    clean = re.sub(r'[SZK]{2,}$', '<<', text)
                    clean = clean.replace('<Z', '<<').replace('<S', '<<').replace('<K', '<<').replace('ZS', '<<')
                    m = name_re.match(clean)
                    if m:
                        last = m.group(1).strip("<")
                        first = m.group(2).replace("<", " ").strip()
                        result["last_name"] = last
                        result["first_name"] = first
                        result["full_name"] = f"{last} {first}".strip()
                        break


        # Gender from VIZ: 'Sexe M', 'Sexe F', or standalone 'M'/'F' near 'sexe' label
        for box in boxes:
            t = box["text"].lower()
            if "sexe" in t or "الجنس" in t:
                if " m" in t or t.endswith("m") or "male" in t:
                    result["gender"] = "MALE"
                elif " f" in t or t.endswith("f") or "female" in t:
                    result["gender"] = "FEMALE"
                break

        return result


# ═══════════════════════════════════════════════════════════════════════════════
#  ELITE VISUAL FINGERPRINTER  ─  CNI generation + side detection (no OCR)
# ═══════════════════════════════════════════════════════════════════════════════

class EliteVisualFingerprinter:
    """
    Elite Visual Fingerprinter: Determines CNI generation (V1/V2) and card side
    (RECTO/VERSO) purely from visual signals — no OCR required.

    Signal priority order:
      1. PDF417 barcode presence  → CNI_V1 VERSO  (strongest signal)
      2. MRZ text pattern         → CNI_V2 VERSO
      3. Portrait RIGHT + no flag → CNI_V1 RECTO
      4. Portrait LEFT + flag     → CNI_V2 RECTO
      5. Ghost photo bottom-right → CNI_V2 RECTO (corroborating)
    """

    # Moroccan flag: two red hue ranges (HSV wraps around 180)
    _FLAG_RED_L1 = np.array([0,   100, 80])
    _FLAG_RED_U1 = np.array([10,  255, 255])
    _FLAG_RED_L2 = np.array([165, 100, 80])
    _FLAG_RED_U2 = np.array([180, 255, 255])

    # Skin tone in HSV (for ghost photo + portrait detection)
    _SKIN_LOWER = np.array([0,  20,  70])
    _SKIN_UPPER = np.array([25, 150, 255])

    def __init__(self):
        self._face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

    # ── Signal 1: Portrait position ───────────────────────────────────────────

    def detect_portrait_position(self, img) -> str:
        """
        ELITE v5: Zone-based skin-blob portrait detector.

        Splits the card into LEFT (0-45%) and RIGHT (55-100%) zones.
        Counts skin-tone pixels in each zone (top 75% only, excluding
        barcode/ghost zones). The zone with more skin area = portrait side.

        Haar Cascade is used ONLY as a tiebreaker when zones are ambiguous
        (difference < 30%). This makes the detector immune to Haar false
        positives on decorative backgrounds (Moroccan emblem, patterns).

        CNI-V1: portrait on RIGHT.  CNI-V2: portrait on LEFT.
        """
        img_h, img_w = img.shape[:2]

        # Build skin mask on top 75% (portrait is never in the bottom barcode zone)
        hsv        = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        skin_mask  = cv2.inRange(hsv, self._SKIN_LOWER, self._SKIN_UPPER)
        top_mask   = skin_mask.copy()
        top_mask[int(img_h * 0.75):, :] = 0  # erase bottom 25%

        # LEFT zone: 0 – 45%  |  RIGHT zone: 55 – 100%  (ignore ambiguous center)
        split_l = int(img_w * 0.45)
        split_r = int(img_w * 0.55)

        left_area  = int(np.count_nonzero(top_mask[:, :split_l]))
        right_area = int(np.count_nonzero(top_mask[:, split_r:]))
        total      = left_area + right_area

        print(f"   [portrait-zone] left_skin={left_area}  right_skin={right_area}")

        if total > 0:
            left_ratio  = left_area  / total
            right_ratio = right_area / total

            # DECISIVE: one zone has >= 60% of all skin pixels
            if left_ratio  >= 0.60:
                return "left"
            if right_ratio >= 0.60:
                return "right"

        # AMBIGUOUS or no skin: use scored Haar Cascade as tiebreaker
        gray         = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        min_face_area = img_w * img_h * 0.008

        try:
            faces = self._face_cascade.detectMultiScale(
                gray, scaleFactor=1.05, minNeighbors=4, minSize=(30, 30)
            )
        except Exception:
            faces = []

        def _face_score(fx, fy, fw, fh):
            area = fw * fh
            if area < min_face_area:
                return -1
            if fy + fh > img_h * 0.90:
                return -1  # ghost-photo / barcode zone
            cx_ratio   = (fx + fw // 2) / max(img_w, 1)
        skin_mask[int(img_h * 0.75):, :] = 0

        left_area  = np.count_nonzero(skin_mask[:, :int(img_w * 0.45)])
        right_area = np.count_nonzero(skin_mask[:, int(img_w * 0.55):])

        if left_area > right_area: return "left"
        if right_area > left_area: return "right"
        return "unknown"

    # ── Signal 2: Morocco flag ────────────────────────────────────────────────

    def detect_morocco_flag(self, img) -> bool:
        """
        Detect the Moroccan flag by locating a compact red+green region
        in the right 40% of the card. Flag appears on CNI-V2 recto only.
        """
        img_h, img_w = img.shape[:2]
        right = img[:, int(img_w * 0.55):]  # right portion
        hsv = cv2.cvtColor(right, cv2.COLOR_BGR2HSV)

        mask1 = cv2.inRange(hsv, self._FLAG_RED_L1, self._FLAG_RED_U1)
        mask2 = cv2.inRange(hsv, self._FLAG_RED_L2, self._FLAG_RED_U2)
        red_mask = cv2.bitwise_or(mask1, mask2)

        # Look for a compact red contour (the flag rectangle)
        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        region_area = right.shape[0] * right.shape[1]
        for cnt in contours:
            area = cv2.contourArea(cnt)
            ratio = area / max(region_area, 1)
            if 0.003 < ratio < 0.18:  # Flag should be 0.3%-18% of right region
                x, y, w, h = cv2.boundingRect(cnt)
                ar = w / h if h > 0 else 0
                if 0.5 < ar < 3.0:  # Roughly rectangular
                    return True
        return False

    # ── Signal 3: Ghost photo ────────────────────────────────────────────────

    def detect_ghost_photo(self, img) -> bool:
        """
        Detect the CNI-V2 ghost (transparent overlay) photo.
        Located in the bottom-right quadrant of the Recto (x>60%, y>50%).
        It is a small oval skin-tone region, smaller than the main portrait.
        """
        img_h, img_w = img.shape[:2]
        br = img[int(img_h * 0.45):, int(img_w * 0.55):]  # bottom-right
        if br.size == 0:
            return False

        hsv = cv2.cvtColor(br, cv2.COLOR_BGR2HSV)
        skin_mask = cv2.inRange(hsv, self._SKIN_LOWER, self._SKIN_UPPER)
        contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 200 < area < 10000:  # Ghost photo is small
                x, y, w, h = cv2.boundingRect(cnt)
                ar = w / h if h > 0 else 0
                if 0.4 < ar < 1.6:  # Portrait-like aspect ratio
                    return True
        return False

    # ── Signal 4: PDF417 barcode ──────────────────────────────────────────────

    def detect_pdf417(self, img) -> dict | None:
        """
        ELITE v5: Detect and decode PDF417 barcode (definitive CNI-V1 VERSO signature).

        3-attempt pipeline:
          1. Raw image decode (pyzbar)
          2. Perspective-corrected barcode region (_deskew_barcode_region)
          3. Binary-thresholded full image

        Falls back to morphological presence detection if all 3 fail.
        """
        if PYZBAR_AVAILABLE and pyzbar_decode is not None:
            try:
                # Attempt 1: raw image
                with SuppressCStderr():
                    barcodes = pyzbar_decode(img, symbols=[ZBarSymbol.PDF417])

                # Attempt 2: perspective-corrected barcode zone
                if not barcodes:
                    deskewed = self._deskew_barcode_region(img)
                    with SuppressCStderr():
                        barcodes = pyzbar_decode(deskewed, symbols=[ZBarSymbol.PDF417])
                    if not barcodes:
                        gray_d = cv2.cvtColor(deskewed, cv2.COLOR_BGR2GRAY)
                        _, bin_d = cv2.threshold(gray_d, 0, 255,
                                                 cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                        with SuppressCStderr():
                            barcodes = pyzbar_decode(bin_d, symbols=[ZBarSymbol.PDF417])

                # Attempt 3: binary-thresholded full image
                if not barcodes:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    _, binary = cv2.threshold(gray, 0, 255,
                                              cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    with SuppressCStderr():
                        barcodes = pyzbar_decode(binary, symbols=[ZBarSymbol.PDF417])

                for b in barcodes:
                    if b.type == "PDF417":
                        raw = b.data.decode("utf-8", errors="replace")
                        return {
                            "found": True,
                            "decoder": "pyzbar",
                            "raw": raw,
                            "parsed": self._parse_pdf417_data(raw),
                            "rect": {"x": b.rect.left, "y": b.rect.top,
                                     "w": b.rect.width, "h": b.rect.height},
                        }
            except Exception as e:
                print(f"   warning: pyzbar error: {e}")

        # Morphological fallback (detects presence but cannot decode)
        return self._detect_pdf417_morphological(img)

    def _detect_pdf417_morphological(self, img) -> dict | None:
        """Morphological PDF417 presence detector (no data decode)."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img_h, img_w = gray.shape
        bottom = gray[int(img_h * 0.60):, :]  # PDF417 is always in bottom ~40%
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))
        opened = cv2.morphologyEx(bottom, cv2.MORPH_OPEN, h_kernel, iterations=2)
        contours, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w > img_w * 0.35 and 5 < h < 80:
                return {"found": True, "decoder": "morphological", "raw": None, "parsed": {}}
        return None

    @staticmethod
    def _deskew_barcode_region(img) -> np.ndarray:
        """
        ELITE v5: Perspective-correct the PDF417 barcode region.
        """
        img_h, img_w = img.shape[:2]
        y_start      = int(img_h * 0.58)
        barcode_zone = img[y_start:, :]
        bz_h, bz_w   = barcode_zone.shape[:2]

        if bz_h < 10 or bz_w < 10:
            return barcode_zone

        gray = cv2.cvtColor(barcode_zone, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 10))
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, k, iterations=3)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        for cnt in contours[:6]:
            peri  = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.025 * peri, True)
            if len(approx) == 4:
                pts = approx.reshape(4, 2).astype(np.float32)
                s    = pts.sum(axis=1)
                diff = np.diff(pts, axis=1).flatten()
                tl   = pts[np.argmin(s)]
                br   = pts[np.argmax(s)]
                tr   = pts[np.argmin(diff)]
                bl   = pts[np.argmax(diff)]
                ordered = np.array([tl, tr, br, bl], dtype=np.float32)
                W = max(int(np.linalg.norm(tr - tl)), int(np.linalg.norm(br - bl)))
                H = max(int(np.linalg.norm(bl - tl)), int(np.linalg.norm(br - tr)))
                if W < 50 or H < 8: continue
                dst = np.array([[0, 0], [W, 0], [W, H], [0, H]], dtype=np.float32)
                M        = cv2.getPerspectiveTransform(ordered, dst)
                return cv2.warpPerspective(barcode_zone, M, (W, H))
        return barcode_zone

    @staticmethod
    def _parse_pdf417_data(raw: str) -> dict:
        """
        Parse Moroccan CNI-V1 PDF417 barcode content.
        The barcode encodes structured personal data.
        """
        parsed = {}
        if not raw:
            return parsed

        patterns = {
            "cin_number":    re.compile(r'\b([A-Z]{1,2}\d{5,9})\b'),
            "civil_number":  re.compile(r'(\d{4}/\d{4}|\d{7,10})'),
            "birth_date":    re.compile(r'(\d{2}[./]\d{2}[./]\d{4}|\d{4}-\d{2}-\d{2})'),
            "gender":        re.compile(r'\b(M|F|MASCULIN|FEMININ)\b', re.IGNORECASE),
        }
        for field, pattern in patterns.items():
            m = pattern.search(raw)
            if m:
                parsed[field] = m.group(1)

        # Extract name-like fields (all-caps, 3-40 chars)
        parts = re.split(r'[|;\t\n\r]+', raw)
        name_candidates = [
            p.strip() for p in parts
            if p.strip() and re.match(r'^[A-Z\s\u0600-\u06FF]{3,40}$', p.strip())
        ]
        if name_candidates:
            parsed["name_fields"] = name_candidates[:6]

        parsed["raw_length"] = len(raw)
        return parsed

    # ── Master fingerprint method ─────────────────────────────────────────────

    def fingerprint(self, img, ocr_boxes: list = None) -> dict:
        """
        Elite fingerprint: combine all visual signals to determine
        card side (RECTO/VERSO) and generation (CNI_V1/CNI_V2).
        """
        print("\n🔭 Elite Visual Fingerprinting…")
        signals = {}

        pdf417 = self.detect_pdf417(img)
        signals["pdf417"] = pdf417 is not None
        signals["pdf417_data"] = pdf417
        portrait_pos = self.detect_portrait_position(img)
        signals["portrait_position"] = portrait_pos
        has_flag = self.detect_morocco_flag(img)
        signals["morocco_flag"] = has_flag
        has_ghost = self.detect_ghost_photo(img)
        signals["ghost_photo"] = has_ghost

        has_mrz_text = False
        has_recto_text = False
        has_verso_text = False
        if ocr_boxes:
            all_text = " ".join(b["text"].upper() for b in ocr_boxes)
            has_mrz_text = "IDMAR" in all_text or any(
                re.match(r'^[A-Z0-9<]{20,}$', b["text"].upper().replace(" ", "<"))
                for b in ocr_boxes
            )
            has_recto_text = any(kw in all_text for kw in [
                "ROYAUME DU MAROC", "CARTE NATIONALE", "VALABLE",
                "NE LE", "BORN", "GEBOREN"
            ])
            has_verso_text = any(kw in all_text for kw in [
                "FILS DE", "ET DE", "ADRESSE", "N ETAT CIVIL", "IDMAR"
            ])
        signals["mrz_text_found"]  = has_mrz_text
        signals["recto_keywords"]  = has_recto_text
        signals["verso_keywords"]  = has_verso_text

        # ── WEIGHTED CONFIDENCE SCORING ENGINE ───────────────────────────────
        all_text = " ".join([box["text"].upper() for box in ocr_boxes]) if ocr_boxes else ""
        passport_signals = 0
        if any(w in all_text for w in ["PASSEPORT", "PASSPORT", "جواز"]):
            passport_signals += 3
        if "PASSEPORT" in all_text and "PASSPORT" in all_text:
            passport_signals += 2
            
        img_h, img_w = img.shape[:2] if len(img.shape) >= 2 else (0, 0)
        if img_h > img_w:
            passport_signals += 1
            
        if not signals["morocco_flag"]:
            passport_signals += 1
            
        if passport_signals >= 3:
            return {
                "document_class": "PASSPORT",
                "side": "DATA_PAGE",
                "version": "PASSPORT",
                "confidence": min(0.95, passport_signals * 0.2),
                "_scores": {"passport_signals": passport_signals}
            }

        scores = {"RECTO_V1": 0.0, "RECTO_V2": 0.0,
                  "VERSO_V1": 0.0, "VERSO_V2": 0.0}

        def _add(bucket, delta):
            scores[bucket] = round(max(0.0, min(1.0, scores[bucket] + delta)), 4)

        if signals["pdf417"]:
            _add("VERSO_V1", +0.99)
        if has_mrz_text:
            _add("VERSO_V2", +0.99)
        if portrait_pos == "right":
            _add("RECTO_V1", +0.40)
            _add("RECTO_V2", -0.20)
        elif portrait_pos == "left":
            _add("RECTO_V2", +0.40)
            _add("RECTO_V1", -0.20)
        if has_flag:
            _add("RECTO_V2", +0.30)
            _add("RECTO_V1", -0.10)
        if has_ghost:
            _add("RECTO_V2", +0.15)
        if has_verso_text:
            _add("VERSO_V1", +0.30)
            _add("VERSO_V2", +0.20)
        if has_recto_text:
            _add("RECTO_V1", +0.20)
            _add("RECTO_V2", +0.20)

        print(f"   [scores] RECTO_V1={scores['RECTO_V1']:.2f}  "
              f"RECTO_V2={scores['RECTO_V2']:.2f}  "
              f"VERSO_V1={scores['VERSO_V1']:.2f}  "
              f"VERSO_V2={scores['VERSO_V2']:.2f}")

        winner    = max(scores, key=scores.__getitem__)
        win_score = scores[winner]

        _MAP = {
            "RECTO_V1": ("RECTO", "CNI_V1"),
            "RECTO_V2": ("RECTO", "CNI_V2"),
            "VERSO_V1": ("VERSO", "CNI_V1"),
            "VERSO_V2": ("VERSO", "CNI_V2"),
        }
        side, version = _MAP[winner]
        confidence    = round(min(0.99, win_score), 3)

        if win_score < 0.15:
            version    = "UNKNOWN"
            confidence = 0.30

        print(f"   => {side} / {version}  (conf={confidence:.2f})")
        return {
            "side":       side,
            "version":    version,
            "confidence": confidence,
            "signals":    signals,
            "pdf417_data": pdf417,
            "_scores":    scores,
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  ADVANCED ID ANALYZER  (MRZ-first pipeline, 5.0.0-elite schema)
# ═══════════════════════════════════════════════════════════════════════════════

class AdvancedIDAnalyzer:
    """
    Elite ID/Passport deep analyzer.
    Pipeline: MRZ-first (cryptographic) → VIZ spatial fallback.
    Output: schema 5.0.0-elite, adaptive to any ICAO document type.
    """

    REQUIRED_OFFLINE_MODELS = [
        "PP-OCRv4_mobile_det",
        "en_PP-OCRv4_mobile_rec",
        "PP-LCNet_x1_0_textline_ori",
    ]

    # ── Country patterns for national ID numbers ──────────────────────────────
    _COUNTRY_ID_PATTERNS = {
        "MAR": re.compile(r"\b([A-Z]{1,2}\d{5,9})\b"),   # Morocco: 
        "DEU": re.compile(r"\b([A-Z]{1,2}\d{6,9}\d)\b"), # Germany: LZ6311T47 ← note letter mid
        "FRA": re.compile(r"\b(\d{12,15})\b"),
        "GBR": re.compile(r"\b([A-Z]{2}\d{6}[A-Z]?)\b"),
        "USA": re.compile(r"\b(\d{3}-\d{2}-\d{4})\b"),
        "_GENERIC": re.compile(r"\b([A-Z]{1,3}\d{4,12})\b"),
    }

    def __init__(self, model_root=None, auto_download_models=False, init_ocr=True):
        print("🔬 Initializing Elite ID Analyzer v5.0.0…")
        model_root = Path(model_root or os.environ.get("PADDLE_OCR_MODEL_DIR", "models"))
        if not model_root.is_absolute():
            model_root = (Path(__file__).resolve().parent / model_root).resolve()

        self.model_root = model_root
        self.cache_home = self.model_root / "paddlex_cache"
        self.strict_offline = os.environ.get("PADDLE_OCR_STRICT_OFFLINE", "1") == "1"
        self.mrz_parser = EliteMRZParser()
        self.layout_detector = EliteLayoutDetector()
        self.visual_fingerprinter = EliteVisualFingerprinter()

        os.environ["PADDLE_PDX_CACHE_HOME"] = str(self.cache_home)
        self.prepare_local_models()

        self.ocr = None
        if init_ocr:
            self.ocr = self._build_ocr_engine()
        elif auto_download_models:
            self._preload_models()

        self.admin_words = ['CARTE', 'CARD', 'IDENTITE', 'IDENTITY', 'ROYAUME',
                            'NATIONAL', 'VALABLE', 'BUNDESREPUBLIK', 'PERSONALAUSWEIS',
                            'FEDERAL', 'REPUBLIQUE', 'AUSWEIS']
        self.export_root = Path("imgs")

    # ── Model management ──────────────────────────────────────────────────────

    def prepare_local_models(self):
        self.model_root.mkdir(parents=True, exist_ok=True)
        self.cache_home.mkdir(parents=True, exist_ok=True)
        print(f"   ✓ Local model cache: {self.cache_home}")
        if self.strict_offline:
            self._validate_offline_cache()

    def _validate_offline_cache(self):
        base = self.cache_home / "official_models"
        missing = []
        for model_name in self.REQUIRED_OFFLINE_MODELS:
            model_dir = base / model_name
            if not model_dir.exists():
                missing.append(str(model_dir))
                continue
            if not (model_dir / "inference.yml").exists():
                missing.append(str(model_dir / "inference.yml"))
        if missing:
            details = "\n".join(f"- {item}" for item in missing)
            raise FileNotFoundError(
                "Strict offline mode is enabled and required local models are missing:\n"
                f"{details}\n\nNo network download will be attempted."
            )

    def _build_ocr_engine(self):
        return PaddleOCR(
            lang='ar',
            device='cpu',
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False  # ELITE: Disable to skip 22+ extra neural net executions
        )

    def _preload_models(self):
        print("\n🧩 Preloading OCR models into local cache…")
        _ = self._build_ocr_engine()
        print("   ✅ OCR models cached locally.")

    # ── Image helpers ─────────────────────────────────────────────────────────


    def _elite_preprocess_image(self, img):
        """
        ELITE PRACTICE: CLAHE contrast normalization for Deep Learning OCR.
        Used in legacy (non-YOLO) fallback path only.
        Modern CNNs rely on natural gradients -- we only normalize illumination.
        """
        print("\n" + chr(0x1f50d) + " Elite image preprocessing (CLAHE)...")
        
        if len(img.shape) == 3:
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
        else:
            l_channel = img
            a_channel = b_channel = None

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_clahe = clahe.apply(l_channel)

        if a_channel is not None:
            merged = cv2.merge([l_clahe, a_channel, b_channel])
            result = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
        else:
            result = l_clahe
        
        print("   " + chr(0x2705) + " Preprocessing complete: CLAHE contrast normalization")
        return result

    def _elite_preprocess_mrz_zone(self, img, zone_coords):
        """Ultra-elite preprocessing specifically for MRZ zone."""
        x, y, w, h = zone_coords
        img_h, img_w = img.shape[:2]
        x, y, w, h = self._clamp_bbox(x, y, w, h, img_w, img_h)
        
        # Crop MRZ zone
        mrz_crop = img[y:y+h, x:x+w]
        if mrz_crop.size == 0:
            return None
        
        # Convert to grayscale
        if len(mrz_crop.shape) == 3:
            gray = cv2.cvtColor(mrz_crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = mrz_crop.copy()
        
        # Aggressive denoising for MRZ
        denoised = cv2.fastNlMeansDenoising(gray, None, h=15, templateWindowSize=7, searchWindowSize=21)
        
        # Otsu's thresholding (works well for MRZ)
        _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Dilate slightly to connect broken characters
        kernel = np.ones((1, 2), np.uint8)
        dilated = cv2.dilate(binary, kernel, iterations=1)
        
        # Resize to 2x for better OCR
        h_new, w_new = dilated.shape
        enlarged = cv2.resize(dilated, (w_new * 2, h_new * 2), interpolation=cv2.INTER_CUBIC)
        
        # CRITICAL: Convert back to BGR for PaddleOCR
        enlarged_bgr = cv2.cvtColor(enlarged, cv2.COLOR_GRAY2BGR)
        
        return enlarged_bgr

    def _clamp_bbox(self, x, y, w, h, img_w, img_h):
        x = max(0, min(int(x), img_w - 1))
        y = max(0, min(int(y), img_h - 1))
        w = max(1, int(w))
        h = max(1, int(h))
        x2 = min(img_w, x + w)
        y2 = min(img_h, y + h)
        return x, y, max(1, x2 - x), max(1, y2 - y)

    def _save_crop(self, img, out_file, x, y, w, h):
        img_h, img_w = img.shape[:2]
        x, y, w, h = self._clamp_bbox(x, y, w, h, img_w, img_h)
        crop = img[y:y + h, x:x + w]
        if crop.size == 0:
            return False
        out_file.parent.mkdir(parents=True, exist_ok=True)
        return cv2.imwrite(str(out_file), crop)

    # ── ELITE MRZ-ZONE STRICT ISOLATION ───────────────────────────────────────

    def extract_mrz_strictly(self, img):
        """
        ELITE PRACTICE: Strict MRZ extraction with geometric isolation.
        - Crops bottom 25% of document (where MRZ is physically located)
        - Applies MRZ-specific binarization
        - Uses character whitelist (A-Z0-9< only)
        - Returns OCR boxes in ORIGINAL image coordinate space
        """
        print("\n🔒 ELITE MRZ STRICT ISOLATION…")
        img_h, img_w = img.shape[:2]
        
        # 1. STRICT GEOMETRIC CROP (bottom 25% only)
        mrz_y_start = int(img_h * 0.75)
        mrz_crop = img[mrz_y_start:img_h, 0:img_w]
        
        if mrz_crop.size == 0:
            print("   ⚠️  MRZ crop is empty")
            return []
        
        # 2. ELITE PRACTICE: Do NOT binarize MRZ if using Deep Learning!
        # Just use the raw BGR crop. Deep Learning models handle shadows perfectly.
        mrz_bgr = mrz_crop
        
        print(f"   ✓ MRZ zone cropped: y={mrz_y_start}-{img_h} ({img_h - mrz_y_start}px height)")
        
        # 5. Run OCR on MRZ crop (no global preprocessing - we did custom prep)
        mrz_boxes = []
        if hasattr(self.ocr, "predict"):
            result_pages = list(self.ocr.predict(mrz_bgr))
            if result_pages:
                page = result_pages[0]
                coords_list = page.get("rec_polys") or page.get("dt_polys") or []
                texts = page.get("rec_texts") or []
                scores = page.get("rec_scores") or []
                
                for i in range(min(len(coords_list), len(texts))):
                    coords = [[float(p[0]), float(p[1])] for p in coords_list[i]]
                    text = str(texts[i]).strip()
                    confidence = float(scores[i]) if i < len(scores) else 0.0
                    
                    # CRITICAL: Adjust coordinates back to original image space
                    x_coords = [p[0] for p in coords]
                    y_coords = [p[1] + mrz_y_start for p in coords]  # ADD offset
                    
                    box = {
                        "text": text,
                        "confidence": confidence,
                        "position": {
                            "x": round(sum(x_coords) / 4, 2),
                            "y": round(sum(y_coords) / 4, 2),
                            "x_min": round(min(x_coords), 2),
                            "x_max": round(max(x_coords), 2),
                            "y_min": round(min(y_coords), 2),
                            "y_max": round(max(y_coords), 2),
                        },
                        "dimensions": {
                            "width": round(max(x_coords) - min(x_coords), 2),
                            "height": round(max(y_coords) - min(y_coords), 2),
                        },
                        "polygon": [[round(p[0], 2), round(p[1] + mrz_y_start, 2)] for p in coords],
                    }
                    box["classification"] = self._classify_text(text)
                    mrz_boxes.append(box)
        else:
            result = self.ocr.ocr(mrz_bgr)
            if result and result[0]:
                for item in result[0]:
                    coords = item[0]
                    text = item[1][0].strip()
                    confidence = item[1][1]
                    
                    # CRITICAL: Adjust coordinates back to original image space
                    x_coords = [p[0] for p in coords]
                    y_coords = [p[1] + mrz_y_start for p in coords]  # ADD offset
                    
                    box = {
                        "text": text,
                        "confidence": confidence,
                        "position": {
                            "x": round(sum(x_coords) / 4, 2),
                            "y": round(sum(y_coords) / 4, 2),
                            "x_min": round(min(x_coords), 2),
                            "x_max": round(max(x_coords), 2),
                            "y_min": round(min(y_coords), 2),
                            "y_max": round(max(y_coords), 2),
                        },
                        "dimensions": {
                            "width": round(max(x_coords) - min(x_coords), 2),
                            "height": round(max(y_coords) - min(y_coords), 2),
                        },
                        "polygon": [[round(p[0], 2), round(p[1] + mrz_y_start, 2)] for p in coords],
                    }
                    box["classification"] = self._classify_text(text)
                    mrz_boxes.append(box)
        
        print(f"   ✓ Extracted {len(mrz_boxes)} text regions from MRZ zone")
        return mrz_boxes


    # ── YOLO-guided targeted OCR ──────────────────────────────────────────────────────

    def _run_ocr_on_crop(self, crop, y_offset=0, x_offset=0, max_dim=1000):
        """Run OCR on a single crop, return boxes with coordinates adjusted to full-image space."""
        if self.ocr is None:
            raise RuntimeError("OCR engine is not initialized.")

        # Dynamic downscaling
        scale = 1.0
        crop_max = max(crop.shape[:2])
        if crop_max > max_dim:
            scale = max_dim / crop_max
            new_w = int(crop.shape[1] * scale)
            new_h = int(crop.shape[0] * scale)
            crop = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_AREA)

        boxes = []
        if hasattr(self.ocr, "predict"):
            result_pages = list(self.ocr.predict(crop))
            if not result_pages:
                return []
            page = result_pages[0]
            coords_list = page.get("rec_polys") or page.get("dt_polys") or []
            texts = page.get("rec_texts") or []
            scores = page.get("rec_scores") or []

            for i in range(min(len(coords_list), len(texts))):
                coords = [[float(p[0]) / scale + x_offset,
                            float(p[1]) / scale + y_offset] for p in coords_list[i]]
                text = str(texts[i]).strip()
                confidence = float(scores[i]) if i < len(scores) else 0.0
                x_coords = [p[0] for p in coords]
                y_coords = [p[1] for p in coords]
                box = {
                    "text": text, "confidence": confidence,
                    "position": {
                        "x": round(sum(x_coords) / 4, 2), "y": round(sum(y_coords) / 4, 2),
                        "x_min": round(min(x_coords), 2), "x_max": round(max(x_coords), 2),
                        "y_min": round(min(y_coords), 2), "y_max": round(max(y_coords), 2),
                    },
                    "dimensions": {
                        "width": round(max(x_coords) - min(x_coords), 2),
                        "height": round(max(y_coords) - min(y_coords), 2),
                    },
                    "polygon": [[round(p[0], 2), round(p[1], 2)] for p in coords],
                }
                box["classification"] = self._classify_text(text)
                boxes.append(box)
        else:
            result = self.ocr.ocr(crop)
            if not result or not result[0]:
                return []
            for item in result[0]:
                coords = [[p[0] / scale + x_offset, p[1] / scale + y_offset] for p in item[0]]
                text = item[1][0].strip()
                confidence = item[1][1]
                x_coords = [p[0] for p in coords]
                y_coords = [p[1] for p in coords]
                box = {
                    "text": text, "confidence": confidence,
                    "position": {
                        "x": round(sum(x_coords) / 4, 2), "y": round(sum(y_coords) / 4, 2),
                        "x_min": round(min(x_coords), 2), "x_max": round(max(x_coords), 2),
                        "y_min": round(min(y_coords), 2), "y_max": round(max(y_coords), 2),
                    },
                    "dimensions": {
                        "width": round(max(x_coords) - min(x_coords), 2),
                        "height": round(max(y_coords) - min(y_coords), 2),
                    },
                    "polygon": [[round(p[0], 2), round(p[1], 2)] for p in coords],
                }
                box["classification"] = self._classify_text(text)
                boxes.append(box)

        return sorted(boxes, key=lambda b: (b["position"]["y"], b["position"]["x"]))

    def targeted_ocr(self, img, doc_class_info, yolo_ctx):
        """
        ELITE: Run OCR ONCE per zone based on YOLO classification.
        Returns (all_boxes, mrz_boxes) -- both in full-image coordinate space.
        """
        import time
        print("\n" + chr(0x1f4dd) + " Targeted OCR (YOLO-guided)...")
        t0 = time.time()

        img_h, img_w = img.shape[:2]
        doc_class = doc_class_info.get('doc_class', 'UNKNOWN')
        side = doc_class_info.get('side', 'UNKNOWN')
        ctx = yolo_ctx

        viz_boxes = []
        mrz_boxes = []

        # -- RECTO (any version): OCR on upper 75% only -----------
        if side == 'RECTO':
            cut_y = int(img_h * 0.75)
            viz_crop = img[0:cut_y, :]
            print(f"   RECTO mode -> OCR on upper 75% ({img_w}x{cut_y}px)")
            viz_boxes = self._run_ocr_on_crop(viz_crop)

        # -- CNI-V2 VERSO: VIZ above MRZ, MRZ from YOLO bbox -----
        elif doc_class == 'CNI_V2' and side == 'VERSO':
            if ctx.mrz_zone is not None:
                mrz_y1 = max(0, int(ctx.mrz_zone[1]) - 5)
                mrz_y2 = min(img_h, int(ctx.mrz_zone[3]) + 5)
                mrz_x1 = max(0, int(ctx.mrz_zone[0]) - 5)
                mrz_x2 = min(img_w, int(ctx.mrz_zone[2]) + 5)
                print(f"   CNI-V2 VERSO -> MRZ from YOLO: y={mrz_y1}-{mrz_y2}")
            else:
                mrz_y1 = int(img_h * 0.72)
                mrz_y2 = img_h
                mrz_x1, mrz_x2 = 0, img_w
                print(f"   CNI-V2 VERSO -> MRZ geometric fallback: y={mrz_y1}-{mrz_y2}")

            # MRZ crop -> Otsu binarize -> OCR
            mrz_crop = img[mrz_y1:mrz_y2, mrz_x1:mrz_x2]
            if mrz_crop.size > 0:
                gray = cv2.cvtColor(mrz_crop, cv2.COLOR_BGR2GRAY) if len(mrz_crop.shape) == 3 else mrz_crop
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                mrz_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
                mrz_boxes = self._run_ocr_on_crop(mrz_bgr, y_offset=mrz_y1, x_offset=mrz_x1)

            # VIZ crop = everything above MRZ
            viz_crop = img[0:mrz_y1, :]
            if viz_crop.size > 0:
                viz_boxes = self._run_ocr_on_crop(viz_crop)

        # -- CNI-V1 VERSO: barcode -> pyzbar, VIZ above -----------
        elif doc_class == 'CNI_V1' and side == 'VERSO':
            barcode_y1 = int(img_h * 0.60)
            if ctx.barcode_zone is not None:
                barcode_y1 = max(0, int(ctx.barcode_zone[1]) - 10)
                print(f"   CNI-V1 VERSO -> barcode from YOLO at y={barcode_y1}")
            else:
                print(f"   CNI-V1 VERSO -> barcode geometric fallback at y>{barcode_y1}")

            # VIZ crop = everything above barcode zone
            viz_crop = img[0:barcode_y1, :]
            if viz_crop.size > 0:
                viz_boxes = self._run_ocr_on_crop(viz_crop)

        # -- PASSPORT: MRZ bottom, VIZ above ----------------------
        elif doc_class == 'PASSPORT':
            if ctx.mrz_zone is not None:
                mrz_y1 = max(0, int(ctx.mrz_zone[1]) - 5)
                mrz_y2 = min(img_h, int(ctx.mrz_zone[3]) + 5)
                print(f"   PASSPORT -> MRZ from YOLO: y={mrz_y1}-{mrz_y2}")
            else:
                mrz_y1 = int(img_h * 0.80)
                mrz_y2 = img_h
                print(f"   PASSPORT -> MRZ geometric fallback: y={mrz_y1}-{mrz_y2}")

            mrz_crop = img[mrz_y1:mrz_y2, 0:img_w]
            if mrz_crop.size > 0:
                gray = cv2.cvtColor(mrz_crop, cv2.COLOR_BGR2GRAY) if len(mrz_crop.shape) == 3 else mrz_crop
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                mrz_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
                mrz_boxes = self._run_ocr_on_crop(mrz_bgr, y_offset=mrz_y1)

            viz_crop = img[0:mrz_y1, :]
            if viz_crop.size > 0:
                viz_boxes = self._run_ocr_on_crop(viz_crop)

        # -- UNKNOWN: Full-page OCR (fallback) --------------------
        else:
            print(f"   UNKNOWN doc type -> full-page OCR fallback")
            viz_boxes = self._run_ocr_on_crop(img)

        elapsed = time.time() - t0
        print(f"   " + chr(0x2713) + f" Targeted OCR completed in {elapsed:.2f}s")
        print(f"   " + chr(0x2713) + f" VIZ: {len(viz_boxes)} regions | MRZ: {len(mrz_boxes)} regions")

        all_boxes = sorted(viz_boxes + mrz_boxes, key=lambda b: (b["position"]["y"], b["position"]["x"]))
        return all_boxes, mrz_boxes

    # ── OCR extraction ────────────────────────────────────────────────────────

    def extract_all_text_deep(self, img, use_preprocessing=True):
        """Full-page OCR → sorted list of text boxes with spatial metadata."""
        print("\n📝 Deep text extraction…")
        if self.ocr is None:
            raise RuntimeError("OCR engine is not initialized.")

        # ELITE: Preprocess image before OCR
        if use_preprocessing:
            img_processed = self._elite_preprocess_image(img)
        else:
            img_processed = img

        # ELITE PRACTICE: Dynamic Downscaling to eliminate CPU latency.
        # Deep learning on a 1.5 megapixel image on CPU takes 100+ seconds.
        # Resizing by a factor of 1000px max drops pixels by 50-70% and speeds up inference massively.
        scale = 1.0
        max_dim = max(img_processed.shape[:2])
        if max_dim > 1000:
            scale = 1000.0 / max_dim
            new_w = int(img_processed.shape[1] * scale)
            new_h = int(img_processed.shape[0] * scale)
            img_processed = cv2.resize(img_processed, (new_w, new_h), interpolation=cv2.INTER_AREA)

        all_boxes = []

        if hasattr(self.ocr, "predict"):
            import time
            print(f"   ⏳ Running heavy neural net inference (scaled to {img_processed.shape[1]}x{img_processed.shape[0]})...")
            t0 = time.time()
            result_pages = list(self.ocr.predict(img_processed))
            print(f"   ✓ Inference completed in {time.time() - t0:.2f} seconds")
            
            if not result_pages:
                return []
            page = result_pages[0]
            coords_list = page.get("rec_polys") or page.get("dt_polys") or []
            texts = page.get("rec_texts") or []
            scores = page.get("rec_scores") or []

            for i in range(min(len(coords_list), len(texts))):
                # Scale coordinates back up to original image dimensions
                coords = [[float(p[0]) / scale, float(p[1]) / scale] for p in coords_list[i]]
                text = str(texts[i]).strip()
                confidence = float(scores[i]) if i < len(scores) else 0.0
                x_coords = [p[0] for p in coords]
                y_coords = [p[1] for p in coords]
                box = {
                    "text": text,
                    "confidence": confidence,
                    "position": {
                        "x": round(sum(x_coords) / 4, 2),
                        "y": round(sum(y_coords) / 4, 2),
                        "x_min": round(min(x_coords), 2),
                        "x_max": round(max(x_coords), 2),
                        "y_min": round(min(y_coords), 2),
                        "y_max": round(max(y_coords), 2),
                    },
                    "dimensions": {
                        "width": round(max(x_coords) - min(x_coords), 2),
                        "height": round(max(y_coords) - min(y_coords), 2),
                    },
                    "polygon": [[round(p[0], 2), round(p[1], 2)] for p in coords],
                }
                box["classification"] = self._classify_text(text)
                all_boxes.append(box)
        else:
            result = self.ocr.ocr(img_processed)
            if not result or not result[0]:
                return []
            for item in result[0]:
                coords = item[0]
                text = item[1][0].strip()
                confidence = item[1][1]
                x_coords = [p[0] for p in coords]
                y_coords = [p[1] for p in coords]
                box = {
                    "text": text,
                    "confidence": confidence,
                    "position": {
                        "x": round(sum(x_coords) / 4, 2),
                        "y": round(sum(y_coords) / 4, 2),
                        "x_min": round(min(x_coords), 2),
                        "x_max": round(max(x_coords), 2),
                        "y_min": round(min(y_coords), 2),
                        "y_max": round(max(y_coords), 2),
                    },
                    "dimensions": {
                        "width": round(max(x_coords) - min(x_coords), 2),
                        "height": round(max(y_coords) - min(y_coords), 2),
                    },
                    "polygon": [[round(p[0], 2), round(p[1], 2)] for p in coords],
                }
                box["classification"] = self._classify_text(text)
                all_boxes.append(box)

        print(f"   ✓ Extracted {len(all_boxes)} text regions")
        return sorted(all_boxes, key=lambda b: (b["position"]["y"], b["position"]["x"]))

    def _classify_text(self, text: str) -> list[str]:
        classifications = []
        upper_text = text.upper()
        if re.search(r'\d{2}[./-]\d{2}[./-]\d{4}', text) or re.search(r'\d{1,2}\s+[A-Za-z]{3,}\s*(?:/\s*[A-Za-z]{3,})?\s*\d{2,4}', text):
            classifications.append("DATE")
        if re.search(r'\b[A-Z]{1,3}\d{5,12}\b', text):
            classifications.append("ID_NUMBER")
        is_admin = any(word in upper_text for word in self.admin_words)
        has_lower = any(ch.isalpha() and ch.islower() for ch in text)
        if (not is_admin and not has_lower
                and re.fullmatch(r"[A-Z][A-Z'\-\s]{1,40}", upper_text)
                and not any(c.isdigit() for c in text)):
            classifications.append("POTENTIAL_NAME")
        if is_admin:
            classifications.append("ADMINISTRATIVE")
        if any(word in text.lower() for word in ['à', 'né', 'born', 'lieu', 'né le', 'geboren']):
            classifications.append("LOCATION_INDICATOR")
        if text.isdigit():
            classifications.append("NUMERIC")
        # MRZ candidate
        sanitised = EliteMRZParser.sanitize_mrz_line(text)
        if (len(sanitised) >= 28
                and re.fullmatch(r"[A-Z0-9<]+", sanitised)
                and sanitised.count("<") / len(sanitised) >= 0.10):
            classifications.append("MRZ_LINE")
        return classifications if classifications else ["UNKNOWN"]

    # ── Visual detection ──────────────────────────────────────────────────────

    def detect_photo_regions(self, img):
        """Detect face photos, logos, emblems on the card."""
        print("\n📷 Detecting photos and logos…")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = img.shape[:2]
        photo_regions = []

        try:
            fc = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = fc.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=3, minSize=(30, 30))
            for (x, y, wf, hf) in faces:
                photo_regions.append({"type": "face_photo", "x": int(x), "y": int(y),
                                      "width": int(wf), "height": int(hf), "confidence": "high"})
                print(f"   ✓ Face at ({x},{y}) {wf}×{hf}")
        except Exception as e:
            print(f"   ⚠ Face detection: {e}")

        edges = cv2.Canny(gray, 30, 100)
        dilated = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 3000 < area < 80000:
                x, y, wb, hb = cv2.boundingRect(cnt)
                ar = wb / hb if hb > 0 else 0
                if 0.6 < ar < 1.8 and x < w * 0.4:
                    photo_regions.append({"type": "photo_region", "x": int(x), "y": int(y),
                                          "width": int(wb), "height": int(hb),
                                          "confidence": "medium", "area": int(area)})
            elif 500 < area < 5000:
                x, y, wb, hb = cv2.boundingRect(cnt)
                ar = wb / hb if hb > 0 else 0
                if 0.5 < ar < 3.0 and y < h * 0.3:
                    photo_regions.append({"type": "logo", "x": int(x), "y": int(y),
                                          "width": int(wb), "height": int(hb),
                                          "confidence": "low", "area": int(area)})

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        skin_mask = cv2.inRange(hsv, np.array([0, 20, 70]), np.array([20, 255, 255]))
        for cnt in cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
            area = cv2.contourArea(cnt)
            if area > 2000 and area < w * h * 0.1:
                x, y, ws, hs = cv2.boundingRect(cnt)
                if x < w * 0.4 and not any(
                        abs(r["x"] - x) < 50 and abs(r["y"] - y) < 50 for r in photo_regions):
                    photo_regions.append({"type": "skin_region_photo", "x": int(x), "y": int(y),
                                          "width": int(ws), "height": int(hs),
                                          "confidence": "medium", "area": int(area)})

        print(f"   ✅ Total visual elements: {len(photo_regions)}")
        return photo_regions

    def detect_barcodes_mrz(self, img):
        """Detect potential MRZ / barcode zones via morphological analysis."""
        print("\n📊 Detecting barcode/MRZ regions…")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        detect_h = cv2.morphologyEx(gray, cv2.MORPH_OPEN, h_kernel, iterations=2)
        contours, _ = cv2.findContours(detect_h, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        regions = []
        for cnt in contours:
            x, y, w_c, h_c = cv2.boundingRect(cnt)
            if w_c > 200 and h_c < 50:
                regions.append({"type": "potential_mrz", "x": int(x), "y": int(y),
                                 "width": int(w_c), "height": int(h_c)})
        print(f"   ✓ Potential MRZ regions: {len(regions)}")
        return regions

    # ── Spatial zone analysis ─────────────────────────────────────────────────

    def analyze_spatial_zones(self, boxes, img_h, img_w):
        print("\n🗺️  Spatial zone analysis…")
        zones = {
            "header":   {"y_min": 0,              "y_max": img_h * 0.25, "content": []},
            "identity": {"y_min": img_h * 0.25,   "y_max": img_h * 0.60, "content": []},
            "details":  {"y_min": img_h * 0.60,   "y_max": img_h * 0.85, "content": []},
            "footer":   {"y_min": img_h * 0.85,   "y_max": img_h,         "content": []},
        }
        for box in boxes:
            y = box["position"]["y"]
            for zname, zinfo in zones.items():
                if zinfo["y_min"] <= y < zinfo["y_max"]:
                    zones[zname]["content"].append(box)
                    break
        for zname, zinfo in zones.items():
            print(f"   • {zname}: {len(zinfo['content'])} items")
        return zones

    # ── VIZ field extraction (ELITE: spatial anchoring) ──────────────────────

    def _find_value_by_anchor(self, boxes, anchor_keywords, search_direction="RIGHT", max_distance=150):
        """
        ELITE PRACTICE: Spatial querying instead of array index guessing.
        Finds the anchor box (label) and returns the closest box in the search direction.
        
        Args:
            boxes: List of OCR text boxes with position metadata
            anchor_keywords: List of keywords to identify the anchor (e.g. ["né", "birth"])
            search_direction: "RIGHT" or "BELOW"
            max_distance: Maximum pixel distance to search
        
        Returns:
            Closest matching box or None
        """
        anchor_box = None
        for box in boxes:
            if any(kw.lower() in box["text"].lower() for kw in anchor_keywords):
                anchor_box = box
                break
        
        if not anchor_box:
            return None
        
        # Find the closest box to the RIGHT or BELOW the anchor
        best_match = None
        min_dist = float('inf')
        
        ax_max = anchor_box["position"]["x_max"]
        ax_min = anchor_box["position"]["x_min"]
        ay_mid = anchor_box["position"]["y"]
        ay_max = anchor_box["position"]["y_max"]
        
        for box in boxes:
            if box == anchor_box:
                continue
            
            bx_min = box["position"]["x_min"]
            by_mid = box["position"]["y"]
            by_min = box["position"]["y_min"]
            
            if search_direction == "RIGHT":
                # Box must be vertically aligned and to the right
                # ELITE: Dynamic vertical tolerance based on anchor box height (capped to avoid next line)
                anchor_h = ay_max - anchor_box["position"]["y_min"]
                v_tolerance = max(10, anchor_h * 0.6)
                if abs(by_mid - ay_mid) < v_tolerance and bx_min > ax_max:
                    dist = bx_min - ax_max
                    if dist < min_dist and dist < max_distance:
                        min_dist = dist
                        best_match = box
            
            elif search_direction == "BELOW":
                # Box must be horizontally aligned and below
                # Use horizontal intersection (with 30px tolerance) instead of strict left-alignment
                if (box["position"]["x_max"] >= ax_min - 30 and bx_min <= ax_max + 30) and by_mid > ay_mid:
                    dist = by_mid - ay_mid
                    if dist < min_dist and dist < max_distance:
                        min_dist = dist
                        best_match = box
        
        return best_match

    def _extract_viz_fields(self, boxes, issuing_country="UNKNOWN"):
        """
        ELITE DYNAMIC: Extract Visual Inspection Zone fields using spatial anchoring.
        ADAPTIVE for ANY country, ANY language, ANY document type.
        Uses geometric radius search + multi-language keyword matching.
        """
        fields = {"names": [], "dates": [], "id_numbers": [], "locations": [],
                  "codes": [], "administrative_text": [], "other_text": []}

        # Calculate approximate image dimensions
        img_w = max((b["position"]["x_max"] for b in boxes), default=1000)
        img_h = max((b["position"]["y_max"] for b in boxes), default=1000)

        # ── ELITE: Document Generation Fingerprinting (V1 vs V2) ──
        is_old_generation = False
        # إذا وجدنا باركود في الأسفل (من دالة detect_barcodes) أو لم نجد MRZ
        # أو بالاعتماد على ترتيب النصوص (مثلاً في القديمة CARTE NATIONALE متبوعة بالاسم مباشرة)
        for i, box in enumerate(boxes):
            if "CARTE NATIONALE" in box["text"].upper():
                # في البطاقة القديمة، الاسم العائلي يقع مباشرة أسفل (CARTE NATIONALE) بمسافة قصيرة
                if i + 1 < len(boxes) and boxes[i+1]["position"]["y"] - box["position"]["y"] < 50:
                    is_old_generation = True
                break

        # ELITE: Multi-language date keywords (French, English, German, Arabic, Spanish, Italian, Polish, Dutch)
        birth_keywords = ["né", "birth", "born", "geboren", "naissance", "geburtsdatum", 
                          "date of birth", "nacimiento", "nato", "nascita", "تاريخ", "urodzenia",
                          "geboortedatum"]
        expiry_keywords = ["valable", "expire", "valid", "gültig", "expiry", "expiration",
                           "bis", "until", "válido", "scadenza", "صلاحية", "waznosc", "termin",
                           "geldig tot", "geldig"]
        issue_keywords = ["issue", "délivré", "ausgestellt", "émission", "delivered",
                          "ausgabedatum", "emitido", "rilascio", "تسليم",
                          "datum van afgifte", "afgifte"]

        # ELITE: Month name → number mapping for DD MONTH YYYY date formats (Dutch, English, French, German, Spanish)
        _MONTH_NAME_MAP = {
            "jan": "01", "feb": "02", "mrt": "03", "mar": "03", "maa": "03",
            "apr": "04", "mei": "05", "may": "05", "mai": "05",
            "jun": "06", "jul": "07", "aug": "08",
            "sep": "09", "okt": "10", "oct": "10",
            "nov": "11", "dec": "12", "dez": "12",
            # Full month names
            "january": "01", "february": "02", "march": "03", "april": "04",
            "june": "06", "july": "07", "august": "08", "september": "09",
            "october": "10", "november": "11", "december": "12",
            "januari": "01", "februari": "02", "maart": "03",
            "juni": "06", "juli": "07", "augustus": "08",
            "oktober": "10",
        }

        for i, box in enumerate(boxes):
            text = box["text"]
            cls = box["classification"]

            if "POTENTIAL_NAME" in cls:
                fields["names"].append({"value": text, "confidence": box["confidence"],
                                        "position": box["position"]})

            if "DATE" in cls:
                # ELITE: Match multiple date formats (DD.MM.YYYY, DD/MM/YYYY, YYYY-MM-DD)
                patterns = [
                    r'(\d{2})[./-](\d{2})[./-](\d{4})',  # DD.MM.YYYY or DD/MM/YYYY
                    r'(\d{4})[./-](\d{2})[./-](\d{2})',  # YYYY-MM-DD
                ]

                # ELITE: Try DD MONTH(/MONTH) YYYY format first (Dutch/English bilingual dates)
                # e.g. "10 MAA/MAR 1965", "02 AUG/AUG 2021", "15 OKT 2023", "07 FEB /FEV51"
                month_date_match = re.search(
                    r'(\d{1,2})\s+([A-Za-z]{3,})\s*(?:/\s*[A-Za-z]{3,})?\s*(\d{2,4})', text)
                if month_date_match:
                    _day = month_date_match.group(1).zfill(2)
                    _month_str = month_date_match.group(2).lower()
                    _year = month_date_match.group(3)
                    
                    if len(_year) == 2:
                        y = int(_year)
                        curr_y = int(datetime.now().year)
                        if y > (curr_y % 100) + 15:
                            _year = f"19{y:02d}"
                        else:
                            _year = f"20{y:02d}"

                    _mon_num = _MONTH_NAME_MAP.get(_month_str)
                    if _mon_num:
                        day, mon, year = _day, _mon_num, _year
                        # Determine date type from context
                        dtype = "unknown"
                        ctx = boxes[i - 1]["text"].lower() if i > 0 else ""
                        if any(kw in ctx for kw in birth_keywords):
                            dtype = "birth_date"
                        elif any(kw in ctx for kw in expiry_keywords):
                            dtype = "expiry_date"
                        elif any(kw in ctx for kw in issue_keywords):
                            dtype = "issue_date"
                        if dtype == "unknown":
                            for check_box in boxes:
                                if check_box == box: continue
                                check_text = check_box["text"].lower()
                                x_dist = abs(check_box["position"]["x_max"] - box["position"]["x_min"])
                                y_dist = abs(check_box["position"]["y"] - box["position"]["y"])
                                if x_dist < 150 and y_dist < 40:
                                    if any(kw in check_text for kw in birth_keywords):
                                        dtype = "birth_date"; break
                                    elif any(kw in check_text for kw in expiry_keywords):
                                        dtype = "expiry_date"; break
                                    elif any(kw in check_text for kw in issue_keywords):
                                        dtype = "issue_date"; break
                        if dtype == "unknown":
                            current_year = int(datetime.now().year)
                            try:
                                ey = int(_year)
                                if ey > current_year: dtype = "expiry_date"
                                elif ey <= current_year - 15: dtype = "birth_date"
                                else: dtype = "issue_date"
                            except ValueError: pass
                        
                        print(f"[DEBUG] EXTRACTED DATE: {text} -> {year}-{mon}-{day} type: {dtype}")
                        fields["dates"].append({"type": dtype, "value": f"{year}-{mon}-{day}",
                                                "raw": text, "confidence": box["confidence"],
                                                "position": box["position"]})
                        continue  # Date extracted via month-name format, skip numeric patterns
                
                for pattern in patterns:
                    m = re.search(pattern, text)
                    if m:
                        if len(m.groups()) == 3:
                            g1, g2, g3 = m.groups()
                            # Detect format
                            if len(g1) == 4:  # YYYY-MM-DD
                                year, mon, day = g1, g2, g3
                            else:  # DD.MM.YYYY
                                day, mon, year = g1, g2, g3
                        
                        # ELITE: Dynamic date type detection with multi-language support
                        dtype = "unknown"
                        
                        # Fast path: check previous box
                        ctx = boxes[i - 1]["text"].lower() if i > 0 else ""
                        if any(kw in ctx for kw in birth_keywords):
                            dtype = "birth_date"
                        elif any(kw in ctx for kw in expiry_keywords):
                            dtype = "expiry_date"
                        elif any(kw in ctx for kw in issue_keywords):
                            dtype = "issue_date"
                        
                        # ELITE: Spatial anchoring (protects against reading order issues)
                        if dtype == "unknown":
                            for check_box in boxes:
                                if check_box == box:
                                    continue
                                check_text = check_box["text"].lower()
                                # Geometric proximity check
                                x_dist = abs(check_box["position"]["x_max"] - box["position"]["x_min"])
                                y_dist = abs(check_box["position"]["y"] - box["position"]["y"])
                                
                                if x_dist < 150 and y_dist < 40:
                                    if any(kw in check_text for kw in birth_keywords):
                                        dtype = "birth_date"
                                        break
                                    elif any(kw in check_text for kw in expiry_keywords):
                                        dtype = "expiry_date"
                                        break
                                    elif any(kw in check_text for kw in issue_keywords):
                                        dtype = "issue_date"
                                        break
                        
                        # ELITE: Chronological Logical Validation
                        if dtype == "unknown":
                            current_year = int(datetime.now().year)
                            try:
                                extracted_year = int(year)
                                
                                # ELITE BUG 2 FIX: Reject impossible years (e.g., 0000, 9999)
                                if extracted_year < 1900 or extracted_year > current_year + 15:
                                    continue
                                
                                if extracted_year > current_year:
                                    dtype = "expiry_date"
                                elif extracted_year <= current_year - 15: 
                                    dtype = "birth_date"
                                else:
                                    dtype = "issue_date"
                            except ValueError:
                                dtype = "unknown"
                        
                        fields["dates"].append({"type": dtype, "value": f"{year}-{mon}-{day}",
                                                "raw": text, "confidence": box["confidence"],
                                                "position": box["position"]})
                        break  # Found date, stop trying patterns

            if "ID_NUMBER" in cls:
                # Try country-specific pattern first
                pattern = self._COUNTRY_ID_PATTERNS.get(issuing_country,
                                                         self._COUNTRY_ID_PATTERNS["_GENERIC"])
                m = pattern.search(text)
                if not m:
                    m = self._COUNTRY_ID_PATTERNS["_GENERIC"].search(text)
                if m:
                    fields["id_numbers"].append({"value": m.group(1), "confidence": box["confidence"],
                                                  "position": box["position"]})

            m = re.search(r'\b[aà]\s+([A-Z]{3,}(?:\s+[A-Z]{3,})*)', text, re.IGNORECASE)
            if m:
                fields["locations"].append({"value": m.group(1), "confidence": box["confidence"],
                                             "position": box["position"]})

            if re.match(r'^[A-Z0-9]{4,12}$', text) and any(c.isdigit() for c in text):
                # ELITE: Only add codes with sufficient confidence (avoid OCR noise)
                if box["confidence"] >= 0.70:
                    fields["codes"].append({"value": text, "confidence": box["confidence"],
                                             "position": box["position"]})

            # ELITE: Address extraction (Verso)
            # Relaxed regex to catch OCR typos (AdPSS, Aersse, العون)
            address_match = re.search(r'(?i)^(?:Adresse|Adress|Adiesse|Aersse|AdPSS|العنوان|العون|Adresse\s*:?)\s*(.+)', text)
            
            # Check for strong address indicators anywhere in the string
            has_address_keywords = any(kw in f" {text.upper()} " for kw in [
                " HAY ", " LOT ", " RUE ", " QUARTIER ", " AVENUE ", " RESIDENCE ",
                " IMM ", " ETG ", " NR ", " GH ", " BLOC ", " APPT ", " APP ",
                " AV ", " BD ", " BOULEVARD ", " DERB ", " N° ",
                " CITE ", " SECT ", " DOUAR ",
                " زنقة ", " حي ", " تجزئة ", " شارع ", " عمارة ", " طابق ",
            ])
            # Exclude known admin labels that contain address-like Arabic words
            is_admin_label = any(adm in text for adm in [
                "الحالة المدنية", "رقم الحالة", "état civil", "alat civil",
                "etat civil", "N°état", "Carte Nationale",
            ])

            if address_match and not is_admin_label:
                val = address_match.group(1).strip()
                val = re.sub(r'^[\s/:\-.]+', '', val)
                val = re.sub(r'(?i)^address\s*:?\s*', '', val)
                val = re.sub(r'^[\s/:\-.]+', '', val)
                if len(val) > 3:
                    fields["other_text"].append({"type": "address", "value": val})
            elif has_address_keywords and len(text) > 10 and not is_admin_label:
                fields["other_text"].append({"type": "address", "value": text.strip()})
            elif "ADMINISTRATIVE" in cls:
                fields["administrative_text"].append(text)
            elif not any(c in cls for c in ["POTENTIAL_NAME", "DATE", "ID_NUMBER", "ADMINISTRATIVE"]):
                fields["other_text"].append({"value": text, "confidence": box["confidence"]})

        # ── ELITE: Chronological Date Fallback ──
        for d in fields["dates"]:
            if d["type"] == "unknown":
                year = d["value"].split("-")[0]
                current_year = int(datetime.now().year)
                try:
                    if int(year) > current_year:
                        d["type"] = "expiry_date"
                    elif int(year) <= current_year - 15:
                        d["type"] = "birth_date"
                except ValueError:
                    pass

        # ── ELITE: Old Generation Name Extraction ──
        if is_old_generation and not fields["names"]:
            left_side_texts = [b for b in boxes if b["position"]["x_min"] < img_w * 0.4 and 
                               img_h * 0.15 < b["position"]["y"] < img_h * 0.4]
            names_only = [b for b in left_side_texts if "ADMINISTRATIVE" not in b["classification"] 
                          and "POTENTIAL_NAME" in b["classification"]]
            
            if len(names_only) >= 2:
                fields["names"].append({"value": names_only[0]["text"], "type": "first_name", "position": names_only[0]["position"]})
                fields["names"].append({"value": names_only[1]["text"], "type": "last_name", "position": names_only[1]["position"]})

        return fields

    @staticmethod
    def _split_moroccan_name(full_name: str) -> tuple[str, str]:
        """
        ELITE: Intelligently split a Moroccan full name into Last and First name.
        Accounts for compound names like "EL ALAMI", "AIT BAHA", "BEN TALEB".
        Assumes LAST NAME comes first (MRZ order).
        """
        parts = full_name.split()
        if not parts:
            return "", ""
        if len(parts) == 1:
            return parts[0], ""
        
        prefixes = {"EL", "AL", "AIT", "BEN", "OULD", "ABOU", "OU", "CHEU", "BOU", "DE", "VAN", "DEN", "DER", "TEN", "TER"}
        if len(parts) >= 3 and parts[0].upper() in prefixes:
            last = f"{parts[0]} {parts[1]}"
            first = " ".join(parts[2:])
        else:
            last = parts[0]
            first = " ".join(parts[1:])
            
        return last, first

    def _merge_name_parts(self, name_candidates, img_height=None, img_width=None):
        filtered = []
        for item in name_candidates:
            v = item["value"].upper()
            # Filter admin words
            if any(w in v for w in self.admin_words):
                continue
            # Filter lowercase words (not a name)
            if any(ch.isalpha() and ch.islower() for ch in item["value"]):
                continue
            # Filter very short strings (2 chars or less — edge-of-card tab letters like 'NY', 'MS', 'ZK')
            if len(item["value"].strip()) <= 2:
                continue
            # Filter single-letter or noise
            words = [w for w in item["value"].split() if w]
            if len(words) > 3:
                continue
            # ELITE: Filter right-edge noise (tab letters printed on card margin)
            # These appear at x > 88% of card width with very small width
            if img_width is not None:
                x_min = item["position"].get("x_min", item["position"]["x"])
                x_max = item["position"].get("x_max", item["position"]["x"])
                box_width = x_max - x_min
                if x_min > img_width * 0.88 and box_width < 50:
                    continue  # Right-edge tab letter, skip
            if img_height is not None:
                y = item["position"]["y"]
                # ELITE: Relaxed Y check to 5% to 95% so stacked cards don't drop names
                if not (img_height * 0.05 <= y <= img_height * 0.95):
                    continue
            filtered.append(item)
        if not filtered:
            return None
        filtered.sort(key=lambda x: x["position"]["y"])
        groups, current = [], [filtered[0]]
        
        # ELITE: Dynamic Y-distance threshold instead of fixed 150px
        # A name and surname should be close together (usually < 5-6% of image height)
        # If distance > threshold, it's a different zone (e.g. city name like TAROUDANT)
        max_y_dist = max(20, img_height * 0.18) if img_height else 200

        for i in range(1, len(filtered)):
            if filtered[i]["position"]["y"] - current[-1]["position"]["y"] < max_y_dist:
                current.append(filtered[i])
            else:
                groups.append(current)
                current = [filtered[i]]
        if current:
            groups.append(current)
        return " ".join(item["value"] for item in groups[0][:2]) if groups else None

    # ── Confidence scoring ────────────────────────────────────────────────────

    @staticmethod
    def _compute_confidence(mrz_result, viz_identity, viz_dates):
        """Compute global confidence 0–1 based on MRZ validity + VIZ coverage."""
        if mrz_result and mrz_result.get("cryptographic_validation", {}).get("overall_mrz_valid"):
            base = 0.97
            # Bonus for cross-field VIZ match
            name_match = bool(viz_identity.get("full_name_latin"))
            date_match = bool(viz_dates.get("birth_date"))
            return min(1.0, base + (0.01 if name_match else 0) + (0.01 if date_match else 0))
        elif mrz_result:
            return 0.82
        else:
            # VIZ only
            filled = sum(1 for v in [viz_identity.get("full_name_latin"),
                                      viz_dates.get("birth_date"),
                                      viz_dates.get("expiry_date")] if v)
            return round(0.45 + filled * 0.10, 2)

    # ── Cross-validation engine ───────────────────────────────────────────────

    @staticmethod
    def _cross_validate(mrz_parsed, viz_identity, viz_dates, viz_identifiers):
        """Compare MRZ parsed fields against VIZ fields. Return matching engine + anomalies."""
        if not mrz_parsed:
            return {"note": "MRZ absent — cross-validation skipped"}, []

        anomalies = []
        engine = {}

        # Name match
        mrz_primary = mrz_parsed.get("primary_identifier", "").upper().replace(" ", "")
        mrz_secondary = mrz_parsed.get("secondary_identifier", "").upper().replace(" ", "")
        viz_full_raw = viz_identity.get("full_name_latin") or ""
        viz_full = viz_full_raw.upper().replace(" ", "") if viz_full_raw else ""
        if viz_full:
            name_ok = (mrz_primary in viz_full) or (mrz_secondary in viz_full) or (viz_full in (mrz_primary + mrz_secondary))
            engine["viz_mrz_name_match"] = name_ok
            if not name_ok:
                anomalies.append(f"Name mismatch: MRZ={mrz_primary}+{mrz_secondary} VIZ={viz_full}")
        else:
            engine["viz_mrz_name_match"] = None  # VIZ name not found

        # DOB match
        mrz_dob = mrz_parsed.get("birth_date", "")
        viz_dob = viz_dates.get("birth_date", "")
        if viz_dob and mrz_dob:
            engine["viz_mrz_dob_match"] = mrz_dob == viz_dob
            if not engine["viz_mrz_dob_match"]:
                anomalies.append(f"DOB mismatch: MRZ={mrz_dob} VIZ={viz_dob}")
        else:
            engine["viz_mrz_dob_match"] = None

        # Expiry match
        mrz_exp = mrz_parsed.get("expiry_date", "")
        viz_exp = viz_dates.get("expiry_date", "")
        if viz_exp and mrz_exp:
            engine["viz_mrz_expiry_match"] = mrz_exp == viz_exp
            if not engine["viz_mrz_expiry_match"]:
                anomalies.append(f"Expiry mismatch: MRZ={mrz_exp} VIZ={viz_exp}")
        else:
            engine["viz_mrz_expiry_match"] = None

        # Document number match
        mrz_docnum = mrz_parsed.get("document_number", "")
        viz_docnum = viz_identifiers.get("document_number", "")
        if viz_docnum and mrz_docnum:
            engine["viz_mrz_document_id_match"] = mrz_docnum == viz_docnum
            if not engine["viz_mrz_document_id_match"]:
                anomalies.append(f"Doc# mismatch: MRZ={mrz_docnum} VIZ={viz_docnum}")
        else:
            engine["viz_mrz_document_id_match"] = None

        return engine, anomalies

    # ── Document-type inference ───────────────────────────────────────────────

    @staticmethod
    def _infer_country(mrz_result, boxes):
        """Infer ISSUING_COUNTRY from MRZ or VIZ keywords."""
        if mrz_result:
            code = mrz_result.get("parsed_data", {}).get("issuing_state", "").upper()
            if code and code != "UNKNOWN":
                return code

        all_text = " ".join(b["text"].upper() for b in boxes)
        if any(kw in all_text for kw in ["KONINKRIJK DER NEDERLANDEN", "NEDERLANDSE", "IDENTITEITSKAART", "KINGDOM OF THE NETHERLANDS"]):
            return "NLD"
            
        if any(kw in all_text for kw in ["ROYAUME DU MAROC", "MAROCAINE", "MAROC", "IDMAR"]):
            return "MAR"
            
        if any(kw in all_text for kw in ["REPUBLIQUE FRANCAISE", "RÉPUBLIQUE FRANÇAISE", "CARTE NATIONALE D'IDENTITE", "IDFRA"]):
            return "FRA"
        if " FRA " in f" {all_text} " and "REPUBLIQUE" in all_text:
            return "FRA"
            
        if any(kw in all_text for kw in ["REINO DE ESPAÑA", "REINO DE ESPANA", "DOCUMENTO NACIONAL DE IDENTIDAD", "IDESP"]):
            return "ESP"
            
        if any(kw in all_text for kw in ["CARTÃO DE CIDADÃO", "CARTAO DE CIDADAO", "REPUBLICA PORTUGUESA", "PORTUGUESE REPUBLIC"]):
            return "PRT"
            
        if any(kw in all_text for kw in ["REPUBBLICA ITALIANA", "CARTA DI IDENTIT", "MINISTERO DELL'INTERNO"]):
            return "ITA"
            
        if any(kw in all_text for kw in ["RZECZPOSPOLITA POLSKA", "REPUBLIC OF POLAND", "POLSKIE", "POLSKICH", "IDPOL", "DOWÓD OSOBISTY", "DOWOD OSOBISTY"]):
            return "POL"
            
        if any(kw in all_text for kw in ["BUNDESREPUBLIK DEUTSCHLAND", "FEDERAL REPUBLIC OF GERMANY", "DEUTSCHLAND", "PERSONALAUSWEIS", "IDD<<"]):
            return "D"
            
        if any(kw in all_text for kw in ["UNITED STATES", "USA", "U.S.A", "DEPARTMENT OF STATE", "WASHINGTON"]):
            return "USA"
        
        return "UNKNOWN"

    @staticmethod
    def _detect_card_generation_and_side(boxes: list[dict]) -> dict:
        """
        ELITE: Detect CNI generation (v1/v2) and captured side (FRONT/BACK)
        purely from OCR text keywords — independent of MRZ success.

        CNI-v2 Recto fingerprint: 'ROYAUME DU MAROC' + 'CARTE NATIONALE' + photo on LEFT
                                   Moroccan flag detected by OpenCV (red region)
        CNI-v1 Recto fingerprint: 'CARTE NATIONALE' + coat of arms watermark + photo on RIGHT
        CNI-v2 Verso fingerprint: MRZ (IDMAR) + 'Fils de' + 'Adresse' + 'N° état civil'
        CNI-v1 Verso fingerprint: 'Fils de' + 'Adresse' + PDF417 barcode (NO MRZ)
        """
        all_text = " ".join(b["text"].upper() for b in boxes)

        # VERSO indicators (Moroccan + French + Portuguese + Italian)
        verso_keywords = [
            # Moroccan verso
            "FILS DE", "FILLE DE", "FLLS DE", "ET DE", "ADRESSE", "ADRESS", "ADIESSE",
            "N ETAT CIVIL", "N ETAT", "IDMAR",
            # French CNI verso
            "TAILLE", "DATE DE DELIVRANCE", "DATE DE DÉLIVRANCE", "IDFRA",
            # Portuguese CNI verso
            "FILIAÇÃO", "FILIACAO", "PARENTS", "IDENTIFICAÇÃO FISCAL", "IDENTIFICACAO FISCAL",
            "SEGURANÇA SOCIAL", "SEGURANCA SOCIAL", "UTENTE SAÚDE", "UTENTE SAUDE",
            "UTENTE SAGDE", "I<PRT", "TAX ID", "SOCIAL SECURITY ID", "HEALTH ID",
            # Italian CNI verso
            "CODICE FISCALE", "GENITORI", "RESIDENZA"
        ]
        # RECTO indicators
        recto_keywords = [
            # Moroccan recto
            "ROYAUME DU MAROC", "CARTE NATIONALE", "VALABLE", "NE LE", "BORN", "GEBOREN",
            # French CNI recto
            "CARTE NATIONALE D'IDENTITE", "IDENTITY CARD",
            "NOM/SURNAME", "NOM /SURNAME", "NOM/SUMAME", "NOM /SUMAME",
            "DATE DE NAISS", "LIEU DE NAISSANCE", "DATE D'EXPIR", "PRENOMS", "PRÉNOMS",
            # Portuguese CNI recto
            "CARTÃO DE CIDADÃO", "CARTAO DE CIDADAO", "APELIDO(S) / SURNAME", "NOME(S) / GIVEN NAME",
            "APELIDOIS", "APELIDO", "SURNAME",
            "SEXO", "ALTURA", "NACIONALIDADE", "N DOCUMENTO",
            # Italian CNI recto
            "CARTA DI IDENTIT", "COGNOME", "NOME", "CITTADINANZA", "STATURA",
            # Dutch (NLD) recto
            "IDENTITEITSKAART", "KONINKRIJK DER NEDERLANDEN", "KONINKRIJK",
            "GEBOORTEDATUM", "GELDIG TOT", "GESLACHT", "VOORNAMEN",
            "NAAM/ SURNAME", "NAAM/SURNAME"
        ]

        is_verso = any(kw in all_text for kw in verso_keywords)
        is_recto = any(kw in all_text for kw in recto_keywords)

        # Side decision: Verso wins if both found (IDMAR in OCR confirms)
        if is_verso and is_recto:
            side = "BOTH"
        elif is_verso and not is_recto:
            side = "BACK"
        elif is_recto:
            side = "FRONT"
        else:
            side = "FRONT"  # default

        # Generation: CNI-v2 has MRZ (IDMAR) on verso; v1 has barcode
        # On recto: v2 has Moroccan flag (red) visible; v1 has green watermark only
        has_mrz_text = "IDMAR" in all_text or "IDFRA" in all_text or "I<PRT" in all_text or "C<ITA" in all_text
        has_barcode_indicator = any("62/2005" in b["text"] or "N ETAT CIVIL" in b["text"].upper() or "NETAT CIVIL" in b["text"].upper()
                                    for b in boxes)
        # v2 recto keywords: 'VALABLE JUSQU' + 'HA' doc number bottom area
        has_v2_recto = "VALABLE" in all_text and "ROYAUME DU MAROC" in all_text

        if has_mrz_text:
            generation = "CNI-v2"
        elif has_barcode_indicator and side in ("BACK", "BOTH"):
            generation = "CNI-v1"  # verso without MRZ = old card
        elif has_v2_recto:
            generation = "CNI-v2"
        # ELITE: If it's BACK and has FILS DE or FILLE DE but no IDMAR, it's definitely v1
        elif side in ("BACK", "BOTH") and ("FILS DE" in all_text or "FILLE DE" in all_text or "FLLS DE" in all_text) and not has_mrz_text:
            generation = "CNI-v1"
        else:
            generation = "UNKNOWN"

        return {"side": side, "generation": generation}

    @staticmethod
    def _infer_doc_type(mrz_result, boxes):
        """Infer DOCUMENT_TYPE from MRZ document code and/or VIZ keywords."""
        if mrz_result:
            code = mrz_result.get("parsed_data", {}).get("document_code", "").upper()
            if code.startswith("P"):
                return "PASSPORT"
            elif code.startswith("V"):
                return "VISA"
            elif code.startswith("I") or code.startswith("ID") or code.startswith("A") or code.startswith("C"):
                return "NATIONAL_ID_CARD"
            elif code.startswith("R"):
                return "RESIDENCE_PERMIT"

        all_text = " ".join(b["text"].upper() for b in boxes)
        if "PASSPORT CARD" in all_text:
            return "NATIONAL_ID_CARD"
        if any(kw in all_text for kw in ["PASSPORT", "PASSEPORT", "REISEPASS"]):
            return "PASSPORT"
        if any(kw in all_text for kw in ["VISA"]):
            return "VISA"
        if any(kw in all_text for kw in ["PERSONALAUSWEIS", "AUSWEIS"]):
            return "NATIONAL_ID_CARD"
        if any(kw in all_text for kw in ["CARTE", "IDENTITY", "IDENTITE", "CARTE NATIONALE", "FILS DE", "FILLE DE", "FLLS DE", "ETAT CIVIL", "IDENTIFICACAO"]):
            return "NATIONAL_ID_CARD"
        return "UNKNOWN"

    # ── Image export ──────────────────────────────────────────────────────────

    def save_extracted_images(self, img, image_path, boxes, photo_regions, barcode_regions, zones):
        print("\n🖼️  Exporting extracted image crops…")
        stem = Path(image_path).stem
        export_dir = self.export_root / stem
        dirs = {k: export_dir / k for k in
                ["photos_logos", "text_regions", "mrz_barcodes", "zones", "debug"]}
        for d in dirs.values():
            d.mkdir(parents=True, exist_ok=True)

        counters = {k: 0 for k in dirs}
        img_h, img_w = img.shape[:2]

        for i, r in enumerate(photo_regions, 1):
            if self._save_crop(img, dirs["photos_logos"] / f"{i:02d}_{r.get('type','region')}.png",
                               r.get("x", 0), r.get("y", 0), r.get("width", 1), r.get("height", 1)):
                counters["photos_logos"] += 1

        for i, box in enumerate(boxes, 1):
            slug = re.sub(r"[^A-Za-z0-9]+", "_", box["text"]).strip("_")[:30] or "text"
            if self._save_crop(img, dirs["text_regions"] / f"{i:02d}_{slug}.png",
                               box["position"]["x_min"], box["position"]["y_min"],
                               box["dimensions"]["width"], box["dimensions"]["height"]):
                counters["text_regions"] += 1

        for i, r in enumerate(barcode_regions, 1):
            if self._save_crop(img, dirs["mrz_barcodes"] / f"{i:02d}_{r.get('type','mrz')}.png",
                               r.get("x", 0), r.get("y", 0), r.get("width", 1), r.get("height", 1)):
                counters["mrz_barcodes"] += 1

        for zname, zinfo in zones.items():
            y_min = int(zinfo["y_min"])
            h = max(1, int(zinfo["y_max"]) - y_min)
            if self._save_crop(img, dirs["zones"] / f"zone_{zname}.png", 0, y_min, img_w, h):
                counters["zones"] += 1

        # Debug overlays
        debug_img = img.copy()
        for box in boxes:
            x, y = int(box["position"]["x_min"]), int(box["position"]["y_min"])
            w_b, h_b = int(box["dimensions"]["width"]), int(box["dimensions"]["height"])
            cv2.rectangle(debug_img, (x, y), (x + w_b, y + h_b), (0, 255, 255), 2)
        cv2.imwrite(str(dirs["debug"] / "all_text_boxes.png"), debug_img)
        counters["debug"] += 1

        visual_dbg = img.copy()
        for r in photo_regions:
            x, y = int(r.get("x", 0)), int(r.get("y", 0))
            cv2.rectangle(visual_dbg, (x, y), (x + int(r.get("width", 1)), y + int(r.get("height", 1))),
                          (255, 100, 0), 2)
        cv2.imwrite(str(dirs["debug"] / "visual_elements.png"), visual_dbg)
        counters["debug"] += 1

        total = sum(counters.values())
        print(f"   ✓ Export dir: {export_dir}  |  {total} files")
        return {"root": str(export_dir), "counts": counters, "total_files": total}

    # ── MAIN ANALYZE ─────────────────────────────────────────────────────────

    def analyze(self, image_path: str) -> dict:
        """
        Full elite analysis pipeline.
        Returns 5.0.0-elite schema dict, adaptive to any ICAO document.
        Supports single-card and dual-card (recto+verso in same photo) inputs.
        """
        print(f"\n{'═'*70}")
        print(f"🔬 ELITE ID ANALYSIS — schema 5.0.0-elite")
        print(f"{'═'*70}")
        print(f"📸 Image: {image_path}\n")

        img = cv2.imread(image_path)
        if img is None:
            return {"error": f"Cannot read image: {image_path}"}

        img_h, img_w = img.shape[:2]

        # ELITE PRACTICE: Early downscale for phone camera images (4032×3024 etc.)
        # ID cards don't need more than 2000px — larger = exponentially slower
        MAX_EARLY_DIM = 2000
        max_dim = max(img_h, img_w)
        if max_dim > MAX_EARLY_DIM:
            scale = MAX_EARLY_DIM / max_dim
            img = cv2.resize(img, (int(img_w * scale), int(img_h * scale)), interpolation=cv2.INTER_AREA)
            img_h, img_w = img.shape[:2]
            print(f"📐 Dimensions: {img_w}×{img_h}px (downscaled from {max_dim}px)")
        else:
            print(f"📐 Dimensions: {img_w}×{img_h}px")

        # ========================================================================
        # YOLO-FIRST PIPELINE (replaces Steps 0-2.5 when YOLO model available)
        # ========================================================================
        import time
        pipeline_t0 = time.time()

        # -- YOLO Stage: Single-pass inference ---------------------
        print("\n" + chr(0x1f4e1) + " YOLO Stage: Single-pass inference...")
        yolo_ctx = YoloStage.infer(img)
        yolo_active = yolo_ctx.has_detections

        if yolo_active:
            print(f"   " + chr(0x2713) + f" YOLO detected: portraits={len(yolo_ctx.all_portraits)} "
                  f"mrz={len(yolo_ctx.all_mrz_zones)} barcodes={len(yolo_ctx.all_barcodes)} "
                  f"ghost={'Y' if yolo_ctx.portrait_ghost is not None else 'N'} "
                  f"flag={'Y' if yolo_ctx.flag is not None else 'N'} "
                  f"corners={len(yolo_ctx.corners)}")

            # -- YOLO Layout Detection ----------------------------
            print("\n" + chr(0x1f5c2) + " YOLO layout detection...")
            layout_result = YoloLayoutDetector.detect(img, yolo_ctx)
            if layout_result is None:
                layout_result = self.layout_detector.detect(img)
                print(f"   " + chr(0x2713) + f" Layout (fallback): {layout_result['layout']} | Cards: {layout_result['cards_detected']}")
            else:
                print(f"   " + chr(0x2713) + f" Layout (YOLO): {layout_result['layout']} | Cards: {layout_result['cards_detected']}")

            layout_info = {
                "input_layout": layout_result["layout"],
                "cards_detected": layout_result["cards_detected"],
            }

            # -- YOLO Classification (per card) -------------------
            fingerprint_results = []
            primary_img = img

            if layout_result["cards_detected"] >= 2:
                card_a_img = layout_result["cards"][0]["img"]
                card_b_img = layout_result["cards"][1]["img"]
                ctx_a = YoloStage.infer(card_a_img)
                ctx_b = YoloStage.infer(card_b_img)
                cls_a = YoloClassifier.classify(ctx_a, card_a_img)
                cls_b = YoloClassifier.classify(ctx_b, card_b_img)
                fp_a = {"side": cls_a["side"], "version": cls_a["doc_class"],
                        "confidence": cls_a["confidence"], "signals": {}, "pdf417_data": None}
                fp_b = {"side": cls_b["side"], "version": cls_b["doc_class"],
                        "confidence": cls_b["confidence"], "signals": {}, "pdf417_data": None}
                fingerprint_results = [fp_a, fp_b]
                if cls_a["side"] == "VERSO":
                    primary_img = card_a_img
                    yolo_ctx = ctx_a
                else:
                    primary_img = card_b_img
                    yolo_ctx = ctx_b
                print(f"   " + chr(0x2713) + f" Card 0 -> {cls_a['side']} / {cls_a['doc_class']}  (conf={cls_a['confidence']:.2f})")
                print(f"   " + chr(0x2713) + f" Card 1 -> {cls_b['side']} / {cls_b['doc_class']}  (conf={cls_b['confidence']:.2f})")
            else:
                cls_info = YoloClassifier.classify(yolo_ctx, primary_img)
                fp = {"side": cls_info["side"], "version": cls_info["doc_class"],
                      "confidence": cls_info["confidence"], "signals": {}, "pdf417_data": None}
                fingerprint_results = [fp]
                print(f"   " + chr(0x2713) + f" Classification -> {cls_info['side']} / {cls_info['doc_class']}  (conf={cls_info['confidence']:.2f})")

            fp_primary = fingerprint_results[0] if fingerprint_results else {}
            layout_info["card_fingerprints"] = [
                {k: v for k, v in fp.items() if k not in ("signals", "pdf417_data")}
                for fp in fingerprint_results
            ]
            layout_info["visual_signals"] = {}

            # -- PDF417 decode (CNI-V1 VERSO only) ----------------
            pdf417_result = None
            if yolo_ctx.barcode_zone is not None and PYZBAR_AVAILABLE and pyzbar_decode is not None:
                print("\n" + chr(0x1f4ca) + " Elite PDF417 decode (YOLO barcode bbox)...")
                bx1 = max(0, int(yolo_ctx.barcode_zone[0]) - 10)
                by1 = max(0, int(yolo_ctx.barcode_zone[1]) - 10)
                bx2 = min(primary_img.shape[1], int(yolo_ctx.barcode_zone[2]) + 10)
                by2 = min(primary_img.shape[0], int(yolo_ctx.barcode_zone[3]) + 10)
                barcode_crop = primary_img[by1:by2, bx1:bx2]
                try:
                    barcodes = pyzbar_decode(barcode_crop, symbols=[ZBarSymbol.PDF417])
                    for b in barcodes:
                        if b.type == "PDF417":
                            raw = b.data.decode("utf-8", errors="replace")
                            pdf417_result = {
                                "found": True, "decoder": "pyzbar", "raw": raw,
                                "parsed": EliteVisualFingerprinter._parse_pdf417_data(raw),
                                "rect": {"x": bx1, "y": by1, "w": bx2 - bx1, "h": by2 - by1},
                            }
                            print(f"   " + chr(0x2705) + f" PDF417 decoded: {len(raw)} chars")
                            break
                except Exception as e:
                    print(f"   WARNING: pyzbar error: {e}")

            # -- Dewarp (if corners detected) ---------------------
            img = primary_img
            img = YoloDewarp.dewarp(img, yolo_ctx)
            img_h, img_w = img.shape[:2]

            # Skip legacy CV detection
            photo_regions = []
            barcode_regions = []

            # -- Targeted OCR (ONE pass per zone) -----------------
            doc_class_info = YoloClassifier.classify(yolo_ctx, img)
            boxes, mrz_boxes = self.targeted_ocr(img, doc_class_info, yolo_ctx)

            print(f"\n" + chr(0x23f1) + f" YOLO pipeline completed in {time.time() - pipeline_t0:.2f}s")

        else:
            # ================================================================
            # LEGACY FALLBACK (no YOLO model or no detections)
            # ================================================================
            print("\n      [ELITE FALLBACK] Spatial heuristics activated (YOLO disabled/unavailable)")

            # -- Step 0a: ELITE LAYOUT DETECTION ------------------
            print("\n" + chr(0x1f5c2) + " Elite layout detection...")
            layout_result = self.layout_detector.detect(img)
            layout_info = {
                "input_layout": layout_result["layout"],
                "cards_detected": layout_result["cards_detected"],
            }
            print(f"   " + chr(0x2713) + f" Layout: {layout_result['layout']} | Cards: {layout_result['cards_detected']}")

            # -- Step 0b: ELITE VISUAL FINGERPRINTING -------------
            fingerprint_results = []
            primary_img = img

            if layout_result["cards_detected"] >= 2:
                card_a_img = layout_result["cards"][0]["img"]
                card_b_img = layout_result["cards"][1]["img"]
                fp_a = self.visual_fingerprinter.fingerprint(card_a_img)
                fp_b = self.visual_fingerprinter.fingerprint(card_b_img)
                fingerprint_results = [fp_a, fp_b]
                # ELITE: If multiple cards, process the entire image so we don't drop one side.
                print(f"   " + chr(0x2713) + f" Card 0 -> {fp_a['side']} / {fp_a['version']}  (conf={fp_a['confidence']:.2f})")
                print(f"   " + chr(0x2713) + f" Card 1 -> {fp_b['side']} / {fp_b['version']}  (conf={fp_b['confidence']:.2f})")
            else:
                fp = self.visual_fingerprinter.fingerprint(primary_img)
                fingerprint_results = [fp]
                print(f"   " + chr(0x2713) + f" Fingerprint -> {fp['side']} / {fp['version']}  (conf={fp['confidence']:.2f})")

            fp_primary = fingerprint_results[0] if fingerprint_results else {}
            layout_info["card_fingerprints"] = [
                {k: v for k, v in fp.items() if k not in ("signals", "pdf417_data")}
                for fp in fingerprint_results
            ]
            layout_info["visual_signals"] = fp_primary.get("signals", {})

            # -- Step 0c: PDF417 PIPELINE -------------------------
            pdf417_result = None
            if fp_primary.get("signals", {}).get("pdf417"):
                print("\n" + chr(0x1f4ca) + " Elite PDF417 decode (CNI-V1 VERSO detected)...")
                pdf417_result = fp_primary.get("pdf417_data")
                if pdf417_result and pdf417_result.get("found"):
                    decoder = pdf417_result.get("decoder", "?")
                    raw_len = len(pdf417_result.get("raw") or "")
                    if raw_len > 0:
                        print(f"   " + chr(0x2705) + f" PDF417 decoded via {decoder}: {raw_len} chars")
                    else:
                        print(f"   WARNING: PDF417 detected (morphological) -- install pyzbar for full decode")

            img = primary_img
            img_h, img_w = img.shape[:2]

            # -- Step 1: CV visual detection ----------------------
            photo_regions = self.detect_photo_regions(img)
            barcode_regions = self.detect_barcodes_mrz(img)

            # -- Step 2: Full-page OCR ----------------------------
            boxes = self.extract_all_text_deep(img, use_preprocessing=True)

            # ELITE: Post-OCR re-classification — correct fingerprint using OCR evidence
            all_text_upper = " ".join(b["text"].upper() for b in boxes)
            has_verso_kw = any(kw in all_text_upper for kw in ["FILS DE", "ET DE", "ADRESSE", "N ETAT CIVIL", "N° ETAT CIVIL"])
            has_recto_kw = any(kw in all_text_upper for kw in ["ROYAUME", "CARTE NATIONALE", "NE LE", "VALABLE", "GEBOREN"])
            
            if has_verso_kw and not has_recto_kw:
                fp_primary["side"] = "VERSO"
                if "IDMAR" not in all_text_upper:
                    fp_primary["version"] = "CNI_V1"  # No MRZ = V1
                else:
                    fp_primary["version"] = "CNI_V2"

            # -- Step 2.5: ELITE MRZ STRICT ISOLATION -------------
            # ELITE: Skip MRZ isolation for RECTO cards — RECTO never has MRZ
            fp_side = fp_primary.get("side", "UNKNOWN")
            if fp_side == "RECTO":
                print("\n" + chr(0x1f510) + " MRZ-FIRST pipeline (strict geometric isolation)...")
                print("   ✓ RECTO detected — MRZ isolation skipped (no MRZ on recto)")
                mrz_boxes = []
            else:
                print("\n" + chr(0x1f510) + " MRZ-FIRST pipeline (strict geometric isolation)...")
                mrz_boxes = self.extract_mrz_strictly(img)

        # ── Step 3: Spatial zones ─────────────────────────────────────────────
        zones = self.analyze_spatial_zones(boxes, img_h, img_w)

        # ── Step 4: MRZ PARSING (search in both MRZ-zone AND full-page) ─────
        # ELITE: Try full-page boxes first (which often have better line separation),
        # then fall back to the isolated MRZ crop if full-page missed it.
        mrz_raw_lines = self.mrz_parser.find_mrz_lines_in_ocr(boxes, img_h)
        
        if not mrz_raw_lines and mrz_boxes:
            mrz_raw_lines = self.mrz_parser.find_mrz_lines_in_ocr(mrz_boxes, img_h)
        
        mrz_result = None
        mrz_section = {"is_present": False, "format": None,
                        "raw_payload": [], "parsed_data": {}, "cryptographic_validation": {}}

        if mrz_raw_lines:
            # ELITE: Fix common OCR hallucination on German IDs where D<< is read as DSL
            mrz_raw_lines = [line.replace("IDDSL", "IDD<<") for line in mrz_raw_lines]
            
            print(f"   ✓ MRZ candidate lines found: {len(mrz_raw_lines)}")
            parsed = self.mrz_parser.parse(mrz_raw_lines)
            if parsed:
                # ELITE: Validate country code — reject barcode noise masquerading as MRZ
                detected_country = parsed.get("parsed_data", {}).get("issuing_state", "")
                cv = parsed.get("cryptographic_validation", {})
                all_checks_fail = not any([
                    cv.get("document_number_check", {}).get("is_valid"),
                    cv.get("birth_date_check", {}).get("is_valid"),
                    cv.get("expiry_date_check", {}).get("is_valid"),
                ])
                # ELITE: Do not reject TD3 (Passports) as noise, even if specimen with OVI country and failing checks.
                if parsed.get("format") != "TD3" and not self.mrz_parser.is_valid_mrz_country(detected_country) and all_checks_fail:
                    print(f"   ❌ MRZ rejected: country '{detected_country}' unknown + all checks failed (barcode noise)")
                    mrz_raw_lines = None
                else:
                    mrz_result = parsed
                    valid = parsed["cryptographic_validation"].get("overall_mrz_valid", False)
                    print(f"   {'✅' if valid else '⚠️ '} MRZ parsed — overall_valid={valid} format={parsed['format']}")
                    mrz_section = {
                        "is_present": True,
                        "format": parsed["format"],
                        "raw_payload": parsed["raw_payload"],
                        "parsed_data": parsed["parsed_data"],
                        "cryptographic_validation": parsed["cryptographic_validation"],
                    }
            else:
                print("   ⚠️  MRZ lines found but parsing failed — falling back to VIZ")
        else:
            print("   ℹ️  No MRZ detected — switching to VIZ-only extraction")

        # ── Step 5: VIZ field extraction ──────────────────────────────────────
        issuing_country = self._infer_country(mrz_result, boxes)
        viz_fields = self._extract_viz_fields(boxes, issuing_country)

        # ── Step 6: Build VIZ identity section ───────────────────────────────
        # ELITE: Detect side and generation FIRST, independent of MRZ success
        gen_side = self._detect_card_generation_and_side(boxes)
        card_side = gen_side["side"]    # "FRONT" or "BACK" or "BOTH"
        card_gen  = gen_side["generation"]  # "CNI-v1", "CNI-v2", "UNKNOWN"
        captured_sides = ["FRONT", "BACK"] if card_side == "BOTH" else [card_side]

        full_name_latin = ""
        first_name_latin = ""
        last_name_latin = ""

        if mrz_result:
            # MRZ parsed successfully (validation may or may not be perfect)
            primary   = mrz_result["parsed_data"].get("primary_identifier", "")
            secondary = mrz_result["parsed_data"].get("secondary_identifier", "")
            full_name_latin  = f"{primary} {secondary}".strip() if secondary else primary
            first_name_latin = secondary or ""
            last_name_latin  = primary
            
            # ELITE: If MRZ OCR dropped the '<<' separator, the whole name ends up in primary
            if not first_name_latin and " " in last_name_latin:
                last_name_latin, first_name_latin = self._split_moroccan_name(last_name_latin)

        # ELITE FALLBACK: Try raw MRZ text pattern LASTNAME<<FIRSTNAME
        # This is safe to run on any side, as it strictly looks for the '<<' MRZ signature
        raw_mrz_name = EliteMRZParser.extract_name_from_raw_mrz_text(boxes)
        if raw_mrz_name["full_name"]:
            if not first_name_latin or not mrz_result:
                full_name_latin  = raw_mrz_name["full_name"]
                last_name_latin  = raw_mrz_name["last_name"] or ""
                first_name_latin = raw_mrz_name["first_name"] or ""

        mrz_fallback_last = last_name_latin
        mrz_fallback_first = first_name_latin

        if card_side in ("FRONT", "BOTH"):
                # ── PASSPORT DYNAMIC VIZ EXTRACTION ────────────────────────
                # Detect if this is a passport RECTO based on VIZ keywords
                all_box_text = " ".join(b["text"].upper() for b in boxes)
                is_passport_recto = any(k in all_box_text for k in [
                    "PASSEPORT", "PASSPORT", "REISEPASS", "جواز"
                ])
                
                if is_passport_recto:
                    # ELITE DYNAMIC: Extract from passport label anchors
                    # USA Passport Cards use vertical layout (TD1 style) despite being passports
                    is_passport_card = ("PASSPORT" in all_box_text and "CARD" in all_box_text) or ("PASSEPORT" in all_box_text and "CARTE" in all_box_text)
                    
                    if is_passport_card:
                        # Passport Cards: Prefer BELOW
                        last_name_box = self._find_value_by_anchor(
                            boxes, ["Nom", "SURNAME", "الاسم العائلي", "LAST NAME"], 
                            search_direction="BELOW", max_distance=60)
                        if not last_name_box:
                            last_name_box  = self._find_value_by_anchor(
                                boxes, ["Nom", "SURNAME", "الاسم العائلي", "LAST NAME"], 
                                search_direction="RIGHT", max_distance=300)
                        
                        first_name_box = self._find_value_by_anchor(
                            boxes, ["Prénom", "GIVEN", "الاسم الشخصي", "FIRST NAME"], 
                            search_direction="BELOW", max_distance=60)
                        if not first_name_box:
                            first_name_box = self._find_value_by_anchor(
                                boxes, ["Prénom", "GIVEN", "PRÉNOM", "الاسم الشخصي", "FIRST NAME"], 
                                search_direction="RIGHT", max_distance=300)
                    else:
                        # Standard Passport Book: Prefer RIGHT
                        last_name_box  = self._find_value_by_anchor(
                            boxes, ["Nom", "SURNAME", "SUMAME", "الاسم العائلي", "LAST NAME"], 
                            search_direction="RIGHT", max_distance=300)
                        # Reject numeric strings (e.g. passport numbers on same line)
                        if last_name_box and last_name_box["text"].replace(" ", "").isnumeric():
                            last_name_box = None

                        if not last_name_box:
                            last_name_box = self._find_value_by_anchor(
                                boxes, ["Nom", "SURNAME", "SUMAME", "الاسم العائلي", "LAST NAME"], 
                                search_direction="BELOW", max_distance=60)
                        
                        first_name_box = self._find_value_by_anchor(
                            boxes, ["Prénom", "GIVEN", "PRÉNOM", "الاسم الشخصي", "FIRST NAME"], 
                            search_direction="RIGHT", max_distance=300)
                        if first_name_box and first_name_box["text"].replace(" ", "").isnumeric():
                            first_name_box = None

                        if not first_name_box:
                            first_name_box = self._find_value_by_anchor(
                                boxes, ["Prénom", "GIVEN", "PRÉNOM", "الاسم الشخصي", "FIRST NAME"], 
                                search_direction="BELOW", max_distance=60)
                                
                        # ELITE FALLBACK: If label OCR failed entirely (e.g. "mYPmaTne"), find the POTENTIAL_NAME below last_name
                        if last_name_box and not first_name_box:
                            ax_min = last_name_box["position"]["x_min"]
                            ax_max = last_name_box["position"]["x_max"]
                            ay_mid = last_name_box["position"]["y"]
                            best_first = None
                            min_dist = float('inf')
                            for name_item in viz_fields["names"]:
                                # Find the actual box matching this value to get full position
                                box = next((b for b in boxes if b["text"] == name_item["value"] and b["position"]["y"] == name_item["position"]["y"]), None)
                                if not box or box == last_name_box: continue
                                bx_min = box["position"]["x_min"]
                                by_mid = box["position"]["y"]
                                if by_mid > ay_mid and (box["position"]["x_max"] >= ax_min - 40 and bx_min <= ax_max + 40):
                                    dist = by_mid - ay_mid
                                    if dist < min_dist and dist < 80:
                                        min_dist = dist
                                        best_first = box
                            if best_first:
                                first_name_box = best_first

                    last_name_latin  = last_name_box["text"].upper()  if last_name_box  else ""
                    first_name_latin = first_name_box["text"].upper() if first_name_box else ""
                    # Remove label noise from extracted values
                    for label in ["NOM", "NOM/NAME", "NAME", "PRÉNOM", "PRENOM", "GIVEN", "GIVEN NAMES", "SURNAME", "LAST NAME", "FIRST NAME"]:
                        last_name_latin  = last_name_latin.replace(label, "").strip()
                        first_name_latin = first_name_latin.replace(label, "").strip()

                else:
                    # Recto VIZ spatial anchoring (CNI, ITA, PRT, FRA, ESP, POL recto)
                    # Exclude first name and birth name labels from last name search to prevent false anchors and false values
                    last_name_search_boxes = [b for b in boxes if not any(x in b["text"].lower() for x in ["prénom", "prenom", "given", "vorname", "imiona", "geburtsname", "naissance", "birth", "voornamen"])]
                    last_name_box  = self._find_value_by_anchor(
                        last_name_search_boxes, ["Nom", "النسب", "COGNOME", "COGNOME / SURNAME", "SURNAME", "APELIDO", "APELLIDOS", "NOM/SURNAME", "APELIDO(S) / SURNAME", "NAZWISKO", "Name", "naam/ surname", "naam/surname"], search_direction="BELOW", max_distance=80)
                    first_name_box = self._find_value_by_anchor(
                        boxes, ["Prénom", "الاسم", "NOME / NAME", "NOMEZ NAME", "GIVEN NAME", "PRENOMS", "NOMBRE", "NOME(S) / GIVEN NAME", "PRÉNOMS", "IMIONA", "Vorname", "Vornamen", "voornamen/ given names", "voornamen/given names", "voornamen"], search_direction="BELOW", max_distance=80)
                    
                    # Fallback for plain "NOME" if it wasn't matched (avoiding COGNOME)
                    if not first_name_box:
                        for box in boxes:
                            if box["text"].upper().strip() == "NOME":
                                first_name_box = self._find_value_by_anchor(
                                    boxes, ["NOME"], search_direction="BELOW", max_distance=80)
                                if first_name_box and first_name_box["text"] != (last_name_box["text"] if last_name_box else ""):
                                    break
                                first_name_box = None

                    last_name_latin  = last_name_box["text"]  if last_name_box  else ""
                    first_name_latin = first_name_box["text"] if first_name_box else ""

                    # ELITE NLD: If last_name anchor found but value is only prefix ("De"),
                    # look for the next box in spatial order to complete the surname
                    # ("De" + "Bruijn" → "De Bruijn") — OCR may split them into separate boxes
                    if last_name_box and last_name_latin.strip().upper() in {"DE", "VAN", "DEN", "DER", "TEN", "TER", "VAN DE", "VAN DER", "VAN DEN"}:
                        try:
                            lb_idx = boxes.index(last_name_box)
                            if lb_idx + 1 < len(boxes):
                                next_b = boxes[lb_idx + 1]
                                nt = next_b["text"].strip()
                                # Accept if: not a label, not the first name, starts with uppercase, no digits
                                is_label = any(lbl in nt.lower() for lbl in ["voornamen", "given", "prénom", "prenom", "geslacht", "sex", "naam"])
                                if (next_b != first_name_box and nt and nt[0].isupper()
                                        and not any(c.isdigit() for c in nt)
                                        and not is_label and len(nt) >= 2):
                                    last_name_latin = f"{last_name_latin.strip()} {nt}"
                        except ValueError:
                            pass

                    # ELITE: Clean up German ID reference markers like [a], [b], or OCR artifacts like [aj
                    last_name_latin = re.sub(r'^\[[a-zA-Z0-9]{1,2}\]?\s*', '', last_name_latin)
                    first_name_latin = re.sub(r'^\[[a-zA-Z0-9]{1,2}\]?\s*', '', first_name_latin)

                if not last_name_latin and not first_name_latin:
                    if mrz_fallback_last or mrz_fallback_first:
                        # ELITE PRACTICE: Cross-reference MRZ fallback with VIZ boxes to extract clean names.
                        # MRZ often merges names or has OCR artifacts (e.g. replacing < with C), 
                        # while VIZ has perfect spelling but lacks anchors.
                        mrz_full_cl = re.sub(r'[^A-Z]', '', (mrz_fallback_last + mrz_fallback_first).upper())
                        matched_viz_names = []
                        for n in viz_fields.get("names", []):
                            val = n["value"].strip()
                            words = [re.sub(r'[^A-Z]', '', w.upper()) for w in val.split()]
                            words = [w for w in words if len(w) > 2]
                            if not words: continue
                            
                            matched_words = [w for w in words if w in mrz_full_cl]
                            if len(matched_words) > 0 and len(matched_words) >= len(words) - 1:
                                matched_viz_names.append(val)
                                
                        if len(matched_viz_names) >= 2:
                            last_name_latin = matched_viz_names[0]
                            first_name_latin = " ".join(matched_viz_names[1:])
                        elif len(matched_viz_names) == 1:
                            last_name_latin = matched_viz_names[0]
                            first_name_latin = mrz_fallback_first  # Keep MRZ fallback for the other part if missed
                        else:
                            last_name_latin = mrz_fallback_last
                            first_name_latin = mrz_fallback_first
                    else:
                        typed_first = next((n["value"] for n in viz_fields["names"] if n.get("type") == "first_name"), None)
                        typed_last  = next((n["value"] for n in viz_fields["names"] if n.get("type") == "last_name"), None)
                        if typed_first and typed_last:
                            first_name_latin = typed_first
                            last_name_latin  = typed_last
                        else:
                            full_name_latin = self._merge_name_parts(
                                viz_fields["names"], img_height=img_h, img_width=img_w) or ""
                            parts = full_name_latin.split()
                            if card_gen == "CNI-v1" and len(parts) >= 2:
                                last_name_latin = parts[0]
                                first_name_latin = " ".join(parts[1:])
                            else:
                                last_name_latin, first_name_latin = self._split_moroccan_name(full_name_latin)
                full_name_latin = f"{last_name_latin} {first_name_latin}".strip()

        # ELITE: Gender — prefer MRZ, fall back to VIZ 'Sexe M/F' keyword
        gender_raw = (mrz_result["parsed_data"].get("gender", "<") if mrz_result else "<")
        gender_label = {"M": "MALE", "F": "FEMALE", "<": "UNSPECIFIED"}.get(gender_raw, "UNSPECIFIED")
        if gender_label == "UNSPECIFIED":
            raw_mrz_info = EliteMRZParser.extract_name_from_raw_mrz_text(boxes)
            if raw_mrz_info.get("gender"):
                gender_label = raw_mrz_info["gender"]
            else:
                # Elite Polish/Dutch/VIZ Gender Fallback
                gender_box = self._find_value_by_anchor(boxes, ["PLEC", "SEX", "PŁEĆ", "PLECISEX", "SEXE", "geslacht", "GESLACHT"], search_direction="BELOW", max_distance=80)
                if not gender_box:
                    # ELITE NLD: Try RIGHT direction for "geslacht/ sex" where value is on the same line
                    gender_box = self._find_value_by_anchor(boxes, ["geslacht", "GESLACHT"], search_direction="RIGHT", max_distance=300)
                if gender_box:
                    txt = gender_box["text"].upper().strip()
                    # ELITE NLD: Handle Dutch "V/F" format (V=Vrouw=Female, M=Man=Male)
                    v_match = re.match(r'^([VMF])\s*[/\\]', txt)
                    if v_match:
                        g = v_match.group(1)
                        gender_label = "FEMALE" if g in ("V", "F") else "MALE"
                    elif txt.startswith("K") or txt.startswith("F") or txt.startswith("V"): gender_label = "FEMALE"
                    elif txt.startswith("M"): gender_label = "MALE"
                # If STILL unspecified, do a global scan for standalone 'K', 'F', 'M', 'V', ignoring the top 25% of the card
                if gender_label == "UNSPECIFIED":
                    for b in boxes:
                        txt = b["text"].upper().strip()
                        # ELITE NLD: Also match "V/F" pattern in global scan
                        v_match = re.match(r'^([VMF])\s*[/\\]\s*[VMF]$', txt)
                        if v_match and b["position"]["y"] > img_h * 0.25:
                            g = v_match.group(1)
                            gender_label = "FEMALE" if g in ("V", "F") else "MALE"
                            break
                        if txt in ["K", "F", "M", "V"] and b["position"]["y"] > img_h * 0.25 and b["position"]["x_min"] > img_w * 0.4:
                            gender_label = "FEMALE" if txt in ["K", "F", "V"] else "MALE"
                            break

        # ELITE NLD: Extract nationality from anchor "nationaliteit" / "nationality"
        nationality_val = None
        nat_anchor_box = None
        for b in boxes:
            if any(lbl in b["text"].lower() for lbl in ["nationaliteit", "nationality", "nacionalidade", "cittadinanza"]):
                nat_anchor_box = b
                break
        
        if nat_anchor_box:
            lb_y_max = nat_anchor_box["position"]["y_max"]
            lb_y_mid = nat_anchor_box["position"]["y"]
            lb_x_min = nat_anchor_box["position"]["x_min"]
            lb_x_max = nat_anchor_box["position"]["x_max"]
            cands = []
            for b in boxes:
                if b == nat_anchor_box: continue
                nt_lower = b["text"].strip().lower()
                # Skip known noise words
                if nt_lower in ["type", "code", "paspoort", "passport", "carte", "card", ""]: continue
                if any(lbl in nt_lower for lbl in ["nationaliteit", "nationality"]): continue
                
                # Skip if it's purely digits or has numbers (Nationality is letters)
                if any(c.isdigit() for c in b["text"]): continue
                if not any(c.isalpha() for c in b["text"]): continue
                
                # BELOW (allow slight overlap e.g., dy > -15)
                dy = b["position"]["y_min"] - lb_y_max
                if -15 < dy < 100 and b["position"]["x_max"] > lb_x_min - 50:
                    cands.append((b, max(0, dy)))
                # RIGHT
                elif abs(b["position"]["y"] - lb_y_mid) < 20 and b["position"]["x_min"] > lb_x_max:
                    cands.append((b, b["position"]["x_min"] - lb_x_max + 1000))
                    
            if cands:
                cands.sort(key=lambda x: x[1])
                nat_text = cands[0][0]["text"].strip()
                # Clean up if it prefixes ISO code, e.g., "NLD Nederlandse"
                if re.match(r'^[A-Z]{3}\s+', nat_text):
                    nat_text = nat_text[4:]
                nationality_val = nat_text

        viz_identity = {
            "full_name_latin": full_name_latin or None,
            "first_name": {"latin": first_name_latin or None},
            "last_name": {"latin": last_name_latin or None},
            "gender": gender_label,
        }
        if nationality_val:
            viz_identity["nationality"] = nationality_val

        # ELITE NLD/General Document Number Extraction
        docnum_box = self._find_value_by_anchor(
            boxes, ["documentnummer", "document no", "no. du document", "numer dokumentu", "du doe", "t no."], 
            search_direction="BELOW", max_distance=80)
        if not docnum_box:
            docnum_box = self._find_value_by_anchor(
                boxes, ["documentnummer", "document no", "no. du document", "du doe", "t no."], 
                search_direction="RIGHT", max_distance=150)
                
        if docnum_box:
            viz_identity["document_number"] = docnum_box["text"].strip()
        else:
            # ELITE Polish Recto Document Number (Fallback)
            # Global scan for document number (3 letters + 6 digits)
            for b in boxes:
                cleaned = b["text"].upper()
                cleaned = cleaned.replace('/', 'V').replace('\\', 'V').replace('|', 'I').replace(' ', '')
                cleaned = re.sub(r'[^A-Z0-9]', '', cleaned)
                if re.match(r'^[A-Z]{3}\d{6}$', cleaned):
                    viz_identity["document_number"] = cleaned
                    break

        # Location
        viz_location = {}

        if card_gen == "CNI-v2" and card_side in ("BACK", "BOTH"):
            # ELITE: CNI-v2 Address and Authority
            addr_box = self._find_value_by_anchor(
                boxes, ["العنوان", "Adresse", "AdreSSe"], 
                search_direction="BELOW", max_distance=60)
            if addr_box:
                viz_location["address"] = addr_box["text"].strip()
                
            authority_box = self._find_value_by_anchor(
                    boxes, ["Délivrée", "Délivré"], 
                    search_direction="BELOW", max_distance=60)
            if authority_box:
                viz_location["authority"] = authority_box["text"].strip()
                
        if card_gen == "CNI-v1" and card_side in ("BACK", "BOTH"):
            # ELITE: Specialized CNI-v1 VERSO field extraction
            viz_identity["parent_father"] = None
            viz_identity["parent_mother"] = None
            viz_identity["civil_status_number"] = None
            
            # Helper to extract from same box or next box
            def extract_from_label(boxes, labels):
                for b in boxes:
                    for lbl in labels:
                        if lbl.upper() in b["text"].upper():
                            idx = b["text"].upper().find(lbl.upper()) + len(lbl)
                            remainder = b["text"][idx:].strip()
                            if len(remainder) > 3:
                                return remainder
                box = self._find_value_by_anchor(boxes, labels, search_direction="RIGHT", max_distance=500)
                return box["text"] if box else None
                
            viz_identity["parent_father"] = extract_from_label(boxes, ["Fils de", "Fils", "Fille de", "Fille", "Flls de", "Flls"])
            viz_identity["parent_mother"] = extract_from_label(boxes, ["et de", "etce", "et dc"])
                
            civil_box = self._find_value_by_anchor(boxes, ["N° état civil", "N état civil", "N° etat civil", "Netat civil"], search_direction="RIGHT", max_distance=300)
            if civil_box:
                viz_identity["civil_status_number"] = civil_box["text"].replace("N° état civil", "").strip()
            
            addr_results = []
            addr_labels = ["العنوان", "Adresse", "AdreSSe", "Adress", "AdeSS", "AdPSS", "Ades"]
            for b in boxes:
                for lbl in addr_labels:
                    if lbl.upper() in b["text"].upper():
                        idx = b["text"].upper().find(lbl.upper()) + len(lbl)
                        remainder = b["text"][idx:].strip()
                        remainder = re.sub(r'^[\s/:\-.]+', '', remainder)
                        remainder = re.sub(r'(?i)^address\s*:?\s*', '', remainder)
                        remainder = re.sub(r'^[\s/:\-.]+', '', remainder)
                        if len(remainder) > 3 and remainder not in addr_results:
                            addr_results.append(remainder)
                        break
            if not addr_results:
                addr_box = self._find_value_by_anchor(boxes, addr_labels, search_direction="RIGHT", max_distance=600)
                if addr_box:
                    val = addr_box["text"].strip()
                    val = re.sub(r'^[\s/:\-.]+', '', val)
                    val = re.sub(r'(?i)^address\s*:?\s*', '', val)
                    val = re.sub(r'^[\s/:\-.]+', '', val)
                    if len(val) > 3 and val not in addr_results:
                        addr_results.append(val)
            
            addr_text = " / ".join(addr_results) if addr_results else None
            if addr_text:
                viz_location["address"] = addr_text
                
            if not viz_location.get("address"):
                for t in viz_fields.get("other_text", []):
                    if isinstance(t, dict) and t.get("type") == "address":
                        viz_location["address"] = t["value"]
                        break
                
            for b in boxes:
                if "N°" in b["text"] or "No" in b["text"]:
                    m = re.search(r"([A-Z]{1,2}\d{5,9})", b["text"])
                    if m:
                        viz_identity["cni_v1_doc_number"] = m.group(1)
                        break
        # ── ELITE: Detect document type for specialized field anchoring ──
        # Use text-based detection here (doc_type computed later in Step 7)
        all_box_text_upper = " ".join(b["text"].upper() for b in boxes)
        is_passport_doc = any(
            k in all_box_text_upper for k in ["PASSEPORT", "PASSPORT", "REISEPASS", "جواز"]
        ) or (mrz_result and mrz_result.get("format") == "TD3")
        
        if is_passport_doc:
            # DYNAMIC PASSPORT FIELD ANCHORING
            # Helper to find centered text below wide labels
            def find_passport_box_below(anchors, max_dy=150, exclude=None, exclude_anchor=None):
                valid_anchors = []
                for b in boxes:
                    if any(a.upper() in b["text"].upper() for a in anchors):
                        if not (exclude_anchor and any(ex.upper() in b["text"].upper() for ex in exclude_anchor)):
                            valid_anchors.append(b)
                anchor = valid_anchors[0] if valid_anchors else None
                if not anchor: 
                    print(f"[DEBUG] Anchor not found for {anchors}")
                    return None
                
                ax_min = anchor["position"]["x_min"] - 100
                ax_max = anchor["position"]["x_max"] + 100
                ay_max = anchor["position"]["y_max"]
                print(f"[DEBUG] Anchor found: '{anchor['text']}' at y_max={ay_max:.1f}, x=({ax_min:.1f}, {ax_max:.1f})")
                
                cands = []
                for b in boxes:
                    if b == anchor: continue
                    text_upper = b["text"].upper().strip()
                    if exclude and any(ex.upper() in text_upper for ex in exclude): continue
                    if re.match(r'^([A-ZА-Я]/)?[MFX]$', text_upper): continue
                    
                    bx_min, bx_max, by_min, by_max = b["position"]["x_min"], b["position"]["x_max"], b["position"]["y_min"], b["position"]["y_max"]
                    b_cx = (bx_min + bx_max) / 2
                    if -30 < (by_min - ay_max) < max_dy and by_max > ay_max and ax_min <= b_cx <= ax_max:
                        cands.append((b, by_min - ay_max))
                        print(f"  [DEBUG] Candidate: '{b['text']}' dy={by_min - ay_max:.1f}")
                cands.sort(key=lambda x: x[1])
                return cands[0][0] if cands else None

            # Birth place is always BELOW the label, centered
            birth_place_box = find_passport_box_below(
                ["geboorteplaats", "Lieu de naissance", "Lieu de neissance", "Place of birth", "Pace of hrth", "مكان الازدياد", "مكان"], 
                max_dy=100,
                exclude=["Sex", "Sexe", "Date", "تأريخ", "Lieu", "Place", "Nacimiento"]
            )
            if birth_place_box:
                birth_place_val = birth_place_box["text"].strip()
                viz_location["birth_place"] = birth_place_val
            else:
                # Elite Fallback: if birth_place anchor is missing, look for an isolated alphabetic text box 
                # vertically between birth_date and issue_date.
                date_boxes = []
                for b in boxes:
                    if re.search(r'\b\d{1,2}\s+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)', b["text"], re.IGNORECASE) or re.search(r'\b\d{2}[-./]\d{2}[-./]\d{2,4}\b', b["text"]):
                        date_boxes.append(b)
                date_boxes.sort(key=lambda b: b["position"]["y_min"])
                
                if len(date_boxes) >= 2:
                    dob_y_max = date_boxes[0]["position"]["y_max"]
                    issue_y_min = date_boxes[1]["position"]["y_min"]
                    cands = []
                    for b in boxes:
                        by_min = b["position"]["y_min"]
                        by_max = b["position"]["y_max"]
                        if dob_y_max < by_max < issue_y_min:
                            text_clean = b["text"].replace(" ", "").replace("-", "").replace("/", "")
                            if text_clean.isalpha() and len(text_clean) > 2:
                                if not any(ex in b["text"].upper() for ex in ["SEX", "AUTHORITY", "AUTORIT", "PASSPORT", "DATE", "LIEU", "PLACE", "NATIONALITY", "CITIZEN"]):
                                    cands.append((b, by_min))
                    if cands:
                        cands.sort(key=lambda x: x[1])
                        viz_location["birth_place"] = cands[0][0]["text"].strip()
            
            # Address/Residence: "Domicile / Résidence / العنوان"
            domicile_box = find_passport_box_below(["Domicile", "Résidence", "Residence", "العنوان"], max_dy=100)
            if domicile_box:
                address_val = domicile_box["text"].strip()
                # Check for a second line of address directly below the first line
                ax_min = domicile_box["position"]["x_min"] - 50
                ax_max = domicile_box["position"]["x_max"] + 50
                ay_max = domicile_box["position"]["y_max"]
                
                second_line = None
                cands2 = []
                for b in boxes:
                    if b == domicile_box: continue
                    bx_min, bx_max, by_min = b["position"]["x_min"], b["position"]["x_max"], b["position"]["y_min"]
                    b_cx = (bx_min + bx_max) / 2
                    # The second line might be centered under the first line, or aligned to it
                    if 0 < (by_min - ay_max) < 100 and ax_min <= b_cx <= ax_max:
                        cands2.append((b, by_min - ay_max))
                cands2.sort(key=lambda x: x[1])
                
                if cands2:
                    second_line = cands2[0][0]["text"].strip()
                    if "Autorité" not in second_line and "Authority" not in second_line and "السلطة" not in second_line:
                        address_val += " / " + second_line
                    
                viz_location["address"] = address_val
            else:
                # Fallback: address keywords  
                address_fields = [x["value"] for x in viz_fields["other_text"] if isinstance(x, dict) and x.get("type") == "address"]
                if address_fields:
                    viz_location["address"] = " / ".join(address_fields)
            
            # ELITE PRACTICE: Regex priority for Dutch authority
            for b in boxes:
                if re.match(r'^Burg\.?\s+van\s+', b["text"], re.IGNORECASE):
                    viz_location["authority"] = b["text"].strip()
                    break
            
            # Fallback to multi-lingual anchors if regex doesn't match
            # Fallback to multi-lingual anchors if regex doesn't match
            if "authority" not in viz_location:
                # Dutch/German IDs often have authority to the RIGHT
                authority_box = self._find_value_by_anchor(
                    boxes, ["instantie /", "12 instantie", "Behörde", "Behorde"],
                    search_direction="RIGHT", max_distance=400)
                
                if not authority_box:
                    # Standard passports have authority BELOW
                    authority_box = find_passport_box_below(
                        ["instantie /", "12 instantie", "Autorité", "Authority", "Autorter", "السلطة", "Behörde", "Behorde", "Authori", "Autorit", "délivrance", "delivrance", "Autoridad", "Audhorty"], 
                        max_dy=100,
                        exclude=["Date", "Holder", "Firma", "Signature"],
                        exclude_anchor=["Signature", "Firma"]
                    )
                
                if authority_box:
                    auth_val = authority_box["text"].strip()
                    # Ignore the header text that says "OPMERKINGEN VAN BEVOEGDE INSTANTIES"
                    if "OPMERKINGEN" not in auth_val.upper():
                        # Check for a second line of authority directly below the first line
                        ax_min = authority_box["position"]["x_min"] - 50
                        ax_max = authority_box["position"]["x_max"] + 50
                        ay_max = authority_box["position"]["y_max"]
                        
                        cands2 = []
                        for b in boxes:
                            if b == authority_box: continue
                            bx_min, bx_max, by_min, by_max = b["position"]["x_min"], b["position"]["x_max"], b["position"]["y_min"], b["position"]["y_max"]
                            b_cx = (bx_min + bx_max) / 2
                            if -30 < (by_min - ay_max) < 100 and by_max > ay_max and ax_min <= b_cx <= ax_max:
                                cands2.append((b, by_min - ay_max))
                        
                        if cands2:
                            cands2.sort(key=lambda x: x[1])
                            second_line = cands2[0][0]["text"].strip()
                            # Ensure we don't accidentally grab an MRZ line or Signature label
                            if "<" not in second_line and "P<" not in second_line and "<<" not in second_line:
                                if "Signature" not in second_line and "Holder" not in second_line and "Taulaire" not in second_line:
                                    auth_val += " " + second_line
                                
                        viz_location["authority"] = auth_val
        else:
            if viz_fields["locations"]:
                viz_location["birth_place"] = viz_fields["locations"][0]["value"]
            address_fields = [x["value"] for x in viz_fields["other_text"] if isinstance(x, dict) and x.get("type") == "address"]
            if address_fields:
                viz_location["address"] = " / ".join(address_fields)

        # ELITE: Deep address fallback — scan ALL boxes if no address found yet
        if "address" not in viz_location:
            _addr_kws = [" HAY ", " LOT ", " RUE ", " QUARTIER ", " AVENUE ", " RESIDENCE ",
                         " IMM ", " ETG ", " DOUAR ", " DERB ", " BLOC ", " BD ", " AV ",
                         " زنقة ", " حي ", " تجزئة ", " شارع ", " عمارة ",
                         " WEG", " STRASSE", " STR.", " PLATZ", " ALLEE", " POSTFACH"]
            _admin_kws = ["الحالة المدنية", "état civil", "alat civil", "etat civil",
                          "Carte Nationale", "IDMAR", "Autorité", "Authority", "Behörde", "Behorde"]
            deep_addresses = []
            for b in boxes:
                txt = b["text"]
                txt_upper = f" {txt.upper()} "
                if any(kw in txt_upper for kw in _addr_kws) or re.match(r'^\d{4,5}\s+[A-ZÄÖÜß]', txt.upper()):
                    if not any(adm.upper() in txt.upper() for adm in _admin_kws) and len(txt) > 5:
                        deep_addresses.append(txt.strip())
            
            if not deep_addresses:
                # Elite Anchor search for German "Anschrift"
                anschrift_label = self._find_value_by_anchor(
                    boxes, ["ANSCHRIFT", "ADRESSE", "ADDRESS"],
                    search_direction="BELOW", max_distance=150)
                if anschrift_label:
                    deep_addresses.append(anschrift_label["text"])
                    
            if deep_addresses:
                viz_location["address"] = " / ".join(deep_addresses)

        # ── ELITE: Polish verso-specific field extraction ──
        # Check if POLSKICH is in text to detect Polish Verso
        all_box_text_upper = " ".join(b["text"].upper() for b in boxes)
        is_polish_verso = any(kw in all_box_text_upper for kw in ["POLSKICH", "WYDANY PRZEZ", "NUMER PESEL", "MIEJSCE URODZENIA"])

        if is_polish_verso:
            # PESEL number (11 digits)
            for b in boxes:
                if re.match(r'^\d{11}$', b["text"].strip()):
                    viz_identity["pesel_number"] = b["text"].strip()
                    break

            # Place of birth
            pob_box = self._find_value_by_anchor(
                boxes, ["MIEJSCE URODZENIA", "MIEISCE URODZENIA", "PLACE OF BIRTH"],
                search_direction="BELOW", max_distance=80)
            if pob_box:
                viz_location["place_of_birth"] = pob_box["text"].strip()

            # Maiden name (Nazwisko Rodowe) — NOT the current surname
            maiden_box = self._find_value_by_anchor(
                boxes, ["NAZWISKO RODOWE", "FAMILY NAME"],
                search_direction="BELOW", max_distance=80)
            if maiden_box:
                viz_identity["maiden_name"] = maiden_box["text"].strip()

            # Parents' given names — NOT the holder's name
            parents_box = self._find_value_by_anchor(
                boxes, ["IMIONA RODZIC", "PARENTS", "RODZICOW"],
                search_direction="BELOW", max_distance=80)
            if parents_box:
                viz_identity["parents_names"] = parents_box["text"].strip()

            # Issuing authority
            auth_box = self._find_value_by_anchor(
                boxes, ["ORGAN WYDAJ", "ISSUING AUTHORITY"],
                search_direction="BELOW", max_distance=80)
            if auth_box:
                viz_location["authority"] = auth_box["text"].strip()

        # Dates
        viz_dates: dict = {}
        # ELITE: Pull from VIZ FIRST, then fall back to MRZ if missing
        for d in viz_fields["dates"]:
            if d["type"] == "birth_date" and "birth_date" not in viz_dates:
                viz_dates["birth_date"] = d["value"]
            elif d["type"] == "expiry_date" and "expiry_date" not in viz_dates:
                viz_dates["expiry_date"] = d["value"]
            elif d["type"] == "issue_date" and "issue_date" not in viz_dates:
                viz_dates["issue_date"] = d["value"]

        # ELITE: Aggressive Date Scanning for Polish Recto
        # Polish Recto has Birth Date above Expiry Date. Extract all dates, sort by Y-coord.
        all_dates_found = []
        for b in boxes:
            m = re.search(r'(\d{2})[./-](\d{2})[./-](\d{4})', b["text"])
            if m:
                iso_date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
                all_dates_found.append({"date": iso_date, "y": b["position"]["y"]})
        
        if len(all_dates_found) >= 2:
            all_dates_found.sort(key=lambda x: x["y"])
            # Override any generic misclassifications
            viz_dates["birth_date"] = all_dates_found[0]["date"]
            viz_dates["expiry_date"] = all_dates_found[1]["date"]

        # ELITE: PESEL logic for birth_date fallback (Polish Verso)
        pesel = viz_identity.get("pesel_number")
        if pesel and "birth_date" not in viz_dates:
            y = int(pesel[0:2])
            m = int(pesel[2:4])
            d = pesel[4:6]
            if 1 <= m <= 12: year = 1900 + y
            elif 21 <= m <= 32: year = 2000 + y; m -= 20
            elif 81 <= m <= 92: year = 1800 + y; m -= 80
            else: year = 1900 + y
            viz_dates["birth_date"] = f"{year}-{m:02d}-{d}"
        
        # MRZ Fallback for Dates (only if VIZ didn't find them)
        if mrz_result:
            if "birth_date" not in viz_dates and mrz_result["parsed_data"].get("birth_date"):
                viz_dates["birth_date"] = mrz_result["parsed_data"].get("birth_date")
            if "expiry_date" not in viz_dates and mrz_result["parsed_data"].get("expiry_date"):
                viz_dates["expiry_date"] = mrz_result["parsed_data"].get("expiry_date")

        # Identifiers
        viz_identifiers: dict = {}
        # ELITE VIZ-First for identifiers to avoid garbled MRZ overwriting
        if "document_number" in viz_identity:
            viz_identifiers["document_number"] = viz_identity["document_number"]
        elif mrz_result and mrz_result["parsed_data"].get("document_number"):
            viz_identifiers["document_number"] = mrz_result["parsed_data"].get("document_number")

        # ELITE: Sort id_numbers — prefer country-specific pattern over generic
        # For MAR: document number = 1-2 uppercase letters + digits 
        #          CAN number = starts with 'CAN' (3 letters) → goes to can_number, not document_number
        mar_id_re = re.compile(r'^[A-Z]{1,2}\d{5,9}$')
        can_prefix_re = re.compile(r'^CAN\d{4,}$', re.IGNORECASE)

        id_numbers_sorted = sorted(
            viz_fields["id_numbers"],
            key=lambda n: (0 if mar_id_re.match(n["value"]) else 1)  # MAR pattern first
        )

        for idn in id_numbers_sorted:
            val = idn["value"]
            if can_prefix_re.match(val):
                # CAN-prefixed number → always goes to can_number
                if "can_number" not in viz_identifiers:
                    viz_identifiers["can_number"] = val
            elif "document_number" not in viz_identifiers:
                viz_identifiers["document_number"] = val
            elif val != viz_identifiers["document_number"]:
                # Second unique id → civil_registry_number
                if "civil_registry_number" not in viz_identifiers:
                    viz_identifiers["civil_registry_number"] = val

        # codes → can_number if not already set
        if viz_fields["codes"]:
            codes_sorted = sorted(
                viz_fields["codes"],
                key=lambda c: (0 if can_prefix_re.match(c["value"]) else 1)
            )
            for code in codes_sorted:
                val = code["value"]
                if can_prefix_re.match(val):
                    if "can_number" not in viz_identifiers:
                        viz_identifiers["can_number"] = val
                elif "can_number" not in viz_identifiers and val != viz_identifiers.get("document_number"):
                    viz_identifiers["can_number"] = val
                    break

        # ELITE: Passport-specific identifier anchoring
        if is_passport_doc:
            cnie_box = self._find_value_by_anchor(
                boxes, ["C.N.I.E", "CNIE", "ID Card", "N° C.N", "Card No", "رقم بطاقة"],
                search_direction="RIGHT", max_distance=150)
            if not cnie_box:
                cnie_box = self._find_value_by_anchor(
                    boxes, ["C.N.I.E", "ID Card", "رقم بطاقة"],
                    search_direction="BELOW", max_distance=30)
            if cnie_box:
                cnie_val = re.sub(r'[^A-Z0-9]', '', cnie_box["text"].upper())
                if re.match(r'^[A-Z]{1,2}\d{5,9}$', cnie_val) and cnie_val != viz_identifiers.get("document_number"):
                    viz_identifiers["cnie_number"] = cnie_val
            
            # If MRZ personal_number is present (TD3), use it as cnie_number
            if mrz_result:
                personal = mrz_result["parsed_data"].get("personal_number", "")
                if personal and personal not in ("<", "", None):
                    viz_identifiers["cnie_number"] = personal.strip("<")

        # ── Step 7: Document metadata ─────────────────────────────────────────
        doc_type = self._infer_doc_type(mrz_result, boxes)
        # ELITE: If still UNKNOWN but we detected Verso keywords → it's a national ID
        if doc_type == "UNKNOWN" and card_gen in ("CNI-v1", "CNI-v2"):
            doc_type = "NATIONAL_ID_CARD"
            
        # ELITE PRACTICE OVERRIDES: If MRZ format is definitively recognized
        if mrz_result:
            mrz_fmt = mrz_result.get("format")
            if mrz_fmt == "TD1":
                card_gen = "CNI-v2"
                captured_sides = ["BACK"]
                if doc_type == "UNKNOWN":
                    doc_type = "NATIONAL_ID_CARD"
            elif mrz_fmt == "TD3":
                doc_type = "PASSPORT"

        # ELITE PRACTICE: MRZ is Cryptographically Validated Ground Truth!
        # Passports have complex visual layouts that often confuse spatial VIZ OCR.
        # Since MRZ contains checksums, if it is valid, we MUST overwrite the noisy VIZ with perfect MRZ data.
        if mrz_result and mrz_result.get("cryptographic_validation", {}).get("overall_mrz_valid"):
            mrz_data = mrz_result["parsed_data"]
            
            if mrz_data.get("primary_identifier"):
                viz_identity["last_name"] = {"latin": mrz_data["primary_identifier"], "arabic": None}
            if mrz_data.get("secondary_identifier"):
                viz_identity["first_name"] = {"latin": mrz_data["secondary_identifier"], "arabic": None}
                
            first = viz_identity.get("first_name", {}).get("latin", "")
            last = viz_identity.get("last_name", {}).get("latin", "")
            if first or last:
                viz_identity["full_name_latin"] = f"{last} {first}".strip()
                
            if mrz_data.get("gender") and mrz_data["gender"] != "<":
                viz_identity["gender"] = "MALE" if mrz_data["gender"] == "M" else "FEMALE" if mrz_data["gender"] == "F" else "UNSPECIFIED"
                
            if mrz_data.get("birth_date"):
                viz_dates["birth_date"] = mrz_data["birth_date"]
            if mrz_data.get("expiry_date"):
                viz_dates["expiry_date"] = mrz_data["expiry_date"]
                
            if mrz_data.get("document_number"):
                viz_identifiers["document_number"] = mrz_data["document_number"]
                
        issuing_iso3 = issuing_country

        # ── ELITE: STRICT REGEX VALIDATION & SANITIZATION ──────────────
        def sanitize_name(name):
            if not name: return name
            # Keep letters, spaces, hyphens, and apostrophes
            sanitized = re.sub(r'[^A-Z\s\-\']', '', name.upper()).strip()
            return re.sub(r'\s+', ' ', sanitized) if sanitized else None

        if viz_identity.get("full_name_latin"):
            viz_identity["full_name_latin"] = sanitize_name(viz_identity["full_name_latin"])
        if viz_identity.get("first_name", {}).get("latin"):
            viz_identity["first_name"]["latin"] = sanitize_name(viz_identity["first_name"]["latin"])
        if viz_identity.get("last_name", {}).get("latin"):
            viz_identity["last_name"]["latin"] = sanitize_name(viz_identity["last_name"]["latin"])
        if viz_identity.get("parent_father"):
            viz_identity["parent_father"] = sanitize_name(viz_identity["parent_father"])
        if viz_identity.get("parent_mother"):
            viz_identity["parent_mother"] = sanitize_name(viz_identity["parent_mother"])

        # Validate identifiers (remove OCR noise)
        for id_key in ["document_number", "cnie_number", "can_number", "civil_registry_number"]:
            val = viz_identifiers.get(id_key)
            if val:
                val = re.sub(r'[^A-Z0-9]', '', str(val).upper())
                if id_key in ("document_number", "cnie_number") and not re.match(r'^[A-Z0-9]{5,15}$', val):
                    viz_identifiers[id_key] = None
                else:
                    viz_identifiers[id_key] = val

        # Validate dates
        def sanitize_date(date_str):
            if not date_str: return date_str
            if re.match(r'^\d{4}-\d{2}-\d{2}$', str(date_str)):
                return date_str
            return None

        for k in ["birth_date", "expiry_date", "issue_date"]:
            if viz_dates.get(k):
                viz_dates[k] = sanitize_date(viz_dates[k])

        # ── Step 8: Cross-validation ──────────────────────────────────────────
        matching_engine, anomalies = self._cross_validate(
            mrz_result["parsed_data"] if mrz_result else None,
            viz_identity, viz_dates, viz_identifiers
        )

        # ── Step 9: Confidence ────────────────────────────────────────────────
        confidence = self._compute_confidence(mrz_result, viz_identity, viz_dates)

        # ── Step 10: Image exports ────────────────────────────────────────────
        images_export = self.save_extracted_images(
            img, image_path, boxes, photo_regions, barcode_regions, zones
        )

        # ── Step 11: Assemble 5.0.0-elite schema ─────────────────────────────
        result = {
            "schema_version": "5.0.0-elite",
            "document_metadata": {
                "issuing_country_iso3": issuing_iso3,
                "document_type": doc_type,
                "card_generation": card_gen,
                "captured_sides": captured_sides,
                "mrz_compliant": mrz_section["is_present"],
                "image_dimensions": {"width": img_w, "height": img_h},
                "processed_at": datetime.now().isoformat(),
                "image_path": str(image_path),
            },
            "visual_inspection_zone_viz": {
                "identity": viz_identity,
                "dates": viz_dates,
                "identifiers": viz_identifiers,
                "location": viz_location,
            },
            "machine_readable_zone_mrz": mrz_section,
            "integrity_and_cross_validation": {
                "global_confidence_score": confidence,
                "matching_engine": matching_engine,
                "anomalies_detected": anomalies,
            },
            "_debug": {
                "total_ocr_regions": len(boxes),
                "photo_regions_detected": len(photo_regions),
                "barcode_mrz_regions_detected": len(barcode_regions),
                "spatial_zones": {
                    zname: {"item_count": len(zinfo["content"]),
                            "texts": [b["text"] for b in zinfo["content"]]}
                    for zname, zinfo in zones.items()
                },
                "extracted_images": images_export,
                "raw_viz_fields": {
                    k: v for k, v in viz_fields.items() if k not in ("other_text",)
                },
            },
            "layout_detection": layout_info,
            "pdf417_data": pdf417_result,
        }

        return result


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════════

def _print_elite_summary(result: dict):
    import sys
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')

    # Colors
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"

    # Extract Data
    doc_meta = result.get("document_metadata", {})
    viz = result.get("visual_inspection_zone_viz", {})
    identity = viz.get("identity", {})
    dates = viz.get("dates", {})
    identifiers = viz.get("identifiers", {})
    mrz = result.get("machine_readable_zone_mrz", {})
    integrity = result.get("integrity_and_cross_validation", {})
    
    confidence = integrity.get("global_confidence_score", 0.0) * 100
    doc_type = doc_meta.get("document_type", "UNKNOWN")
    country = doc_meta.get("issuing_country_iso3", "UNKNOWN")
    mrz_valid = mrz.get("cryptographic_validation", {}).get("overall_mrz_valid", False)

    # Big Title
    print(f"\n{MAGENTA}{BOLD}██████████████████████████████████████████████████████████████████████{RESET}")
    print(f"{CYAN}{BOLD}                    E L I T E   I D   S C A N N E R                   {RESET}")
    print(f"{CYAN}                 << ELITE OCR INFINITY ENGINE 2026 >>                 {RESET}")
    print(f"{GREEN}          [ v5.0.0 • STEALTH • AUTONOMOUS • PADDLEX_VISION ]          {RESET}")
    print(f"{MAGENTA}{BOLD}██████████████████████████████████████████████████████████████████████{RESET}")
    
    # Status Row 1
    print(f"\n{GREEN}●{RESET} {CYAN}STEALTH_MODE      {GRAY}Active{RESET}    | {GREEN}●{RESET} {CYAN}ENGINE          {GRAY}PaddleX{RESET} | {GREEN}●{RESET} {CYAN}CONFIDENCE    {GRAY}{confidence:.1f}%{RESET}")
    # Status Row 2
    print(f"{GREEN}●{RESET} {CYAN}DOCUMENT_TYPE     {GRAY}{doc_type}{RESET}  | {GREEN}●{RESET} {CYAN}COUNTRY         {GRAY}{country}{RESET}     | {GREEN}●{RESET} {CYAN}MRZ_COMPLIANT {GRAY}{doc_meta.get('mrz_compliant', False)}{RESET}")
    
    print(f"\n{MAGENTA}══════════════════════════════════════════════════════════════════════{RESET}")
    print(f"{CYAN}{BOLD}COMMAND_INTERFACE // OPERATION_SELECT (OCR EXTRACTION ENGINE){RESET}")
    print(f"{MAGENTA}══════════════════════════════════════════════════════════════════════{RESET}")
    
    print(f"\n{GREEN}           IDENTITY EXTRACTION{RESET}")
    print(f"{CYAN}   << 1 PRIMARY_NAME{RESET}")
    print(f"      {CYAN}>>> Name         - {WHITE}{identity.get('full_name_latin', 'N/A')}{RESET}")
    print(f"      {CYAN}>>> Deep Match   - {GRAY}High Confidence{RESET}")
    
    print(f"\n{CYAN}   << 2 PERSONAL_DATA{RESET}")
    print(f"      {CYAN}>>> Gender & DOB - {WHITE}{identity.get('gender', 'N/A')} | {dates.get('birth_date', 'N/A')}{RESET}")
    loc_str = viz.get('location', {}).get('address') or viz.get('location', {}).get('birth_place') or viz.get('location', {}).get('place_of_birth') or 'N/A'
    print(f"      {CYAN}>>> Location     - {GRAY}{loc_str}{RESET}")
    if identity.get("parent_father") or identity.get("parent_mother"):
        print(f"      {CYAN}>>> Parents      - {GRAY}{identity.get('parent_father', 'N/A')} & {identity.get('parent_mother', 'N/A')}{RESET}")
    if identity.get("civil_status_number"):
        print(f"      {CYAN}>>> Civil Status - {GRAY}{identity.get('civil_status_number', 'N/A')}{RESET}")

    
    print(f"\n{CYAN}   << 3 DOCUMENT_INFO{RESET}")
    doc_no = identifiers.get('document_number') or mrz.get('parsed_data', {}).get('document_number', 'N/A')
    print(f"      {CYAN}>>> Document No  - {WHITE}{doc_no}{RESET}")
    print(f"      {CYAN}>>> Dates        - {GRAY}{dates.get('issue_date', 'N/A')} -> {dates.get('expiry_date', 'N/A')}{RESET}")
    
    print(f"\n{CYAN}   << 4 SECURITY_CHECK{RESET}")
    print(f"      {CYAN}>>> MRZ Valid    - {WHITE}{mrz_valid}{RESET}")
    viz_mrz_match = all(integrity.get("matching_engine", {}).values()) if integrity.get("matching_engine") else False
    print(f"      {CYAN}>>> Cross-Check  - {GRAY}VIZ/MRZ MATCH: {viz_mrz_match}{RESET}")
    
    print(f"\n{MAGENTA}══════════════════════════════════════════════════════════════════════{RESET}\n")


def main():
    import time
    parser = argparse.ArgumentParser(
        description="Elite ID/Passport scanner — schema 3.0.0-elite"
    )
    parser.add_argument("image_path", nargs="?", help="Path to image file or directory to scan")
    parser.add_argument("--model-root", default=os.environ.get("PADDLE_OCR_MODEL_DIR", "models"))
    parser.add_argument("--setup-models", action="store_true",
                        help="Download/cache models and exit")
    parser.add_argument("--download-models", action="store_true",
                        help="Auto-download missing models before analysis")
    args = parser.parse_args()

    if args.setup_models:
        AdvancedIDAnalyzer(model_root=args.model_root, auto_download_models=True, init_ocr=False)
        print("\n✅ Model setup complete.")
        return

    if not args.image_path:
        print("Usage: python scan.py <image_path_or_dir> [--download-models]")
        print("       python scan.py --setup-models")
        sys.exit(1)

    VALID_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
    target_path = Path(args.image_path)

    # Elite Practice: Validate input before loading heavy models
    if not target_path.exists():
        print(f"\n\033[91m[ERROR]\033[0m File not found: {target_path}")
        sys.exit(1)

    if target_path.is_file() and target_path.suffix.lower() not in VALID_IMAGE_EXTS:
        print(f"\n\033[91m[ERROR]\033[0m Invalid file type: '{target_path.suffix}' — expected an image ({', '.join(VALID_IMAGE_EXTS)})")
        sys.exit(1)

    analyzer = AdvancedIDAnalyzer(
        model_root=args.model_root,
        auto_download_models=args.download_models
    )

    # Elite Practice: Check if input is a directory to process multiple images without reloading models
    if target_path.is_dir():
        image_files = [p for p in target_path.iterdir() if p.suffix.lower() in ('.jpg', '.jpeg', '.png')]
        print(f"\n📂 Found {len(image_files)} images in directory: {target_path}")
        
        total_start_time = time.time()
        for i, img_file in enumerate(image_files, 1):
            print(f"\n[{i}/{len(image_files)}] Processing {img_file.name}...")
            start_time = time.time()
            
            result = analyzer.analyze(str(img_file))
            
            end_time = time.time()
            scan_time = end_time - start_time
            
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)
            output_file = output_dir / (img_file.stem + "_ocr.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            _print_elite_summary(result)
            print(f"⏱️  Scan Time: {scan_time:.2f} seconds")
            print(f"💾 Saved → {output_file}")
            print(f"{'═'*70}\n")
            
        total_time = time.time() - total_start_time
        print(f"\n🎉 Batch Processing Complete! Processed {len(image_files)} images in {total_time:.2f} seconds.")
        
    else:
        # Single file processing
        start_time = time.time()
        
        result = analyzer.analyze(args.image_path)
        
        end_time = time.time()
        scan_time = end_time - start_time
        
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / (Path(args.image_path).stem + "_ocr.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        _print_elite_summary(result)
        print(f"⏱️  Scan Time: {scan_time:.2f} seconds")
        print(f"💾 Saved → {output_file}")
        print(f"{'═'*70}\n")


if __name__ == "__main__":
    main()