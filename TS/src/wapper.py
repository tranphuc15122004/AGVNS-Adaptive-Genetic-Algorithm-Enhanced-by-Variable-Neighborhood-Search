import os
import threading
import traceback
import datetime
import sys
import re
import logging
from threading import Thread
from queue import Queue
import time
from src.conf.configs import Configs as SimulatorConfigs
from src.simulator.simulate_api import simulate
from src.utils.log_utils import ini_logger, remove_file_handler_of_logging
from src.utils.logging_engine import logger


class SimulationWrapper:
    def __init__(self):
        self.running = False
        self.paused = False
        self.current_instance = None
        self.current_algorithm = None
        self.output_queue = Queue()
        self.scores = []
        self.log_file_path = None
        self._original_stdout = sys.stdout  # Lưu lại stdout gốc
        self.queue_lock = threading.Lock()
        
        # Thêm các biến theo dõi từ log
        self.simulation_cur_time = None  # Thời gian hiện tại trong mô phỏng
        self.simulation_pre_time = None  # Thời gian trước đó trong mô phỏng
        self.unallocated_orders = 0      # Số đơn hàng chưa phân bổ
        self.ongoing_orders = 0          # Số đơn hàng đang xử lý
        self.completed_orders = 0        # Số đơn hàng đã hoàn thành
        
        # Thêm các biến mới để theo dõi thông tin cuối cùng
        self.vehicle_distances = {}  # Dictionary lưu khoảng cách từng xe
        self.vehicle_nodes = {}      # Dictionary lưu số node đã ghé thăm
        self.total_distance = 0      # Tổng khoảng cách
        self.sum_over_time = 0       # Tổng thời gian
        self.final_score = 0         # Điểm số cuối cùng
            
    def run_simulation(self, instance_id , algorithm_name = 'GA', socketio=None  ):
        """Run simulation for a specific instance"""
        self.current_instance = instance_id
        self.current_algorithm = algorithm_name
        self.running = True
        self.paused = False
        
        # Reset các thống kê cho lần chạy mới
        self.simulation_cur_time = None
        self.simulation_pre_time = None
        self.unallocated_orders = 0
        self.ongoing_orders = 0
        self.completed_orders = 0
        
        # Tạo log file
        log_file_name = f"dpdp_{datetime.datetime.now().strftime('%y%m%d%H%M%S')}.log"
        log_dir = "src/output/log"
        os.makedirs(log_dir, exist_ok=True)
        self.log_file_path = os.path.join(log_dir, log_file_name)
        ini_logger(log_file_name)
        
        # Thêm handler tùy chỉnh để bắt log
        log_handler = SocketIOHandler(self.output_queue, instance_id, socketio, self.log_file_path , wrapper=self)
        logging.getLogger().addHandler(log_handler)
        
        # Emit event khi bắt đầu
        if socketio:
            socketio.emit('simulation_started', {
                'instance_id': instance_id,
                'timestamp': time.time()
            })
        
        try:
            logger.info(f"Starting simulation for {instance_id}")
            logger.info(f"Using algorithm: {algorithm_name}")
            
            # Sử dụng OutputCapturer để capture stdout và stderr
            with OutputCapturer(self.output_queue, instance_id, socketio, self.log_file_path , wrapper= self) as _:
                idx = int(instance_id.split('_')[1])
                if idx <= 64:
                    score = simulate(
                        SimulatorConfigs.factory_info_file,
                        SimulatorConfigs.route_info_file,
                        instance_id,
                        algorithm_name
                    )
                else:
                    score = simulate(
                        SimulatorConfigs.customed_factory_info_file,
                        SimulatorConfigs.customed_route_info_file,
                        instance_id,
                        algorithm_name
                    )
                self.scores.append(score)
                logger.info(f"Score of {instance_id}: {score}")
                
                # Emit event khi hoàn thành
                if socketio:
                    socketio.emit('simulation_completed', {
                        'instance_id': instance_id,
                        'score': score,
                        'timestamp': time.time()
                    })
                
        except Exception as e:
            logger.error(f"Simulation failed: {e}\n{traceback.format_exc()}")
            self.scores.append(sys.maxsize)
            
            # Emit event khi có lỗi
            if socketio:
                socketio.emit('simulation_error', {
                    'error': str(e),
                    'timestamp': time.time()
                })
                
        finally:
            # Xóa handler tùy chỉnh
            logging.getLogger().removeHandler(log_handler)
            remove_file_handler_of_logging(log_file_name)
            self.running = False
            
            # Emit thông báo kết thúc
            if socketio:
                socketio.emit('simulation_completed', {
                    'instance_id': instance_id,
                    'algorithm': algorithm_name,
                    'score': self.scores[-1] if self.scores else None,
                    'timestamp': time.time(),
                    
                    # Thông tin về đơn hàng
                    'completed_orders': self.completed_orders,
                    'ongoing_orders': self.ongoing_orders,
                    'unallocated_orders': self.unallocated_orders,
                    
                    # Thông tin về kết quả thực hiện cuối cùng
                    'vehicle_distances': self.vehicle_distances,
                    'vehicle_nodes': self.vehicle_nodes,
                    'total_distance': self.total_distance,
                    'sum_over_time': self.sum_over_time,
                    'final_score': self.final_score
                })

    def parse_log_entry(self, log_entry):
        """Trích xuất thông tin từ log entry"""
        if not log_entry or 'message' not in log_entry:
            return
            
        message = log_entry['message']
        
        # Thêm trường để kiểm tra nguồn log và tránh đệ quy
        if log_entry.get('_from_debug', False):
            return
        
        # Trích xuất thông tin khoảng cách của từng phương tiện
        vehicle_match = re.search(r'Traveling Distance of Vehicle (V_\d+) is\s+(\d+\.\d+), visited node list: (\d+)', message)
        if vehicle_match:
            vehicle_id = vehicle_match.group(1)
            distance = float(vehicle_match.group(2))
            nodes = int(vehicle_match.group(3))
            self.vehicle_distances[vehicle_id] = distance
            self.vehicle_nodes[vehicle_id] = nodes
            return
        
        # Trích xuất tổng khoảng cách
        total_distance_match = re.search(r'Total distance:\s+(\d+\.\d+)', message)
        if total_distance_match:
            self.total_distance = float(total_distance_match.group(1))
            return
        
        # Trích xuất tổng thời gian
        sum_time_match = re.search(r'Sum over time:\s+(\d+\.\d+)', message)
        if sum_time_match:
            self.sum_over_time = float(sum_time_match.group(1))
            return
        
        # Trích xuất điểm số cuối cùng
        score_match = re.search(r'Total score:\s+(\d+\.\d+)', message)
        if score_match:
            self.final_score = float(score_match.group(1))
            return
        
        
        orders_patterns = [
            r'(?:INFO:)?\s*Get (\d+) unallocated order items, (\d+) ongoing order items, (\d+) completed order items',
            r'(?:INFO:)?\s*Orders: (\d+) unallocated, (\d+) ongoing, (\d+) completed',
            r'(\d+)\s*unallocated.*?(\d+)\s*ongoing.*?(\d+)\s*completed'
        ]
        
        # Thử từng pattern cho đến khi tìm thấy khớp
        for pattern in orders_patterns:
            orders_match = re.search(pattern, message)
            if orders_match:
                self.unallocated_orders = int(orders_match.group(1))
                self.ongoing_orders = int(orders_match.group(2))
                self.completed_orders = int(orders_match.group(3))
                return  # Dừng tìm kiếm khi đã tìm thấy pattern khớp
        
        # Debug: in ra tin nhắn để kiểm tra định dạng
        """ if 'unallocated order' in message or 'cur time' in message:
            print(f"DEBUG LOG: {message}") """
        
        # Trích xuất thời gian mô phỏng (cur time và pre time)
        time_match = re.search(r'(?:INFO:)?\s*cur time: ([\d-]+ [\d:]+), pre time: ([\d-]+ [\d:]+)', message)

        if time_match:
            self.simulation_cur_time = time_match.group(1)
            self.simulation_pre_time = time_match.group(2)
        
        # Trích xuất thông tin đơn hàng
        orders_match = re.search(r'(?:INFO:)?\s*Get (\d+) unallocated order items, (\d+) ongoing order items, (\d+) completed order items', message)
        if orders_match:
            self.unallocated_orders = int(orders_match.group(1))
            self.ongoing_orders = int(orders_match.group(2))
            self.completed_orders = int(orders_match.group(3))

    def get_state(self):
        """Get current simulation state"""
        output_list = []
        with self.queue_lock:
            while not self.output_queue.empty():
                log_entry = self.output_queue.get()
                output_list.append(log_entry)
                # Phân tích log entry để cập nhật thông số
                self.parse_log_entry(log_entry)
                    
        return {
            'running': self.running,
            'paused': self.paused,
            'current_instance': self.current_instance,
            'current_algorithm': self.current_algorithm,
            'current_time': time.time(),
            'scores': self.scores,
            'output': output_list,
            
            # Thêm các thông số được trích xuất từ log
            'simulation_cur_time': self.simulation_cur_time,
            'simulation_pre_time': self.simulation_pre_time,
            'unallocated_orders': self.unallocated_orders,
            'ongoing_orders': self.ongoing_orders,
            'completed_orders': self.completed_orders
        }


class OutputCapturer:
    """Context manager to capture simulator output (stdout and stderr)"""
    def __init__(self, queue, instance_id, socketio=None, log_file_path=None , wrapper=None):
        self.queue = queue
        self.instance_id = instance_id
        self.socketio = socketio
        self.log_file_path = log_file_path
        self.original_stdout = None
        self.original_stderr = None
        self.log_file = None
        self.wrapper = wrapper  # Tham chiếu đến SimulationWrapper
        
    def __enter__(self):
        # Mở file log để ghi
        if self.log_file_path:
            self.log_file = open(self.log_file_path, 'a', encoding='utf-8')
        
        # Thay thế stdout và stderr
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        sys.stdout = self
        sys.stderr = self
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Khôi phục stdout và stderr
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        if self.log_file:
            self.log_file.close()
        
    def write(self, text):
        """Capture stdout and stderr writes"""
        if text:
            # Tách text thành các dòng
            lines = text.split('\n')
            timestamp = datetime.datetime.now().strftime('%H:%M:%S')
            
            for line in lines:
                if line.strip():  # Chỉ xử lý các dòng không rỗng
                    # Kiểm tra nếu này là debug message từ parse_log_entry
                    if line.startswith("DEBUG:"):
                        # Chỉ ghi ra stdout gốc, không xử lý để tránh đệ quy
                        self.original_stdout.write(line + "\n")
                        self.original_stdout.flush()
                        continue
                    
                    log_entry = {
                        'time': timestamp,
                        'message': line,
                        'instance': self.instance_id,
                        'level': 'info'
                    }
                    
                    # Phát hiện level log
                    if "ERROR" in line.upper() or "CRITICAL" in line.upper():
                        log_entry['level'] = 'error'
                    elif "WARNING" in line.upper():
                        log_entry['level'] = 'warning'
                    
                    # Phân tích log entry để cập nhật thông số nếu wrapper khả dụng
                    if self.wrapper and not log_entry.get('_from_debug', False):
                        self.wrapper.parse_log_entry(log_entry)
                    
                    # Thêm vào queue (sẽ được SocketIOHandler xử lý)
                    self.queue.put(log_entry)
                    
                    # Ghi vào file log
                    if self.log_file:
                        self.log_file.write(line + '\n')
                        self.log_file.flush()
            
            # Ghi ra stdout/stderr gốc
            self.original_stdout.write(text)
            self.original_stderr.write(text)
    
    def flush(self):
        self.original_stdout.flush()
        self.original_stderr.flush()
        if self.log_file:
            self.log_file.flush()


class SocketIOHandler(logging.Handler):
    """Custom logging handler to send logs to SocketIO"""
    def __init__(self, queue, instance_id, socketio=None, log_file_path=None , wrapper=None):
        super().__init__()
        self.queue = queue
        self.instance_id = instance_id
        self.socketio = socketio
        self.log_file_path = log_file_path
        self.wrapper = wrapper
        self.log_file = open(log_file_path, 'a', encoding='utf-8') if log_file_path else None
        self.log_buffer = []  # Buffer để gửi log theo lô
        self.last_flush = time.time()
        
    def handle_queue(self):
        """Process logs from queue"""
        while not self.queue.empty():
            log_entry = self.queue.get()
            if log_entry and all(key in log_entry for key in ['time', 'message', 'instance', 'level']):
                
                # Phân tích log entry để cập nhật thông số nếu wrapper khả dụng
                if self.wrapper:
                    self.wrapper.parse_log_entry(log_entry)
                
                self.log_buffer.append(log_entry)
                
    def emit(self, record):
        """Handle logging record and queue items"""
        try:
            # Xử lý log từ logging
            msg = self.format(record)
            lines = msg.split('\n')
            timestamp = datetime.datetime.now().strftime('%H:%M:%S')
            
            # Theo dõi nếu tìm thấy thông tin đơn hàng
            order_info_updated = False
            
            for line in lines:
                if line.strip():
                    log_entry = {
                        'time': timestamp,
                        'message': line,
                        'instance': self.instance_id,
                        'level': record.levelname.lower()
                    }
                    
                    # Phân tích log entry để cập nhật thông số nếu wrapper khả dụng
                    if self.wrapper:
                        # Kiểm tra nếu đây là log về đơn hàng
                        if 'Get' in line and 'unallocated order items' in line:
                            order_info_updated = True
                        self.wrapper.parse_log_entry(log_entry)
                    
                    self.log_buffer.append(log_entry)
                    #self.queue.put(log_entry)  # Thêm dòng này!
                    
                    # Ghi vào file log
                    if self.log_file:
                        self.log_file.write(line + '\n')
                        self.log_file.flush()
            
            # Xử lý log từ queue (từ OutputCapturer)
            self.handle_queue()
            
            if order_info_updated and self.socketio and self.wrapper:
                self.socketio.emit('order_update', {
                    'unallocated_orders': self.wrapper.unallocated_orders,
                    'ongoing_orders': self.wrapper.ongoing_orders,
                    'completed_orders': self.wrapper.completed_orders,
                    'current_time': self.wrapper.simulation_cur_time
                })
            
            # Gửi buffer nếu đủ lớn hoặc sau 0.5 giây
            current_time = time.time()
            if len(self.log_buffer) >= 10 or (current_time - self.last_flush) >= 0.5:
                if self.socketio:
                    self.socketio.emit('log_update', self.log_buffer)
                self.log_buffer.clear()
                self.last_flush = current_time
        
        except Exception as e:
            print(f"Error in SocketIOHandler: {e}", file=sys.stderr)
            
    def close(self):
        # Gửi các log còn lại trong buffer
        if self.socketio and self.log_buffer:
            self.socketio.emit('log_update', self.log_buffer)
            self.log_buffer.clear()
        if self.log_file:
            self.log_file.close()
        super().close()