### **통합된 전체 코드 (main.py)**

import sys
import os

# Fix Qt plugin path issue (especially for paths with non-ASCII characters)
# Must be set BEFORE importing PyQt5
try:
    import PyQt5
    pyqt5_path = os.path.dirname(PyQt5.__file__)
    plugin_path = os.path.join(pyqt5_path, 'Qt5', 'plugins')
    if os.path.exists(plugin_path):
        os.environ['QT_PLUGIN_PATH'] = plugin_path
        # Also set QT_QPA_PLATFORM_PLUGIN_PATH for additional compatibility
        os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path
except Exception as e:
    print(f"Warning: Could not set Qt plugin path: {e}")

import math
import json
import datetime
import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET

# UI Framework
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, 
    QFileDialog, QLabel, QSlider, QGroupBox, QMessageBox, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QTabWidget, QDial,
    QSpinBox, QComboBox, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QPointF, QTimer
from PyQt5.QtGui import QColor, QPainter, QBrush, QPen, QFont

# 3D Plotting & Calculation Libraries
import matplotlib
matplotlib.use('Qt5Agg') # PyQt5와 충돌 방지
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D
from scipy.interpolate import interp1d

# --- 1. Data Processors ---

class AISDataProcessor:
    """AIS 데이터 처리 클래스"""
    @staticmethod
    def load_ais_data(file_path):
        try:
            df = pd.read_excel(file_path)
            # 컬럼 이름 소문자 변환 및 필수 컬럼 확인
            df.columns = [c.lower() for c in df.columns]
            required_columns = ['lat', 'lon', 'spd', 'co'] # Time은 옵션 (없으면 인덱스 사용)
            
            for col in required_columns:
                if col not in df.columns:
                    raise ValueError(f"Missing column: {col}")
            
            df = df.dropna(subset=['lat', 'lon', 'spd', 'co'])
            
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'])
                df = df.sort_values('time')
            
            return df
        except Exception as e:
            raise Exception(f"AIS Load Error: {str(e)}")

class OntologyProcessor:
    """OWL 온톨로지 처리 클래스 (Skeleton)"""
    @staticmethod
    def load_owl_file(file_path):
        # 실제 로직은 파일 구조에 따라 다르므로 기본 골격만 유지
        return [{'type': 'class', 'name': 'CollisionAvoidance', 'score': 0.0}]

    @staticmethod
    def analyze_scenario_evaluation_items(items, scenario_data):
        return items

# --- 2. 3D Viewer (Space-Time Cube) ---

class SpaceTimeCubeViewer(QMainWindow):
    """3D 항적 분석 및 전문가 경로 수정 도구"""
    def __init__(self, os_data, ts_data_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Space-Time Cube Analysis (Expert Review)")
        self.setGeometry(200, 200, 1000, 800)
        
        self.os_data = os_data
        self.ts_data_list = ts_data_list
        self.expert_path_data = None 
        
        self.init_ui()
        self.plot_space_time_cube()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # Matplotlib Canvas
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111, projection='3d')
        layout.addWidget(self.canvas, stretch=4)

        # Control Panel
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        
        info_group = QGroupBox("Scenario Info")
        info_layout = QVBoxLayout(info_group)
        self.info_label = QLabel("Analyzing trajectory...")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)
        control_layout.addWidget(info_group)

        expert_group = QGroupBox("Expert Interaction (IRL)")
        expert_layout = QVBoxLayout(expert_group)
        
        btn_edit = QPushButton("🖊️ Draw Expert Path")
        btn_edit.clicked.connect(self.enable_expert_editing)
        btn_edit.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold;")
        expert_layout.addWidget(btn_edit)
        
        btn_save = QPushButton("💾 Save Expert Demo")
        btn_save.clicked.connect(self.save_expert_demonstration)
        btn_save.setStyleSheet("background-color: #198754; color: white; font-weight: bold;")
        expert_layout.addWidget(btn_save)
        
        control_layout.addWidget(expert_group)
        control_layout.addStretch()
        layout.addWidget(control_panel, stretch=1)

    def plot_space_time_cube(self):
        self.ax.clear()
        self.ax.set_xlabel('Relative Longitude (m)')
        self.ax.set_ylabel('Relative Latitude (m)')
        self.ax.set_zlabel('Time Sequence')
        self.ax.set_title('Space-Time Cube Trajectory')

        # TS Drawing
        for ts in self.ts_data_list:
            self.ax.plot(ts['x'], ts['y'], ts['time'], label=f"{ts['name']}", color='red', alpha=0.6)
            self.ax.plot(ts['x'], ts['y'], np.zeros_like(ts['time']), color='red', linestyle=':', alpha=0.2)

        # OS Drawing
        if self.os_data:
            self.ax.plot(self.os_data['x'], self.os_data['y'], self.os_data['time'], label='OS (Original)', color='blue', linewidth=2)
            self.ax.plot(self.os_data['x'], self.os_data['y'], np.zeros_like(self.os_data['time']), color='blue', linestyle=':', alpha=0.3)

        self.ax.legend()
        self.canvas.draw()

    def enable_expert_editing(self):
        """전문가 수정을 위한 Waypoint 생성"""
        if not self.os_data: return
        t = self.os_data['time']
        x = self.os_data['x']
        y = self.os_data['y']
        
        indices = np.linspace(0, len(t)-1, 8, dtype=int) # 8개의 제어점 생성
        
        if hasattr(self, 'scatter_points'): self.scatter_points.remove()
        
        self.scatter_points = self.ax.scatter(x[indices], y[indices], t[indices], 
                                            color='green', s=60, marker='o', 
                                            label='Expert CP', picker=True)
        
        self.info_label.setText("Mode: Editing\nClick green points to simulate deviation (avoidance).")
        self.cid = self.canvas.mpl_connect('pick_event', self.on_pick)
        self.canvas.draw()

    def on_pick(self, event):
        """점 클릭 시 회피 동작 시뮬레이션 (우현 회피 가정)"""
        ind = event.ind[0]
        data_3d = self.scatter_points._offsets3d
        x_data, y_data, z_data = list(data_3d[0]), list(data_3d[1]), list(data_3d[2])
        
        x_data[ind] += 300 # 300m 우측 이동 (간소화)
        y_data[ind] += 100
        
        self.scatter_points._offsets3d = (x_data, y_data, z_data)
        self.update_expert_curve(x_data, y_data, z_data)
        self.info_label.setText(f"Waypoint {ind} modified.")
        self.canvas.draw()

    def update_expert_curve(self, wx, wy, wt):
        if hasattr(self, 'expert_line'): self.expert_line[0].remove()
        
        f_x = interp1d(wt, wx, kind='cubic')
        f_y = interp1d(wt, wy, kind='cubic')
        new_t = np.linspace(wt[0], wt[-1], 200)
        
        self.expert_path_data = {'time': new_t, 'x': f_x(new_t), 'y': f_y(new_t)}
        self.expert_line = self.ax.plot(self.expert_path_data['x'], self.expert_path_data['y'], new_t, 
                                      color='green', linewidth=3, linestyle='-', label='Expert Path')

    def save_expert_demonstration(self):
        if self.expert_path_data is None:
            QMessageBox.warning(self, "Warning", "No expert path created.")
            return
        try:
            path, _ = QFileDialog.getSaveFileName(self, "Save Expert Demo", "expert_demo.csv", "CSV (*.csv)")
            if path:
                pd.DataFrame(self.expert_path_data).to_csv(path, index=False)
                QMessageBox.information(self, "Success", "Expert trajectory saved for IRL.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

# --- 3. 2D Simulator Canvas ---

class SimCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 800)
        self.setStyleSheet("background-color: #0a0a0a; border: 2px solid #1a1a1a;")
        self.ships = []
        self.ownship = None
        self.scale_factor = 70
        self.zoom_level = 1.0
        self.center_lat = 35.0
        self.center_lon = 129.0
        self.os_heading = 0
        self.trajectory_points = []
        
        # 가상 지형 데이터
        self.landmarks = self.generate_landmarks()

    def generate_landmarks(self):
        return [(self.center_lat + 0.02, self.center_lon + 0.02, 'lighthouse', 'Lighthouse A')]

    def set_ships(self, ownship, ships):
        self.ownship = ownship
        self.ships = ships
        if ownship:
            self.os_heading = ownship['heading']
            # 궤적 추가
            cx, cy = self.width() // 2, self.height() // 2
            self.trajectory_points.append(QPointF(cx, cy))
            if len(self.trajectory_points) > 200: self.trajectory_points.pop(0)
        self.update()

    def convert_latlon_to_xy(self, lat, lon, center_lat, center_lon):
        # 1 degree approx 60 NM, 1 NM = 70 pixels (Scale)
        x = (lon - center_lon) * 60 * 70
        y = -(lat - center_lat) * 60 * 70 # Y축 반전
        return x, y

    def paintEvent(self, event):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        
        cx, cy = self.width() // 2, self.height() // 2
        scale = self.scale_factor * self.zoom_level

        # 1. Grid
        self.draw_grid(qp, cx, cy)

        # 2. Landmarks
        for lat, lon, ltype, name in self.landmarks:
            lx, ly = self.convert_latlon_to_xy(lat, lon, self.center_lat, self.center_lon)
            lx = cx + lx * self.zoom_level
            ly = cy + ly * self.zoom_level
            qp.setBrush(QColor(255, 255, 0))
            qp.drawEllipse(QPointF(lx, ly), 5, 5)
            qp.setPen(QColor(255, 255, 255))
            qp.drawText(QPointF(lx+10, ly), name)

        # 3. Trajectory
        if len(self.trajectory_points) > 1:
            qp.setPen(QPen(QColor(0, 255, 0, 100), 2))
            for i in range(len(self.trajectory_points)-1):
                qp.drawLine(self.trajectory_points[i], self.trajectory_points[i+1])

        # 4. Ships
        if self.ownship:
            self.draw_ship(qp, cx, cy, self.ownship['heading'], QColor(0, 100, 255), "OS")
        
        for ship in self.ships:
            # Relative Position
            self.draw_ship(qp, ship['x'], ship['y'], ship['heading'], ship['color'], "TS")

    def draw_grid(self, qp, cx, cy):
        qp.setPen(QPen(QColor(50, 50, 50), 1, Qt.DotLine))
        for i in range(0, self.width(), 100):
            qp.drawLine(i, 0, i, self.height())
        for i in range(0, self.height(), 100):
            qp.drawLine(0, i, self.width(), i)

    def draw_ship(self, qp, x, y, heading, color, label):
        qp.save()
        qp.translate(x, y)
        qp.rotate(heading) # Qt rotates clockwise
        
        # Ship Shape
        qp.setPen(QPen(Qt.white, 2))
        qp.setBrush(color)
        qp.drawPolygon(QPointF(0, -15), QPointF(-8, 10), QPointF(8, 10))
        
        qp.restore()
        # Label
        qp.setPen(Qt.white)
        qp.drawText(QPointF(x+10, y), label)

# --- 4. Main Simulator Window ---

class SimulatorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Integrated Ship Simulator & IRL Tool")
        self.setGeometry(100, 100, 1600, 900)
        self.ship_data = {}
        self.is_simulation_running = False
        self.current_time_index = 0
        self.setup_ui()
        
        self.simulation_timer = QTimer()
        self.simulation_timer.timeout.connect(self.update_simulation)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)

        # Left Panel (Controls)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setFixedWidth(300)
        
        # Import Section
        import_group = QGroupBox("Data Import")
        import_layout = QVBoxLayout(import_group)
        
        self.btn_os = QPushButton("📂 Load OS (Own Ship)")
        self.btn_os.clicked.connect(lambda: self.load_ship_data("OS"))
        import_layout.addWidget(self.btn_os)
        
        self.btn_ts1 = QPushButton("📂 Load TS1")
        self.btn_ts1.clicked.connect(lambda: self.load_ship_data("TS1"))
        import_layout.addWidget(self.btn_ts1)
        
        self.lbl_status = QLabel("Status: Ready")
        import_layout.addWidget(self.lbl_status)
        left_layout.addWidget(import_group)

        # Simulation Control
        sim_group = QGroupBox("Simulation")
        sim_layout = QVBoxLayout(sim_group)
        
        btn_layout = QHBoxLayout()
        self.btn_play = QPushButton("▶ Play")
        self.btn_play.clicked.connect(self.start_simulation)
        btn_layout.addWidget(self.btn_play)
        
        self.btn_stop = QPushButton("■ Stop")
        self.btn_stop.clicked.connect(self.stop_simulation)
        btn_layout.addWidget(self.btn_stop)
        sim_layout.addLayout(btn_layout)
        
        self.progress_bar = QProgressBar()
        sim_layout.addWidget(self.progress_bar)
        left_layout.addWidget(sim_group)

        # 3D / IRL Analysis (핵심 기능)
        irl_group = QGroupBox("Space-Time Cube (IRL)")
        irl_layout = QVBoxLayout(irl_group)
        
        self.btn_3d = QPushButton("🧊 Open Space-Time Cube")
        self.btn_3d.setStyleSheet("background-color: #6610f2; color: white; font-weight: bold; padding: 10px;")
        self.btn_3d.clicked.connect(self.open_space_time_cube)
        irl_layout.addWidget(self.btn_3d)
        
        self.lbl_3d_info = QLabel("Visualizes 2D trajectory in 3D (Time axis) and allows expert modification.")
        self.lbl_3d_info.setWordWrap(True)
        self.lbl_3d_info.setStyleSheet("font-size: 10px; color: gray;")
        irl_layout.addWidget(self.lbl_3d_info)
        
        left_layout.addWidget(irl_group)
        left_layout.addStretch()

        layout.addWidget(left_panel)

        # Center (Simulator Canvas)
        self.sim_canvas = SimCanvas()
        layout.addWidget(self.sim_canvas, stretch=1)

    def load_ship_data(self, ship_id):
        fname, _ = QFileDialog.getOpenFileName(self, f"Load {ship_id}", "", "Excel Files (*.xlsx);;All Files (*)")
        if fname:
            try:
                self.ship_data[ship_id] = AISDataProcessor.load_ais_data(fname)
                self.lbl_status.setText(f"{ship_id} Loaded.")
                
                # OS가 로드되면 중심 좌표 설정
                if ship_id == "OS":
                    first_row = self.ship_data["OS"].iloc[0]
                    self.sim_canvas.center_lat = first_row['lat']
                    self.sim_canvas.center_lon = first_row['lon']
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def start_simulation(self):
        if not self.ship_data:
            QMessageBox.warning(self, "Warning", "No ship data loaded.")
            return
        self.is_simulation_running = True
        self.simulation_timer.start(100) # 100ms interval

    def stop_simulation(self):
        self.is_simulation_running = False
        self.simulation_timer.stop()
        self.current_time_index = 0
        self.progress_bar.setValue(0)

    def update_simulation(self):
        if "OS" not in self.ship_data: return
        
        df_os = self.ship_data["OS"]
        if self.current_time_index >= len(df_os):
            self.stop_simulation()
            return

        # Update Progress
        self.progress_bar.setValue(int((self.current_time_index / len(df_os)) * 100))

        # Get Current Data
        row_os = df_os.iloc[self.current_time_index]
        
        # 캔버스 중심 업데이트 (OS Follow Mode)
        self.sim_canvas.center_lat = row_os['lat']
        self.sim_canvas.center_lon = row_os['lon']
        
        # OS Data Packet
        ownship = {
            'x': self.sim_canvas.width() // 2, 
            'y': self.sim_canvas.height() // 2,
            'heading': row_os['co'],
            'speed': row_os['spd']
        }

        # TS Data Packet
        ships = []
        for ship_id, df_ts in self.ship_data.items():
            if ship_id == "OS": continue
            if self.current_time_index < len(df_ts):
                row_ts = df_ts.iloc[self.current_time_index]
                # 좌표 변환
                tx, ty = self.sim_canvas.convert_latlon_to_xy(
                    row_ts['lat'], row_ts['lon'], 
                    self.sim_canvas.center_lat, self.sim_canvas.center_lon
                )
                ships.append({
                    'x': (self.sim_canvas.width() // 2) + tx,
                    'y': (self.sim_canvas.height() // 2) + ty,
                    'heading': row_ts['co'],
                    'speed': row_ts['spd'],
                    'color': QColor(255, 0, 0)
                })

        self.sim_canvas.set_ships(ownship, ships)
        self.current_time_index += 1

    def open_space_time_cube(self):
        """3D 분석 기능 실행"""
        if "OS" not in self.ship_data:
            QMessageBox.warning(self, "Warning", "Please load OS data first.")
            return

        # 1. OS 데이터 변환 (Relative Meters for 3D view)
        df_os = self.ship_data["OS"]
        ref_lat = df_os.iloc[0]['lat']
        ref_lon = df_os.iloc[0]['lon']
        
        # 시간축 생성
        time_seq = np.arange(len(df_os))
        
        # 좌표 변환 (LatLon -> XY Meters)
        x_vals, y_vals = [], []
        for _, row in df_os.iterrows():
            x, y = self.sim_canvas.convert_latlon_to_xy(row['lat'], row['lon'], ref_lat, ref_lon)
            x_vals.append(x)
            y_vals.append(y)
            
        os_3d_data = {'x': np.array(x_vals), 'y': np.array(y_vals), 'time': time_seq}

        # 2. TS 데이터 변환
        ts_3d_list = []
        for ship_id, df_ts in self.ship_data.items():
            if ship_id == "OS": continue
            # 데이터 길이 맞추기 (간소화)
            min_len = min(len(df_os), len(df_ts))
            df_ts_cut = df_ts.iloc[:min_len]
            
            ts_x, ts_y = [], []
            for _, row in df_ts_cut.iterrows():
                tx, ty = self.sim_canvas.convert_latlon_to_xy(row['lat'], row['lon'], ref_lat, ref_lon)
                ts_x.append(tx)
                ts_y.append(ty)
            
            ts_3d_list.append({
                'x': np.array(ts_x), 'y': np.array(ts_y), 
                'time': time_seq[:min_len], 'name': ship_id
            })

        # 3. 뷰어 실행
        self.stc_viewer = SpaceTimeCubeViewer(os_3d_data, ts_3d_list, parent=self)
        self.stc_viewer.show()

if __name__ == "__main__":
    # Ensure Qt plugin path is set before creating QApplication
    try:
        import PyQt5
        pyqt5_path = os.path.dirname(PyQt5.__file__)
        plugin_path = os.path.join(pyqt5_path, 'Qt5', 'plugins')
        if os.path.exists(plugin_path):
            os.environ['QT_PLUGIN_PATH'] = plugin_path
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path
    except:
        pass
    
    app = QApplication(sys.argv)
    window = SimulatorWindow()
    window.show()
    sys.exit(app.exec_())