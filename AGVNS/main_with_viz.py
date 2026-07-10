#!/usr/bin/env python3
"""
main_with_viz.py — Run simulation + auto-generate all visualization outputs
================================================================================
Khác với main.py (chỉ chạy simulation, không visualize):
  - Bật VisualizationRecorder để ghi snapshot epoch
  - Sau khi simulation kết thúc, tự động tạo:
      1. timeline.html       (bảng lịch trình node-card)
      2. animated_simulation.html (animation động trên bản đồ)
      3. Validation report   (kiểm tra chéo dữ liệu)

Usage:
    python main_with_viz.py                        # chạy instance mặc định
    python main_with_viz.py --instance 1           # chạy instance 1
    python main_with_viz.py --instance 1,2,3       # chạy nhiều instance
    python main_with_viz.py --no-animation         # bỏ qua animation (nhanh hơn)
    python main_with_viz.py --frame-interval 600   # animation 10 phút/frame
"""

import argparse
import datetime
import os
import sys
import time
import traceback

import numpy as np

# ── Force enable visualization ──
from src.conf.configs import Configs
Configs.ENABLE_VISUALIZATION = True
Configs.VISUALIZATION_RECORD_MODE = "json"
Configs.ENABLE_EXECUTED_ROUTE_RECORDING = True

from src.simulator.simulate_api import simulate
from src.utils.log_utils import ini_logger, remove_file_handler_of_logging
from src.utils.logging_engine import logger


def run_simulation(instance_idx: int) -> float:
    """Run simulation for one instance. Returns score."""
    instance = f"instance_{instance_idx}"
    logger.info(f"{'='*60}")
    logger.info(f"Running {instance}")
    logger.info(f"{'='*60}")
    
    score = simulate(Configs.factory_info_file, Configs.route_info_file, instance)
    logger.info(f"Score of {instance}: {score}")
    return score


def generate_visualizations(instance_idx: int, skip_animation: bool = False,
                            frame_interval: int = 300, playback_speed: int = 80):
    """Generate all visualization outputs for a completed instance."""
    instance_name = f"instance_{instance_idx}"
    vis_dir = os.path.join(Configs.VISUALIZATION_OUTPUT_DIR, instance_name)
    summary_path = os.path.join(vis_dir, "epoch_summary.json")
    
    if not os.path.exists(summary_path):
        print(f"  ⚠ No epoch_summary.json found at {summary_path}")
        print(f"    VisualizationRecorder may not have been called.")
        print(f"    Check that SimulateEnvironment received the visualizer.")
        return
    
    results = {}
    
    # ── 1. Timeline ──
    print(f"\n  📋 Generating timeline...")
    try:
        from build_instance_timeline import main as build_timeline_main
        # Monkey-patch sys.argv temporarily
        old_argv = sys.argv
        sys.argv = ["build_instance_timeline.py", summary_path,
                    os.path.join(vis_dir, "timeline.html")]
        build_timeline_main()
        sys.argv = old_argv
        results['timeline'] = os.path.join(vis_dir, "timeline.html")
    except Exception as e:
        print(f"    ⚠ Timeline generation failed: {e}")
    
    # ── 2. Animation ──
    if not skip_animation:
        print(f"  🎬 Generating animation...")
        try:
            from render_animation import render_animation, load_summary
            anim_dir = os.path.join(vis_dir, "animation")
            summary = load_summary(summary_path)
            render_animation(summary, anim_dir,
                             title=f"DPDP {instance_name}",
                             frame_interval=frame_interval,
                             playback_speed=playback_speed)
            results['animation'] = os.path.join(anim_dir, "animated_simulation.html")
        except Exception as e:
            print(f"    ⚠ Animation generation failed: {e}")
    
    # ── 3. Validation ──
    print(f"  ✅ Running validation...")
    try:
        from validate_visualization import validate
        validate(summary_path,
                 Configs.algorithm_data_interaction_folder_path,
                 Configs.benchmark_folder_path)
    except Exception as e:
        print(f"    ⚠ Validation failed: {e}")
    
    # ── 4. Executed Route Visualization ──
    # Always extract from epoch_summary.json (more reliable than ExecutedRouteRecorder)
    print(f"  🚛 Generating executed route visualization...")
    try:
        from extract_executed_routes_from_summary import main as extract_main
        from build_executed_route_viz import main as build_executed_viz_main
        
        # Step 4a: Extract executed routes from epoch_summary.json
        old_argv = sys.argv
        sys.argv = ["extract_executed_routes.py", summary_path,
                    os.path.join(vis_dir, "executed_routes.json")]
        extract_main()
        
        # Step 4b: Generate HTML
        sys.argv = ["build_executed_route_viz.py",
                    os.path.join(vis_dir, "executed_routes.json"),
                    os.path.join(vis_dir, "executed_routes.html")]
        build_executed_viz_main()
        sys.argv = old_argv
        
        results['executed_routes'] = os.path.join(vis_dir, "executed_routes.html")
    except Exception as e:
        print(f"    ⚠ Executed route viz failed: {e}")
    
    return results


def print_summary(all_results: dict):
    """Print final summary of all generated outputs."""
    print(f"\n{'='*70}")
    print(f"  📊 VISUALIZATION OUTPUTS")
    print(f"{'='*70}")
    
    for instance_name, results in all_results.items():
        print(f"\n  🏭 {instance_name}:")
        if 'timeline' in results:
            p = results['timeline'].replace(os.sep, '/')
            print(f"     📋 Timeline:  file:///{os.path.abspath(p).replace(os.sep, '/')}")
        if 'animation' in results:
            p = results['animation'].replace(os.sep, '/')
            print(f"     🎬 Animation: file:///{os.path.abspath(p).replace(os.sep, '/')}")
        if 'executed_routes' in results:
            p = results['executed_routes'].replace(os.sep, '/')
            print(f"     🚛 Executed Routes: file:///{os.path.abspath(p).replace(os.sep, '/')}")
        # Show JSON path too
        executed_json = os.path.join(Configs.VISUALIZATION_OUTPUT_DIR, instance_name, "executed_routes.json")
        if os.path.exists(executed_json) and 'executed_routes' not in results:
            p = executed_json.replace(os.sep, '/')
            print(f"     🚛 Executed Routes JSON: file:///{os.path.abspath(p).replace(os.sep, '/')}")
    
    print(f"\n{'='*70}")
    print(f"  Mở file HTML trong browser để xem kết quả.")
    print(f"{'='*70}")


def main():
    parser = argparse.ArgumentParser(
        description="DPDP Simulation + Auto Visualization")
    parser.add_argument("--instance", "-i", type=str, default=None,
                        help="Instance indices, comma-separated (default: from Configs.selected_instances)")
    parser.add_argument("--no-animation", action="store_true",
                        help="Skip animation generation (faster)")
    parser.add_argument("--frame-interval", "-f", type=int, default=300,
                        help="Seconds per animation frame (default: 300)")
    parser.add_argument("--playback-speed", "-s", type=int, default=80,
                        help="ms per frame in browser (default: 80)")
    args = parser.parse_args()
    
    # Determine instances to run
    if args.instance:
        test_instances = [int(x.strip()) for x in args.instance.split(",")]
    elif Configs.selected_instances:
        test_instances = Configs.selected_instances
    else:
        test_instances = Configs.all_test_instances
    
    print(f"{'='*70}")
    print(f"  DPDP Simulation + Auto Visualization")
    print(f"{'='*70}")
    print(f"  Instances: {test_instances}")
    print(f"  Animation: {'OFF' if args.no_animation else f'ON ({args.frame_interval}s/frame)'}")
    print(f"  Visualization output: {os.path.abspath(Configs.VISUALIZATION_OUTPUT_DIR)}")
    print()
    
    score_list = []
    all_viz_results = {}
    
    for idx in test_instances:
        instance_name = f"instance_{idx}"
        
        # Init logger
        log_file_name = f"dpdp_viz_{datetime.datetime.now().strftime('%y%m%d%H%M%S')}.log"
        ini_logger(log_file_name)
        
        try:
            # ── Run simulation ──
            score = run_simulation(idx)
            score_list.append(score)
            
            # ── Generate visualizations ──
            print(f"\n  🎨 Generating visualizations for {instance_name}...")
            viz_results = generate_visualizations(
                idx,
                skip_animation=args.no_animation,
                frame_interval=args.frame_interval,
                playback_speed=args.playback_speed
            )
            all_viz_results[instance_name] = viz_results
            
        except Exception as e:
            logger.error(f"Failed to run {instance_name}")
            logger.error(f"Error: {e}, {traceback.format_exc()}")
            score_list.append(sys.maxsize)
        
        # Clean up log handler
        remove_file_handler_of_logging(log_file_name)
    
    # ── Summary ──
    avg_score = np.mean(score_list)
    print(f"\n{'='*70}")
    print(f"  SCORES: {score_list}")
    print(f"  AVERAGE: {avg_score}")
    print(f"{'='*70}")
    
    print_summary(all_viz_results)
    print("\nHappy Ending 🎉")


if __name__ == "__main__":
    main()
