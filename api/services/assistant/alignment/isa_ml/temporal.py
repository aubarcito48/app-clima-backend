"""Own regularized temporal linear classifier with optional sequence decoding."""
import numpy as np
from api.services.assistant.alignment.isa_ml.classifier import SHAPES
VERSION = 'isa-context-ridge-v1'
NONLINEAR_VERSION = 'isa-context-rff-v1'
OFFSETS = (-4, -2, 0, 2, 4)
