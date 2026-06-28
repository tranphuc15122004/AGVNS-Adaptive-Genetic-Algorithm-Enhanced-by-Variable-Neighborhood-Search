# Copyright (C) 2021. Huawei Technologies Co., Ltd. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE

"""
Bronze Algorithm — Quickest Route (Top-3 Huawei Competition)

Python wrapper that calls the compiled C++ binary (main_algorithm.exe)
to solve the Dynamic Pickup and Delivery Problem (DPDP).
"""

import os
import subprocess
import sys
import time

from src.conf.configs import Configs
from src.utils.logging_engine import logger


def scheduling():
    """
    Main scheduling function called by main_algorithm.py.
    
    This wrapper:
    1. Determines the paths to input/output files (from Configs)
    2. Calls the compiled C++ binary (main_algorithm.exe) as a subprocess
    3. The binary reads from algorithm/data_interaction/ and writes results back
    """
    algorithm_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Try Windows executable first, then Linux binary
    binary_candidates = [
        os.path.join(algorithm_dir, "main_algorithm.exe"),
        os.path.join(algorithm_dir, "main_algorithm.out"),
    ]
    
    binary_path = None
    for candidate in binary_candidates:
        if os.path.exists(candidate):
            binary_path = candidate
            break
    
    if binary_path is None:
        logger.error("Bronze Algorithm binary not found! Expected main_algorithm.exe or main_algorithm.out")
        print("FAIL")
        return
    
    logger.info(f"Bronze Algorithm binary: {binary_path}")
    
    # The C++ binary reads/writes directly from/to these hardcoded paths:
    #   algorithm/data_interaction/vehicle_info.json
    #   algorithm/data_interaction/unallocated_order_items.json
    #   algorithm/data_interaction/ongoing_order_items.json
    #   algorithm/data_interaction/output_route.json
    #   algorithm/data_interaction/output_destination.json
    #   benchmark/factory_info.csv
    #   benchmark/route_info.csv
    
    # Ensure data_interaction directory exists
    data_interaction_dir = os.path.join(algorithm_dir, "algorithm", "data_interaction")
    os.makedirs(data_interaction_dir, exist_ok=True)
    
    # Build command: binary accepts up to 12 arguments overriding defaults
    cmd = [binary_path]
    
    # Optional: pass explicit paths as command-line arguments
    # (binary uses hardcoded defaults if arguments are omitted)
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])
    
    logger.info(f"Running command: {' '.join(cmd)}")
    
    try:
        start_time = time.time()
        
        proc = subprocess.Popen(
            cmd,
            cwd=algorithm_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        
        stdout, stderr = proc.communicate(timeout=Configs.MAX_RUNTIME_OF_ALGORITHM)
        elapsed = time.time() - start_time
        
        if stdout:
            logger.info(f"Binary stdout: {stdout.decode('utf-8', errors='replace').strip()}")
        if stderr:
            logger.debug(f"Binary stderr: {stderr.decode('utf-8', errors='replace').strip()}")
        
        if proc.returncode != 0:
            raise RuntimeError(f"Bronze Algorithm binary exited with code {proc.returncode}")
        
        logger.info(f"Bronze Algorithm completed in {elapsed:.2f}s (exit code 0)")
            
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError(f"Bronze Algorithm timed out after {Configs.MAX_RUNTIME_OF_ALGORITHM}s")
    except Exception as e:
        logger.error(f"Failed to run Bronze Algorithm binary: {e}")
        raise


if __name__ == '__main__':
    scheduling()
