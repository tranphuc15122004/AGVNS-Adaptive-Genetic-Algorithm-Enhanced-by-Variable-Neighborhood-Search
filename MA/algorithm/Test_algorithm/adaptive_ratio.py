"""Adaptive crossover ratio computation utilities.

Encapsulates the logic for computing CROSSOVER_TYPE_RATIO using:
 1. KWW (stretched exponential) base decay.
 2. Optional vehicle influence scaling.
 3. Logistic shaping with early-phase power compression (slow start, fast end).

This separation allows easier tuning, testing and plotting without touching the GA core.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Any


@dataclass
class AdaptiveRatioParams:
    # Core size / growth related
    threshold_orders: int = 100          # T
    kww_beta: float = 0.8                # β
    kww_tau_factor: float = 3.0          # tau = factor * T

    # Bounds on pre-weight ratio
    min_ratio: float = 0.0
    max_ratio: float = 0.95

    # Vehicle influence 0..1
    vehicle_influence: float = 0.0

    # Logistic shaping
    pivot_fraction: float = 0.5          # c
    logistic_slope: float = 8.0          # s
    early_shape: float = 0.7             # alpha (<1 => slower early decay)

    # Safety clamps
    def clamp(self) -> None:
        if self.threshold_orders <= 0:
            self.threshold_orders = 1
        if self.kww_beta <= 0:
            self.kww_beta = 0.8
        if self.kww_tau_factor <= 0:
            self.kww_tau_factor = 3.0
        if not (0 <= self.min_ratio <= self.max_ratio <= 1):
            self.min_ratio, self.max_ratio = 0.0, 0.95
        self.vehicle_influence = max(0.0, min(1.0, self.vehicle_influence))
        self.pivot_fraction = float(min(0.9, max(0.1, self.pivot_fraction)))
        self.logistic_slope = float(max(0.5, self.logistic_slope))
        self.early_shape = float(max(0.1, self.early_shape))


def compute_adaptive_ratio(num_orders: int, num_vehicles: int, p: AdaptiveRatioParams) -> Dict[str, Any]:
    """Compute crossover ratio and return detailed diagnostics.

    Returns
    -------
    dict with keys: ratio, base, weight, and all intermediate pieces.
    """
    p.clamp()
    T = p.threshold_orders

    # 1. Base KWW decay
    tau = p.kww_tau_factor * T
    if tau <= 0:
        tau = float(T)

    if num_orders >= T:
        base = 0.0
    else:
        x = num_orders / tau
        try:
            base = math.exp(-(x ** p.kww_beta))
        except OverflowError:
            base = 0.0

    # 2. Vehicle influence
    if p.vehicle_influence > 0 and num_vehicles > 0 and num_orders < T:
        kv = max(1.0, T / 10.0)
        veh_scale = num_vehicles / (num_vehicles + kv)
        base = (1 - p.vehicle_influence) * base + p.vehicle_influence * (base * veh_scale)

    # 3. Shaping progress
    prog = 1.0 if num_orders >= T else num_orders / T
    prog_early = prog ** p.early_shape

    # Logistic
    start = 1.0 / (1.0 + math.exp(p.logistic_slope * (0 - p.pivot_fraction)))
    end = 1.0 / (1.0 + math.exp(p.logistic_slope * (1 - p.pivot_fraction)))
    raw = 1.0 / (1.0 + math.exp(p.logistic_slope * (prog_early - p.pivot_fraction)))
    denom = max(1e-12, start - end)
    weight = (raw - end) / denom
    weight = max(0.0, min(1.0, weight))

    # 4. Combine
    ratio_pre = p.min_ratio + (p.max_ratio - p.min_ratio) * base
    ratio = ratio_pre * weight
    if num_orders >= T:
        ratio = 0.0
    ratio = max(0.0, min(1.0, ratio))

    return {
        'ratio': ratio,
        'num_orders': num_orders,
        'num_vehicles': num_vehicles,
        'threshold_T': T,
        'tau': tau,
        'base': base,
        'weight': weight,
        'ratio_pre': ratio_pre,
        'pivot_fraction': p.pivot_fraction,
        'logistic_slope': p.logistic_slope,
        'early_shape': p.early_shape,
        'kww_beta': p.kww_beta,
        'kww_tau_factor': p.kww_tau_factor,
        'min_ratio': p.min_ratio,
        'max_ratio': p.max_ratio,
        'vehicle_influence': p.vehicle_influence,
    }


def compute_adaptive_ratio_quadratic(  # kept name for backward compatibility
    num_orders: int,
    num_vehicles: int,
    p: AdaptiveRatioParams,
    *,
    power: float = 3.0,
    cutoff: bool = True,
    allow_negative: bool = False,  # retained (no effect now, but kept for API stability)
) -> Dict[str, Any]:
    """Exponential (y = e^x) based schedule (replaces previous quadratic version).

    Normalised form:
        base_raw = (exp(k * (1 - prog)) - 1) / (exp(k) - 1),  prog = n/T ∈ [0,1]
    So:
        prog = 0  -> base_raw = 1
        prog = 1  -> base_raw = 0

    Meaning: large k ("power" parameter) keeps value ~1 for most of early phase
    then drops rapidly near the end (slow-early / fast-late). If k→0, it tends
    to a linear schedule (1 - prog).

    Parameters
    ----------
    power : float
        Steepness k (>0). Typical: 1.0 (moderate), 3.0 (sharper tail), 5.0+ (very sharp).
    cutoff : bool
        If True, hard set ratio=0 after reaching T.
    allow_negative : bool
        Kept for interface compatibility (ignored as base_raw is already in [0,1]).
    """
    p.clamp()
    T = max(1, p.threshold_orders)
    n = max(0, num_orders)
    prog = min(1.0, n / T)

    k = max(1e-6, float(power))  # prevent division by zero
    ek = math.exp(k)
    numerator = math.exp(k * (1.0 - prog)) - 1.0
    denom = ek - 1.0
    if denom <= 0:
        base_raw = 0.0
    else:
        base_raw = numerator / denom

    # Safety clamp
    base_raw = max(0.0, min(1.0, base_raw))
    base = base_raw  # already the shaped value

    ratio_pre = p.min_ratio + (p.max_ratio - p.min_ratio) * base
    ratio = ratio_pre
    if cutoff and n >= T:
        ratio = 0.0
    ratio = max(0.0, min(1.0, ratio))

    return {
        'mode': 'exponential',
        'ratio': ratio,
        'ratio_pre': ratio_pre,
        'base': base,
        'base_raw': base_raw,
        'k_param': k,
        'num_orders': n,
        'num_vehicles': num_vehicles,
        'threshold_T': T,
        'min_ratio': p.min_ratio,
        'max_ratio': p.max_ratio,
        'cutoff': cutoff,
        # Compatibility fields (unused):
        'kww_beta': p.kww_beta,
        'kww_tau_factor': p.kww_tau_factor,
        'pivot_fraction': p.pivot_fraction,
        'logistic_slope': p.logistic_slope,
        'early_shape': p.early_shape,
        'vehicle_influence': p.vehicle_influence,
    }


def compute_adaptive_ratio_concave(
    num_orders: int,
    num_vehicles: int,
    p: AdaptiveRatioParams,
    *,
    concave_power: float = 2.0,
    cutoff: bool = True,
) -> Dict[str, Any]:
    """Concave-down (võng xuống gần trục Ox) schedule.

    Uses: base = 1 - prog^k with prog = n/T, k = concave_power (>1 -> steep early drop, flatten tail).
    Then scaled to [min_ratio, max_ratio].

    This ignores logistic / KWW on purpose for a pure shape emphasizing early reduction.
    """
    p.clamp()
    T = max(1, p.threshold_orders)
    n = max(0, num_orders)
    prog = min(1.0, n / T)

    k = max(1.0, concave_power)
    base_shape = 1.0 - (prog ** k)  # 1 -> 0 concave-down
    ratio_pre = p.min_ratio + (p.max_ratio - p.min_ratio) * base_shape
    ratio = ratio_pre
    if cutoff and n >= T:
        ratio = 0.0
    ratio = max(0.0, min(1.0, ratio))

    return {
        'mode': 'concave',
        'ratio': ratio,
        'ratio_pre': ratio_pre,
        'base_shape': base_shape,
        'concave_power': k,
        'num_orders': n,
        'threshold_T': T,
        'min_ratio': p.min_ratio,
        'max_ratio': p.max_ratio,
        'cutoff': cutoff,
    }


def params_from_config(config_module) -> AdaptiveRatioParams:
    """Build params object from a config module (graceful fallbacks)."""
    return AdaptiveRatioParams(
        threshold_orders=getattr(config_module, 'ADAPT_THRESHOLD_ORDERS', 100),
        kww_beta=getattr(config_module, 'ADAPT_KWW_BETA', 0.8),
        kww_tau_factor=getattr(config_module, 'ADAPT_KWW_TAU_FACTOR', 3.0),
        
        min_ratio=getattr(config_module, 'ADAPT_MIN_RATIO', 0.0),
        max_ratio=getattr(config_module, 'ADAPT_MAX_RATIO', 1.0),
        
        vehicle_influence=getattr(config_module, 'ADAPT_NUM_VEHICLE_INFL', 0.0),
        
        pivot_fraction=getattr(config_module, 'ADAPT_PIVOT_FRACTION', 0.5),
        logistic_slope=getattr(config_module, 'ADAPT_ACCEL_SHARPNESS', 8.0),
        early_shape=getattr(config_module, 'ADAPT_SLOW_POWER', 0.7),
    )


__all__ = [
    'AdaptiveRatioParams',
    'compute_adaptive_ratio',
    'compute_adaptive_ratio_quadratic',
    'compute_adaptive_ratio_concave',
    'compute_adaptive_ratio_erfc',
    'params_from_config',
]

def compute_adaptive_ratio_erfc(
    num_orders: int,
    num_vehicles: int,
    p: AdaptiveRatioParams,
    *,
    center: float = 0.7,
    width: float = 0.12,
    cutoff: bool = True,
) -> Dict[str, Any]:
    """ERFC-based smooth schedule with controllable center and width.

    base_raw = 0.5 * erfc( (prog - center) / (sigma * sqrt(2)) ), prog = n/T
    where sigma = width. This yields a bell-tail shape that stays high early
    and drops smoothly around 'center' with spread 'width'.

    Properties:
      - base_raw(0) ~ 1 if center>0 and width small
      - base_raw(1) ~ 0 if center<1 and width small
      - Increasing width -> gentler slope; decreasing width -> sharper drop.
    """
    p.clamp()
    T = max(1, p.threshold_orders)
    n = max(0, num_orders)
    prog = min(1.0, n / T)

    # Numerical safety
    sigma = max(1e-6, float(width))
    mu = float(center)

    # Helper for ERFC value at a given progress
    def erfc_val(pv: float) -> float:
        zloc = (pv - mu) / (sigma * math.sqrt(2.0))
        try:
            return 0.5 * math.erfc(zloc)
        except AttributeError:
            return 0.5 * (1.0 - math.erf(zloc))

    # Raw values at endpoints and current progress
    raw_start = erfc_val(0.0)
    raw_end = erfc_val(1.0)
    raw_prog = erfc_val(prog)

    # Normalize so that base_raw(0)=1 and base_raw(1)=0
    denom = raw_start - raw_end
    if abs(denom) < 1e-12:
        base_raw = 0.0  # degenerate width -> fallback flat
    else:
        base_raw = (raw_prog - raw_end) / denom

    base_raw = max(0.0, min(1.0, base_raw))
    base = base_raw

    ratio_pre = p.min_ratio + (p.max_ratio - p.min_ratio) * base
    ratio = ratio_pre
    if cutoff and n >= T:
        ratio = 0.0
    ratio = max(0.0, min(1.0, ratio))

    return {
        'num_orders' : num_orders,
        'mode': 'erfc',
        'raw_prog' : raw_prog,
        'ratio': ratio,
        'ratio_pre': ratio_pre,
        'base': base,
        'base_raw': base_raw,
        'center': mu,
        'width': sigma,
        'num_orders': n,
        'num_vehicles': num_vehicles,
        'threshold_T': T,
        'min_ratio': p.min_ratio,
        'max_ratio': p.max_ratio,
        'cutoff': cutoff,
    }
