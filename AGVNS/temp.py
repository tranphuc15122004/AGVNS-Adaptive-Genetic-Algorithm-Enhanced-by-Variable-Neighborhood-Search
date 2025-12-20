import math
import numpy as np
from algorithm.Test_algorithm.adaptive_ratio import (
    AdaptiveRatioParams,
    compute_adaptive_ratio,
    compute_adaptive_ratio_quadratic,
    compute_adaptive_ratio_concave,
    compute_adaptive_ratio_erfc,
)


# Global placeholder (mirrors structure in main code)
CROSSOVER_TYPE_RATIO = 0.0

def adaptive_local_configs(num_order: int, num_vehicles: int):
    global CROSSOVER_TYPE_RATIO
    # Standalone plotting parameters (can adjust here for experiments)
    params = AdaptiveRatioParams(
        threshold_orders=100,
        kww_beta=3,
        kww_tau_factor=10.0,
        min_ratio=0.0,
        max_ratio=1.0,
        vehicle_influence=0.0,
        pivot_fraction=0.5,
        logistic_slope=10,
        early_shape=0.7,
    )
    info = compute_adaptive_ratio(num_orders=num_order, num_vehicles=num_vehicles, p=params)
    CROSSOVER_TYPE_RATIO = info['ratio']
    # Map keys to match previous plotting usage
    info['applied_ratio'] = info['ratio']
    info['raw_base'] = info['base']
    return info


def adaptive_local_configs_quadratic(num_order: int, num_vehicles: int, power: float = 4.0):
    """Exponential variant (was quadratic) using normalized exp schedule.

    power (k) càng lớn -> giữ cao lâu hơn rồi rơi nhanh hơn về cuối (độ cong tăng).
    """
    global CROSSOVER_TYPE_RATIO
    params = AdaptiveRatioParams(
        threshold_orders=100,
        kww_beta=0.8,
        kww_tau_factor=10.0,
        min_ratio=0.0,
        max_ratio=1.0,
        vehicle_influence=0.0,
        pivot_fraction=0.5,
        logistic_slope=12.5,
        early_shape=0.7,
    )
    info = compute_adaptive_ratio_quadratic(num_orders=num_order, num_vehicles=num_vehicles, p=params, power=power, cutoff=True)
    CROSSOVER_TYPE_RATIO = info['ratio']
    info['applied_ratio'] = info['ratio']
    info['raw_base'] = info['base']
    return info


import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator

def plot_erfc_only(order_min=0,
                   order_max=200,
                   center=0.5,
                   width=0.2,
                   threshold_orders=80,
                   num_vehicles=20,
                   save_path=None,
                   show_threshold=True,
                   annotate=True,
                   show_legend=True):
    """Vẽ DUY NHẤT một đường ERFC ratio theo số lượng đơn hàng.

    Parameters
    ----------
    order_min, order_max : khoảng số đơn.
    center, width : tham số điều chỉnh vị trí và độ dốc của đường ERFC.
    threshold_orders : ngưỡng để truyền vào AdaptiveRatioParams (dùng chuẩn hoá nếu cần).
    num_vehicles : số xe (ảnh hưởng nếu hàm erfc có dùng).
    save_path : nếu cung cấp, lưu hình ra file.
    """
    orders = np.arange(order_min, order_max + 1)
    params = AdaptiveRatioParams(threshold_orders=threshold_orders, min_ratio=0.0, max_ratio=1.0)
    erfc_vals = [compute_adaptive_ratio_erfc(o, num_vehicles, params, center=center, width=width)['ratio'] for o in orders]

    plt.figure(figsize=(9, 5.2), dpi=140)
    plt.plot(orders, erfc_vals, color='steelblue', linewidth=5.6,
             label=f'ERFC μ={center}, σ={width}')

    ax = plt.gca()
    # Improve ticks and add minor ticks for clearer grid
    ax.tick_params(axis='both', labelsize=9, width=0.9, length=4)
    ax.xaxis.set_minor_locator(AutoMinorLocator())
    ax.yaxis.set_minor_locator(AutoMinorLocator())
    ax.tick_params(axis='both', which='minor', length=2)

    # Optional threshold line
    if show_threshold:
        plt.axvline(threshold_orders, color='crimson', linestyle='--', alpha=0.9, linewidth=2.6,
                     label=f'Threshold T={threshold_orders}')

    if annotate:
        # Derive an approximate center order (assuming center is normalized fraction of span)
        center_order = int(order_min + center * (order_max - order_min))
        # Clamp center_order within range
        center_order = max(order_min, min(order_max, center_order))
        center_ratio = erfc_vals[center_order - order_min]
        # Annotate center point
        """ plt.scatter([center_order], [center_ratio], color='orange', s=55, zorder=5)
        plt.annotate(f'Center≈{center_order}\nRatio={center_ratio:.3f}',
                     xy=(center_order, center_ratio),
                     xytext=(center_order + 5, center_ratio + 0.05),
                     arrowprops=dict(arrowstyle='->', color='orange'),
                     fontsize=9, bbox=dict(boxstyle='round,pad=0.25', fc='white', alpha=0.7)) """

        # Annotate start & end ratios
        start_ratio = erfc_vals[0]
        end_ratio = erfc_vals[-1]
        """ plt.annotate(f'Start={start_ratio:.3f}',
                     xy=(order_min, start_ratio),
                     xytext=(order_min + 8, start_ratio + 0.08),
                     arrowprops=dict(arrowstyle='->', color='gray'),
                     fontsize=8, color='black', bbox=dict(boxstyle='round,pad=0.2', fc='white', alpha=0.6))
        plt.annotate(f'End={end_ratio:.3f}',
                     xy=(order_max, end_ratio),
                     xytext=(order_max - 40, end_ratio + 0.08),
                     arrowprops=dict(arrowstyle='->', color='gray'),
                     fontsize=8, color='black', bbox=dict(boxstyle='round,pad=0.2', fc='white', alpha=0.6))

        # Width note (sigma-like) near center
        plt.annotate(f'Width σ={width}',
                     xy=(center_order, center_ratio),
                     xytext=(center_order - 25, center_ratio - 0.12),
                     fontsize=8, color='dimgray') """
    # Grid styling for clarity
    ax.grid(True, which='major', linestyle='-', alpha=0.35, linewidth=0.8)
    ax.grid(True, which='minor', linestyle=':', alpha=0.25, linewidth=0.6)
    # Sharpen axes spines slightly
    for spine in ax.spines.values():
        spine.set_linewidth(0.9)

    plt.xlabel('Number of Orders', fontsize=14)
    plt.ylabel('CROSSOVER_TYPE_RATIO', fontsize=14)
    plt.title('Adaptive CROSSOVER_TYPE_RATIO', fontsize=15)
    plt.ylim(-0.05, 1.05)
    plt.grid(True, alpha=0.3)
    if show_legend:
        plt.legend(fontsize=11, frameon=True, framealpha=0.85, borderpad=0.6)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=180, bbox_inches='tight')
    plt.show()


if __name__ == "__main__":
    # Vẽ ERFC với đường ngưỡng và chú thích
    plot_erfc_only(order_min=0,
                   order_max=100,
                   center=0.5,
                   width=0.2,
                   threshold_orders=80,
                   num_vehicles=20,
                   save_path=None,
                   show_threshold=True,
                   annotate=False,
                   show_legend=True)