"""Model loading and inference. The pipeline is loaded once at process start."""
from __future__ import annotations

import json
import logging
import os
import time

import joblib
import pandas as pd

from app.config import settings
from app.schemas import FlightRequest
from constants import FEATURES
from utils import risk_level

logger = logging.getLogger(__name__)
