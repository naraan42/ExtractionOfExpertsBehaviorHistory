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

import pandas as pd
import numpy as np
import time
import json
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, 
    QFileDialog, QLabel, QSlider, QGroupBox, QMessageBox, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QSplitter, QTextEdit, QScrollArea, QTabWidget, QDial,
    QSpinBox, QComboBox, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QPointF, QTimer
from PyQt5.QtGui import QColor, QPainter, QBrush, QPen, QFont, QLinearGradient, QPixmap
import math
import xml.etree.ElementTree as ET

# National Oceanographic Research Institute Electronic Chart OpenAPI Loader Import
try:
    from real_chart_loader import RealChartDataLoader
    REAL_CHART_AVAILABLE = True
    print("✅ National Oceanographic Research Institute Electronic Chart OpenAPI Loader Available")
except ImportError:
    REAL_CHART_AVAILABLE = False
    print("⚠️ National Oceanographic Research Institute Electronic Chart OpenAPI Loader not available. Run pip install requests")

# Geo Plotting Related Libraries
try:
    import folium
    import geopandas as gpd
    from shapely.geometry import Point, LineString, Polygon
    from shapely.ops import unary_union
    GEO_PLOT_AVAILABLE = True
    print("✅ Geo plotting libraries available")
except ImportError:
    GEO_PLOT_AVAILABLE = False
    print("⚠️ Geo plotting libraries not available. Install with: pip install folium geopandas shapely")

# Electronic Chart Related Module Import
try:
    from electronic_chart_canvas import ElectronicChartCanvas
    ELECTRONIC_CHART_AVAILABLE = True
except ImportError:
    ELECTRONIC_CHART_AVAILABLE = False
    print("Warning: Electronic chart modules not available. Using basic canvas.")

# --- 시뮬레이션 캔버스 ---
class SimCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 800)
        self.setStyleSheet("""
            QWidget {
                background-color: #0a0a0a;
                border: 2px solid #1a1a1a;
                border-radius: 8px;
            }
        """)
        self.ships = []
        self.ownship = None
        self.scale_factor = 70  # 1NM = 70 pixels for better fit
        self.center_lat = 0  # Center Latitude
        self.center_lon = 0  # Center Longitude
        self.os_heading = 0  # OS heading initial value
        
        # National Oceanographic Research Institute Electronic Chart API Related Properties
        self.zoom_level = 1.0  # Zoom Level
        self.center_lat = 37.4565  # Incheon Port Center Latitude
        self.center_lon = 126.5980  # Incheon Port Center Longitude
        
        # OS Position (실제 GPS 좌표 - 해도 중심과 다름)
        self.os_lat = 37.4565  # OS 실제 위도
        self.os_lon = 126.5980  # OS 실제 경도
        
        # Debug Mode Properties
        self.debug_mode = False
        
        # Drag Related Properties
        self.dragging = False
        self.chart_dragging = False
        self.os_dragging = False
        self.last_mouse_pos = None
        
        # OS Position Offset (Position moved by dragging)
        self.os_offset_x = 0
        self.os_offset_y = 0
        
        # Third Person View Mode Related Properties
        self.third_person_mode = False  # Third Person View Mode
        self.camera_position = {'x': 0, 'y': 0}  # Camera Position
        self.camera_distance = 200  # Distance between camera and own ship
        self.camera_angle = 45  # Camera Angle (degrees)
        
        # Own Ship Trajectory Display Related Properties
        self.draw_trajectory = False  # Trajectory Display Flag
        self.trajectory_points = []  # Trajectory Points
        self.max_trajectory_points = 100  # Maximum Trajectory Points
        
        # National Oceanographic Research Institute Electronic Chart OpenAPI Related Properties
        self.real_chart_loader = None
        self.use_real_chart_data = False
        self.chart_data_cache = {}
        self.last_center_lat = 0
        self.last_center_lon = 0
        
        # Basic Chart Data Properties (Virtual Data + Real API Data)
        self.coastline_data = []
        self.depth_contours = []
        self.navigation_aids = []
        self.dangerous_areas = []
        self.marine_zones = []
        self.landmarks = []  # Landmark Data
        
        # Load National Oceanographic Research Institute Electronic Chart OpenAPI Key
        self.load_api_key()
        
        # Enable Mouse Events
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
    
    def load_api_key(self):
        """Load National Oceanographic Research Institute Electronic Chart OpenAPI Key"""
        try:
            with open('api_config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                api_key = config.get('khoa_api_key', '')
                use_real_data = config.get('use_real_data', True)
                
                if api_key and api_key != "Enter_API_Key_Here" and use_real_data:
                    if REAL_CHART_AVAILABLE:
                        self.real_chart_loader = RealChartDataLoader(api_key)
                        self.use_real_chart_data = True
                        print("✅ National Oceanographic Research Institute Electronic Chart OpenAPI Connection Successful!")
                    else:
                        print("⚠️ National Oceanographic Research Institute Electronic Chart OpenAPI Loader not available.")
                else:
                    print("⚠️ National Oceanographic Research Institute Electronic Chart OpenAPI Key not set - Using Virtual Data")
                    self.use_real_chart_data = False
        except FileNotFoundError:
            print("⚠️ API Configuration File not found - Using Virtual Data")
            self.use_real_chart_data = False
        except Exception as e:
            print(f"❌ API Key Loading Error: {e}")
            self.use_real_chart_data = False
    
    def load_real_chart_data(self, center_lat: float, center_lon: float, zoom_level: float):
        """Load National Oceanographic Research Institute Electronic Chart OpenAPI Data"""
        if not self.real_chart_loader or not self.use_real_chart_data:
            return
        
        # Calculate Current Viewport Range
        view_range = 0.1 / zoom_level  # Viewport size based on zoom level
        
        min_lon = center_lon - view_range
        max_lon = center_lon + view_range
        min_lat = center_lat - view_range
        max_lat = center_lat + view_range
        
        # Load Data
        try:
            # Coastline Data
            coastline_data = self.real_chart_loader.get_coastline_data(
                min_lon, min_lat, max_lon, max_lat
            )
            if coastline_data:
                self.coastline_data = coastline_data
            
            # Depth Contour Data
            depth_contours = self.real_chart_loader.get_depth_contours(
                min_lon, min_lat, max_lon, max_lat
            )
            if depth_contours:
                self.depth_contours_data = depth_contours
            
            # Navigation Aid Data
            navigation_aids = self.real_chart_loader.get_navigation_aids(
                min_lon, min_lat, max_lon, max_lat
            )
            if navigation_aids:
                self.navigation_aids_data = navigation_aids
            
            # Dangerous Area Data
            dangerous_areas = self.real_chart_loader.get_dangerous_areas(
                min_lon, min_lat, max_lon, max_lat
            )
            if dangerous_areas:
                self.dangerous_areas_data = dangerous_areas
                
            print(f"🗺️ National Oceanographic Research Institute Electronic Chart Data Loading Complete: {len(coastline_data)} coastlines, {len(depth_contours)} depth contours")
            
        except Exception as e:
            print(f"❌ National Oceanographic Research Institute Electronic Chart Data Loading Error: {e}")
    
    def clear_chart_data_cache(self):
        """Clear Chart Data Cache"""
        if self.real_chart_loader:
            self.real_chart_loader.clear_cache()
        self.chart_data_cache.clear()
        print("🗺️ Chart Data Cache Clear Complete")
    
    def initialize_chart_data_for_location(self, center_lat, center_lon, radius_nm):
        """Initialize chart data for a specific location and radius."""
        # Convert radius to degrees (1 nautical mile ≈ 0.0167 degrees)
        radius_deg = radius_nm * 0.0167
        
        # Calculate range based on center point
        lat_min = center_lat - radius_deg
        lat_max = center_lat + radius_deg
        lon_min = center_lon - radius_deg
        lon_max = center_lon + radius_deg
        
        # Generate landmarks for new location
        self.landmarks = self.generate_landmarks_for_area(center_lat, center_lon, radius_nm)
        
        # Generate depth contours for new location
        self.depth_contours = self.generate_depth_contours_for_area(center_lat, center_lon, radius_nm)
        
        # Generate navigation aids for new location
        self.navigation_aids = self.generate_navigation_aids_for_area(center_lat, center_lon, radius_nm)
        
        # Generate dangerous areas for new location
        self.dangerous_areas = self.generate_dangerous_areas_for_area(center_lat, center_lon, radius_nm)
        
        # Generate coastline for new location
        self.coastline_data = self.generate_coastline_for_area(center_lat, center_lon, radius_nm)
        
        # Generate marine zones for new location
        self.marine_zones = self.generate_marine_zones_for_area(center_lat, center_lon, radius_nm)
        
        # Record progress
        if hasattr(self, 'parent') and hasattr(self.parent(), 'add_progress_entry'):
            self.parent().add_progress_entry(f"🗺️ Chart data initialized for area: ({lat_min:.4f}, {lon_min:.4f}) to ({lat_max:.4f}, {lon_max:.4f})")
    
    def generate_landmarks_for_area(self, center_lat, center_lon, radius_nm):
        """Generate landmarks for a specified area."""
        landmarks = []
        
        # Randomly place landmarks within radius from center point
        import random
        
        # Landmark types and names
        landmark_types = [
            ('lighthouse', 'Lighthouse'),
            ('buoy', 'Buoy'),
            ('rock', 'Rock'),
            ('wreck', 'Shipwreck'),
            ('bridge', 'Bridge'),
            ('port', 'Port'),
            ('anchorage', 'Anchorage'),
            ('restricted_area', 'Restricted Area'),
            ('traffic_separation', 'Traffic Separation'),
            ('depth_area', 'Depth Area'),
            ('fishing_zone', 'Fishing Zone'),
            ('environmental', 'Environmental Protection Area')
        ]
        
        # Generate 5-15 landmarks
        num_landmarks = random.randint(5, 15)
        
        for i in range(num_landmarks):
            # Generate random position within radius
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(0, radius_nm * 0.8)  # Within 80% of radius from center
            
            # Convert to latitude/longitude
            lat_offset = (distance * math.cos(angle)) / 60.0  # 1 degree = 60 nautical miles
            lon_offset = (distance * math.sin(angle)) / (60.0 * math.cos(math.radians(center_lat)))
            
            lat = center_lat + lat_offset
            lon = center_lon + lon_offset
            
            # Select landmark type and name
            landmark_type, base_name = random.choice(landmark_types)
            name = f"{base_name} {chr(65 + i)}"  # A, B, C, ...
            
            landmarks.append((lat, lon, landmark_type, name))
        
        return landmarks
    
    def generate_depth_contours_for_area(self, center_lat, center_lon, radius_nm):
        """Generate depth contours for a specified area."""
        depth_contours = []
        
        import random
        
        # Depth levels (meters)
        depth_levels = [5, 10, 20, 50, 100]
        
        # Generate multiple points for each depth level
        for depth in depth_levels:
            num_points = random.randint(3, 8)
            
            for i in range(num_points):
                # Generate random position within radius
                angle = random.uniform(0, 2 * math.pi)
                distance = random.uniform(0, radius_nm * 0.9)
                
                # Convert to latitude/longitude
                lat_offset = (distance * math.cos(angle)) / 60.0
                lon_offset = (distance * math.sin(angle)) / (60.0 * math.cos(math.radians(center_lat)))
                
                lat = center_lat + lat_offset
                lon = center_lon + lon_offset
                
                depth_contours.append((lat, lon, depth))
        
        return depth_contours
    
    def generate_navigation_aids_for_area(self, center_lat, center_lon, radius_nm):
        """지정된 영역에 맞는 항로표지를 생성합니다."""
        navigation_aids = []
        
        import random
        
        # 항로표지 타입
        aid_types = ['cardinal_north', 'cardinal_south', 'cardinal_east', 'cardinal_west', 
                    'isolated_danger', 'safe_water']
        
        # 3-8개의 항로표지 생성
        num_aids = random.randint(3, 8)
        
        for i in range(num_aids):
            # 반지름 내에서 랜덤 위치 생성
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(0, radius_nm * 0.7)
            
            # 위경도로 변환
            lat_offset = (distance * math.cos(angle)) / 60.0
            lon_offset = (distance * math.sin(angle)) / (60.0 * math.cos(math.radians(center_lat)))
            
            lat = center_lat + lat_offset
            lon = center_lon + lon_offset
            
            # 항로표지 타입과 이름 선택
            aid_type = random.choice(aid_types)
            name = f"항로표지 {chr(65 + i)}"
            
            navigation_aids.append((lat, lon, aid_type, name))
        
        return navigation_aids
    
    def generate_dangerous_areas_for_area(self, center_lat, center_lon, radius_nm):
        """지정된 영역에 맞는 위험구역을 생성합니다."""
        dangerous_areas = []
        
        import random
        
        # 위험구역 타입
        area_types = ['military', 'fishing', 'environmental']
        
        # 2-5개의 위험구역 생성
        num_areas = random.randint(2, 5)
        
        for i in range(num_areas):
            # 반지름 내에서 랜덤 위치 생성
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(0, radius_nm * 0.6)
            
            # 위경도로 변환
            lat_offset = (distance * math.cos(angle)) / 60.0
            lon_offset = (distance * math.sin(angle)) / (60.0 * math.cos(math.radians(center_lat)))
            
            lat = center_lat + lat_offset
            lon = center_lon + lon_offset
            
            # 위험구역 타입과 이름 선택
            area_type = random.choice(area_types)
            name = f"{area_type.title()} 구역 {chr(65 + i)}"
            
            dangerous_areas.append((lat, lon, area_type, name))
        
        return dangerous_areas
    
    def generate_coastline_for_area(self, center_lat, center_lon, radius_nm):
        """지정된 영역에 맞는 해안선을 생성합니다."""
        coastline_data = []
        
        import random
        
        # 해안선 점의 개수 (10-20개)
        num_points = random.randint(10, 20)
        
        # 중심점에서 북쪽으로 시작하여 시계방향으로 해안선 생성
        for i in range(num_points):
            angle = (i / num_points) * 2 * math.pi
            
            # 해안선은 반지름의 60-90% 지점에 위치
            distance = random.uniform(radius_nm * 0.6, radius_nm * 0.9)
            
            # 위경도로 변환
            lat_offset = (distance * math.cos(angle)) / 60.0
            lon_offset = (distance * math.sin(angle)) / (60.0 * math.cos(math.radians(center_lat)))
            
            lat = center_lat + lat_offset
            lon = center_lon + lon_offset
            
            coastline_data.append((lat, lon))
        
        return coastline_data
    
    def generate_marine_zones_for_area(self, center_lat, center_lon, radius_nm):
        """지정된 영역에 맞는 해양 구역을 생성합니다."""
        marine_zones = []
        
        import random
        
        # 해양 구역 타입
        zone_types = ['port_area', 'anchorage_area', 'restricted_area', 'fishing_area', 'environmental_area']
        
        # 3-8개의 해양 구역 생성
        num_zones = random.randint(3, 8)
        
        for i in range(num_zones):
            # 반지름 내에서 랜덤 위치 생성
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(0, radius_nm * 0.5)
            
            # 위경도로 변환
            lat_offset = (distance * math.cos(angle)) / 60.0
            lon_offset = (distance * math.sin(angle)) / (60.0 * math.cos(math.radians(center_lat)))
            
            lat = center_lat + lat_offset
            lon = center_lon + lon_offset
            
            # 구역 반지름 (0.1-0.3마일)
            zone_radius = random.uniform(0.1, 0.3)
            
            # 구역 타입과 이름 선택
            zone_type = random.choice(zone_types)
            name = f"{zone_type.replace('_', ' ').title()} {chr(65 + i)}"
            
            marine_zones.append((lat, lon, zone_radius, zone_type, name))
        
        return marine_zones

    def load_api_key(self):
        """국립해양조사원 전자해도 API 키 로드"""
        try:
            with open('api_config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                api_key = config.get('khoa_api_key', '')
                if api_key and api_key != "여기에_발급받은_API_키_입력":
                    if REAL_CHART_AVAILABLE:
                        self.real_chart_loader = RealChartDataLoader(api_key)
                        print("✅ National Oceanographic Research Institute Electronic Chart API Connection Successful!")
                    else:
                        print("⚠️ National Oceanographic Research Institute Electronic Chart API Loader not available.")
                else:
                    print("⚠️ National Oceanographic Research Institute Electronic Chart API Key not set")
        except FileNotFoundError:
            print("⚠️ API Configuration File not found - Create api_config.json file and enter API key")
        except Exception as e:
            print(f"❌ API Key Loading Error: {e}")

    def load_real_chart_data(self, center_lat: float, center_lon: float, zoom_level: float):
        """국립해양조사원 전자해도 API 데이터 로드"""
        if not self.real_chart_loader:
            return
        
        # 현재 뷰포트 범위 계산
        view_range = 0.1 / zoom_level  # 줌 레벨에 따른 뷰포트 크기
        
        min_lon = center_lon - view_range
        max_lon = center_lon + view_range
        min_lat = center_lat - view_range
        max_lat = center_lat + view_range
        
        # 데이터 로드
        try:
            # 해안선 데이터
            coastline_data = self.real_chart_loader.get_coastline_data(
                min_lon, min_lat, max_lon, max_lat
            )
            if coastline_data:
                self.coastline_data = coastline_data
            
            # 등심선 데이터
            depth_contours = self.real_chart_loader.get_depth_contours(
                min_lon, min_lat, max_lon, max_lat
            )
            if depth_contours:
                self.depth_contours_data = depth_contours
            
            # 항로표지 데이터
            navigation_aids = self.real_chart_loader.get_navigation_aids(
                min_lon, min_lat, max_lon, max_lat
            )
            if navigation_aids:
                self.navigation_aids_data = navigation_aids
            
            # 위험구역 데이터
            dangerous_areas = self.real_chart_loader.get_dangerous_areas(
                min_lon, min_lat, max_lon, max_lat
            )
            if dangerous_areas:
                self.dangerous_areas_data = dangerous_areas
                
            print(f"🗺️ National Oceanographic Research Institute Electronic Chart Data Loading Complete: {len(coastline_data)} coastlines, {len(depth_contours)} depth contours")
            
        except Exception as e:
            print(f"❌ National Oceanographic Research Institute Electronic Chart Data Loading Error: {e}")
    
    def clear_chart_data_cache(self):
        """Clear Chart Data Cache"""
        self.chart_data_cache.clear()
        print("🗺️ Chart Data Cache Clear Complete")

    def set_ships(self, ownship, ships):
        self.ownship = ownship
        self.ships = ships
        
        # OS heading 업데이트
        if ownship and isinstance(ownship, dict) and 'heading' in ownship:
            self.os_heading = ownship['heading']
        elif ownship and hasattr(ownship, 'heading'):
            self.os_heading = ownship.heading
        
        # OS 위경도 설정 (해도 중심과 다르게)
        if ownship:
            if isinstance(ownship, dict):
                # ownship이 딕셔너리인 경우
                if 'lat' in ownship and 'lon' in ownship:
                    self.os_lat = ownship['lat']
                    self.os_lon = ownship['lon']
                else:
                    # lat, lon이 없으면 해도 중심에서 약간 떨어진 위치로 설정
                    self.os_lat = self.center_lat + 0.01  # 약 0.6NM 북쪽
                    self.os_lon = self.center_lon + 0.01  # 약 0.6NM 동쪽
            else:
                # ownship이 객체인 경우
                if hasattr(ownship, 'lat') and hasattr(ownship, 'lon'):
                    self.os_lat = ownship.lat
                    self.os_lon = ownship.lon
                else:
                    # lat, lon이 없으면 해도 중심에서 약간 떨어진 위치로 설정
                    self.os_lat = self.center_lat + 0.01  # 약 0.6NM 북쪽
                    self.os_lon = self.center_lon + 0.01  # 약 0.6NM 동쪽
            
            if self.debug_mode:
                print(f"🚢 OS Position Set: ({self.os_lat:.6f}, {self.os_lon:.6f})")
                print(f"🗺️ Chart Center: ({self.center_lat:.6f}, {self.center_lon:.6f})")
        
        # 자선 위치가 변경될 때 궤적에 추가
        if ownship and self.draw_trajectory:
            if isinstance(ownship, dict):
                ship_x = ownship.get('x', 0)
                ship_y = ownship.get('y', 0)
            else:
                ship_x = getattr(ownship, 'x', 0)
                ship_y = getattr(ownship, 'y', 0)
            
            # 화면 중심을 기준으로 상대 위치 계산
            center_x = self.width() // 2
            center_y = self.height() // 2
            
            # OS 오프셋을 고려한 실제 화면 위치
            if hasattr(self, 'os_offset_x') and hasattr(self, 'os_offset_y'):
                actual_x = center_x + self.os_offset_x
                actual_y = center_y + self.os_offset_y
            else:
                actual_x = center_x
                actual_y = center_y
            
            # 궤적에 추가
            self.add_trajectory_point(actual_x, actual_y)
        
        # 드래깅 오프셋 보존 확인
        if hasattr(self, 'os_offset_x') and hasattr(self, 'os_offset_y'):
            if self.debug_mode:
                print(f"🔒 set_ships: OS offset preserved - ({self.os_offset_x:.1f}, {self.os_offset_y:.1f})")
        
        self.update()
    
    def set_center_coordinates(self, lat, lon):
        """중심 좌표를 설정합니다 (지형지물 중심 화면용)"""
        self.center_lat = lat
        self.center_lon = lon
        self.update()
    
    def set_os_heading(self, heading):
        """OS heading을 설정합니다"""
        self.os_heading = heading
        self.update()
    
    def set_debug_mode(self, enabled):
        """디버그 모드를 설정합니다"""
        self.debug_mode = enabled
        self.update()
    
    def toggle_third_person_mode(self):
        """3자 시점 모드를 토글합니다"""
        self.third_person_mode = not self.third_person_mode
        
        if self.third_person_mode:
            # 3자 시점 모드 활성화
            self.camera_position = {'x': 0, 'y': 0}
            self.camera_distance = 200
            self.camera_angle = 45
            print("🎥 Third Person View Mode Activated")
        else:
            # 1자 시점 모드로 복원
            self.camera_position = {'x': 0, 'y': 0}
            self.camera_distance = 0
            self.camera_angle = 0
            print("👁️ First Person View Mode Restored")
        
        self.update()
    
    def set_camera_position(self, x, y):
        """카메라 위치를 설정합니다"""
        self.camera_position = {'x': x, 'y': y}
        self.update()
    
    def set_camera_distance(self, distance):
        """카메라와 자선 간의 거리를 설정합니다"""
        self.camera_distance = max(50, min(distance, 500))  # 50-500 픽셀 범위
        self.update()
    
    def set_camera_angle(self, angle):
        """카메라 각도를 설정합니다"""
        self.camera_angle = max(0, min(angle, 90))  # 0-90도 범위
        self.update()
    


    def paintEvent(self, event):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        
        # 국립해양조사원 전자해도 오픈API 데이터 로드
        if self.use_real_chart_data and self.real_chart_loader:
            self.load_real_chart_data(self.center_lat, self.center_lon, self.zoom_level)
        
        # 전자해도 스타일 배경 (실제 바다와 육지 색상)
        self.draw_realistic_background(qp)
        
        # 화면 중심점 (자선 위치)
        center_x, center_y = self.width() // 2, self.height() // 2
        
        # 줌 레벨에 따른 스케일 계산
        scale = self.scale_factor * self.zoom_level
        
        # 국립해양조사원 API + 가상 데이터 기반 화면 구성
        # 1. 해안선 및 육지 그리기 (가장 뒤쪽)
        self.draw_realistic_coastline(qp, center_x, center_y, scale)
        
        # 2. 해양 구역 그리기
        self.draw_marine_zones(qp, center_x, center_y, scale)
        
        # 3. 등심선 그리기
        self.draw_depth_contours(qp, center_x, center_y, scale)
        
        # 4. 지형지물 그리기 (등대, 부표, 항구 등)
        self.draw_landmarks(qp, center_x, center_y, scale)
        
        # 5. 항로표지 그리기
        self.draw_navigation_aids(qp, center_x, center_y, scale)
        
        # 6. 위험구역 그리기
        self.draw_dangerous_areas(qp, center_x, center_y, scale)
        
        # 7. 해도 그리드 그리기 (지형지물 위에 얇게)
        self.draw_chart_grid(qp, center_x, center_y, scale)
        
        # 8. 자선과 타겟 선박 그리기 (가장 앞쪽)
        if self.ownship:
            # 자선의 실제 속도 전달
            os_speed = self.ownship.get('speed', 12) if self.ownship else 12
            
            # OS를 실제 GPS 좌표에 그대로 두고 해도와 함께 움직이게 함
            # OS의 실제 위경도 위치를 화면 좌표로 변환
            os_lat = getattr(self, 'os_lat', self.center_lat)
            os_lon = getattr(self, 'os_lon', self.center_lon)
            
            # 디버깅: OS와 해도 중심의 위경도 차이 확인
            if hasattr(self, 'debug_mode') and self.debug_mode:
                print(f"🔍 OS Position Debug:")
                print(f"  OS Lat: {os_lat:.6f}, OS Lon: {os_lon:.6f}")
                print(f"  Chart Center Lat: {self.center_lat:.6f}, Chart Center Lon: {self.center_lon:.6f}")
                print(f"  Lat Diff: {os_lat - self.center_lat:.6f}, Lon Diff: {os_lon - self.center_lon:.6f}")
            
            # 위경도를 화면 좌표로 변환 (해도 중심 기준)
            os_x, os_y = self.convert_latlon_to_xy(os_lat, os_lon, self.center_lat, self.center_lon)
            os_x = center_x + os_x * self.zoom_level
            os_y = center_y + os_y * self.zoom_level
            
            # 디버깅: 최종 화면 좌표 확인
            if hasattr(self, 'debug_mode') and self.debug_mode:
                print(f"  Final OS Screen Position: ({os_x:.1f}, {os_y:.1f})")
                print(f"  Screen Center: ({center_x}, {center_y})")
            
            self.draw_ship(qp, os_x, os_y, self.os_heading, 'os', os_speed)
        
        # 타겟 선박을 실제 위치에 그리기 (지형지물과 함께)
        self.draw_target_ships_with_terrain(qp, center_x, center_y, scale)
        
        # 9. 거리 및 방위 정보 표시
        self.draw_navigation_info(qp, center_x, center_y)
        
        # 10. 기상 효과 시각화 (실제 환경 반영)
        if hasattr(self, 'weather_data'):
            self.draw_weather_effects(qp, center_x, center_y, scale)
        
        # 11. 오프센터 정보 표시
        self.draw_off_center_info(qp, center_x, center_y)
        


    def draw_ship(self, qp, x, y, heading, color, speed=12):
        """선박을 그립니다. heading은 실제 침로(진행방향)를 나타냅니다."""
        qp.save()
        qp.translate(int(x), int(y))
        
        # heading 값 검증 및 정규화 (0-360도)
        if heading is None or pd.isna(heading):
            heading = 0.0
        heading = float(heading) % 360
        
        # 디버깅 정보
        if hasattr(self, 'debug_mode') and self.debug_mode:
            print(f"Drawing ship at ({x}, {y}) with heading={heading:.1f}°")
            print(f"  Color: {color}, Speed: {speed} kts")
            print(f"  Ship will point in direction: {heading:.1f}° (North=0°, East=90°)")
        
        # 선박형상을 heading 방향으로 회전
        # Qt 좌표계는 y축이 아래쪽이므로 -heading으로 회전
        qp.rotate(-heading)
        
        if color == 'os':
            pen_color = QColor(13, 110, 253)  # Modern blue
            brush_color = QColor(13, 110, 253, 200)  # More opaque for better visibility
            size = 18
        else:
            pen_color = color
            brush_color = color
            size = 12
            
        # 선수 방향이 위쪽(0도)을 향하는 배 모양
        # heading이 0도일 때 선수가 북쪽을 향함
        ship_points = [
            QPointF(0, -size),                    # 선수 (뾰족한 앞부분) - 북쪽(0도)
            QPointF(-size * 0.3, -size * 0.5),   # 왼쪽 앞부분
            QPointF(-size * 0.4, size * 0.3),    # 왼쪽 중간
            QPointF(-size * 0.3, size * 0.8),    # 왼쪽 뒤
            QPointF(0, size),                     # 선미 (뒤쪽 끝) - 남쪽(180도)
            QPointF(size * 0.3, size * 0.8),     # 오른쪽 뒤
            QPointF(size * 0.4, size * 0.3),     # 오른쪽 중간
            QPointF(size * 0.3, -size * 0.5),    # 오른쪽 앞부분
        ]
        
        # Draw ship with improved visibility
        qp.setPen(QPen(QColor(255, 255, 255), 4))  # White border for contrast
        qp.setBrush(QBrush(brush_color))
        qp.drawPolygon(*ship_points)
        
        # Draw ship interior with original color
        qp.setPen(QPen(pen_color, 2))
        qp.drawPolygon(*ship_points)
        
        # 선박 그림자 (깊이감 표현)
        qp.setPen(QPen(QColor(0, 0, 0, 30), 1))
        qp.setBrush(QBrush(QColor(0, 0, 0, 20)))
        shadow_points = [QPointF(p.x() + 2, p.y() + 2) for p in ship_points]
        qp.drawPolygon(*shadow_points)
        
        qp.restore()
        
        # 진행방향 벡터 (화살표) - heading 방향으로 정확히 표시
        qp.save()
        qp.translate(x, y)
        
        # 속도 기반 벡터 길이 계산
        time_minutes = 6  # 6분 후 도달 위치
        speed_knots = speed if speed and not pd.isna(speed) else 12
        distance_nm = (speed_knots * time_minutes) / 60.0  # NM
        pixels_per_nm = 80  # 화면에서 1NM당 픽셀 수
        arrow_len = distance_nm * pixels_per_nm
        
        # 벡터 길이 제한 (15-60 pixels)
        arrow_len = max(15, min(arrow_len, 60))
        
        # Vector colors and styles with improved visibility
        if color == 'os':
            vector_color = QColor(13, 110, 253)  # OS blue
            vector_width = 4  # Thicker for better visibility
        else:
            vector_color = QColor(220, 53, 69)   # TS red
            vector_width = 3  # Thicker for better visibility
        
        qp.setPen(QPen(vector_color, vector_width, Qt.SolidLine))
        
        # heading 방향으로 벡터 계산
        # 북쪽(0도)에서 시계방향으로 증가
        # Qt 좌표계: y축이 아래쪽이므로 cos에 음수 적용
        end_x = arrow_len * math.sin(math.radians(heading))
        end_y = -arrow_len * math.cos(math.radians(heading))
        
        if self.debug_mode:
            print(f"  Vector calculation:")
            print(f"    heading: {heading:.1f}°")
            print(f"    sin({heading:.1f}°) = {math.sin(math.radians(heading)):.3f}")
            print(f"    -cos({heading:.1f}°) = {-math.cos(math.radians(heading)):.3f}")
            print(f"    Vector: ({end_x:.1f}, {end_y:.1f})")
            print(f"    Expected direction: {heading:.1f}° (North=0°, East=90°, South=180°, West=270°)")
        
        # 메인 벡터 라인 그리기
        qp.drawLine(QPointF(0, 0), QPointF(end_x, end_y))
        
        # 화살촉 그리기 (heading 방향과 일치)
        head_size = max(4, arrow_len // 8)
        arrow_rad = math.radians(heading)
        
        for angle in [math.pi / 6, -math.pi / 6]:
            hx = end_x - head_size * math.sin(arrow_rad + angle)
            hy = end_y + head_size * math.cos(arrow_rad + angle)
            qp.drawLine(QPointF(end_x, end_y), QPointF(hx, hy))
        
        qp.restore()
        
        # 디버깅: heading과 bearing의 관계 표시 (작은 텍스트)
        if hasattr(self, 'debug_mode') and self.debug_mode:
            qp.save()
            qp.setPen(QPen(QColor(255, 255, 255), 1))
            qp.setFont(QFont("Arial", 8))
            
            # heading 정보를 명확하게 표시
            debug_text = f"H:{heading:.1f}°"
            qp.drawText(QPointF(x + 20, y - 10), debug_text)
            
            # 속도 정보 표시 (TS인 경우)
            if color != 'os':
                speed_text = f"S:{speed:.1f} kts"
                qp.drawText(QPointF(x + 20, y + 5), speed_text)
                
                # 기상 효과 표시 (속도 변화가 있을 때)
                if hasattr(self, 'weather_data'):
                    wind_speed = self.weather_data['wind_speed']
                    wave_height = self.weather_data['wave_height']
                    weather_text = f"W:{wind_speed} m/s, H:{wave_height} m"
                    qp.setFont(QFont("Arial", 7))
                    qp.drawText(QPointF(x + 20, y + 20), weather_text)
            
            qp.restore()
    
    def draw_ship_third_person(self, qp, x, y, heading, color, speed=12):
        """3자 시점에서 자선을 그립니다 (공중에서 내려다보는 시점)"""
        qp.save()
        
        # 3자 시점 효과: 그림자와 입체감 추가
        # 자선 그림자 그리기 (지면에 투영)
        shadow_offset = 15  # 그림자 오프셋
        shadow_alpha = 80   # 그림자 투명도
        
        qp.setPen(QPen(QColor(0, 0, 0, shadow_alpha), 1))
        qp.setBrush(QBrush(QColor(0, 0, 0, shadow_alpha // 2)))
        
        # 그림자 위치 (자선 뒤쪽에 약간 오프셋)
        shadow_x = x + shadow_offset
        shadow_y = y + shadow_offset
        
        # 그림자 크기 (약간 확대)
        shadow_size = 25
        qp.drawEllipse(QPointF(shadow_x, shadow_y), shadow_size, shadow_size)
        
        # 자선 그리기 (기존 방식과 동일하지만 약간 작게)
        qp.translate(int(x), int(y))
        
        # heading 값 검증 및 정규화
        if heading is None or pd.isna(heading):
            heading = 0.0
        heading = float(heading) % 360
        
        # 선박형상을 heading 방향으로 회전
        qp.rotate(-heading)
        
        if color == 'os':
            pen_color = QColor(13, 110, 253)  # Modern blue
            brush_color = QColor(13, 110, 253, 200)  # 약간 더 불투명
            size = 16  # 3자 시점에서는 약간 작게
        else:
            pen_color = color
            brush_color = color
            size = 10
        
        # 선박형상 그리기
        ship_points = [
            QPointF(0, -size),                    # 선수
            QPointF(-size * 0.3, -size * 0.5),   # 왼쪽 앞
            QPointF(-size * 0.4, size * 0.3),    # 왼쪽 중간
            QPointF(-size * 0.3, size * 0.8),    # 왼쪽 뒤
            QPointF(0, size),                     # 선미
            QPointF(size * 0.3, size * 0.8),     # 오른쪽 뒤
            QPointF(size * 0.4, size * 0.3),     # 오른쪽 중간
            QPointF(size * 0.3, -size * 0.5),    # 오른쪽 앞
        ]
        
        qp.setPen(QPen(pen_color, 2))
        qp.setBrush(QBrush(brush_color))
        qp.drawPolygon(*ship_points)
        
        # 3자 시점 효과: 선박 위에 입체감 추가
        qp.setPen(QPen(QColor(255, 255, 255, 100), 1))
        qp.setBrush(QBrush(QColor(255, 255, 255, 50)))
        
        # 선박 위쪽에 작은 하이라이트
        highlight_size = size * 0.3
        qp.drawEllipse(QPointF(0, -size * 0.3), highlight_size, highlight_size)
        
        qp.restore()
        
        # 진행방향 벡터 (3자 시점에서는 더 명확하게)
        qp.save()
        qp.translate(x, y)
        
        # 속도 기반 벡터 길이 계산
        time_minutes = 6
        speed_knots = speed if speed and not pd.isna(speed) else 12
        distance_nm = (speed_knots * time_minutes) / 60.0
        pixels_per_nm = 80
        arrow_len = distance_nm * pixels_per_nm
        arrow_len = max(20, min(arrow_len, 70))  # 3자 시점에서는 더 길게
        
        # 벡터 그리기
        if color == 'os':
            vector_color = QColor(13, 110, 253)
            vector_width = 4  # 더 두껍게
        else:
            vector_color = QColor(220, 53, 69)
            vector_width = 3
        
        qp.setPen(QPen(vector_color, vector_width, Qt.SolidLine))
        
        # heading 방향으로 벡터 계산
        end_x = arrow_len * math.sin(math.radians(heading))
        end_y = -arrow_len * math.cos(math.radians(heading))
        
        # 메인 벡터 라인
        qp.drawLine(QPointF(0, 0), QPointF(end_x, end_y))
        
        # 화살촉 (더 크게)
        head_size = max(6, arrow_len // 6)
        arrow_rad = math.radians(heading)
        
        for angle in [math.pi / 6, -math.pi / 6]:
            hx = end_x - head_size * math.sin(arrow_rad + angle)
            hy = end_y + head_size * math.cos(arrow_rad + angle)
            qp.drawLine(QPointF(end_x, end_y), QPointF(hx, hy))
        
        qp.restore()
        
        # 3자 시점 정보 표시
        if hasattr(self, 'debug_mode') and self.debug_mode:
            qp.save()
            qp.setPen(QPen(QColor(255, 255, 255), 1))
            qp.setFont(QFont("Arial", 9))
            
            # 3자 시점 모드 표시
            mode_text = "3P VIEW"
            qp.drawText(QPointF(x + 25, y - 15), mode_text)
            
            # 카메라 정보 표시
            camera_text = f"C:{self.camera_distance}px, {self.camera_angle}°"
            qp.setFont(QFont("Arial", 7))
            qp.drawText(QPointF(x + 25, y), camera_text)
            
            qp.restore()
    
    def draw_os_trajectory(self, qp, center_x, center_y):
        """자선 궤적을 그립니다"""
        if not self.trajectory_points or len(self.trajectory_points) < 2:
            return
        
        qp.save()
        
        # 궤적 그리기
        qp.setPen(QPen(QColor(13, 110, 253, 150), 2, Qt.DashLine))
        
        # 궤적 점들을 연결하여 그리기
        for i in range(len(self.trajectory_points) - 1):
            start_point = self.trajectory_points[i]
            end_point = self.trajectory_points[i + 1]
            
            # 투명도 그라데이션 (최근 점일수록 더 진하게)
            alpha = int(150 * (i + 1) / len(self.trajectory_points))
            qp.setPen(QPen(QColor(13, 110, 253, alpha), 2, Qt.DashLine))
            
            qp.drawLine(start_point, end_point)
        
        # 궤적 시작점과 끝점 표시
        if self.trajectory_points:
            # 시작점 (녹색)
            start_point = self.trajectory_points[0]
            qp.setPen(QPen(QColor(40, 167, 69), 3))
            qp.setBrush(QBrush(QColor(40, 167, 69)))
            qp.drawEllipse(start_point, 4, 4)
            
            # 끝점 (파란색)
            end_point = self.trajectory_points[-1]
            qp.setPen(QPen(QColor(13, 110, 253), 3))
            qp.setBrush(QBrush(QColor(13, 110, 253)))
            qp.drawEllipse(end_point, 4, 4)
        
        qp.restore()
    
    def add_trajectory_point(self, x, y):
        """궤적에 새로운 점을 추가합니다"""
        self.trajectory_points.append(QPointF(x, y))
        
        # 최대 점 수 제한
        if len(self.trajectory_points) > self.max_trajectory_points:
            self.trajectory_points.pop(0)
    
    def clear_trajectory(self):
        """궤적을 초기화합니다"""
        self.trajectory_points.clear()
    
    def draw_off_center_info(self, qp, center_x, center_y):
        """오프센터 정보를 화면에 표시합니다"""
        if not self.ownship:
            return
        
        # 차트 오프센터 거리 계산
        chart_off_center_distance = self.get_off_center_distance()
        
        # OS 오프센터 거리 계산
        os_off_center_distance = self.get_os_off_center_distance()
        
        # 오프센터가 있을 때만 표시
        if chart_off_center_distance > 0.1 or os_off_center_distance > 0.1:
            # 화면 우상단에 오프센터 정보 표시
            info_x = self.width() - 200
            info_y = 50
            
            # 배경 박스
            qp.setPen(QPen(QColor(255, 255, 0), 2))  # 노란색 테두리
            qp.setBrush(QBrush(QColor(0, 0, 0, 150)))  # 반투명 검은색 배경
            qp.drawRect(info_x - 10, info_y - 25, 190, 80)
            
            # 오프센터 정보 텍스트
            qp.setPen(QPen(QColor(255, 255, 0), 1))  # 노란색 텍스트
            qp.setFont(QFont("Arial", 10, QFont.Bold))
            qp.drawText(QPointF(info_x, info_y - 10), "OFF-CENTER INFO")
            
            qp.setFont(QFont("Arial", 9))
            
            # 차트 오프센터 정보
            if chart_off_center_distance > 0.1:
                qp.drawText(QPointF(info_x, info_y + 10), f"Chart: {chart_off_center_distance:.2f} NM")
            
            # OS 오프센터 정보
            if os_off_center_distance > 0.1:
                qp.setPen(QPen(QColor(13, 110, 253), 1))  # OS는 파란색
                qp.drawText(QPointF(info_x, info_y + 25), f"OS: {os_off_center_distance:.2f} NM")
                qp.setPen(QPen(QColor(255, 255, 0), 1))  # 다시 노란색으로
            
            # 방향 표시 (OS가 화면 중심에서 어느 방향에 있는지)
            if os_off_center_distance > 0.1:
                if hasattr(self, 'os_offset_x') and hasattr(self, 'os_offset_y'):
                    dx = self.os_offset_x
                    dy = self.os_offset_y
                    
                    if abs(dx) > abs(dy):
                        if dx > 0:
                            direction = "EAST"
                        else:
                            direction = "WEST"
                    else:
                        if dy > 0:
                            direction = "SOUTH"
                        else:
                            direction = "NORTH"
                    
                    qp.drawText(QPointF(info_x, info_y + 40), f"OS Direction: {direction}")
            
            # 오프센터 해제 안내
            qp.setPen(QPen(QColor(255, 255, 255), 1))
            qp.setFont(QFont("Arial", 8))
            qp.drawText(QPointF(info_x, info_y + 55), "SPACE: Reset Chart | R: Reset OS")
    
    def draw_chart_grid(self, qp, center_x, center_y, scale):
        """Draw minimal chart reference (grid and circles removed for better readability)"""
        # Grid and distance circles removed to improve chart readability
        # Only essential chart elements remain for clean visualization
        pass
    
    def draw_coastline(self, qp, center_x, center_y, scale):
        """해안선을 그립니다"""
        if not self.coastline_data:
            return
            
        qp.setPen(QPen(QColor(139, 69, 19), 3))  # 갈색 해안선
        
        # 해안선을 연결하여 그리기
        points = []
        for lat, lon in self.coastline_data:
            x, y = self.convert_latlon_to_xy(lat, lon, self.center_lat, self.center_lon)
            x = int(center_x + x * self.zoom_level)
            y = int(center_y + y * self.zoom_level)
            points.append(QPointF(x, y))
        
        # 해안선 그리기
        for i in range(len(points) - 1):
            qp.drawLine(points[i], points[i + 1])
        
        # 해안선 라벨
        if points:
            qp.setPen(QPen(QColor(139, 69, 19), 1))
            qp.setFont(QFont("Arial", 8, QFont.Bold))
            qp.drawText(QPointF(points[0].x() + 10, points[0].y() - 10), "COASTLINE")
    
    def draw_marine_zones(self, qp, center_x, center_y, scale):
        """Draw marine zones with optimized visibility and contrast"""
        for lat, lon, radius, zone_type, name in self.marine_zones:
            # Convert lat/lon to screen coordinates
            x, y = self.convert_latlon_to_xy(lat, lon, self.center_lat, self.center_lon)
            x = int(center_x + x * self.zoom_level)
            y = int(center_y + y * self.zoom_level)
            
            # Convert radius to pixels
            radius_pixels = radius * 60 * 70 * self.zoom_level  # 1 degree = 60NM, 1NM = 70 pixels
            
            # Zone colors and styles with improved visibility
            if zone_type == 'port_area':
                fill_color = QColor(0, 0, 0)  # Black
                border_color = QColor(255, 255, 255)  # White border for contrast
                pattern = Qt.SolidPattern
                border_width = 2
            elif zone_type == 'anchorage_area':
                fill_color = QColor(100, 100, 100)  # Dark gray
                border_color = QColor(200, 200, 200)  # Light gray border
                pattern = Qt.DiagCrossPattern
                border_width = 1
            elif zone_type == 'restricted_area':
                fill_color = QColor(220, 0, 0)  # Bright red (danger zone)
                border_color = QColor(255, 255, 255)  # White border for visibility
                pattern = Qt.DiagCrossPattern
                border_width = 2
            elif zone_type == 'fishing_area':
                fill_color = QColor(0, 0, 0)  # Black
                border_color = QColor(255, 255, 0)  # Yellow border
                pattern = Qt.Dense4Pattern
                border_width = 1
            elif zone_type == 'environmental_area':
                fill_color = QColor(0, 150, 0)  # Bright green
                border_color = QColor(255, 255, 255)  # White border
                pattern = Qt.Dense3Pattern
                border_width = 2
            else:
                fill_color = QColor(0, 0, 0)  # Black
                border_color = QColor(128, 128, 128)  # Gray border
                pattern = Qt.SolidPattern
                border_width = 1
            
            # Draw zone with improved visibility
            qp.setPen(QPen(border_color, border_width, Qt.SolidLine))
            qp.setBrush(QBrush(fill_color, pattern))
            qp.drawEllipse(QPointF(x, y), radius_pixels, radius_pixels)
            
            # Zone name labels with better contrast
            if zone_type in ['restricted_area', 'environmental_area', 'port_area']:
                # Use white text on dark backgrounds for better readability
                if zone_type in ['restricted_area', 'port_area']:
                    text_color = QColor(255, 255, 255)  # White text
                else:
                    text_color = QColor(0, 0, 0)  # Black text
                
                qp.setPen(QPen(text_color, 1))
                qp.setFont(QFont("Arial", 8, QFont.Bold))
                
                # Position label to avoid overlap
                label_x = x + radius_pixels + 10
                label_y = y + 5
                qp.drawText(QPointF(label_x, label_y), name)
    
    def draw_depth_contours(self, qp, center_x, center_y, scale):
        """Draw depth contours with optimized visibility"""
        for lat, lon, depth in self.depth_contours:
            # Convert lat/lon to screen coordinates
            x, y = self.convert_latlon_to_xy(lat, lon, self.center_lat, self.center_lon)
            x = int(center_x + x * self.zoom_level)
            y = int(center_y + y * self.zoom_level)
            
            # Depth-based colors with improved contrast
            if depth <= 10:
                color = QColor(0, 0, 0)  # Black (shallow)
                size = 10  # Larger size for shallow areas
                border_color = QColor(255, 255, 255)  # White border
            elif depth <= 20:
                color = QColor(40, 40, 40)  # Dark gray
                size = 8
                border_color = QColor(200, 200, 200)  # Light gray border
            elif depth <= 50:
                color = QColor(80, 80, 80)  # Medium gray
                size = 6
                border_color = QColor(180, 180, 180)  # Light gray border
            else:
                color = QColor(120, 120, 120)  # Light gray (deep)
                size = 5
                border_color = QColor(160, 160, 160)  # Medium gray border
            
            # Draw depth contour with border for better visibility
            qp.setPen(QPen(border_color, 2, Qt.SolidLine))
            qp.setBrush(QBrush(color, Qt.SolidPattern))
            qp.drawEllipse(QPointF(x, y), size, size)
            
            # Depth labels with improved readability
            if depth <= 30:  # Show labels for shallow to medium depths
                # Use contrasting text color
                if depth <= 10:
                    text_color = QColor(255, 255, 255)  # White text on black
                else:
                    text_color = QColor(0, 0, 0)  # Black text on light backgrounds
                
                qp.setPen(QPen(text_color, 1))
                qp.setFont(QFont("Arial", 7, QFont.Bold))
                qp.drawText(QPointF(x + size + 5, y + 3), f"{depth}m")
    
    def draw_landmarks(self, qp, center_x, center_y, scale):
        """Draw landmarks with optimized visibility and contrast"""
        for lat, lon, landmark_type, name in self.landmarks:
            # Convert lat/lon to screen coordinates
            x, y = self.convert_latlon_to_xy(lat, lon, self.center_lat, self.center_lon)
            x = int(center_x + x * self.zoom_level)
            y = int(center_y + y * self.zoom_level)
            
            # Landmark colors and styles with improved visibility
            if landmark_type == 'lighthouse':
                color = QColor(0, 0, 0)  # Black
                border_color = QColor(255, 255, 255)  # White border
                self.draw_lighthouse(qp, x, y)
            elif landmark_type == 'buoy':
                color = QColor(255, 0, 0)  # Red (more visible)
                border_color = QColor(255, 255, 255)  # White border
                self.draw_buoy(qp, x, y)
            elif landmark_type == 'rock':
                color = QColor(0, 0, 0)  # Black
                border_color = QColor(255, 255, 255)  # White border
                self.draw_rock(qp, x, y)
            elif landmark_type == 'wreck':
                color = QColor(139, 69, 19)  # Brown (more visible)
                border_color = QColor(255, 255, 255)  # White border
                self.draw_wreck(qp, x, y)
            elif landmark_type == 'bridge':
                color = QColor(0, 0, 0)  # Black
                border_color = QColor(255, 255, 255)  # White border
                self.draw_bridge(qp, x, y)
            elif landmark_type == 'port':
                color = QColor(0, 100, 0)  # Dark green
                border_color = QColor(255, 255, 255)  # White border
                self.draw_port(qp, x, y)
            elif landmark_type == 'anchorage':
                color = QColor(128, 128, 128)  # Gray
                border_color = QColor(255, 255, 255)  # White border
                self.draw_anchorage(qp, x, y)
            elif landmark_type == 'restricted_area':
                color = QColor(220, 0, 0)  # Bright red (danger zone)
                border_color = QColor(255, 255, 255)  # White border
                self.draw_restricted_area(qp, x, y)
            elif landmark_type == 'traffic_separation':
                color = QColor(0, 0, 0)  # Black
                border_color = QColor(255, 255, 255)  # White border
                self.draw_traffic_separation(qp, x, y)
            elif landmark_type == 'depth_area':
                color = QColor(128, 128, 128)  # Gray
                border_color = QColor(255, 255, 255)  # White border
                self.draw_depth_area(qp, x, y)
            elif landmark_type == 'fishing_zone':
                color = QColor(0, 0, 0)  # Black
                border_color = QColor(255, 255, 0)  # Yellow border
                self.draw_fishing_zone(qp, x, y)
            elif landmark_type == 'environmental':
                color = QColor(0, 128, 0)  # 진한 초록색
                self.draw_environmental_zone(qp, x, y)
            
            # 이름 라벨 (필요한 경우만)
            if landmark_type in ['lighthouse', 'port', 'restricted_area']:
                qp.setPen(QPen(color, 1))
                qp.setFont(QFont("Arial", 7))
                qp.drawText(QPointF(x + 12, y + 3), name)
    
    def draw_navigation_aids(self, qp, center_x, center_y, scale):
        """실제 해도와 유사한 항로표지를 그립니다"""
        for lat, lon, aid_type, name in self.navigation_aids:
            # 위경도를 화면 좌표로 변환
            x, y = self.convert_latlon_to_xy(lat, lon, self.center_lat, self.center_lon)
            x = int(center_x + x * self.zoom_level)
            y = int(center_y + y * self.zoom_level)
            
            # 항로표지 타입에 따른 그리기
            if 'cardinal' in aid_type:
                self.draw_cardinal_mark(qp, x, y, aid_type)
            elif aid_type == 'isolated_danger':
                self.draw_isolated_danger_mark(qp, x, y)
            elif aid_type == 'safe_water':
                self.draw_safe_water_mark(qp, x, y)
            
            # 이름 라벨 (필요한 경우만)
            if aid_type in ['isolated_danger']:
                qp.setPen(QPen(QColor(0, 0, 0), 1))
                qp.setFont(QFont("Arial", 6))
                qp.drawText(QPointF(x + 12, y + 3), name)
    
    def draw_dangerous_areas(self, qp, center_x, center_y, scale):
        """실제 해도와 유사한 위험구역을 그립니다"""
        for lat, lon, area_type, name in self.dangerous_areas:
            # 위경도를 화면 좌표로 변환
            x, y = self.convert_latlon_to_xy(lat, lon, self.center_lat, self.center_lon)
            x = int(center_x + x * self.zoom_level)
            y = int(center_y + y * self.zoom_level)
            
            # 위험구역 타입에 따른 색상 (실제 해도와 유사)
            if area_type == 'military':
                color = QColor(255, 0, 0)    # 빨간색
            elif area_type == 'fishing':
                color = QColor(0, 0, 0)      # 검은색
            elif area_type == 'environmental':
                color = QColor(0, 128, 0)    # 진한 초록색
            
            # 위험구역 표시 (실제 해도와 동일한 스타일)
            qp.setPen(QPen(color, 1, Qt.DashLine))
            qp.setBrush(QBrush(color, Qt.DiagCrossPattern))
            qp.drawEllipse(QPointF(x, y), 15, 15)
            
            # 이름 라벨 (필요한 경우만)
            if area_type in ['military', 'environmental']:
                qp.setPen(QPen(color, 1))
                qp.setFont(QFont("Arial", 6))
                qp.drawText(QPointF(x + 18, y + 3), name)
    
    def draw_target_ships(self, qp, center_x, center_y, scale):
        """타겟 선박을 그립니다 (상대운동)"""
        for ship in self.ships:
            if isinstance(ship, dict):
                # TS의 상대위치 계산 (OS 기준)
                rel_x = ship['x'] - center_x
                rel_y = ship['y'] - center_y
                
                # OS heading에 따라 회전된 좌표로 변환
                cos_h = math.cos(math.radians(self.os_heading))
                sin_h = math.sin(math.radians(self.os_heading))
                rotated_x = rel_x * cos_h + rel_y * sin_h
                rotated_y = -rel_x * sin_h + rel_y * cos_h
                
                # 상대운동 모드에서 TS의 heading은 절대 heading 사용
                # 실제 침로(진행방향)와 속도를 전달
                absolute_heading = ship['heading']
                ship_speed = ship.get('speed', 12)  # 기본값 12 knots
                self.draw_ship(qp, center_x + rotated_x, center_y + rotated_y, 
                              absolute_heading, ship['color'], ship_speed)
            elif isinstance(ship, tuple) and len(ship) == 5:
                # 튜플 형태의 경우도 동일하게 처리
                x, y, heading, color, speed = ship  # bearing 대신 speed 사용
                rel_x = x - center_x
                rel_y = y - center_y
                
                cos_h = math.cos(math.radians(self.os_heading))
                sin_h = math.sin(math.radians(self.os_heading))
                rotated_x = rel_x * cos_h + rel_y * sin_h
                rotated_y = -rel_x * sin_h + rel_y * cos_h
                
                # 절대 heading과 속도 사용
                absolute_heading = heading
                ship_speed = speed if speed and not pd.isna(speed) else 12
                self.draw_ship(qp, center_x + rotated_x, center_y + rotated_y,
                              absolute_heading, color, ship_speed)
    
    def draw_target_ships_true_motion(self, qp, center_x, center_y, scale):
        """타겟 선박을 그립니다 (트루모션)"""
        for ship in self.ships:
            if isinstance(ship, dict):
                # TS를 실제 위치에 그리기 (OS heading 회전 없음)
                # 실제 침로(진행방향)와 속도를 전달
                ship_speed = ship.get('speed', 12)  # 기본값 12 knots
                self.draw_ship(qp, ship['x'], ship['y'], ship['heading'], ship['color'], ship_speed)
            elif isinstance(ship, tuple) and len(ship) == 5:
                # 튜플 형태의 경우도 동일하게 처리
                x, y, heading, color, speed = ship  # bearing 대신 speed 사용
                ship_speed = speed if speed and not pd.isna(speed) else 12
                self.draw_ship(qp, x, y, heading, color, ship_speed)
    
    def draw_navigation_info(self, qp, center_x, center_y):
        """항해 정보를 표시합니다"""
        # GPS 좌표 정보 (실제 해도와 동일한 스타일)
        qp.setPen(QPen(QColor(0, 0, 0), 1))
        qp.setFont(QFont("Arial", 9))
        
        # AIS 데이터가 있을 때 실제 경위도 표시
        if hasattr(self, 'ship_data') and "OS" in self.ship_data and len(self.ship_data["OS"]) > 0:
            # 현재 시뮬레이션 시간에 해당하는 AIS 데이터 사용
            current_index = min(self.current_time_index, len(self.ship_data["OS"]) - 1) if hasattr(self, 'current_time_index') else 0
            os_data = self.ship_data["OS"].iloc[current_index]
            actual_lat = os_data['lat']
            actual_lon = os_data['lon']
            actual_heading = os_data['co']
            actual_speed = os_data['spd']
            
            qp.drawText(QPointF(10, 30), f"Lat: {actual_lat:.6f}°")
            qp.drawText(QPointF(10, 50), f"Lon: {actual_lon:.6f}°")
            qp.drawText(QPointF(10, 70), f"Hdg: {actual_heading:.1f}°")
            qp.drawText(QPointF(10, 90), f"Spd: {actual_speed:.1f} kts")
        else:
            # 기본값 표시
            qp.drawText(QPointF(10, 30), f"Lat: {self.center_lat:.6f}°")
            qp.drawText(QPointF(10, 50), f"Lon: {self.center_lon:.6f}°")
            qp.drawText(QPointF(10, 70), f"Hdg: {self.os_heading:.1f}°")
            qp.drawText(QPointF(10, 90), f"Spd: -- kts")
        
        qp.drawText(QPointF(10, 110), f"Zoom: {self.zoom_level:.1f}x")
        
        # 컨트롤 모드 표시 (실제 해도와 동일한 스타일)
        if hasattr(self, 'os_control_mode'):
            mode_text = "Manual Control" if self.os_control_mode else "AIS Auto"
            mode_color = QColor(220, 53, 69) if self.os_control_mode else QColor(40, 167, 69)
            qp.setPen(QPen(mode_color, 1))
            qp.setFont(QFont("Arial", 9, QFont.Bold))
            qp.drawText(QPointF(10, 130), f"Mode: {mode_text}")
        
        # 지형지물 중심 화면 모드 표시 (실제 해도와 동일한 스타일)
        if hasattr(self, 'terrain_centered_mode'):
            terrain_mode_text = "TER (Terrain Centered)" if self.terrain_centered_mode else "SHIP (Ship Centered)"
            terrain_mode_color = QColor(40, 167, 69) if self.terrain_centered_mode else QColor(0, 123, 255)
            qp.setPen(QPen(terrain_mode_color, 1))
            qp.setFont(QFont("Arial", 8, QFont.Bold))
            qp.drawText(QPointF(10, 150), f"Terrain: {terrain_mode_text}")
        
        # Compass directions with improved visibility
        qp.setPen(QPen(QColor(0, 0, 0), 2))
        qp.setFont(QFont("Arial", 12, QFont.Bold))
        
        # North (top)
        qp.drawText(QPointF(center_x - 8, 25), "N")
        
        # East (right)
        qp.drawText(QPointF(self.width() - 25, center_y + 5), "E")
        
        # South (bottom)
        qp.drawText(QPointF(center_x - 8, self.height() - 15), "S")
        
        # West (left)
        qp.drawText(QPointF(25, center_y + 5), "W")
        
        # Add compass rose indicator in top-left corner
        qp.setPen(QPen(QColor(100, 100, 100), 1))
        qp.setFont(QFont("Arial", 8))
        qp.drawText(QPointF(15, 25), "COMPASS")
        
        # 드래그 사용법 안내 (화면 우하단) - 실제 해도와 동일한 스타일
        qp.setPen(QPen(QColor(0, 0, 0, 180), 1))
        qp.setFont(QFont("Arial", 8))
        
        help_text = "🖱️ Mouse Drag: Move Chart | Mouse Wheel: Zoom | SPACE: Reset Chart to Ship | 0: Reset Zoom"
        
        help_width = qp.fontMetrics().width(help_text)
        help_x = self.width() - help_width - 10
        help_y = self.height() - 10
        qp.drawText(QPointF(help_x, help_y), help_text)
        
        # 드래그 중일 때 시각적 피드백
        if hasattr(self, 'chart_dragging') and self.chart_dragging:
            # 차트 드래깅 중 최소한의 피드백만 표시 (배경색 변경 없음)
            # 차트 드래깅 상태 텍스트 (작게)
            qp.setPen(QPen(QColor(0, 0, 0), 1))
            qp.setFont(QFont("Arial", 10))
            qp.drawText(QPointF(center_x - 50, center_y + 40), "CHART PANNING")
    
    # 지형지물 그리기 헬퍼 메서드들
    def draw_lighthouse(self, qp, x, y):
        """Draw lighthouse with improved visibility"""
        # Main structure with white border for contrast
        qp.setPen(QPen(QColor(255, 255, 255), 3))
        qp.setBrush(QBrush(QColor(255, 255, 0), Qt.SolidPattern))
        qp.drawRect(x - 8, y - 8, 16, 16)
        
        # Light beam
        qp.setPen(QPen(QColor(255, 255, 255), 2))
        qp.drawLine(x, y - 8, x, y - 15)
    
    def draw_buoy(self, qp, x, y):
        """Draw buoy with improved visibility"""
        # Red buoy with white border
        qp.setPen(QPen(QColor(255, 255, 255), 3))
        qp.setBrush(QBrush(QColor(255, 0, 0), Qt.SolidPattern))
        qp.drawEllipse(QPointF(x, y), 6, 6)
    
    def draw_rock(self, qp, x, y):
        """Draw rock with improved visibility"""
        # Red rock with white border
        qp.setPen(QPen(QColor(255, 255, 255), 3))
        qp.setBrush(QBrush(QColor(255, 0, 0), Qt.SolidPattern))
        qp.drawPolygon([QPointF(x-5, y+5), QPointF(x+5, y+5), QPointF(x, y-5)])
    
    def draw_wreck(self, qp, x, y):
        """Draw wreck with improved visibility"""
        # Brown wreck with white border
        qp.setPen(QPen(QColor(255, 255, 255), 3))
        qp.drawLine(x-8, y+8, x+8, y-8)
        qp.drawLine(x-8, y-8, x+8, y+8)
    
    def draw_bridge(self, qp, x, y):
        """Draw bridge with improved visibility"""
        # Gray bridge with white border
        qp.setPen(QPen(QColor(255, 255, 255), 4))
        qp.drawLine(x-10, y, x+10, y)
    
    def draw_port(self, qp, x, y):
        """Draw port with improved visibility"""
        # Green port with white border
        qp.setPen(QPen(QColor(255, 255, 255), 3))
        qp.setBrush(QBrush(QColor(0, 150, 0), Qt.SolidPattern))
        qp.drawRect(x - 10, y - 10, 20, 20)
    
    def draw_anchorage(self, qp, x, y):
        """Draw anchorage with improved visibility"""
        # Yellow anchorage with white border
        qp.setPen(QPen(QColor(255, 255, 255), 3))
        qp.setBrush(QBrush(QColor(255, 255, 0), Qt.DiagCrossPattern))
        qp.drawEllipse(QPointF(x, y), 15, 15)
    
    def draw_restricted_area(self, qp, x, y):
        """Draw restricted area with improved visibility"""
        # Magenta restricted area with white border
        qp.setPen(QPen(QColor(255, 255, 255), 3, Qt.DashLine))
        qp.setBrush(QBrush(QColor(220, 0, 220), Qt.DiagCrossPattern))
        qp.drawEllipse(QPointF(x, y), 25, 25)
    
    def draw_traffic_separation(self, qp, x, y):
        """Draw traffic separation with improved visibility"""
        # Cyan traffic separation with white border
        qp.setPen(QPen(QColor(255, 255, 255), 3, Qt.DashLine))
        qp.drawLine(x-20, y, x+20, y)
        qp.drawLine(x, y-20, x, y+20)
    
    def draw_depth_area(self, qp, x, y):
        """Draw depth area with improved visibility"""
        # Blue depth area with white border
        qp.setPen(QPen(QColor(255, 255, 255), 3))
        qp.setBrush(QBrush(QColor(0, 150, 255), Qt.Dense4Pattern))
        qp.drawEllipse(QPointF(x, y), 20, 20)
    
    def draw_fishing_zone(self, qp, x, y):
        """Draw fishing zone with improved visibility"""
        # Orange fishing zone with white border
        qp.setPen(QPen(QColor(255, 255, 255), 3))
        qp.setBrush(QBrush(QColor(255, 165, 0), Qt.Dense5Pattern))
        qp.drawEllipse(QPointF(x, y), 25, 25)
        
        # Fishing zone indicator (fish shape)
        qp.setPen(QPen(QColor(255, 255, 255), 1))
        qp.drawText(QPointF(x - 5, y + 5), "🐟")
    
    def draw_environmental_zone(self, qp, x, y):
        """환경보호구역을 그립니다"""
        qp.setPen(QPen(QColor(0, 255, 0), 2))
        qp.setBrush(QBrush(QColor(0, 255, 0), Qt.Dense2Pattern))
        qp.drawEllipse(QPointF(x, y), 30, 30)
        
        # 환경보호구역 표시 (나무 모양)
        qp.setPen(QPen(QColor(255, 255, 255), 1))
        qp.drawText(QPointF(x - 5, y + 5), "🌳")
    
    # 항로표지 그리기 헬퍼 메서드들
    def draw_cardinal_mark(self, qp, x, y, direction):
        """방위표지를 그립니다"""
        qp.setPen(QPen(QColor(255, 255, 255), 2))
        qp.setBrush(QBrush(QColor(255, 255, 255)))
        
        if 'north' in direction:
            qp.drawPolygon([QPointF(x, y-8), QPointF(x-5, y+8), QPointF(x+5, y+8)])
        elif 'south' in direction:
            qp.drawPolygon([QPointF(x, y+8), QPointF(x-5, y-8), QPointF(x+5, y-8)])
        elif 'east' in direction:
            qp.drawPolygon([QPointF(x+8, y), QPointF(x-8, y-5), QPointF(x-8, y+5)])
        elif 'west' in direction:
            qp.drawPolygon([QPointF(x-8, y), QPointF(x+8, y-5), QPointF(x+8, y+5)])
    
    def draw_isolated_danger_mark(self, qp, x, y):
        """고립위험표지를 그립니다"""
        qp.setPen(QPen(QColor(255, 0, 0), 2))
        qp.setBrush(QBrush(QColor(255, 0, 0)))
        qp.drawPolygon([QPointF(x, y-8), QPointF(x-5, y+8), QPointF(x+5, y+8)])
    
    def draw_safe_water_mark(self, qp, x, y):
        """안전수역표지를 그립니다"""
        qp.setPen(QPen(QColor(0, 255, 0), 2))
        qp.setBrush(QBrush(QColor(0, 255, 0)))
        qp.drawEllipse(QPointF(x, y), 8, 8)
    
    def convert_latlon_to_xy(self, lat, lon, center_lat, center_lon):
        """위경도를 캔버스 좌표로 변환합니다"""
        # 위경도 차이 계산
        lat_diff = lat - center_lat
        lon_diff = lon - center_lon
        
        # 1도 = 약 60NM, 1NM = 70 pixels
        # 경도는 동쪽이 양수, 위도는 북쪽이 양수
        # Qt 좌표계: x축은 오른쪽이 양수, y축은 아래쪽이 양수
        x = lon_diff * 60 * 70  # 경도 차이를 픽셀로 변환 (동쪽이 양수)
        y = -lat_diff * 60 * 70  # 위도 차이를 픽셀로 변환 (북쪽이 양수, y축은 반대)
        
        # OS 위치 변환 시 상세 디버깅
        if hasattr(self, 'debug_mode') and self.debug_mode:
            # OS인지 확인 (lat, lon이 os_lat, os_lon과 같은 경우)
            if hasattr(self, 'os_lat') and hasattr(self, 'os_lon'):
                if abs(lat - self.os_lat) < 0.000001 and abs(lon - self.os_lon) < 0.000001:
                    print(f"🎯 OS Coordinate Conversion:")
                    print(f"  Input: ({lat:.6f}, {lon:.6f})")
                    print(f"  Center: ({center_lat:.6f}, {center_lon:.6f})")
                    print(f"  Diff: lat_diff={lat_diff:.6f}, lon_diff={lon_diff:.6f}")
                    print(f"  Output: x={x:.1f}, y={y:.1f}")
        
        return x, y
    
    def wheelEvent(self, event):
        """마우스 휠로 줌 인/아웃 - 전자해도 방식"""
        delta = event.angleDelta().y()
        
        # 줌 인/아웃
        if delta > 0:
            self.zoom_level = min(self.zoom_level * 1.2, 5.0)  # 최대 5배 줌
        else:
            self.zoom_level = max(self.zoom_level / 1.2, 0.2)  # 최소 0.2배 줌
        
        self.update()
    
    def mousePressEvent(self, event):
        """마우스 클릭 이벤트 - 전자해도 방식"""
        if event.button() == Qt.LeftButton:
            # 차트 드래깅 시작
            self.chart_dragging = True
            self.dragging = True
            self.last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)  # 손 모양 커서로 변경
            if self.debug_mode:
                print("🗺️ Chart dragging started")
            self.update()
    
    def mouseMoveEvent(self, event):
        """마우스 이동 이벤트 - 해도 이동 방식"""
        if self.last_mouse_pos and self.chart_dragging:
            # 마우스 이동 거리 계산
            delta_x = event.x() - self.last_mouse_pos.x()
            delta_y = event.y() - self.last_mouse_pos.y()
            
            # 해도 중심 이동 (OS는 실제 GPS 좌표에 고정, 해도가 움직임)
            # 이동 거리를 위경도로 변환 (줌 레벨과 스케일 팩터를 고려)
            # 1NM = 70 pixels, 1NM ≈ 0.0167도
            pixels_per_nm = 70 * self.zoom_level
            nm_per_degree = 60  # 1도 = 60NM
            
            lat_delta = -delta_y / (pixels_per_nm * nm_per_degree)
            lon_delta = delta_x / (pixels_per_nm * nm_per_degree)
            
            # 중심 좌표 업데이트 (해도가 움직임)
            self.center_lat += lat_delta
            self.center_lon += lon_delta
            
            if self.debug_mode:
                print(f"🗺️ Chart moved - Center: ({self.center_lat:.6f}, {self.center_lon:.6f})")
            
            # 마우스 위치 업데이트
            self.last_mouse_pos = event.pos()
            
            # 화면 갱신
            self.update()
    
    def mouseReleaseEvent(self, event):
        """마우스 릴리즈 이벤트"""
        if event.button() == Qt.LeftButton:
            # 드래그 종료
            if hasattr(self, 'chart_dragging'):
                self.chart_dragging = False
            self.dragging = False
            self.setCursor(Qt.ArrowCursor)  # 기본 커서로 복원
    
    def reset_to_ship_center(self):
        """해도 중심을 자선 위치로 리셋합니다 (해도 오프센터 해제)"""
        if self.ownship:
            # 자선이 있는 경우 자선 위치로 해도 중심 이동
            ship_lat = getattr(self, 'os_lat', self.center_lat)
            ship_lon = getattr(self, 'os_lon', self.center_lon)
            
            # 해도 중심을 자선 위치로 설정
            old_lat = self.center_lat
            old_lon = self.center_lon
            
            self.center_lat = ship_lat
            self.center_lon = ship_lon
            
            # 진행 상황에 기록
            if hasattr(self, 'parent') and hasattr(self.parent(), 'add_progress_entry'):
                self.parent().add_progress_entry(f"🎯 Chart center reset to ship position (was at: {old_lat:.6f}, {old_lon:.6f})")
        else:
            # 자선이 없는 경우 기본 위치로 리셋
            self.center_lat = 0
            self.center_lon = 0
            if hasattr(self, 'parent') and hasattr(self.parent(), 'add_progress_entry'):
                self.parent().add_progress_entry("🎯 Chart center reset to default position")
    
    def reset_os_to_center(self):
        """OS 위치를 화면 중심으로 리셋합니다 (전자해도 방식)"""
        # OS 오프셋 초기화
        if hasattr(self, 'os_offset_x') and hasattr(self, 'os_offset_y'):
            self.os_offset_x = 0
            self.os_offset_y = 0
            
            # 진행 상황에 기록
            if hasattr(self, 'parent') and hasattr(self.parent(), 'add_progress_entry'):
                self.parent().add_progress_entry("🚢 OS position reset to center")
        else:
            # OS 오프셋이 없는 경우 초기화
            self.os_offset_x = 0
            self.os_offset_y = 0
    
    def move_to_random_location(self):
        """테스트를 위해 랜덤 위치로 이동합니다"""
        import random
        
        # 한국 주변 해역 범위 내에서 랜덤 위치 생성
        lat_range = (33.0, 38.0)  # 제주도 ~ 강원도
        lon_range = (126.0, 130.0)  # 서해 ~ 동해
        
        new_lat = random.uniform(*lat_range)
        new_lon = random.uniform(*lon_range)
        
        self.center_lat = new_lat
        self.center_lon = new_lon
        
        # 해당 위치에 맞는 해도 데이터 초기화
        self.initialize_chart_data_for_location(new_lat, new_lon, 5.0)  # 5NM 반지름
        
        # 진행 상황에 기록
        if hasattr(self, 'parent') and hasattr(self.parent(), 'add_progress_entry'):
            self.parent().add_progress_entry(f"🎲 Chart moved to random location: ({new_lat:.4f}, {new_lon:.4f})")
    
    def get_off_center_distance(self):
        """현재 해도 중심과 자선 위치 간의 오프센터 거리를 계산합니다"""
        if not self.ownship:
            return 0.0
        
        # 자선의 실제 위경도 위치
        ship_lat = getattr(self, 'os_lat', self.center_lat)
        ship_lon = getattr(self, 'os_lon', self.center_lon)
        
        # 해도 중심과 자선 위치 간의 거리 계산 (위경도 차이)
        lat_diff = abs(ship_lat - self.center_lat)
        lon_diff = abs(ship_lon - self.center_lon)
        
        # 위경도 차이를 해리로 변환 (대략적인 변환)
        # 1도 ≈ 60NM
        distance_nm = math.sqrt((lat_diff * 60)**2 + (lon_diff * 60)**2)
        
        return distance_nm
    
    def get_os_off_center_distance(self):
        """OS가 화면 중심에서 얼마나 떨어져 있는지 계산합니다 (드래깅으로 이동된 경우)"""
        if not hasattr(self, 'os_offset_x') or not hasattr(self, 'os_offset_y'):
            return 0.0
        
        # OS 오프셋 거리 계산
        pixel_distance = math.sqrt(self.os_offset_x**2 + self.os_offset_y**2)
        
        # 해리로 변환
        distance_nm = pixel_distance / (self.scale_factor * self.zoom_level)
        
        return distance_nm
    

    
    def keyPressEvent(self, event):
        """키보드 이벤트 - 전자해도 기본 기능만"""
        if event.key() == Qt.Key_Space:
            # 스페이스바로 차트 중심을 자선 위치로 리셋
            self.reset_to_ship_center()
            self.update()
        elif event.key() == Qt.Key_0:
            # 0 키로 줌 레벨 리셋
            self.zoom_level = 1.0
            self.update()
    
    def draw_realistic_background(self, qp):
        """Draw clean background without grid for better readability"""
        # Clean white background (like real charts)
        qp.fillRect(self.rect(), QColor(255, 255, 255))
        
        # Grid removed for cleaner visualization
        # Only subtle border remains for chart area definition
        qp.setPen(QPen(QColor(220, 220, 220), 1))
        qp.drawRect(0, 0, self.width() - 1, self.height() - 1)
    
    def draw_realistic_coastline(self, qp, center_x, center_y, scale):
        """Draw realistic coastline with optimized visibility"""
        if not self.coastline_data:
            return
        
        # Coastline drawing with improved contrast
        qp.setPen(QPen(QColor(0, 0, 0), 3))  # Thicker black coastline
        
        # Connect coastline points
        points = []
        for lat, lon in self.coastline_data:
            x, y = self.convert_latlon_to_xy(lat, lon, self.center_lat, self.center_lon)
            x = int(center_x + x * self.zoom_level)
            y = int(center_y + y * self.zoom_level)
            points.append(QPointF(x, y))
        
        # Draw coastline
        for i in range(len(points) - 1):
            qp.drawLine(points[i], points[i + 1])
        
        # Fill land area with improved visibility
        if len(points) > 2:
            # Land color with better contrast (light beige)
            land_brush = QBrush(QColor(240, 240, 220))
            qp.setBrush(land_brush)
            qp.setPen(QPen(QColor(0, 0, 0), 1))
            
            # Fill land area as polygon
            land_points = points + [QPointF(self.width(), self.height()), QPointF(0, self.height())]
            qp.drawPolygon(*land_points)
            
            # Add coastline label for better identification
            if points:
                qp.setPen(QPen(QColor(0, 0, 0), 1))
                qp.setFont(QFont("Arial", 9, QFont.Bold))
                qp.drawText(QPointF(points[0].x() + 15, points[0].y() - 15), "COASTLINE")
    
    def draw_target_ships_with_terrain(self, qp, center_x, center_y, scale):
        """지형지물과 함께 타겟 선박을 그립니다."""
        for ship in self.ships:
            if isinstance(ship, dict):
                # TS를 실제 위치에 그리기 (지형지물과 함께)
                ship_speed = ship.get('speed', 12)
                self.draw_ship(qp, ship['x'], ship['y'], ship['heading'], ship['color'], ship_speed)
                
                # 선박과 지형지물 간의 거리 표시 (가까운 경우)
                self.draw_ship_terrain_distance(qp, ship, center_x, center_y, scale)
                
            elif isinstance(ship, tuple) and len(ship) == 5:
                x, y, heading, color, speed = ship
                ship_speed = speed if speed and not pd.isna(speed) else 12
                self.draw_ship(qp, x, y, heading, color, ship_speed)
                
                # 선박과 지형지물 간의 거리 표시
                ship_dict = {'x': x, 'y': y, 'heading': heading, 'color': color, 'speed': ship_speed}
                self.draw_ship_terrain_distance(qp, ship_dict, center_x, center_y, scale)
    
    def draw_ship_terrain_distance(self, qp, ship, center_x, center_y, scale):
        """선박과 지형지물 간의 거리를 표시합니다."""
        ship_x, ship_y = ship['x'], ship['y']
        
        # 가장 가까운 지형지물 찾기
        min_distance = float('inf')
        nearest_landmark = None
        
        for lat, lon, landmark_type, name in self.landmarks:
            landmark_x, landmark_y = self.convert_latlon_to_xy(lat, lon, self.center_lat, self.center_lon)
            landmark_x = center_x + landmark_x * self.zoom_level
            landmark_y = center_y + landmark_y * self.zoom_level
            
            distance = math.sqrt((ship_x - landmark_x)**2 + (ship_y - landmark_y)**2)
            
            if distance < min_distance and distance < 100:  # 100픽셀 이내만 표시
                min_distance = distance
                nearest_landmark = (landmark_x, landmark_y, name, landmark_type)
        
        # 가까운 지형지물이 있으면 거리 표시
        if nearest_landmark and min_distance < 100:
            landmark_x, landmark_y, name, landmark_type = nearest_landmark
            
            # 거리 선 그리기
            qp.setPen(QPen(QColor(255, 255, 255, 150), 1, Qt.DashLine))
            qp.drawLine(int(ship_x), int(ship_y), int(landmark_x), int(landmark_y))
            
            # 거리 텍스트
            distance_nm = min_distance / (scale * 0.7)  # 픽셀을 해리로 변환
            qp.setPen(QPen(QColor(255, 255, 255), 1))
            qp.setFont(QFont("Arial", 8))
            
            # 선박과 지형지물 중간에 거리 표시
            mid_x = (ship_x + landmark_x) / 2
            mid_y = (ship_y + landmark_y) / 2
            qp.drawText(QPointF(mid_x + 5, mid_y - 5), f"{distance_nm:.1f}NM")
            
            # 지형지물 이름 강조
            qp.setPen(QPen(QColor(255, 255, 0), 2))
            qp.setFont(QFont("Arial", 9, QFont.Bold))
            qp.drawText(QPointF(landmark_x + 20, landmark_y), name)

class AISDataProcessor:
    """AIS 데이터 처리 클래스"""
    
    @staticmethod
    def load_ais_data(file_path):
        """AIS 엑셀 파일을 로드하고 처리합니다."""
        try:
            # 엑셀 파일 읽기
            df = pd.read_excel(file_path)
            
            # 필수 컬럼 확인
            required_columns = ['mmsi', 'lat', 'lon', 'spd', 'co', 'time']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                raise ValueError(f"필수 컬럼이 누락되었습니다: {missing_columns}")
            
            # 데이터 정리
            df = df.dropna(subset=['lat', 'lon', 'spd', 'co'])
            
            # 시간순 정렬
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'])
                df = df.sort_values('time')
            
            return df
            
        except Exception as e:
            raise Exception(f"AIS 데이터 로드 오류: {str(e)}")
    
    @staticmethod
    def convert_latlon_to_xy(lat, lon, center_lat, center_lon):
        """위경도를 캔버스 좌표로 변환합니다."""
        # 위경도 차이 계산
        lat_diff = lat - center_lat
        lon_diff = lon - center_lon
        
        # 1도 = 약 60NM, 1NM = 70 pixels
        # 경도는 동쪽이 양수, 위도는 북쪽이 양수
        # Qt 좌표계: x축은 오른쪽이 양수, y축은 아래쪽이 양수
        x = lon_diff * 60 * 70  # 경도 차이를 픽셀로 변환 (동쪽이 양수)
        y = -lat_diff * 60 * 70  # 위도 차이를 픽셀로 변환 (북쪽이 양수, y축은 반대)
        
        return x, y

class OntologyProcessor:
    """OWL 온톨로지 처리 클래스"""
    
    @staticmethod
    def load_owl_file(file_path):
        """OWL 파일을 로드하고 파싱합니다."""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # 네임스페이스 정의
            namespaces = {
                'owl': 'http://www.w3.org/2002/07/owl#',
                'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
                'xml': 'http://www.w3.org/XML/1998/namespace'
            }
            
            # COLREG 및 재결서 기반 성능평가 항목 추출
            evaluation_items = []
            
            # Class 정의 찾기
            for class_elem in root.findall('.//owl:Class', namespaces):
                class_id = class_elem.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about')
                if class_id:
                    class_name = class_id.split('#')[-1] if '#' in class_id else class_id
                    
                    # 성능평가 관련 클래스 필터링
                    if any(keyword in class_name.lower() for keyword in ['evaluation', 'performance', 'assessment', 'colreg', 'rule']):
                        evaluation_items.append({
                            'type': 'class',
                            'name': class_name,
                            'id': class_id,
                            'description': '',
                            'score': 0.0
                        })
            
            # ObjectProperty 정의 찾기
            for prop_elem in root.findall('.//owl:ObjectProperty', namespaces):
                prop_id = prop_elem.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about')
                if prop_id:
                    prop_name = prop_id.split('#')[-1] if '#' in prop_id else prop_id
                    
                    # 성능평가 관련 속성 필터링
                    if any(keyword in prop_name.lower() for keyword in ['evaluate', 'assess', 'measure', 'performance']):
                        evaluation_items.append({
                            'type': 'property',
                            'name': prop_name,
                            'id': prop_id,
                            'description': '',
                            'score': 0.0
                        })
            
            return evaluation_items
            
        except Exception as e:
            raise Exception(f"OWL 파일 로드 오류: {str(e)}")
    
    @staticmethod
    def analyze_scenario_evaluation_items(evaluation_items, scenario_data):
        """시나리오 환경에 맞는 성능평가 항목을 분석합니다."""
        relevant_items = []
        
        # COLREG 규칙 기반 필터링
        colreg_keywords = ['head_on', 'crossing', 'overtaking', 'give_way', 'stand_on', 'safe_speed', 'collision_avoidance']
        
        for item in evaluation_items:
            item_lower = item['name'].lower()
            
            # COLREG 관련 항목 필터링
            if any(keyword in item_lower for keyword in colreg_keywords):
                relevant_items.append(item)
            
            # 일반적인 성능평가 항목
            elif any(keyword in item_lower for keyword in ['safety', 'efficiency', 'compliance', 'risk']):
                relevant_items.append(item)
        
        return relevant_items

class SimulatorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AIS-Based Ship Simulator")
        self.setGeometry(100, 100, 2200, 800)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f9fa;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #495057;
            }
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
            QSlider::groove:horizontal {
                border: 1px solid #dee2e6;
                height: 8px;
                background: #e9ecef;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #007bff;
                border: 2px solid #007bff;
                width: 16px;
                height: 16px;
                border-radius: 8px;
                margin: -4px 0;
            }
        """)

        # 메인 위젯과 레이아웃
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # 왼쪽 컨트롤 패널
        self.setup_left_panel()
        main_layout.addWidget(self.left_panel)

        # 중앙 시뮬레이터 캔버스
        self.setup_simulator_canvas()
        main_layout.addWidget(self.sim_canvas)
        
        # 전자해도 제어는 기본 캔버스에 통합되어 있음

        # 오른쪽 온톨로지 패널
        self.setup_right_panel()
        main_layout.addWidget(self.right_panel)

        # 시뮬레이션 관련 변수
        self.ship_data = {}  # 각 선박별 데이터 저장
        self.current_time_index = 0
        self.simulation_timer = QTimer()
        self.simulation_timer.timeout.connect(self.update_simulation)
        self.is_simulation_running = False
        
        # OS 컨트롤 모드 관련 변수
        self.os_control_mode = False  # False: AIS 자동 모드, True: 수동 조종 모드
        self.os_initial_position_set = False  # 초기 위치 설정 여부
        self.os_manual_position = {'x': 0, 'y': 0, 'heading': 0, 'speed': 12}  # 수동 조종 위치
        
        # 지형지물 중심 화면 모드 관련 변수
        self.terrain_centered_mode = True  # True: 지형지물 중심, False: 자선 중심
        
        # 자선 행동 추적 관련 변수
        self.behavior_history = []
        self.progress_history = []  # 진행 상황 전체 이력
        self.os_trajectory = []
        self.ts_trajectories = {}
        self.scenario_end_time = 300  # 기본 5분 (300초)
        self.current_time = 0
        self.is_scenario_completed = False
        
        # 이력 추적 타이밍 제어
        self.last_behavior_change_time = 0
        self.last_os_heading = None
        self.last_os_speed = None
        self.behavior_delay_seconds = 1.0  # 1초 이상 유지될 때만 기록
        
        # 기상 환경 관련 변수
        self.weather_data = {
            'wind_speed': 10,      # m/s
            'stream_direction': 'E', # 16방위법
            'stream_speed': 2,      # kn
            'wave_height': 2.0,     # m
            'visibility': 10        # nm
        }
        
        # 디버그 모드 변수
        self.debug_mode = True  # 디버그 모드 활성화/비활성화 (기본값: True로 설정)
        
        # 선박 속도 안정화를 위한 변수들
        self.previous_os_speed = 12.0
        self.previous_ts_speed_TS1 = 10.0
        self.previous_ts_speed_TS2 = 10.0
        self.previous_ts_speed_TS3 = 10.0
        self.previous_ts_speed_TS4 = 10.0
        
        # 전자해도 관련 변수
        if ELECTRONIC_CHART_AVAILABLE:
            print("✅ Electronic chart canvas available")
        else:
            print("⚠️ Electronic chart canvas not available")
        
        # 초기 샘플 데이터 설정
        self.setup_sample_ships()
        
        # 초기 UI 상태 설정
        self.update_control_mode_ui()
        
        # 캔버스의 디버그 모드 동기화
        self.sim_canvas.set_debug_mode(self.debug_mode)

    def setup_left_panel(self):
        """왼쪽 컨트롤 패널을 설정합니다."""
        self.left_panel = QWidget()
        self.left_panel.setFixedWidth(600)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(15)

        # 첫 번째 행 (3개 위젯)
        first_row_layout = QHBoxLayout()
        
        # AIS 데이터 임포트 섹션
        self.setup_ais_import_section(first_row_layout)
        
        # 자선 제어 섹션
        self.setup_os_control_section(first_row_layout)
        
        # 기상 환경 설정 섹션
        self.setup_weather_section(first_row_layout)
        
        left_layout.addLayout(first_row_layout)
        
        # 두 번째 행 (3개 위젯)
        second_row_layout = QHBoxLayout()
        
        # 시나리오 종료 설정 섹션
        self.setup_scenario_end_section(second_row_layout)
        
        # 시나리오 진행속도 조정 섹션
        self.setup_speed_control_section(second_row_layout)
        
        # 시뮬레이션 컨트롤 섹션
        self.setup_simulation_control_section(second_row_layout)
        
        left_layout.addLayout(second_row_layout)
        
        # 세 번째 행 (1개 위젯 - 넓게 배치)
        third_row_layout = QHBoxLayout()
        
        # 정보 표시 섹션
        self.setup_info_section(third_row_layout)
        
        left_layout.addLayout(third_row_layout)
        
        # 네 번째 행 (국립해양조사원 전자해도 오픈API 제어)
        fourth_row_layout = QHBoxLayout()
        
        # 국립해양조사원 전자해도 오픈API 제어 섹션
        self.setup_real_chart_section(fourth_row_layout)
        
        left_layout.addLayout(fourth_row_layout)

    def setup_ais_import_section(self, parent_layout):
        """AIS 데이터 임포트 섹션을 설정합니다."""
        import_group = QGroupBox("📁 AIS Data Import")
        import_group.setFixedWidth(175)
        import_layout = QVBoxLayout(import_group)
        
        # OS 파일 선택
        os_label = QLabel("Own Ship (OS):")
        os_label.setStyleSheet("font-weight: bold; color: #007bff; font-size: 12px;")
        import_layout.addWidget(os_label)
        
        self.os_import_button = QPushButton("📂 Load OS")
        self.os_import_button.clicked.connect(lambda: self.import_ship_file("OS"))
        import_layout.addWidget(self.os_import_button)
        
        self.os_file_label = QLabel("Selected: None")
        self.os_file_label.setStyleSheet("color: #6c757d; font-size: 10px;")
        import_layout.addWidget(self.os_file_label)
        
        # TS 파일 선택들
        self.ts_import_buttons = []
        self.ts_file_labels = []
        
        for i in range(1, 5):  # TS1 ~ TS4
            ts_label = QLabel(f"Target Ship {i} (TS{i}):")
            ts_label.setStyleSheet("font-weight: bold; color: #28a745; font-size: 12px;")
            import_layout.addWidget(ts_label)
            
            ts_button = QPushButton(f"📂 Load TS{i}")
            ts_button.clicked.connect(lambda checked, ship_id=f"TS{i}": self.import_ship_file(ship_id))
            import_layout.addWidget(ts_button)
            self.ts_import_buttons.append(ts_button)
            
            ts_file_label = QLabel("Selected: None")
            ts_file_label.setStyleSheet("color: #6c757d; font-size: 10px;")
            import_layout.addWidget(ts_file_label)
            self.ts_file_labels.append(ts_file_label)
        
        # 전체 데이터 정보 표시
        self.data_info_label = QLabel("Data Info: None")
        self.data_info_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        self.data_info_label.setWordWrap(True)
        import_layout.addWidget(self.data_info_label)
        
        parent_layout.addWidget(import_group)

    def setup_speed_control_section(self, parent_layout):
        """시나리오 진행속도 조정 섹션을 설정합니다."""
        speed_group = QGroupBox("⏱️ Scenario Speed Control")
        speed_group.setFixedWidth(175)
        speed_layout = QVBoxLayout(speed_group)
        
        # 속도 슬라이더
        speed_label = QLabel("Time Speed Multiplier:")
        speed_layout.addWidget(speed_label)
        
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setMinimum(1)
        self.speed_slider.setMaximum(100)
        self.speed_slider.setValue(10)
        self.speed_slider.setTickPosition(QSlider.TicksBelow)
        self.speed_slider.setTickInterval(10)
        speed_layout.addWidget(self.speed_slider)
        
        # 속도 값 표시
        self.speed_value_label = QLabel("10x")
        self.speed_value_label.setStyleSheet("color: #007bff; font-weight: bold; font-size: 14px;")
        self.speed_value_label.setAlignment(Qt.AlignCenter)
        speed_layout.addWidget(self.speed_value_label)
        
        # 슬라이더 값 변경 연결
        self.speed_slider.valueChanged.connect(self.update_speed_display)
        
        parent_layout.addWidget(speed_group)

    def setup_simulation_control_section(self, parent_layout):
        """시뮬레이션 컨트롤 섹션을 설정합니다."""
        control_group = QGroupBox("🎮 Simulation Control")
        control_group.setFixedWidth(175)
        control_layout = QVBoxLayout(control_group)
        
        # 컨트롤 버튼들
        button_layout = QHBoxLayout()
        
        self.play_button = QPushButton("▶")
        self.play_button.clicked.connect(self.start_simulation)
        button_layout.addWidget(self.play_button)
        
        self.pause_button = QPushButton("||")
        self.pause_button.clicked.connect(self.pause_simulation)
        self.pause_button.setEnabled(False)
        button_layout.addWidget(self.pause_button)
        
        self.stop_button = QPushButton("■")
        self.stop_button.clicked.connect(self.stop_simulation)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        
        control_layout.addLayout(button_layout)
        
        # 진행률 표시
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        control_layout.addWidget(self.progress_bar)
        
        # 지형지물 중심 화면 모드 선택 (하단에 작은 버튼으로)
        terrain_separator = QLabel("─" * 20)
        terrain_separator.setStyleSheet("color: #6c757d; font-size: 10px;")
        terrain_separator.setAlignment(Qt.AlignCenter)
        control_layout.addWidget(terrain_separator)
        
        # 지형지물 중심 화면 모드 라벨
        terrain_label = QLabel("Terrain Mode:")
        terrain_label.setStyleSheet("color: #495057; font-size: 9px; font-weight: bold;")
        terrain_label.setAlignment(Qt.AlignCenter)
        control_layout.addWidget(terrain_label)
        
        # 지형지물 중심 화면 모드 버튼들
        terrain_mode_layout = QHBoxLayout()
        
        self.terrain_centered_button = QPushButton("TER")
        self.terrain_centered_button.setCheckable(True)
        self.terrain_centered_button.setChecked(True)  # 기본값
        self.terrain_centered_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 3px 6px;
                border-radius: 3px;
                font-size: 8px;
                min-width: 35px;
            }
            QPushButton:checked {
                background-color: #28a745;
                border: 2px solid #ffffff;
            }
            QPushButton:!checked {
                background-color: #6c757d;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        self.terrain_centered_button.clicked.connect(lambda: self.set_terrain_mode(True))
        terrain_mode_layout.addWidget(self.terrain_centered_button)
        
        self.ship_centered_button = QPushButton("SHIP")
        self.ship_centered_button.setCheckable(True)
        self.ship_centered_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                padding: 3px 6px;
                border-radius: 3px;
                font-size: 8px;
                min-width: 40px;
            }
            QPushButton:checked {
                background-color: #007bff;
                border: 2px solid #ffffff;
            }
            QPushButton:!checked {
                background-color: #6c757d;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        self.ship_centered_button.clicked.connect(lambda: self.set_terrain_mode(False))
        terrain_mode_layout.addWidget(self.ship_centered_button)
        
        control_layout.addLayout(terrain_mode_layout)
        
        # 지형지물 중심 화면 모드 상태 표시
        self.terrain_mode_label = QLabel("Mode: TER")
        self.terrain_mode_label.setStyleSheet("color: #28a745; font-weight: bold; font-size: 8px;")
        self.terrain_mode_label.setAlignment(Qt.AlignCenter)
        control_layout.addWidget(self.terrain_mode_label)
        
        # 디버그 모드 토글 버튼
        debug_separator = QLabel("─" * 20)
        debug_separator.setStyleSheet("color: #6c757d; font-size: 10px;")
        debug_separator.setAlignment(Qt.AlignCenter)
        control_layout.addWidget(debug_separator)
        
        self.debug_button = QPushButton("🐛 Debug Mode")
        self.debug_button.setCheckable(True)
        self.debug_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                padding: 3px 6px;
                border-radius: 3px;
                font-size: 8px;
                min-width: 70px;
            }
            QPushButton:checked {
                background-color: #dc3545;
                border: 2px solid #ffffff;
            }
            QPushButton:!checked {
                background-color: #6c757d;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        self.debug_button.clicked.connect(self.toggle_debug_mode)
        control_layout.addWidget(self.debug_button)
        
        parent_layout.addWidget(control_group)

    def setup_info_section(self, parent_layout):
        """정보 표시 섹션을 설정합니다."""
        info_group = QGroupBox("ℹ️ Simulation Info")
        info_group.setFixedWidth(575)
        info_layout = QVBoxLayout(info_group)
        
        self.time_info_label = QLabel("Current Time: --")
        self.time_info_label.setStyleSheet("color: #495057; font-size: 12px;")
        info_layout.addWidget(self.time_info_label)
        
        self.ship_count_label = QLabel("Ship Count: 0")
        self.ship_count_label.setStyleSheet("color: #495057; font-size: 12px;")
        info_layout.addWidget(self.ship_count_label)
        
        # 자동 해도 설정 상태 표시
        self.chart_status_label = QLabel("Chart Status: Not configured")
        self.chart_status_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        info_layout.addWidget(self.chart_status_label)
        
        # 해도 중심 좌표 표시
        self.chart_center_label = QLabel("Chart Center: --")
        self.chart_center_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        info_layout.addWidget(self.chart_center_label)
        
        # 해도 반지름 표시
        self.chart_radius_label = QLabel("Chart Radius: --")
        self.chart_radius_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        info_layout.addWidget(self.chart_radius_label)
        
        parent_layout.addWidget(info_group)

    def setup_real_chart_section(self, parent_layout):
        """국립해양조사원 전자해도 오픈API 제어 섹션을 설정합니다."""
        real_chart_group = QGroupBox("🗺️ National Oceanographic Research Institute Electronic Chart OpenAPI")
        real_chart_group.setFixedWidth(575)
        real_chart_layout = QVBoxLayout(real_chart_group)
        
        # 실제 해도 데이터 토글 버튼
        self.real_chart_toggle = QPushButton("Use National Oceanographic Research Institute API Data")
        self.real_chart_toggle.setCheckable(True)
        self.real_chart_toggle.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:checked {
                background-color: #138496;
                border: 2px solid #ffffff;
            }
            QPushButton:!checked {
                background-color: #6c757d;
            }
            QPushButton:hover {
                background-color: #117a8b;
            }
        """)
        self.real_chart_toggle.clicked.connect(self.toggle_real_chart_data)
        real_chart_layout.addWidget(self.real_chart_toggle)
        
        # API 상태 표시
        self.api_status_label = QLabel("API Status: Not connected")
        self.api_status_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        real_chart_layout.addWidget(self.api_status_label)
        
        # 데이터 로드 상태 표시
        self.data_load_status_label = QLabel("Data Load: Virtual chart data")
        self.data_load_status_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        real_chart_layout.addWidget(self.data_load_status_label)
        
        # 캐시 정보 버튼
        self.cache_info_btn = QPushButton("Cache Info")
        self.cache_info_btn.setStyleSheet("""
            QPushButton {
                background-color: #6f42c1;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5a32a3;
            }
        """)
        self.cache_info_btn.clicked.connect(self.show_cache_info)
        real_chart_layout.addWidget(self.cache_info_btn)
        
        parent_layout.addWidget(real_chart_group)

    def setup_os_control_section(self, parent_layout):
        """자선 제어 섹션을 설정합니다."""
        os_group = QGroupBox("🚢 Own Ship Control")
        os_group.setFixedWidth(175)
        os_layout = QVBoxLayout(os_group)
        
        # 자선 침로 제어
        heading_label = QLabel("OS Heading Control:")
        heading_label.setStyleSheet("font-weight: bold; color: #007bff; font-size: 12px;")
        os_layout.addWidget(heading_label)
        
        self.os_heading_wheel = WheelSteeringWidget("OS Heading [deg.]", 0, 360, 0)
        self.os_heading_wheel.dial.valueChanged.connect(self.on_os_parameter_changed)
        os_layout.addWidget(self.os_heading_wheel)
        
        # 자선 속도 제어
        speed_label = QLabel("OS Speed Control:")
        speed_label.setStyleSheet("font-weight: bold; color: #007bff; font-size: 12px;")
        os_layout.addWidget(speed_label)
        
        self.os_speed_wheel = WheelSteeringWidget("OS Speed [kts]", 0, 30, 12)
        self.os_speed_wheel.dial.valueChanged.connect(self.on_os_parameter_changed)
        os_layout.addWidget(self.os_speed_wheel)
        
        # OS 컨트롤 모드 선택 (하단에 작은 버튼으로)
        mode_separator = QLabel("─" * 20)
        mode_separator.setStyleSheet("color: #6c757d; font-size: 10px;")
        mode_separator.setAlignment(Qt.AlignCenter)
        os_layout.addWidget(mode_separator)
        
        # 모드 선택 버튼들
        mode_layout = QHBoxLayout()
        
        self.ais_auto_button = QPushButton("AIS")
        self.ais_auto_button.setCheckable(True)
        self.ais_auto_button.setChecked(True)  # 기본값
        self.ais_auto_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 9px;
                min-width: 40px;
            }
            QPushButton:checked {
                background-color: #28a745;
                border: 2px solid #ffffff;
            }
            QPushButton:!checked {
                background-color: #6c757d;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        self.ais_auto_button.clicked.connect(lambda: self.set_control_mode(False))
        mode_layout.addWidget(self.ais_auto_button)
        
        self.manual_control_button = QPushButton("MAN")
        self.manual_control_button.setCheckable(True)
        self.manual_control_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 9px;
                min-width: 40px;
            }
            QPushButton:checked {
                background-color: #dc3545;
                border: 2px solid #ffffff;
            }
            QPushButton:!checked {
                background-color: #6c757d;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        self.manual_control_button.clicked.connect(lambda: self.set_control_mode(True))
        mode_layout.addWidget(self.manual_control_button)
        
        os_layout.addLayout(mode_layout)
        
        # 모드 상태 표시 (작은 라벨)
        self.control_mode_label = QLabel("Mode: AIS")
        self.control_mode_label.setStyleSheet("color: #28a745; font-weight: bold; font-size: 9px;")
        self.control_mode_label.setAlignment(Qt.AlignCenter)
        os_layout.addWidget(self.control_mode_label)
        
        parent_layout.addWidget(os_group)

    def setup_scenario_end_section(self, parent_layout):
        """시나리오 종료 설정 섹션을 설정합니다."""
        end_group = QGroupBox("⏰ Scenario End Settings")
        end_group.setFixedWidth(175)
        end_layout = QVBoxLayout(end_group)
        
        # 종료 시간 설정
        end_time_label = QLabel("Scenario End Time (seconds):")
        end_time_label.setStyleSheet("font-weight: bold; color: #495057; font-size: 11px;")
        end_layout.addWidget(end_time_label)
        
        self.end_time_slider = QSlider(Qt.Horizontal)
        self.end_time_slider.setMinimum(60)  # 1분
        self.end_time_slider.setMaximum(1800)  # 30분
        self.end_time_slider.setValue(300)  # 5분
        self.end_time_slider.setTickPosition(QSlider.TicksBelow)
        self.end_time_slider.setTickInterval(60)
        end_layout.addWidget(self.end_time_slider)
        
        # 종료 시간 표시
        self.end_time_label = QLabel("5:00")
        self.end_time_label.setStyleSheet("color: #007bff; font-weight: bold; font-size: 14px;")
        self.end_time_label.setAlignment(Qt.AlignCenter)
        end_layout.addWidget(self.end_time_label)
        
        # 슬라이더 값 변경 연결
        self.end_time_slider.valueChanged.connect(self.update_end_time_display)
        
        parent_layout.addWidget(end_group)

    def setup_weather_section(self, parent_layout):
        """기상 환경 설정 섹션을 설정합니다."""
        weather_group = QGroupBox("🌤️ Weather Conditions")
        weather_group.setFixedWidth(175)
        weather_layout = QVBoxLayout(weather_group)
        
        # 풍속 설정
        wind_speed_layout = QHBoxLayout()
        wind_speed_label = QLabel("Wind Speed:")
        wind_speed_label.setStyleSheet("font-weight: bold; color: #495057; font-size: 11px;")
        wind_speed_layout.addWidget(wind_speed_label)
        
        self.wind_speed_spinbox = QSpinBox()
        self.wind_speed_spinbox.setRange(0, 50)
        self.wind_speed_spinbox.setValue(10)
        self.wind_speed_spinbox.setStyleSheet("""
            QSpinBox {
                border: 2px solid #dee2e6;
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
            }
        """)
        wind_speed_layout.addWidget(self.wind_speed_spinbox)
        
        wind_unit_label = QLabel("m/s")
        wind_unit_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        wind_speed_layout.addWidget(wind_unit_label)
        weather_layout.addLayout(wind_speed_layout)
        
        # 스트림 방향 설정
        stream_direction_layout = QHBoxLayout()
        stream_direction_label = QLabel("Stream Direction:")
        stream_direction_label.setStyleSheet("font-weight: bold; color: #495057; font-size: 11px;")
        stream_direction_layout.addWidget(stream_direction_label)
        
        self.stream_direction_combo = QComboBox()
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", 
                     "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        self.stream_direction_combo.addItems(directions)
        self.stream_direction_combo.setCurrentText("E")
        self.stream_direction_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #dee2e6;
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
            }
        """)
        stream_direction_layout.addWidget(self.stream_direction_combo)
        weather_layout.addLayout(stream_direction_layout)
        
        # 스트림 유속 설정
        stream_speed_layout = QHBoxLayout()
        stream_speed_label = QLabel("Stream Speed:")
        stream_speed_label.setStyleSheet("font-weight: bold; color: #495057; font-size: 11px;")
        stream_speed_layout.addWidget(stream_speed_label)
        
        self.stream_speed_spinbox = QSpinBox()
        self.stream_speed_spinbox.setRange(0, 10)
        self.stream_speed_spinbox.setValue(2)
        self.stream_speed_spinbox.setStyleSheet("""
            QSpinBox {
                border: 2px solid #dee2e6;
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
            }
        """)
        stream_speed_layout.addWidget(self.stream_speed_spinbox)
        
        stream_unit_label = QLabel("kn")
        stream_unit_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        stream_speed_layout.addWidget(stream_unit_label)
        weather_layout.addLayout(stream_speed_layout)
        
        # 파고 설정
        wave_height_layout = QHBoxLayout()
        wave_height_label = QLabel("Wave Height:")
        wave_height_label.setStyleSheet("font-weight: bold; color: #495057; font-size: 11px;")
        wave_height_layout.addWidget(wave_height_label)
        
        self.wave_height_spinbox = QDoubleSpinBox()
        self.wave_height_spinbox.setRange(0, 20)
        self.wave_height_spinbox.setValue(2.0)
        self.wave_height_spinbox.setDecimals(1)
        self.wave_height_spinbox.setSingleStep(0.5)
        self.wave_height_spinbox.setStyleSheet("""
            QDoubleSpinBox {
                border: 2px solid #dee2e6;
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
            }
        """)
        wave_height_layout.addWidget(self.wave_height_spinbox)
        
        wave_unit_label = QLabel("m")
        wave_unit_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        wave_height_layout.addWidget(wave_unit_label)
        weather_layout.addLayout(wave_height_layout)
        
        # 시정 설정
        visibility_layout = QHBoxLayout()
        visibility_label = QLabel("Visibility:")
        visibility_label.setStyleSheet("font-weight: bold; color: #495057; font-size: 11px;")
        visibility_layout.addWidget(visibility_label)
        
        self.visibility_spinbox = QSpinBox()
        self.visibility_spinbox.setRange(0, 50)
        self.visibility_spinbox.setValue(10)
        self.visibility_spinbox.setStyleSheet("""
            QSpinBox {
                border: 2px solid #dee2e6;
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
            }
        """)
        visibility_layout.addWidget(self.visibility_spinbox)
        
        visibility_unit_label = QLabel("nm")
        visibility_unit_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        visibility_layout.addWidget(visibility_unit_label)
        weather_layout.addLayout(visibility_layout)
        
        # 기상 효과 강도 조절
        effect_intensity_layout = QHBoxLayout()
        effect_intensity_label = QLabel("Effect Intensity:")
        effect_intensity_label.setStyleSheet("font-weight: bold; color: #495057; font-size: 11px;")
        effect_intensity_layout.addWidget(effect_intensity_label)
        
        self.effect_intensity_slider = QSlider(Qt.Horizontal)
        self.effect_intensity_slider.setRange(1, 10)
        self.effect_intensity_slider.setValue(5)
        self.effect_intensity_slider.setTickPosition(QSlider.TicksBelow)
        self.effect_intensity_slider.setTickInterval(1)
        self.effect_intensity_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #dee2e6;
                height: 6px;
                background: #f8f9fa;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #007bff;
                border: 1px solid #0056b3;
                width: 16px;
                height: 16px;
                border-radius: 8px;
                margin: -5px 0;
            }
        """)
        effect_intensity_layout.addWidget(self.effect_intensity_slider)
        
        self.effect_intensity_label = QLabel("5x")
        self.effect_intensity_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        effect_intensity_layout.addWidget(self.effect_intensity_label)
        
        # 슬라이더 값 변경 연결
        self.effect_intensity_slider.valueChanged.connect(self.update_effect_intensity)
        
        weather_layout.addLayout(effect_intensity_layout)
        
        # 기상 정보 표시
        self.weather_info_label = QLabel("Weather: Wind 10 m/s, Stream E 2 kn, Wave 2.0 m, Visibility 10 nm")
        self.weather_info_label.setStyleSheet("color: #6c757d; font-size: 10px;")
        self.weather_info_label.setWordWrap(True)
        weather_layout.addWidget(self.weather_info_label)
        
        # 기상 파라미터 변경 연결
        self.wind_speed_spinbox.valueChanged.connect(self.update_weather_info)
        self.stream_direction_combo.currentTextChanged.connect(self.update_weather_info)
        self.stream_speed_spinbox.valueChanged.connect(self.update_weather_info)
        self.wave_height_spinbox.valueChanged.connect(self.update_weather_info)
        self.visibility_spinbox.valueChanged.connect(self.update_weather_info)
        
        # 기상 효과 실시간 적용을 위한 타이머
        self.weather_timer = QTimer()
        self.weather_timer.timeout.connect(self.apply_weather_effects_realtime)
        self.weather_timer.start(1000)  # 1초마다 기상 효과 적용
        
        parent_layout.addWidget(weather_group)

    def update_weather_info(self):
        """기상 정보를 업데이트합니다."""
        # 기상 데이터 업데이트
        self.weather_data['wind_speed'] = self.wind_speed_spinbox.value()
        self.weather_data['stream_direction'] = self.stream_direction_combo.currentText()
        self.weather_data['stream_speed'] = self.stream_speed_spinbox.value()
        self.weather_data['wave_height'] = self.wave_height_spinbox.value()
        self.weather_data['visibility'] = self.visibility_spinbox.value()
        
        # 기상 정보 라벨 업데이트
        weather_text = f"Weather: Wind {self.weather_data['wind_speed']} m/s, Stream {self.weather_data['stream_direction']} {self.weather_data['stream_speed']} kn, Wave {self.weather_data['wave_height']} m, Visibility {self.weather_data['visibility']} nm"
        self.weather_info_label.setText(weather_text)
        
        # 자선 행동 히스토리에 기상 변경 기록
        self.add_progress_entry(f"Weather conditions updated: {weather_text}")
        
        # 시나리오 진행 상황에도 기상 변경 기록
        self.add_progress_entry(f"🌤️ Weather settings changed: Wind {self.weather_data['wind_speed']} m/s, Stream {self.weather_data['stream_direction']} {self.weather_data['stream_speed']} kn, Wave {self.weather_data['wave_height']} m, Visibility {self.weather_data['visibility']} nm")
        
        # 시뮬레이션에 기상 영향 적용
        self.apply_weather_effects()
    
    def update_effect_intensity(self):
        """기상 효과 강도를 업데이트합니다."""
        intensity = self.effect_intensity_slider.value()
        self.effect_intensity_label.setText(f"{intensity}x")
        
        # 기상 효과 강도 변경을 행동 히스토리에 기록
        self.add_progress_entry(f"🌊 Weather effect intensity changed to {intensity}x")
        
        # 캔버스 업데이트
        if hasattr(self, 'sim_canvas'):
            self.sim_canvas.update()
    
    def apply_weather_effects(self):
        """기상 효과를 시뮬레이션에 적용합니다."""
        # 풍속에 따른 선박 속도 영향
        wind_effect = self.weather_data['wind_speed'] * 0.1  # 풍속의 10% 영향
        
        # 스트림에 따른 위치 변화
        stream_effect = self.weather_data['stream_speed'] * 0.05  # 스트림의 5% 영향
        
        # 파고에 따른 안정성 영향
        wave_effect = self.weather_data['wave_height'] * 0.02  # 파고의 2% 영향
        
        # 시정에 따른 탐지 거리 영향
        visibility_effect = min(self.weather_data['visibility'], 20) / 20  # 시정의 영향
        
        # 기상 효과를 행동 추적에 기록
        self.add_progress_entry(f"Weather effects applied - Wind: {wind_effect:.2f}, Stream: {stream_effect:.2f}, Wave: {wave_effect:.2f}, Visibility: {visibility_effect:.2f}")
    
    def apply_weather_effects_realtime(self):
        """실시간으로 기상 효과를 적용합니다."""
        if not hasattr(self, 'sim_canvas') or not self.sim_canvas.ships:
            return
        
        # 현재 선박 상태에 기상 효과 적용
        if hasattr(self.sim_canvas, 'ownship') and self.sim_canvas.ownship:
            # 자선에 기상 효과 적용
            self.apply_weather_to_ships(self.sim_canvas.ownship, self.sim_canvas.ships)
            
            # 캔버스 업데이트
            self.sim_canvas.update()
    
    def apply_weather_to_ships(self, ownship, ships):
        """기상 효과를 선박에 적용합니다."""
        # 기상 데이터 가져오기
        wind_speed = self.weather_data['wind_speed']
        stream_direction = self.weather_data['stream_direction']
        stream_speed = self.weather_data['stream_speed']
        wave_height = self.weather_data['wave_height']
        visibility = self.weather_data['visibility']
        
        # 기상 효과 강도 가져오기
        effect_intensity = getattr(self, 'effect_intensity_slider', None)
        intensity_multiplier = effect_intensity.value() / 5.0 if effect_intensity else 1.0
        
        # 1. 풍속 효과 (Wind Effect)
        # 역풍/순풍에 따른 속도 변화
        wind_heading = self.calculate_wind_heading(ownship['heading'])
        wind_angle_diff = abs(ownship['heading'] - wind_heading)
        if wind_angle_diff > 180:
            wind_angle_diff = 360 - wind_angle_diff
        
        # 풍향과 선박 진행방향의 각도에 따른 효과
        if wind_angle_diff < 45:  # 순풍
            wind_speed_effect = wind_speed * 0.05 * intensity_multiplier  # 속도 증가
        elif wind_angle_diff > 135:  # 역풍
            wind_speed_effect = -wind_speed * 0.08 * intensity_multiplier  # 속도 감소
        else:  # 횡풍
            wind_speed_effect = -wind_speed * 0.03 * intensity_multiplier  # 약간의 속도 감소
        
        # 2. 조류 효과 (Stream Effect)
        stream_direction_angle = self.get_direction_angle(stream_direction)
        stream_effect_x = math.cos(math.radians(stream_direction_angle)) * stream_speed * 0.1 * intensity_multiplier
        stream_effect_y = math.sin(math.radians(stream_direction_angle)) * stream_speed * 0.1 * intensity_multiplier
        
        # 3. 파고 효과 (Wave Effect)
        # 파고에 따른 속도 감소 (비선형 관계)
        wave_resistance = (wave_height ** 1.5) * 0.15 * intensity_multiplier  # 파고의 1.5승에 비례
        wave_speed_effect = -ownship['speed'] * wave_resistance
        
        # 4. 시정 효과 (Visibility Effect)
        # 시정에 따른 안전 속도 조정
        visibility_factor = min(visibility, 20) / 20
        safety_speed_reduction = (1 - visibility_factor) * 0.3 * intensity_multiplier  # 시정이 낮을수록 속도 감소
        
        # 모든 기상 효과를 종합하여 선박 운동에 적용
        # 속도 변화
        total_speed_change = wind_speed_effect + wave_speed_effect
        ownship['speed'] = max(0.5, ownship['speed'] + total_speed_change)  # 최소 0.5 knots
        
        # 위치 변화 (조류 효과)
        ownship['x'] += stream_effect_x
        ownship['y'] += stream_effect_y
        
        # 안전 속도 조정 (시정 효과)
        ownship['speed'] *= (1 - safety_speed_reduction)
        
        # 기상 효과를 행동 히스토리에 기록
        weather_summary = f"🌊 Weather Effects Applied:"
        weather_summary += f" Wind: {wind_speed_effect:+.1f} kts,"
        weather_summary += f" Stream: ({stream_effect_x:+.1f}, {stream_effect_y:+.1f}),"
        weather_summary += f" Wave: {wave_speed_effect:+.1f} kts,"
        weather_summary += f" Visibility: {safety_speed_reduction:.1%}"
        
        self.add_progress_entry(weather_summary)
        self.add_progress_entry(f"Final OS Speed: {ownship['speed']:.1f} kts, Position: ({ownship['x']:.1f}, {ownship['y']:.1f})")
        
        # 타겟 선박에도 기상 효과 적용
        for ship in ships:
            self.apply_weather_to_target_ship(ship)
    
    def apply_weather_to_target_ship(self, ship):
        """타겟 선박에 기상 효과를 적용합니다."""
        wind_speed = self.weather_data['wind_speed']
        stream_direction = self.weather_data['stream_direction']
        stream_speed = self.weather_data['stream_speed']
        wave_height = self.weather_data['wave_height']
        
        # 기상 효과 강도 가져오기
        effect_intensity = getattr(self, 'effect_intensity_slider', None)
        intensity_multiplier = effect_intensity.value() / 5.0 if effect_intensity else 1.0
        
        # 풍속 효과
        wind_heading = self.calculate_wind_heading(ship['heading'])
        wind_angle_diff = abs(ship['heading'] - wind_heading)
        if wind_angle_diff > 180:
            wind_angle_diff = 360 - wind_angle_diff
        
        if wind_angle_diff < 45:  # 순풍
            wind_speed_effect = wind_speed * 0.04 * intensity_multiplier
        elif wind_angle_diff > 135:  # 역풍
            wind_speed_effect = -wind_speed * 0.06 * intensity_multiplier
        else:  # 횡풍
            wind_speed_effect = -wind_speed * 0.02 * intensity_multiplier
        
        # 조류 효과
        stream_direction_angle = self.get_direction_angle(stream_direction)
        stream_effect_x = math.cos(math.radians(stream_direction_angle)) * stream_speed * 0.08 * intensity_multiplier
        stream_effect_y = math.sin(math.radians(stream_direction_angle)) * stream_speed * 0.08 * intensity_multiplier
        
        # 파고 효과
        wave_resistance = (wave_height ** 1.5) * 0.12 * intensity_multiplier
        wave_speed_effect = -ship['speed'] * wave_resistance
        
        # 효과 적용
        ship['speed'] = max(0.5, ship['speed'] + wind_speed_effect + wave_speed_effect)
        ship['x'] += stream_effect_x
        ship['y'] += stream_effect_y
    
    def calculate_wind_heading(self, ship_heading):
        """선박의 진행방향을 고려한 풍향을 계산합니다."""
        # 기본 풍향 (북쪽에서 시계방향)
        base_wind_direction = 0  # 북풍을 기본값으로
        
        # 선박의 진행방향에 따른 상대 풍향 계산
        # 실제 해상에서는 풍향이 선박의 진행방향에 따라 상대적으로 변화
        relative_wind = (base_wind_direction - ship_heading) % 360
        
        # 상대 풍향을 절대 풍향으로 변환
        absolute_wind = (ship_heading + relative_wind) % 360
        
        return absolute_wind
    
    def draw_weather_effects(self, qp, center_x, center_y, scale):
        """기상 효과를 시각적으로 표시합니다."""
        if not hasattr(self, 'weather_data'):
            return
        
        # 기상 데이터 가져오기
        wind_speed = self.weather_data['wind_speed']
        stream_direction = self.weather_data['stream_direction']
        stream_speed = self.weather_data['stream_speed']
        wave_height = self.weather_data['wave_height']
        visibility = self.weather_data['visibility']
        
        # 1. 풍향/풍속 표시 (화면 우상단)
        self.draw_wind_indicator(qp, center_x, center_y, wind_speed)
        
        # 2. 조류 방향 표시 (화면 좌하단)
        self.draw_stream_indicator(qp, center_x, center_y, stream_direction, stream_speed)
        
        # 3. 파도 효과 표시 (화면 전체에 미세한 움직임)
        self.draw_wave_effects(qp, center_x, center_y, wave_height)
        
        # 4. 시정 효과 표시 (화면 가장자리)
        self.draw_visibility_effects(qp, center_x, center_y, visibility)
    
    def draw_wind_indicator(self, qp, center_x, center_y, wind_speed):
        """풍향/풍속 표시기를 그립니다."""
        # 화면 우상단에 풍향 표시
        wind_x = center_x + 200
        wind_y = center_y - 200
        
        # 풍향 화살표
        qp.setPen(QPen(QColor(255, 255, 0), 2))  # 노란색
        qp.setFont(QFont("Arial", 10, QFont.Bold))
        
        # 풍속에 따른 화살표 길이
        arrow_length = min(30, max(10, wind_speed * 2))
        
        # 북풍 방향으로 화살표 그리기
        qp.drawLine(wind_x, wind_y, wind_x, wind_y - arrow_length)
        
        # 화살촉
        head_size = 5
        qp.drawLine(wind_x, wind_y - arrow_length, wind_x - head_size, wind_y - arrow_length + head_size)
        qp.drawLine(wind_x, wind_y - arrow_length, wind_x + head_size, wind_y - arrow_length + head_size)
        
        # 풍속 텍스트
        qp.drawText(QPointF(wind_x + 10, wind_y), f"Wind: {wind_speed} m/s")
    
    def draw_stream_indicator(self, qp, center_x, center_y, stream_direction, stream_speed):
        """조류 방향 표시기를 그립니다."""
        # 화면 좌하단에 조류 표시
        stream_x = center_x - 200
        stream_y = center_y + 200
        
        # 조류 방향 각도 계산
        stream_angle = self.get_direction_angle(stream_direction)
        
        # 조류 방향 화살표
        qp.setPen(QPen(QColor(0, 255, 255), 2))  # 시안색
        
        # 조류 속도에 따른 화살표 길이
        arrow_length = min(25, max(8, stream_speed * 3))
        
        # 조류 방향으로 화살표 그리기
        end_x = stream_x + arrow_length * math.sin(math.radians(stream_angle))
        end_y = stream_y - arrow_length * math.cos(math.radians(stream_angle))
        
        qp.drawLine(stream_x, stream_y, end_x, end_y)
        
        # 화살촉
        head_size = 4
        arrow_rad = math.radians(stream_angle)
        for angle in [math.pi / 6, -math.pi / 6]:
            hx = end_x - head_size * math.sin(arrow_rad + angle)
            hy = end_y + head_size * math.cos(arrow_rad + angle)
            qp.drawLine(QPointF(end_x, end_y), QPointF(hx, hy))
        
        # 조류 정보 텍스트
        qp.setFont(QFont("Arial", 9))
        qp.drawText(QPointF(stream_x - 30, stream_y + 20), f"Stream: {stream_direction} {stream_speed} kn")
    
    def draw_wave_effects(self, qp, center_x, center_y, wave_height):
        """파도 효과를 표시합니다."""
        if wave_height < 0.5:  # 파도가 작으면 표시하지 않음
            return
        
        # 파도 높이에 따른 미세한 움직임 효과
        qp.setPen(QPen(QColor(0, 150, 255, 50), 1))  # 반투명 파란색
        
        # 화면 전체에 파도 패턴 그리기
        for i in range(0, self.width(), 50):
            for j in range(0, self.height(), 50):
                # 파도 높이에 따른 진폭
                amplitude = wave_height * 2
                wave_x = i + math.sin(j * 0.02) * amplitude
                wave_y = j + math.cos(i * 0.02) * amplitude
                
                # 작은 원으로 파도 효과 표시
                qp.drawEllipse(QPointF(wave_x, wave_y), 1, 1)
    
    def draw_visibility_effects(self, qp, center_x, center_y, visibility):
        """시정 효과를 표시합니다."""
        if visibility >= 15:  # 시정이 좋으면 효과 없음
            return
        
        # 시정이 낮을 때 화면 가장자리에 안개 효과
        qp.setPen(QPen(QColor(200, 200, 200, 30), 1))  # 반투명 회색
        
        # 화면 가장자리에 안개 효과 그리기
        fog_thickness = (20 - visibility) * 2  # 시정이 낮을수록 안개 두꺼움
        
        # 상단 안개
        qp.fillRect(0, 0, self.width(), fog_thickness, QColor(200, 200, 200, 30))
        
        # 하단 안개
        qp.fillRect(0, self.height() - fog_thickness, self.width(), fog_thickness, QColor(200, 200, 200, 30))
        
        # 좌측 안개
        qp.fillRect(0, 0, fog_thickness, self.height(), QColor(200, 200, 200, 30))
        
        # 우측 안개
        qp.fillRect(self.width() - fog_thickness, 0, fog_thickness, self.height(), QColor(200, 200, 200, 30))
    
    def get_direction_angle(self, direction):
        """16방위법을 각도로 변환합니다."""
        direction_map = {
            "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5,
            "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
            "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
            "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5
        }
        return direction_map.get(direction, 0)
    
    def generate_geo_plot(self, center_lat, center_lon, zoom_level=10):
        """지오플롯을 생성합니다 (Folium 기반)"""
        if not GEO_PLOT_AVAILABLE:
            return None
        
        try:
            # Folium 지도 생성
            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=zoom_level,
                tiles='OpenStreetMap'
            )
            
            # 해안선 추가
            if self.coastline_data:
                coastline_coords = [[lat, lon] for lat, lon in self.coastline_data]
                folium.PolyLine(
                    locations=coastline_coords,
                    color='brown',
                    weight=3,
                    opacity=0.8,
                    popup='Coastline'
                ).add_to(m)
            
            # 지형지물 추가
            for lat, lon, landmark_type, name in self.landmarks:
                if landmark_type == 'lighthouse':
                    folium.Marker(
                        [lat, lon],
                        popup=name,
                        icon=folium.Icon(color='yellow', icon='info-sign')
                    ).add_to(m)
                elif landmark_type == 'buoy':
                    folium.Marker(
                        [lat, lon],
                        popup=name,
                        icon=folium.Icon(color='red', icon='info-sign')
                    ).add_to(m)
                elif landmark_type == 'port':
                    folium.Marker(
                        [lat, lon],
                        popup=name,
                        icon=folium.Icon(color='green', icon='info-sign')
                    ).add_to(m)
                else:
                    folium.Marker(
                        [lat, lon],
                        popup=f"{name} ({landmark_type})",
                        icon=folium.Icon(color='blue', icon='info-sign')
                    ).add_to(m)
            
            # 해양 구역 추가
            for lat, lon, radius, zone_type, name in self.marine_zones:
                if zone_type == 'port_area':
                    color = 'darkgreen'
                elif zone_type == 'anchorage_area':
                    color = 'yellow'
                elif zone_type == 'restricted_area':
                    color = 'red'
                elif zone_type == 'fishing_area':
                    color = 'orange'
                elif zone_type == 'environmental_area':
                    color = 'lightgreen'
                else:
                    color = 'gray'
                
                folium.Circle(
                    radius=radius * 1000,  # 미터 단위로 변환
                    location=[lat, lon],
                    popup=name,
                    color=color,
                    fill=True,
                    opacity=0.3
                ).add_to(m)
            
            # 등심선 추가
            for lat, lon, depth in self.depth_contours:
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=5,
                    popup=f"Depth: {depth}m",
                    color='blue',
                    fill=True,
                    opacity=0.7
                ).add_to(m)
            
            return m
            
        except Exception as e:
            print(f"Error generating geo plot: {e}")
            return None
    
    def save_geo_plot(self, filename="electronic_chart.html"):
        """지오플롯을 HTML 파일로 저장합니다"""
        if not GEO_PLOT_AVAILABLE:
            print("Geo plotting libraries not available")
            return False
        
        try:
            m = self.generate_geo_plot(self.center_lat, self.center_lon)
            if m:
                m.save(filename)
                print(f"Geo plot saved as {filename}")
                return True
            return False
        except Exception as e:
            print(f"Error saving geo plot: {e}")
            return False

    def setup_right_panel(self):
        """오른쪽 행동 추적 패널을 설정합니다."""
        self.right_panel = QWidget()
        self.right_panel.setFixedWidth(400)
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(15)

        # 자선 행동 추적 섹션
        self.setup_behavior_tracking_section(right_layout)
        
        # 궤적 추출 섹션
        self.setup_trajectory_extraction_section(right_layout)
        
        # 지오플롯 섹션
        self.setup_geo_plot_section(right_layout)

    def setup_owl_import_section(self, parent_layout):
        """OWL 파일 임포트 섹션을 설정합니다."""
        owl_group = QGroupBox("🔍 Ontology Import")
        owl_layout = QVBoxLayout(owl_group)
        
        # OWL 파일 선택 버튼
        self.owl_import_button = QPushButton("📂 Load OWL File")
        self.owl_import_button.clicked.connect(self.import_owl_file)
        owl_layout.addWidget(self.owl_import_button)
        
        # OWL 파일 정보 표시
        self.owl_file_label = QLabel("Selected: None")
        self.owl_file_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        self.owl_file_label.setWordWrap(True)
        owl_layout.addWidget(self.owl_file_label)
        
        # 온톨로지 정보 표시
        self.ontology_info_label = QLabel("Ontology Info: None")
        self.ontology_info_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        self.ontology_info_label.setWordWrap(True)
        owl_layout.addWidget(self.ontology_info_label)
        
        parent_layout.addWidget(owl_group)

    def setup_evaluation_section(self, parent_layout):
        """성능평가 항목 섹션을 설정합니다."""
        eval_group = QGroupBox("📊 Performance Evaluation Items")
        eval_layout = QVBoxLayout(eval_group)
        
        # 평가 항목 트리
        self.evaluation_tree = QTreeWidget()
        self.evaluation_tree.setHeaderLabels(["Evaluation Item", "Score"])
        self.evaluation_tree.setColumnWidth(0, 200)
        self.evaluation_tree.setColumnWidth(1, 80)
        self.evaluation_tree.setStyleSheet("""
            QTreeWidget {
                font-size: 11px;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                background-color: white;
            }
            QTreeWidget::item {
                padding: 4px;
                border-bottom: 1px solid #f8f9fa;
            }
            QTreeWidget::item:selected {
                background-color: #007bff;
                color: white;
            }
        """)
        eval_layout.addWidget(self.evaluation_tree)
        
        # 분석 버튼
        self.analyze_button = QPushButton("🔍 Analyze Scenario")
        self.analyze_button.clicked.connect(self.analyze_scenario_evaluation)
        self.analyze_button.setEnabled(False)
        eval_layout.addWidget(self.analyze_button)
        
        parent_layout.addWidget(eval_group)

    def setup_evaluation_results_section(self, parent_layout):
        """평가 결과 섹션을 설정합니다."""
        results_group = QGroupBox("📈 Evaluation Results")
        results_layout = QVBoxLayout(results_group)
        
        # 결과 텍스트 영역
        self.results_text = QTextEdit()
        self.results_text.setMaximumHeight(150)
        self.results_text.setStyleSheet("""
            QTextEdit {
                font-size: 11px;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                background-color: white;
                padding: 8px;
            }
        """)
        self.results_text.setPlainText("Evaluation results will appear here...")
        results_layout.addWidget(self.results_text)
        
        # 총점 표시
        self.total_score_label = QLabel("Total Score: 0.0")
        self.total_score_label.setStyleSheet("color: #28a745; font-weight: bold; font-size: 14px;")
        self.total_score_label.setAlignment(Qt.AlignCenter)
        results_layout.addWidget(self.total_score_label)
        
        parent_layout.addWidget(results_group)

    def setup_logic_tracking_section(self, parent_layout):
        """로직 추적 섹션을 설정합니다."""
        logic_group = QGroupBox("🔍 Logic Tracking & History")
        logic_layout = QVBoxLayout(logic_group)
        
        # 탭 위젯 생성
        self.logic_tab_widget = QTabWidget()
        self.logic_tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #dee2e6;
                border-radius: 6px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                padding: 8px 12px;
                margin-right: 2px;
                border-radius: 4px 4px 0 0;
                font-size: 11px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #007bff;
                color: white;
            }
        """)
        
        # 평가 항목 추출 히스토리 탭
        self.setup_evaluation_extraction_tab()
        
        # 스코어링 과정 히스토리 탭
        self.setup_scoring_process_tab()
        
        # 전체 로직 히스토리 탭
        self.setup_general_logic_tab()
        
        logic_layout.addWidget(self.logic_tab_widget)
        parent_layout.addWidget(logic_group)

    def setup_evaluation_extraction_tab(self):
        """평가 항목 추출 히스토리 탭을 설정합니다."""
        extraction_widget = QWidget()
        extraction_layout = QVBoxLayout(extraction_widget)
        
        # 제목
        title_label = QLabel("📊 Evaluation Item Extraction Process")
        title_label.setStyleSheet("font-weight: bold; color: #495057; font-size: 12px; margin-bottom: 8px;")
        extraction_layout.addWidget(title_label)
        
        # 추출 과정 텍스트 영역
        self.extraction_history_text = QTextEdit()
        self.extraction_history_text.setStyleSheet("""
            QTextEdit {
                font-size: 10px;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                background-color: #f8f9fa;
                padding: 8px;
                font-family: 'Courier New', monospace;
            }
        """)
        self.extraction_history_text.setPlainText("Evaluation item extraction process will be tracked here...")
        extraction_layout.addWidget(self.extraction_history_text)
        
        self.logic_tab_widget.addTab(extraction_widget, "Item Extraction")

    def setup_scoring_process_tab(self):
        """스코어링 과정 히스토리 탭을 설정합니다."""
        scoring_widget = QWidget()
        scoring_layout = QVBoxLayout(scoring_widget)
        
        # 제목
        title_label = QLabel("📈 Scoring Process Tracking")
        title_label.setStyleSheet("font-weight: bold; color: #495057; font-size: 12px; margin-bottom: 8px;")
        scoring_layout.addWidget(title_label)
        
        # 스코어링 과정 텍스트 영역
        self.scoring_history_text = QTextEdit()
        self.scoring_history_text.setStyleSheet("""
            QTextEdit {
                font-size: 10px;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                background-color: #f8f9fa;
                padding: 8px;
                font-family: 'Courier New', monospace;
            }
        """)
        self.scoring_history_text.setPlainText("Scoring process will be tracked here...")
        scoring_layout.addWidget(self.scoring_history_text)
        
        self.logic_tab_widget.addTab(scoring_widget, "Scoring Process")

    def setup_general_logic_tab(self):
        """전체 로직 히스토리 탭을 설정합니다."""
        general_widget = QWidget()
        general_layout = QVBoxLayout(general_widget)
        
        # 제목
        title_label = QLabel("🔍 General Logic History")
        title_label.setStyleSheet("font-weight: bold; color: #495057; font-size: 12px; margin-bottom: 8px;")
        general_layout.addWidget(title_label)
        
        # 전체 로직 히스토리 텍스트 영역
        self.general_logic_text = QTextEdit()
        self.general_logic_text.setStyleSheet("""
            QTextEdit {
                font-size: 10px;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                background-color: #f8f9fa;
                padding: 8px;
                font-family: 'Courier New', monospace;
            }
        """)
        self.general_logic_text.setPlainText("General logic history will appear here...")
        general_layout.addWidget(self.general_logic_text)
        
        self.logic_tab_widget.addTab(general_widget, "General Logic")

    def setup_behavior_tracking_section(self, parent_layout):
        """자선 행동 추적 섹션을 설정합니다."""
        behavior_group = QGroupBox("📊 OS Behavior Tracking")
        behavior_layout = QVBoxLayout(behavior_group)
        
        # 탭 위젯 생성
        self.behavior_tab_widget = QTabWidget()
        self.behavior_tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #dee2e6;
                border-radius: 6px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                padding: 8px 12px;
                margin-right: 2px;
                border-radius: 4px 4px 0 0;
                font-size: 11px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #007bff;
                color: white;
            }
        """)
        
        # 자선 행동 히스토리 탭
        self.setup_os_behavior_tab()
        
        # 시나리오 진행 상황 탭
        self.setup_scenario_progress_tab()
        
        behavior_layout.addWidget(self.behavior_tab_widget)
        parent_layout.addWidget(behavior_group)

    def setup_os_behavior_tab(self):
        """자선 행동 히스토리 탭을 설정합니다."""
        behavior_widget = QWidget()
        behavior_layout = QVBoxLayout(behavior_widget)
        
        # 제목
        title_label = QLabel("🚢 OS Behavior History")
        title_label.setStyleSheet("font-weight: bold; color: #495057; font-size: 12px; margin-bottom: 8px;")
        behavior_layout.addWidget(title_label)
        
        # 행동 히스토리 텍스트 영역
        self.os_behavior_text = QTextEdit()
        self.os_behavior_text.setStyleSheet("""
            QTextEdit {
                font-size: 10px;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                background-color: #f8f9fa;
                padding: 8px;
                font-family: 'Courier New', monospace;
            }
        """)
        self.os_behavior_text.setPlainText("OS behavior history will appear here...")
        behavior_layout.addWidget(self.os_behavior_text)
        
        # Export 버튼
        export_behavior_button = QPushButton("📋 Export OS Behavior History")
        export_behavior_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        export_behavior_button.clicked.connect(self.export_behavior_history)
        behavior_layout.addWidget(export_behavior_button)
        
        self.behavior_tab_widget.addTab(behavior_widget, "OS Behavior")

    def setup_scenario_progress_tab(self):
        """시나리오 진행 상황 탭을 설정합니다."""
        progress_widget = QWidget()
        progress_layout = QVBoxLayout(progress_widget)
        
        # 제목
        title_label = QLabel("⏱️ Scenario Progress")
        title_label.setStyleSheet("font-weight: bold; color: #495057; font-size: 12px; margin-bottom: 8px;")
        progress_layout.addWidget(title_label)
        
        # 진행 상황 텍스트 영역
        self.scenario_progress_text = QTextEdit()
        self.scenario_progress_text.setStyleSheet("""
            QTextEdit {
                font-size: 10px;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                background-color: #f8f9fa;
                padding: 8px;
                font-family: 'Courier New', monospace;
            }
        """)
        self.scenario_progress_text.setPlainText("Scenario progress will appear here...")
        progress_layout.addWidget(self.scenario_progress_text)
        
        # Export 버튼
        export_progress_button = QPushButton("📋 Export Progress History")
        export_progress_button.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        export_progress_button.clicked.connect(self.export_progress_history)
        progress_layout.addWidget(export_progress_button)
        
        self.behavior_tab_widget.addTab(progress_widget, "Progress")

    def setup_trajectory_extraction_section(self, parent_layout):
        """궤적 추출 섹션을 설정합니다."""
        trajectory_group = QGroupBox("📈 Trajectory Extraction")
        trajectory_layout = QVBoxLayout(trajectory_group)
        
        # 궤적 추출 버튼
        self.extract_trajectory_button = QPushButton("📊 Extract Trajectories")
        self.extract_trajectory_button.clicked.connect(self.extract_trajectories)
        self.extract_trajectory_button.setEnabled(False)
        trajectory_layout.addWidget(self.extract_trajectory_button)
        
        # 궤적 정보 표시
        self.trajectory_info_label = QLabel("Trajectory Info: No data available")
        self.trajectory_info_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        self.trajectory_info_label.setWordWrap(True)
        trajectory_layout.addWidget(self.trajectory_info_label)
        
        parent_layout.addWidget(trajectory_group)
    
    def setup_geo_plot_section(self, parent_layout):
        """지오플롯 섹션을 설정합니다."""
        geo_group = QGroupBox("🗺️ Geo Plotting")
        geo_group.setFixedWidth(400)
        geo_layout = QVBoxLayout(geo_group)
        
        # 지오플롯 생성 버튼
        self.generate_geo_plot_button = QPushButton("🗺️ Generate Geo Plot")
        self.generate_geo_plot_button.clicked.connect(self.generate_geo_plot_from_ui)
        geo_layout.addWidget(self.generate_geo_plot_button)
        
        # 지오플롯 저장 버튼
        self.save_geo_plot_button = QPushButton("💾 Save Geo Plot")
        self.save_geo_plot_button.clicked.connect(self.save_geo_plot_from_ui)
        geo_layout.addWidget(self.save_geo_plot_button)
        
        # 지오플롯 상태 표시
        self.geo_plot_status_label = QLabel("Status: Ready to generate")
        self.geo_plot_status_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        geo_layout.addWidget(self.geo_plot_status_label)
        
        parent_layout.addWidget(geo_group)
        self.save_geo_plot_button = QPushButton("💾 Save Geo Plot")
        self.save_geo_plot_button.clicked.connect(self.save_geo_plot_from_ui)
        geo_layout.addWidget(self.save_geo_plot_button)
        
        # 지오플롯 정보 표시
        self.geo_plot_info_label = QLabel("Geo Plot Info: Click 'Generate' to create interactive map")
        self.geo_plot_info_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        self.geo_plot_info_label.setWordWrap(True)
        geo_layout.addWidget(self.geo_plot_info_label)
        
        # 지오플롯 상태 표시
        self.geo_plot_status_label = QLabel("Status: Ready")
        self.geo_plot_status_label.setStyleSheet("color: #28a745; font-size: 10px;")
        geo_layout.addWidget(self.geo_plot_status_label)
        
        parent_layout.addWidget(geo_group)

    def update_speed_display(self):
        """속도 표시를 업데이트합니다."""
        speed_value = self.speed_slider.value()
        self.speed_value_label.setText(f"{speed_value}x")
        
        # 시뮬레이션 타이머 간격 조정
        if self.is_simulation_running:
            interval = max(50, 1000 // speed_value)  # 최소 50ms
            self.simulation_timer.setInterval(interval)

    def start_simulation(self):
        """시뮬레이션을 시작합니다."""
        if not self.ship_data:
            QMessageBox.warning(self, "Warning", "Please import ship data files first.")
            return
        
        self.is_simulation_running = True
        self.play_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        
        # 디버그 모드 자동 활성화 (문제 해결을 위해)
        if not self.debug_mode:
            self.debug_mode = True
            self.debug_button.setChecked(True)
            if hasattr(self, 'sim_canvas'):
                self.sim_canvas.set_debug_mode(True)
            self.add_progress_entry("🐛 Debug mode auto-enabled for troubleshooting")
        
        # 시뮬레이션 초기화
        self.current_time = 0
        self.current_time_index = 0
        self.os_trajectory = []
        self.ts_trajectories = {}
        self.behavior_history = []
        
        # 진행률 바 초기화
        self.progress_bar.setValue(0)
        
        # 선박 속도 안정화 변수 초기화
        if "OS" in self.ship_data and len(self.ship_data["OS"]) > 0:
            self.previous_os_speed = self.ship_data["OS"].iloc[0]['spd']
            if pd.isna(self.previous_os_speed):
                self.previous_os_speed = 12.0
        
        for ship_id in ["TS1", "TS2", "TS3", "TS4"]:
            if ship_id in self.ship_data and len(self.ship_data[ship_id]) > 0:
                speed_key = f'previous_ts_speed_{ship_id}'
                initial_speed = self.ship_data[ship_id].iloc[0]['spd']
                if pd.isna(initial_speed):
                    setattr(self, speed_key, 10.0)
                else:
                    setattr(self, speed_key, initial_speed)
        
        # OS 컨트롤 모드 초기화
        if self.os_control_mode:
            self.os_initial_position_set = False
            # AIS 데이터에서 초기 위치와 헤딩 설정
            if "OS" in self.ship_data and len(self.ship_data["OS"]) > 0:
                initial_data = self.ship_data["OS"].iloc[0]
                self.os_manual_position['heading'] = initial_data['co']
                self.os_manual_position['speed'] = initial_data['spd']
                self.add_progress_entry(f"🎮 Manual control mode - Initial Heading: {initial_data['co']}°, Speed: {initial_data['spd']} kts")
        else:
            self.add_progress_entry("🔄 AIS auto mode - Following AIS data")
        
        # 시뮬레이션 시작 시 자동으로 해도 설정
        if len(self.ship_data) >= 2:  # 최소 2개 이상의 선박이 로드된 경우
            self.auto_setup_chart_from_ships()
            self.add_progress_entry("🗺️ Chart automatically configured for simulation")
        
        # 타이머 간격 설정
        speed_value = self.speed_slider.value()
        interval = max(50, 1000 // speed_value)
        self.simulation_timer.start(interval)
        
        self.add_progress_entry("🚀 Simulation started")
        self.add_progress_entry("Simulation initialized")

    def pause_simulation(self):
        """시뮬레이션을 일시정지합니다."""
        self.is_simulation_running = False
        self.simulation_timer.stop()
        self.play_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        
        self.add_progress_entry("⏸ Simulation paused")

    def stop_simulation(self):
        """시뮬레이션을 정지합니다."""
        self.is_simulation_running = False
        self.simulation_timer.stop()
        self.current_time = 0
        self.current_time_index = 0
        self.progress_bar.setValue(0)
        self.play_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        
        # 드래깅 오프셋은 보존 (사용자가 설정한 위치 유지)
        if hasattr(self, 'sim_canvas') and hasattr(self.sim_canvas, 'os_offset_x') and hasattr(self.sim_canvas, 'os_offset_y'):
            if self.debug_mode:
                print(f"🔒 Stop simulation: OS offset preserved - ({self.sim_canvas.os_offset_x:.1f}, {self.sim_canvas.os_offset_y:.1f})")
        
        # 초기 상태로 복원 (드래깅 오프셋 제외)
        self.setup_sample_ships()
        self.os_initial_position_set = False
        
        self.add_progress_entry("⏹ Simulation stopped (OS drag position preserved)")

    def update_simulation(self):
        """시뮬레이션을 업데이트합니다."""
        if not self.ship_data:
            self.stop_simulation()
            return
        
        try:
            # 시나리오 종료 시간 확인 (인덱스 기반)
            if self.current_time_index >= self.scenario_end_time:
                self.complete_scenario()
                return
            
            # 모든 선박 데이터에서 최소 시간 찾기
            all_timestamps = []
            for ship_id, data in self.ship_data.items():
                if 'time' in data.columns and len(data) > self.current_time_index:
                    all_timestamps.append(data.iloc[self.current_time_index]['time'])
            
            if not all_timestamps:
                self.stop_simulation()
                return
            
            # 현재 시간 (가장 빠른 시간 사용)
            current_time = min(all_timestamps)
            self.time_info_label.setText(f"Current Time: {current_time}")
            
            # 캔버스 중심 좌표
            center_x, center_y = self.sim_canvas.width() // 2, self.sim_canvas.height() // 2
            
            # OS 데이터 처리
            ownship = None
            ships = []
            
            if "OS" in self.ship_data and len(self.ship_data["OS"]) > self.current_time_index:
                os_data = self.ship_data["OS"].iloc[self.current_time_index]
                
                if self.os_control_mode:
                    # 수동 조종 모드: 수동 위치 사용
                    # 수동 모드에서도 속도 안정화 적용
                    manual_speed = self.os_manual_position['speed']
                    if hasattr(self, 'previous_os_speed'):
                        speed_diff = abs(manual_speed - self.previous_os_speed)
                        if speed_diff > 2.0:  # 2노트 이상 차이나면 점진적으로 조정
                            if manual_speed > self.previous_os_speed:
                                manual_speed = self.previous_os_speed + 1.0
                            else:
                                manual_speed = self.previous_os_speed - 1.0
                    
                    self.previous_os_speed = manual_speed
                    
                    # 수동 모드에서도 드래깅 오프셋 보존
                    if hasattr(self.sim_canvas, 'os_offset_x') and hasattr(self.sim_canvas, 'os_offset_x'):
                        # 드래깅 오프셋을 고려한 수동 위치
                        manual_x = center_x + self.sim_canvas.os_offset_x
                        manual_y = center_y + self.sim_canvas.os_offset_y
                        
                        if self.debug_mode:
                            print(f"🔒 Manual mode preserving OS drag offset: ({self.sim_canvas.os_offset_x:.1f}, {self.sim_canvas.os_offset_y:.1f})")
                    else:
                        # 드래깅 오프셋이 없으면 기본 수동 위치 사용
                        manual_x = self.os_manual_position['x']
                        manual_y = self.os_manual_position['y']
                    
                    ownship = {
                        'x': manual_x,
                        'y': manual_y,
                        'heading': self.os_manual_position['heading'],
                        'speed': manual_speed,  # 안정화된 속도 사용
                        'bearing': 0
                    }
                    # 초기 위치 설정 (한 번만)
                    if not self.os_initial_position_set:
                        center_lat, center_lon = os_data['lat'], os_data['lon']
                        self.os_initial_position_set = True
                        self.add_progress_entry(f"📍 Initial position set - Lat: {center_lat:.6f}°, Lon: {center_lon:.6f}°")
                    else:
                        # 이미 설정된 중심 좌표 사용
                        center_lat, center_lon = self.sim_canvas.center_lat, self.sim_canvas.center_lon
                else:
                    # AIS 자동 모드: AIS 데이터 사용
                    # OS heading 값 검증 및 정규화
                    raw_os_heading = os_data['co']
                    if pd.isna(raw_os_heading) or raw_os_heading is None:
                        raw_os_heading = 0.0
                    
                    normalized_os_heading = float(raw_os_heading) % 360
                    
                    if self.debug_mode:
                        print(f"OS: Raw heading={raw_os_heading}, Normalized={normalized_os_heading:.1f}°")
                    
                    # OS 속도 안정화
                    current_speed = os_data['spd']
                    if pd.isna(current_speed) or current_speed is None:
                        current_speed = 12.0
                    
                    # 이전 속도와의 차이를 제한하여 안정화
                    if hasattr(self, 'previous_os_speed'):
                        speed_diff = abs(current_speed - self.previous_os_speed)
                        if speed_diff > 2.0:  # 2노트 이상 차이나면 점진적으로 조정
                            if current_speed > self.previous_os_speed:
                                current_speed = self.previous_os_speed + 1.0
                            else:
                                current_speed = self.previous_os_speed - 1.0
                    
                    self.previous_os_speed = current_speed
                    
                    # AIS 데이터에서 실제 위치 가져오기
                    actual_lat = os_data['lat']
                    actual_lon = os_data['lon']
                    
                    # 드래깅으로 이동된 OS 오프셋을 보존하면서 위치 계산
                    if hasattr(self.sim_canvas, 'os_offset_x') and hasattr(self.sim_canvas, 'os_offset_y'):
                        # 기존 드래깅 오프셋 사용
                        ship_x = center_x + self.sim_canvas.os_offset_x
                        ship_y = center_y + self.sim_canvas.os_offset_y
                        
                        if self.debug_mode:
                            print(f"🔒 Preserving OS drag offset: ({self.sim_canvas.os_offset_x:.1f}, {self.sim_canvas.os_offset_y:.1f})")
                    else:
                        # 드래깅 오프셋이 없으면 AIS 데이터 기반으로 계산
                        if hasattr(self.sim_canvas, 'center_lat') and hasattr(self.sim_canvas, 'center_lon'):
                            # 위경도 차이를 픽셀로 변환
                            lat_diff = actual_lat - self.sim_canvas.center_lat
                            lon_diff = actual_lon - self.sim_canvas.center_lon
                            
                            # 1도 = 60마일, 1마일 = 70픽셀
                            x_offset = lon_diff * 60 * 70
                            y_offset = -lat_diff * 60 * 70  # y축은 반대
                            
                            ship_x = center_x + x_offset
                            ship_y = center_y + y_offset
                        else:
                            ship_x = center_x
                            ship_y = center_y
                    
                    ownship = {
                        'x': ship_x,
                        'y': ship_y,
                        'heading': normalized_os_heading,  # 정규화된 heading 사용
                        'speed': current_speed,  # 안정화된 속도 사용
                        'bearing': 0,
                        'lat': actual_lat,
                        'lon': actual_lon
                    }
                    
                    # 캔버스 중심 좌표는 변경하지 않음 (드래깅 위치 보존)
                    # center_lat, center_lon = actual_lat, actual_lon
                    # self.sim_canvas.set_center_coordinates(center_lat, center_lon)
            else:
                # OS가 없으면 첫 번째 TS를 중심으로 설정
                for ship_id in ["TS1", "TS2", "TS3", "TS4"]:
                    if ship_id in self.ship_data and len(self.ship_data[ship_id]) > self.current_time_index:
                        center_data = self.ship_data[ship_id].iloc[self.current_time_index]
                        center_lat, center_lon = center_data['lat'], center_data['lon']
                        ownship = {
                            'x': center_x,
                            'y': center_y,
                            'heading': center_data['co'],
                            'speed': center_data['spd'],
                            'bearing': 0
                        }
                        break
            
            # TS 데이터 처리
            ship_colors = [QColor('#e74c3c'), QColor('#90EE90'), QColor('#FFB347'), 
                         QColor('#3498db')]
            
            for i, ship_id in enumerate(["TS1", "TS2", "TS3", "TS4"]):
                if ship_id in self.ship_data and len(self.ship_data[ship_id]) > self.current_time_index:
                    ts_data = self.ship_data[ship_id].iloc[self.current_time_index]
                    
                    # 위경도를 캔버스 좌표로 변환
                    lat, lon = ts_data['lat'], ts_data['lon']
                    x, y = AISDataProcessor.convert_latlon_to_xy(lat, lon, center_lat, center_lon)
                    
                    # OS에서 TS까지의 방위(bearing) 계산
                    dx = x
                    dy = y
                    # Qt 좌표계에서 방위 계산: 북쪽이 0도, 시계방향으로 증가
                    # atan2(dx, -dy)는 Qt 좌표계에 맞춰 계산
                    bearing = math.degrees(math.atan2(dx, -dy))
                    if bearing < 0:
                        bearing += 360
                    
                    # TS의 heading 값 검증 및 정규화
                    raw_heading = ts_data['co']
                    if pd.isna(raw_heading) or raw_heading is None:
                        raw_heading = 0.0
                    
                    # AIS 데이터의 course 값이 실제 진행 방향과 다를 수 있음
                    # bearing을 기반으로 실제 진행 방향을 추정
                    # AIS course 값과 bearing 값의 차이가 너무 크면 bearing 기반으로 추정
                    
                    # 방법 1: AIS course 값을 그대로 사용 (기본값)
                    normalized_heading = float(raw_heading) % 360
                    
                    # 방법 2: bearing을 기반으로 진행 방향 추정 (AIS 데이터가 부정확할 때)
                    # AIS course와 bearing의 차이가 90도 이상이면 bearing 기반으로 추정
                    direction_diff = abs(normalized_heading - bearing)
                    if direction_diff > 180:
                        direction_diff = 360 - direction_diff
                    
                    if direction_diff > 90:  # 90도 이상 차이나면 bearing 기반으로 추정
                        estimated_heading = bearing
                        if self.debug_mode:
                            print(f"  ⚠️ Large difference detected: AIS({normalized_heading:.1f}°) vs Bearing({bearing:.1f}°) = {direction_diff:.1f}°")
                            print(f"  🔄 Using bearing-based heading: {estimated_heading:.1f}°")
                        normalized_heading = estimated_heading
                    else:
                        if self.debug_mode:
                            print(f"  ✅ AIS course and bearing are consistent: {direction_diff:.1f}° difference")
                    
                    # 디버그 로깅
                    if self.debug_mode:
                        print(f"{ship_id}: Raw heading={raw_heading}, Normalized={normalized_heading:.1f}°, Bearing={bearing:.1f}°")
                        print(f"  Position: ({lat:.6f}, {lon:.6f}) -> Canvas: ({x:.1f}, {y:.1f})")
                        print(f"  dx={dx:.1f}, dy={y:.1f}, atan2={math.degrees(math.atan2(dx, -dy)):.1f}°")
                        print(f"  AIS Course vs Bearing: {normalized_heading:.1f}° vs {bearing:.1f}°")
                    
                    # TS 속도 안정화
                    current_ts_speed = ts_data['spd']
                    if pd.isna(current_ts_speed) or current_ts_speed is None:
                        current_ts_speed = 10.0
                    
                    # 이전 속도와의 차이를 제한하여 안정화
                    speed_key = f'previous_ts_speed_{ship_id}'
                    if hasattr(self, speed_key):
                        speed_diff = abs(current_ts_speed - getattr(self, speed_key))
                        if speed_diff > 1.5:  # 1.5노트 이상 차이나면 점진적으로 조정
                            if current_ts_speed > getattr(self, speed_key):
                                current_ts_speed = getattr(self, speed_key) + 0.5
                            else:
                                current_ts_speed = getattr(self, speed_key) - 0.5
                    
                    setattr(self, speed_key, current_ts_speed)
                    
                    ships.append({
                        'x': center_x + x,
                        'y': center_y + y,
                        'heading': normalized_heading,  # 수정된 heading 사용
                        'speed': current_ts_speed,  # 안정화된 속도 사용
                        'color': ship_colors[i % len(ship_colors)],
                        'bearing': bearing,  # OS에서 TS까지의 방위
                        'lat': lat,  # 실제 위도
                        'lon': lon   # 실제 경도
                    })
            
            # 캔버스 업데이트
            if ownship:
                self.sim_canvas.set_ships(ownship, ships)
                self.sim_canvas.set_os_heading(ownship['heading'])
                
                # 선박 수 업데이트
                self.ship_count_label.setText(f"Ship Count: {len(ships) + 1}")
                
                # 궤적 추적
                self.track_trajectories(ownship, ships)
                
                # 자선 행동 추적
                self.track_os_behavior(ownship, ships)
                
                # 기상 효과 적용
                self.apply_weather_to_ships(ownship, ships)
                
                # 전자해도에 실시간 해상 데이터 표시
                if ELECTRONIC_CHART_AVAILABLE and hasattr(self, 'marine_data_service'):
                    self.update_electronic_chart_data()
            
            # 진행률 업데이트
            self.current_time_index += 1
            self.current_time += 1
            # 진행률을 실제 데이터 인덱스 기반으로 계산
            progress = (self.current_time_index / self.scenario_end_time) * 100
            self.progress_bar.setValue(int(progress))
            
        except Exception as e:
            print(f"Simulation update error: {e}")
            self.stop_simulation()
    
    def toggle_real_chart_data(self, checked: bool):
        """국립해양조사원 전자해도 오픈API 데이터 사용 토글"""
        if checked and self.sim_canvas.real_chart_loader:
            self.sim_canvas.use_real_chart_data = True
            self.sim_canvas.clear_chart_data_cache()
            self.api_status_label.setText("API Status: Connected")
            self.data_load_status_label.setText("Data Load: National Oceanographic Research Institute API Data")
            print("✅ National Oceanographic Research Institute Electronic Chart OpenAPI Data Usage Started")
        else:
            self.sim_canvas.use_real_chart_data = False
            self.api_status_label.setText("API Status: Not connected")
            self.data_load_status_label.setText("Data Load: Virtual Chart Data")
            print("🔄 Virtual Chart Data Usage")
        self.sim_canvas.update()
    
    def show_cache_info(self):
        """국립해양조사원 전자해도 오픈API 캐시 정보 표시"""
        if self.sim_canvas.real_chart_loader:
            info = self.sim_canvas.real_chart_loader.get_cache_info()
            QMessageBox.information(self, "Cache Information", 
                                  f"National Oceanographic Research Institute Electronic Chart OpenAPI Cache Information:\n"
                                  f"Cached Data: {info['cache_size']} items\n"
                                  f"Cache Keys: {', '.join(info['cache_keys'][:5])}")
        else:
            QMessageBox.information(self, "Cache Information", "National Oceanographic Research Institute Electronic Chart OpenAPI is not connected.")
    
    def track_trajectories(self, ownship, ships):
        """궤적을 추적합니다."""
        # OS 궤적 추가
        self.os_trajectory.append({
            'time': self.current_time,
            'x': ownship['x'],
            'y': ownship['y'],
            'heading': ownship['heading'],
            'speed': ownship['speed']
        })
        
        # TS 궤적 추가
        for i, ship in enumerate(ships):
            ts_id = f"TS{i+1}"
            if ts_id not in self.ts_trajectories:
                self.ts_trajectories[ts_id] = []
            
            self.ts_trajectories[ts_id].append({
                'time': self.current_time,
                'x': ship['x'],
                'y': ship['y'],
                'heading': ship['heading'],
                'speed': ship['speed']
            })
    
    def track_os_behavior(self, ownship, ships):
        """자선 행동을 추적합니다."""
        # 자선 행동 히스토리에 추가
        self.add_progress_entry(f"OS position: ({ownship['x']:.1f}, {ownship['y']:.1f}), Heading: {ownship['heading']}°, Speed: {ownship['speed']} kts")
        
        # 시나리오 진행 상황 업데이트
        progress_percent = (self.current_time_index / self.scenario_end_time) * 100
        self.add_progress_entry(f"Scenario progress: {progress_percent:.1f}% ({self.current_time_index}/{self.scenario_end_time} indices)")
    
    def complete_scenario(self):
        """시나리오를 완료합니다."""
        self.is_scenario_completed = True
        
        # 진행률을 100%로 설정
        self.progress_bar.setValue(100)
        
        # 시나리오 완료 메시지
        self.add_progress_entry("🎯 SCENARIO COMPLETED")
        self.add_progress_entry("✅ Scenario completed successfully")
        self.add_progress_entry(f"📊 Final progress: 100% ({self.scenario_end_time}/{self.scenario_end_time} indices)")
        
        # 궤적 추출 버튼 활성화
        self.extract_trajectory_button.setEnabled(True)
        
        # 시뮬레이션 정지
        self.stop_simulation()
        
        QMessageBox.information(self, "Scenario Complete", "Scenario has been completed successfully. You can now extract trajectory data.")

    def setup_sample_ships(self):
        """샘플 선박 데이터를 설정합니다."""
        center_x, center_y = self.sim_canvas.width() // 2, self.sim_canvas.height() // 2
        
        # 드래깅 오프셋을 고려한 자선 위치 설정
        if hasattr(self.sim_canvas, 'os_offset_x') and hasattr(self.sim_canvas, 'os_offset_x'):
            # 기존 드래깅 오프셋 보존
            ship_x = center_x + self.sim_canvas.os_offset_x
            ship_y = center_y + self.sim_canvas.os_offset_y
            
            if self.debug_mode:
                print(f"🔒 setup_sample_ships: OS offset preserved - ({self.sim_canvas.os_offset_x:.1f}, {self.sim_canvas.os_offset_y:.1f})")
        else:
            # 드래깅 오프셋이 없으면 화면 중심
            ship_x = center_x
            ship_y = center_y
        
        # Own ship at preserved position
        ownship = {
            'x': ship_x,
            'y': ship_y,
            'heading': 0,
            'speed': 12,
            'bearing': 0
        }
        
        # No target ships initially
        ships = []
        
        self.sim_canvas.set_ships(ownship, ships)

    def set_control_mode(self, is_manual):
        """OS 컨트롤 모드를 설정합니다."""
        self.os_control_mode = is_manual
        
        if is_manual:
            # 수동 조종 모드로 전환
            self.manual_control_button.setChecked(True)
            self.ais_auto_button.setChecked(False)
            self.control_mode_label.setText("Mode: MAN")
            self.control_mode_label.setStyleSheet("color: #dc3545; font-weight: bold; font-size: 9px;")
            
            # AIS 데이터에서 초기 위치와 헤딩 설정
            if "OS" in self.ship_data and len(self.ship_data["OS"]) > 0:
                initial_data = self.ship_data["OS"].iloc[0]  # 인덱스 0의 데이터
                self.os_manual_position['heading'] = initial_data['co']
                self.os_manual_position['speed'] = initial_data['spd']
                
                # 초기 위치 설정 (드래깅 오프셋 고려)
                center_x, center_y = self.sim_canvas.width() // 2, self.sim_canvas.height() // 2
                
                if hasattr(self.sim_canvas, 'os_offset_x') and hasattr(self.sim_canvas, 'os_offset_x'):
                    # 드래깅 오프셋을 고려한 수동 위치
                    self.os_manual_position['x'] = center_x + self.sim_canvas.os_offset_x
                    self.os_manual_position['y'] = center_y + self.sim_canvas.os_offset_y
                    
                    if self.debug_mode:
                        print(f"🔒 set_control_mode: OS offset preserved - ({self.sim_canvas.os_offset_x:.1f}, {self.sim_canvas.os_offset_y:.1f})")
                else:
                    # 드래깅 오프셋이 없으면 화면 중심
                    self.os_manual_position['x'] = center_x
                    self.os_manual_position['y'] = center_y
                
                # 휠 컨트롤에 초기값 설정
                self.os_heading_wheel.setValue(int(initial_data['co']))
                self.os_speed_wheel.setValue(int(initial_data['spd']))
                
                self.add_progress_entry(f"🎮 Switched to Manual Control Mode - Initial Heading: {initial_data['co']}°, Speed: {initial_data['spd']} kts")
            else:
                self.add_progress_entry("⚠️ No OS data available for manual control")
        else:
            # AIS 자동 모드로 전환
            self.ais_auto_button.setChecked(True)
            self.manual_control_button.setChecked(False)
            self.control_mode_label.setText("Mode: AIS")
            self.control_mode_label.setStyleSheet("color: #28a745; font-weight: bold; font-size: 9px;")
            
            self.add_progress_entry("🔄 Switched to AIS Auto Mode")
        
        # 시뮬레이션 상태에 따라 UI 업데이트
        self.update_control_mode_ui()

    def set_terrain_mode(self, terrain_centered):
        """지형지물 중심 화면 모드를 설정합니다."""
        self.terrain_centered_mode = terrain_centered
        
        if terrain_centered:
            # 지형지물 중심 모드
            self.terrain_centered_button.setChecked(True)
            self.ship_centered_button.setChecked(False)
            self.terrain_mode_label.setText("Mode: TER")
            self.terrain_mode_label.setStyleSheet("color: #28a745; font-weight: bold; font-size: 8px;")
            
            # 캔버스 모드 업데이트
            self.sim_canvas.terrain_centered_mode = True
            
            self.add_progress_entry("🗺️ Switched to Terrain Centered Mode")
        else:
            # 자선 중심 모드
            self.terrain_centered_button.setChecked(False)
            self.ship_centered_button.setChecked(True)
            self.terrain_mode_label.setText("Mode: SHIP")
            self.terrain_mode_label.setStyleSheet("color: #007bff; font-weight: bold; font-size: 8px;")
            
            # 캔버스 모드 업데이트
            self.sim_canvas.terrain_centered_mode = False
            
            self.add_progress_entry("🚢 Switched to Ship Centered Mode")
        
        # 캔버스 업데이트
        self.sim_canvas.update()

    def update_control_mode_ui(self):
        """컨트롤 모드에 따라 UI를 업데이트합니다."""
        if self.os_control_mode:
            # 수동 조종 모드일 때 휠 컨트롤 활성화
            self.os_heading_wheel.setEnabled(True)
            self.os_speed_wheel.setEnabled(True)
        else:
            # AIS 자동 모드일 때 휠 컨트롤 비활성화
            self.os_heading_wheel.setEnabled(False)
            self.os_speed_wheel.setEnabled(False)

    def on_os_parameter_changed(self):
        """자선 파라미터가 변경되었을 때 호출되는 메서드"""
        # 수동 조종 모드에서만 작동
        if not self.os_control_mode:
            return
            
        import time
        
        current_time = time.time()
        heading = self.os_heading_wheel.value()
        speed = self.os_speed_wheel.value()
        
        # 수동 조종 위치 업데이트
        self.os_manual_position['heading'] = heading
        self.os_manual_position['speed'] = speed
        
        # 1초 이상 유지된 변경사항만 기록 (미세조정 제외)
        if (current_time - self.last_behavior_change_time >= self.behavior_delay_seconds and 
            (self.last_os_heading != heading or self.last_os_speed != speed)):
            
            self.add_behavior_entry(f"OS parameter changed - Heading: {heading}°, Speed: {speed} kts")
            self.last_behavior_change_time = current_time
            self.last_os_heading = heading
            self.last_os_speed = speed
        
        # 시뮬레이션 데이터 업데이트 (즉시)
        if self.is_simulation_running:
            self.update_os_parameters()
    
    def update_end_time_display(self):
        """종료 시간 표시를 업데이트합니다."""
        seconds = self.end_time_slider.value()
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        time_str = f"{minutes}:{remaining_seconds:02d}"
        self.end_time_label.setText(time_str)
        
        # 시나리오 종료 시간 업데이트
        self.scenario_end_time = seconds
        
        self.add_progress_entry(f"Scenario end time set to {time_str}")

    def add_behavior_entry(self, details):
        """자선 행동 히스토리에 항목을 추가합니다. (Own Ship Control 인터페이스 조정사항만 기록)"""
        import datetime
        
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {details}"
        
        self.behavior_history.append(entry)
        
        # 모든 항목을 표시 (스크롤 가능)
        self.os_behavior_text.setPlainText("\n".join(self.behavior_history))
        
        # 자동 스크롤을 최신 항목으로 이동
        cursor = self.os_behavior_text.textCursor()
        cursor.movePosition(cursor.End)
        self.os_behavior_text.setTextCursor(cursor)
    
    def add_progress_entry(self, details):
        """시나리오 진행 상황에 항목을 추가합니다. (모든 기타 활동 및 이력 기록)"""
        import datetime
        
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {details}"
        
        # 진행 상황 전체 이력에 추가
        self.progress_history.append(entry)
        
        # 모든 항목을 표시 (스크롤 가능)
        self.scenario_progress_text.setPlainText("\n".join(self.progress_history))
        
        # 자동 스크롤을 최신 항목으로 이동
        cursor = self.scenario_progress_text.textCursor()
        cursor.movePosition(cursor.End)
        self.scenario_progress_text.setTextCursor(cursor)
    
    def update_os_parameters(self):
        """자선 파라미터를 업데이트합니다."""
        if hasattr(self, 'sim_data') and self.sim_data:
            os = self.sim_data['ownship']
            os['heading'] = self.os_heading_wheel.value()
            os['speed'] = self.os_speed_wheel.value()
    
    def extract_trajectories(self):
        """궤적을 추출합니다."""
        if not self.os_trajectory:
            QMessageBox.warning(self, "Warning", "No trajectory data available.")
            return
        
        try:
            # 파일 저장 다이얼로그
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Trajectory Data", "trajectory_data.xlsx", 
                "Excel Files (*.xlsx);;CSV Files (*.csv)"
            )
            
            if file_path:
                # OS 궤적 데이터
                os_data = {
                    'Time': [point['time'] for point in self.os_trajectory],
                    'X': [point['x'] for point in self.os_trajectory],
                    'Y': [point['y'] for point in self.os_trajectory],
                    'Heading': [point['heading'] for point in self.os_trajectory],
                    'Speed': [point['speed'] for point in self.os_trajectory]
                }
                
                # TS 궤적 데이터
                ts_data = {}
                for ts_id, trajectory in self.ts_trajectories.items():
                    ts_data[f'{ts_id}_X'] = [point['x'] for point in trajectory]
                    ts_data[f'{ts_id}_Y'] = [point['y'] for point in trajectory]
                    ts_data[f'{ts_id}_Heading'] = [point['heading'] for point in trajectory]
                    ts_data[f'{ts_id}_Speed'] = [point['speed'] for point in trajectory]
                
                # 데이터프레임 생성
                df_os = pd.DataFrame(os_data)
                df_ts = pd.DataFrame(ts_data)
                
                # Excel 파일로 저장
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    df_os.to_excel(writer, sheet_name='OS_Trajectory', index=False)
                    if not df_ts.empty:
                        df_ts.to_excel(writer, sheet_name='TS_Trajectories', index=False)
                
                # 궤적 정보 업데이트
                trajectory_info = f"OS points: {len(self.os_trajectory)}, TS ships: {len(self.ts_trajectories)}"
                self.trajectory_info_label.setText(f"Trajectory Info: {trajectory_info}")
                
                QMessageBox.information(self, "Success", f"Trajectory data saved to {file_path}")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error extracting trajectories:\n{str(e)}")

    def setup_simulator_canvas(self):
        """시뮬레이터 캔버스를 설정합니다."""
        if ELECTRONIC_CHART_AVAILABLE:
            # 전자해도 캔버스 사용
            self.sim_canvas = ElectronicChartCanvas()
            self.sim_canvas.setMinimumSize(900, 700)
        else:
            # 기본 캔버스 사용
            self.sim_canvas = SimCanvas()
            self.sim_canvas.setMinimumSize(900, 700)
    
    def setup_electronic_chart_control(self):
        """전자해도 제어 패널을 설정합니다."""
        # 전자해도 제어는 기본 캔버스에 통합되어 있음
        pass
    
    def on_chart_style_changed(self, style):
        """해도 스타일이 변경되었을 때 호출됩니다."""
        if ELECTRONIC_CHART_AVAILABLE and hasattr(self.sim_canvas, 'set_chart_style'):
            self.sim_canvas.set_chart_style(style)
            self.add_progress_entry(f"🎨 Chart style changed to: {style}")
    
    def on_layer_toggled(self, layer_name, enabled):
        """해도 레이어가 토글되었을 때 호출됩니다."""
        if ELECTRONIC_CHART_AVAILABLE and hasattr(self.sim_canvas, 'toggle_layer'):
            self.sim_canvas.toggle_layer(layer_name, enabled)
            status = "enabled" if enabled else "disabled"
            self.add_progress_entry(f"🔍 Layer '{layer_name}' {status}")
    
    def on_zoom_changed(self, zoom_level):
        """줌 레벨이 변경되었을 때 호출됩니다."""
        if ELECTRONIC_CHART_AVAILABLE and hasattr(self.sim_canvas, 'zoom_level'):
            self.sim_canvas.zoom_level = zoom_level
            self.sim_canvas.update()
            self.add_progress_entry(f"🔍 Zoom level changed to: {zoom_level:.1f}x")
    
    def update_electronic_chart_data(self):
        """전자해도에 실시간 해상 데이터를 업데이트합니다."""
        try:
            # 현재 중심 좌표
            center_lat = self.sim_canvas.center_lat
            center_lon = self.sim_canvas.center_lon
            
            # 진행 상황에 해상 정보 기록
            self.add_progress_entry(f"🌍 Chart center: Lat {center_lat:.6f}°, Lon {center_lon:.6f}°")
                
        except Exception as e:
            print(f"Error updating electronic chart data: {e}")
            self.add_progress_entry(f"⚠️ Error updating chart data: {str(e)}")

    def import_ship_file(self, ship_id):
        """개별 선박 엑셀 파일을 임포트합니다."""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, f"Select {ship_id} File", "", 
                "Excel Files (*.xlsx *.xls);;All Files (*)"
            )
            
            if file_path:
                # AIS 데이터 로드
                ship_data = AISDataProcessor.load_ais_data(file_path)
                
                # 파일 정보 업데이트
                file_name = os.path.basename(file_path)
                
                if ship_id == "OS":
                    self.os_file_label.setText(f"Selected: {file_name}")
                else:
                    ts_index = int(ship_id[2]) - 1  # TS1 -> 0, TS2 -> 1, ...
                    if 0 <= ts_index < len(self.ts_file_labels):
                        self.ts_file_labels[ts_index].setText(f"Selected: {file_name}")
                
                # 선박 데이터 저장
                self.ship_data[ship_id] = ship_data
                
                # 전체 데이터 정보 업데이트
                self.update_data_info()
                
                # 모든 선박 데이터가 로드되었는지 확인하고 해도 자동 설정
                if len(self.ship_data) > 1:  # 최소 2개 이상의 선박이 로드된 경우
                    self.auto_setup_chart_from_ships()
                
                QMessageBox.information(self, "Success", f"{ship_id} data loaded successfully.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading {ship_id} file:\n{str(e)}")
    
    def auto_setup_chart_from_ships(self):
        """로드된 선박 데이터를 기반으로 해도를 자동 설정합니다."""
        try:
            if len(self.ship_data) < 2:
                return
            
            # 모든 선박의 시작 좌표 수집 (인덱스 1)
            ship_start_positions = []
            ship_names = []
            
            for ship_id, data in self.ship_data.items():
                if len(data) > 1:  # 최소 2개 이상의 데이터가 있는 경우
                    # 인덱스 1의 좌표 사용 (시작 위치)
                    start_lat = data.iloc[1]['lat']
                    start_lon = data.iloc[1]['lon']
                    ship_start_positions.append((start_lat, start_lon))
                    ship_names.append(ship_id)
            
            if not ship_start_positions:
                return
            
            # 선박 수에 따른 해도 설정
            if len(ship_start_positions) == 1:
                # 단일 선박: 시작 위치에서 5마일 반경
                center_lat, center_lon = ship_start_positions[0]
                self.setup_chart_for_single_ship(center_lat, center_lon, ship_names[0])
            else:
                # 다중 선박: 클러스터링하여 중심점 계산 후 5마일 반경
                self.setup_chart_for_multiple_ships(ship_start_positions, ship_names)
            
            # 진행 상황에 기록
            self.add_progress_entry(f"🗺️ Chart automatically configured for {len(ship_start_positions)} ships")
            
        except Exception as e:
            self.add_progress_entry(f"⚠️ Error in auto chart setup: {str(e)}")
    
    def setup_chart_for_single_ship(self, center_lat, center_lon, ship_name):
        """단일 선박을 위한 해도를 설정합니다."""
        # 5마일 반경으로 해도 설정
        radius_nm = 5.0
        
        # 캔버스 중심 좌표 설정
        if hasattr(self, 'sim_canvas'):
            self.sim_canvas.center_lat = center_lat
            self.sim_canvas.center_lon = center_lon
            self.sim_canvas.center_mode = True  # 트루모션 모드 활성화
            
            # 줌 레벨 조정 (5마일이 화면에 잘 보이도록)
            self.sim_canvas.zoom_level = 1.0
            
            # 해도 데이터를 새로운 중심점으로 업데이트
            self.sim_canvas.initialize_chart_data_for_location(center_lat, center_lon, radius_nm)
            
            # 캔버스 업데이트
            self.sim_canvas.update()
        
        # 진행 상황에 기록
        self.add_progress_entry(f"📍 Chart centered on {ship_name} at ({center_lat:.4f}, {center_lon:.4f})")
        self.add_progress_entry(f"🎯 Chart radius: {radius_nm} NM, True Motion mode activated")
        
        # UI 상태 업데이트
        self.update_chart_status_ui(center_lat, center_lon, radius_nm, f"Single Ship: {ship_name}")
    
    def setup_chart_for_multiple_ships(self, ship_positions, ship_names):
        """다중 선박을 위한 해도를 설정합니다."""
        # 클러스터링을 위한 중심점 계산
        center_lat, center_lon = self.calculate_cluster_center(ship_positions)
        
        # 모든 선박을 포함하는 최소 반경 계산
        max_distance = self.calculate_max_distance_from_center(center_lat, center_lon, ship_positions)
        
        # 5마일 반경과 최대 거리 중 큰 값 사용 (최소 5마일 보장)
        radius_nm = max(5.0, max_distance + 1.0)  # 여유분 1마일 추가
        
        # 캔버스 중심 좌표 설정
        if hasattr(self, 'sim_canvas'):
            self.sim_canvas.center_lat = center_lat
            self.sim_canvas.center_lon = center_lon
            self.sim_canvas.center_mode = True  # 트루모션 모드 활성화
            
            # 줌 레벨 조정
            self.sim_canvas.zoom_level = 1.0
            
            # 해도 데이터를 새로운 중심점으로 업데이트
            self.sim_canvas.initialize_chart_data_for_location(center_lat, center_lon, radius_nm)
            
            # 캔버스 업데이트
            self.sim_canvas.update()
        
        # 진행 상황에 기록
        self.add_progress_entry(f"📍 Chart centered on cluster center at ({center_lat:.4f}, {center_lon:.4f})")
        self.add_progress_entry(f"🎯 Chart radius: {radius_nm:.1f} NM, covering {len(ship_names)} ships")
        self.add_progress_entry(f"🚢 Ships: {', '.join(ship_names)}")
        
        # UI 상태 업데이트
        self.update_chart_status_ui(center_lat, center_lon, radius_nm, f"Cluster: {len(ship_names)} ships")
    
    def calculate_cluster_center(self, positions):
        """선박 위치들의 클러스터 중심점을 계산합니다."""
        if not positions:
            return 0.0, 0.0
        
        # 단순 평균 중심점 계산
        total_lat = sum(pos[0] for pos in positions)
        total_lon = sum(pos[1] for pos in positions)
        
        center_lat = total_lat / len(positions)
        center_lon = total_lon / len(positions)
        
        return center_lat, center_lon
    
    def calculate_max_distance_from_center(self, center_lat, center_lon, positions):
        """중심점에서 가장 먼 선박까지의 거리를 계산합니다 (마일 단위)."""
        max_distance = 0.0
        
        for lat, lon in positions:
            # 위경도 차이를 마일로 변환 (1도 ≈ 60마일)
            lat_diff = abs(lat - center_lat) * 60
            lon_diff = abs(lon - center_lon) * 60 * math.cos(math.radians(center_lat))
            
            # 유클리드 거리 계산
            distance = math.sqrt(lat_diff**2 + lon_diff**2)
            max_distance = max(max_distance, distance)
        
        return max_distance
    
    def update_chart_status_ui(self, center_lat, center_lon, radius_nm, chart_type):
        """해도 상태 UI를 업데이트합니다."""
        try:
            if hasattr(self, 'chart_status_label'):
                self.chart_status_label.setText(f"Chart Status: {chart_type}")
                self.chart_status_label.setStyleSheet("color: #28a745; font-weight: bold; font-size: 12px;")
            
            if hasattr(self, 'chart_center_label'):
                self.chart_center_label.setText(f"Chart Center: {center_lat:.4f}°, {center_lon:.4f}°")
                self.chart_center_label.setStyleSheet("color: #007bff; font-size: 12px;")
            
            if hasattr(self, 'chart_radius_label'):
                self.chart_radius_label.setText(f"Chart Radius: {radius_nm:.1f} NM")
                self.chart_radius_label.setStyleSheet("color: #007bff; font-size: 12px;")
                
        except Exception as e:
            self.add_progress_entry(f"⚠️ Error updating chart status UI: {str(e)}")
    
    def update_data_info(self):
        """전체 데이터 정보를 업데이트합니다."""
        if not self.ship_data:
            self.data_info_label.setText("Data Info: None")
            return
        
        total_ships = len(self.ship_data)
        time_ranges = []
        
        # 시나리오 실제 종료 시간 계산
        max_time_index = 0
        for ship_id, data in self.ship_data.items():
            if 'time' in data.columns:
                time_range = f"{data['time'].min()} ~ {data['time'].max()}"
                time_ranges.append(f"{ship_id}: {time_range}")
                
                # 최대 시간 인덱스 찾기
                if len(data) > max_time_index:
                    max_time_index = len(data)
        
        # 시나리오 종료 시간을 실제 데이터 길이로 업데이트
        if max_time_index > 0:
            self.scenario_end_time = max_time_index
            # 시나리오 종료 시간 라벨 업데이트
            if hasattr(self, 'end_time_label'):
                minutes = max_time_index // 60
                remaining_seconds = max_time_index % 60
                time_str = f"{minutes}:{remaining_seconds:02d}"
                self.end_time_label.setText(time_str)
            
            # 진행 상황에 시나리오 정보 추가
            self.add_progress_entry(f"📊 Scenario duration updated: {max_time_index} indices ({time_str})")
            self.add_progress_entry(f"📈 Progress bar will now reach 100% at index {max_time_index}")
        
        info_text = f"Ships: {total_ships}\n" + "\n".join(time_ranges[:3])  # 최대 3개만 표시
        if len(time_ranges) > 3:
            info_text += f"\n... and {len(time_ranges) - 3} more"
        
        self.data_info_label.setText(info_text)
    
    def import_owl_file(self):
        """OWL 파일을 임포트합니다."""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select OWL File", "", 
                "OWL Files (*.owl *.xml);;All Files (*)"
            )
            
            if file_path:
                # OWL 데이터 로드
                self.evaluation_items = OntologyProcessor.load_owl_file(file_path)
                
                # 파일 정보 업데이트
                file_name = os.path.basename(file_path)
                self.owl_file_label.setText(f"Selected: {file_name}")
                
                # 온톨로지 정보 업데이트
                class_count = len([item for item in self.evaluation_items if item['type'] == 'class'])
                property_count = len([item for item in self.evaluation_items if item['type'] == 'property'])
                self.ontology_info_label.setText(f"Classes: {class_count}, Properties: {property_count}")
                
                # 평가 트리 업데이트
                self.update_evaluation_tree()
                
                # 분석 버튼 활성화
                self.analyze_button.setEnabled(True)
                
                QMessageBox.information(self, "Success", f"OWL file loaded successfully.\nClasses: {class_count}, Properties: {property_count}")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading OWL file:\n{str(e)}")
    
    def update_evaluation_tree(self):
        """평가 항목 트리를 업데이트합니다."""
        self.evaluation_tree.clear()
        
        # 클래스와 속성 분리
        classes = [item for item in self.evaluation_items if item['type'] == 'class']
        properties = [item for item in self.evaluation_items if item['type'] == 'property']
        
        # 클래스 노드
        if classes:
            class_root = QTreeWidgetItem(self.evaluation_tree, ["Classes", ""])
            for item in classes:
                class_item = QTreeWidgetItem(class_root, [item['name'], f"{item['score']:.1f}"])
                class_item.setData(0, Qt.UserRole, item)
        
        # 속성 노드
        if properties:
            prop_root = QTreeWidgetItem(self.evaluation_tree, ["Properties", ""])
            for item in properties:
                prop_item = QTreeWidgetItem(prop_root, [item['name'], f"{item['score']:.1f}"])
                prop_item.setData(0, Qt.UserRole, item)
        
        self.evaluation_tree.expandAll()
    
    def analyze_scenario_evaluation(self):
        """시나리오 환경에 맞는 성능평가 항목을 분석합니다."""
        if not self.evaluation_items:
            QMessageBox.warning(self, "Warning", "Please load OWL file first.")
            return
        
        if not self.ship_data:
            QMessageBox.warning(self, "Warning", "Please import ship data files first.")
            return
        
        try:
            # 시나리오 데이터 분석
            scenario_data = {
                'ships': list(self.ship_data.keys()),
                'encounter_types': self.analyze_encounter_types()
            }
            
            # 평가 트리거 확인
            if self.check_evaluation_trigger(scenario_data):
                # 관련 평가 항목 필터링
                self.scenario_evaluation_items = OntologyProcessor.analyze_scenario_evaluation_items(
                    self.evaluation_items, scenario_data
                )
                
                # 각 평가 항목에 대해 점수 계산
                for item in self.scenario_evaluation_items:
                    item['score'] = self.calculate_performance_score(item['name'], scenario_data)
                
                # 평가 트리 업데이트
                self.update_scenario_evaluation_tree()
                
                # 결과 텍스트 업데이트
                self.update_evaluation_results()
                
                QMessageBox.information(self, "Success", f"Scenario analysis completed.\nRelevant items: {len(self.scenario_evaluation_items)}")
            else:
                QMessageBox.information(self, "Info", "Evaluation conditions not met yet.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error analyzing scenario:\n{str(e)}")
    
    def analyze_encounter_types(self):
        """현재 시나리오의 조우 유형을 분석합니다."""
        encounter_types = []
        
        # 간단한 조우 유형 분석 (실제로는 더 복잡한 로직 필요)
        if len(self.ship_data) > 1:
            encounter_types.extend(['head_on', 'crossing', 'collision_avoidance'])
        
        return encounter_types
    
    def update_scenario_evaluation_tree(self):
        """시나리오 관련 평가 항목 트리를 업데이트합니다."""
        self.evaluation_tree.clear()
        
        if not self.scenario_evaluation_items:
            return
        
        # 관련 항목만 표시
        for item in self.scenario_evaluation_items:
            tree_item = QTreeWidgetItem(self.evaluation_tree, [item['name'], f"{item['score']:.1f}"])
            tree_item.setData(0, Qt.UserRole, item)
        
        self.evaluation_tree.expandAll()
    
    def update_evaluation_results(self):
        """평가 결과를 업데이트합니다."""
        if not self.scenario_evaluation_items:
            self.results_text.setPlainText("No evaluation items available.")
            self.total_score_label.setText("Total Score: 0.0")
            return
        
        # 결과 텍스트 생성
        results_text = "Scenario Evaluation Results:\n\n"
        
        for item in self.scenario_evaluation_items:
            results_text += f"• {item['name']}: {item['score']:.1f}\n"
        
        # 총점 계산
        total_score = sum(item['score'] for item in self.scenario_evaluation_items)
        avg_score = total_score / len(self.scenario_evaluation_items) if self.scenario_evaluation_items else 0
        
        results_text += f"\nTotal Score: {total_score:.1f}\n"
        results_text += f"Average Score: {avg_score:.1f}\n"
        
        # 성능 등급
        if avg_score >= 8.0:
            grade = "Excellent"
        elif avg_score >= 6.0:
            grade = "Good"
        elif avg_score >= 4.0:
            grade = "Fair"
        else:
            grade = "Poor"
        
        results_text += f"Performance Grade: {grade}"
        
        self.results_text.setPlainText(results_text)
        self.total_score_label.setText(f"Total Score: {total_score:.1f}")
    
    def add_logic_entry(self, entry_type, details, target_tab="general"):
        """로직 히스토리에 항목을 추가합니다."""
        import datetime
        
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        if entry_type == "evaluation_extraction":
            entry = f"[{timestamp}] 📊 Evaluation Item Extraction: {details}"
            self.evaluation_process_history.append(entry)
            self.update_extraction_history()
        elif entry_type == "scoring_process":
            entry = f"[{timestamp}] 📈 Scoring Process: {details}"
            self.scoring_process_history.append(entry)
            self.update_scoring_history()
        elif entry_type == "general_logic":
            entry = f"[{timestamp}] 🔍 {details}"
            self.logic_history.append(entry)
            self.update_general_logic()
        else:
            entry = f"[{timestamp}] {entry_type}: {details}"
            self.logic_history.append(entry)
            self.update_general_logic()
    
    def update_extraction_history(self):
        """평가 항목 추출 히스토리를 업데이트합니다."""
        recent_entries = self.evaluation_process_history[-15:]  # 최근 15개
        self.extraction_history_text.setPlainText("\n".join(recent_entries))
    
    def update_scoring_history(self):
        """스코어링 과정 히스토리를 업데이트합니다."""
        recent_entries = self.scoring_process_history[-15:]  # 최근 15개
        self.scoring_history_text.setPlainText("\n".join(recent_entries))
    
    def update_general_logic(self):
        """전체 로직 히스토리를 업데이트합니다."""
        recent_entries = self.logic_history[-15:]  # 최근 15개
        self.general_logic_text.setPlainText("\n".join(recent_entries))
    
    def track_evaluation_extraction(self, scenario_data):
        """평가 항목 추출 과정을 추적합니다."""
        self.add_logic_entry("evaluation_extraction", f"Starting evaluation extraction for scenario with {len(scenario_data.get('ships', []))} ships")
        
        # OWL 파일에서 평가 항목 추출 과정 추적
        if self.evaluation_items:
            class_count = len([item for item in self.evaluation_items if item['type'] == 'class'])
            property_count = len([item for item in self.evaluation_items if item['type'] == 'property'])
            
            self.add_logic_entry("evaluation_extraction", f"Found {class_count} classes and {property_count} properties in OWL file")
        
        # 시나리오 관련 항목 필터링 과정 추적
        if self.scenario_evaluation_items:
            self.add_logic_entry("evaluation_extraction", f"Filtered {len(self.scenario_evaluation_items)} relevant evaluation items for current scenario")
            
            for item in self.scenario_evaluation_items:
                self.add_logic_entry("evaluation_extraction", f"Selected item: {item['name']} (type: {item['type']})")
    
    def track_scoring_process(self, item_name, scoring_details):
        """스코어링 과정을 추적합니다."""
        self.add_logic_entry("scoring_process", f"Calculating score for '{item_name}': {scoring_details}")
    
    def check_evaluation_trigger(self, scenario_conditions):
        """평가 트리거 조건을 확인합니다."""
        # 시나리오 조건에 따른 평가 트리거 로직
        trigger_conditions = []
        
        if len(scenario_conditions.get('ships', [])) > 1:
            trigger_conditions.append("Multiple ships detected")
        
        if scenario_conditions.get('encounter_types'):
            trigger_conditions.append(f"Encounter types: {', '.join(scenario_conditions['encounter_types'])}")
        
        if trigger_conditions and not self.evaluation_triggered:
            self.evaluation_triggered = True
            trigger_reason = "; ".join(trigger_conditions)
            
            self.add_logic_entry("general_logic", f"⚠️ EVALUATION TRIGGERED: {trigger_reason}")
            
            # 성능평가 항목 추출 과정 추적
            self.track_evaluation_extraction(scenario_conditions)
            
            return True
        return False
    
    def calculate_performance_score(self, item_name, scenario_data):
        """성능평가 점수를 계산합니다."""
        # 간단한 점수 계산 로직 (실제로는 더 복잡한 알고리즘 필요)
        base_score = 5.0  # 기본 점수
        
        # 시나리오 조건에 따른 점수 조정
        ship_count = len(scenario_data.get('ships', []))
        encounter_types = scenario_data.get('encounter_types', [])
        
        # 선박 수에 따른 점수 조정
        if ship_count > 2:
            base_score += 1.0
        elif ship_count > 1:
            base_score += 0.5
        
        # 조우 유형에 따른 점수 조정
        if 'head_on' in encounter_types:
            base_score += 1.5
        if 'crossing' in encounter_types:
            base_score += 1.0
        if 'overtaking' in encounter_types:
            base_score += 0.5
        
        # 점수 범위 제한
        final_score = max(0.0, min(10.0, base_score))
        
        # 스코어링 과정 추적
        scoring_details = f"Base: {base_score:.1f}, Ships: {ship_count}, Encounters: {encounter_types}, Final: {final_score:.1f}"
        self.track_scoring_process(item_name, scoring_details)
        
        return final_score
    
    def export_behavior_history(self):
        """자선 행동 히스토리를 파일로 내보냅니다."""
        try:
            from PyQt5.QtWidgets import QFileDialog
            import pandas as pd
            import datetime
            
            if not self.behavior_history:
                QMessageBox.warning(self, "Warning", "No behavior history to export.")
                return
            
            # 파일 저장 다이얼로그
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export OS Behavior History", 
                f"os_behavior_history_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", 
                "Text Files (*.txt);;CSV Files (*.csv);;Excel Files (*.xlsx)"
            )
            
            if file_path:
                if file_path.endswith('.txt'):
                    # 텍스트 파일로 저장
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write("=== Own Ship Behavior History ===\n")
                        f.write(f"Exported on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"Total entries: {len(self.behavior_history)}\n")
                        f.write("="*50 + "\n\n")
                        for entry in self.behavior_history:
                            f.write(entry + "\n")
                            
                elif file_path.endswith(('.csv', '.xlsx')):
                    # CSV/Excel 파일로 저장
                    data = []
                    for entry in self.behavior_history:
                        # 시간과 내용 분리
                        if entry.startswith('[') and ']' in entry:
                            time_end = entry.find(']')
                            timestamp = entry[1:time_end]
                            details = entry[time_end+2:]  # '] ' 다음부터
                        else:
                            timestamp = ""
                            details = entry
                        
                        data.append({
                            'Timestamp': timestamp,
                            'Details': details,
                            'Full_Entry': entry
                        })
                    
                    df = pd.DataFrame(data)
                    if file_path.endswith('.csv'):
                        df.to_csv(file_path, index=False, encoding='utf-8')
                    else:
                        df.to_excel(file_path, index=False)
                
                QMessageBox.information(self, "Export Complete", f"OS Behavior history exported to:\n{file_path}")
                
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export behavior history:\n{str(e)}")
    
    def export_progress_history(self):
        """시나리오 진행 히스토리를 파일로 내보냅니다."""
        try:
            from PyQt5.QtWidgets import QFileDialog
            import pandas as pd
            import datetime
            
            if not self.progress_history:
                QMessageBox.warning(self, "Warning", "No progress history to export.")
                return
            
            # 파일 저장 다이얼로그
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Progress History", 
                f"scenario_progress_history_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", 
                "Text Files (*.txt);;CSV Files (*.csv);;Excel Files (*.xlsx)"
            )
            
            if file_path:
                if file_path.endswith('.txt'):
                    # 텍스트 파일로 저장
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write("=== Scenario Progress History ===\n")
                        f.write(f"Exported on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"Total entries: {len(self.progress_history)}\n")
                        f.write("="*50 + "\n\n")
                        for entry in self.progress_history:
                            f.write(entry + "\n")
                            
                elif file_path.endswith(('.csv', '.xlsx')):
                    # CSV/Excel 파일로 저장
                    data = []
                    for entry in self.progress_history:
                        # 시간과 내용 분리
                        if entry.startswith('[') and ']' in entry:
                            time_end = entry.find(']')
                            timestamp = entry[1:time_end]
                            details = entry[time_end+2:]  # '] ' 다음부터
                        else:
                            timestamp = ""
                            details = entry
                        
                        data.append({
                            'Timestamp': timestamp,
                            'Details': details,
                            'Full_Entry': entry
                        })
                    
                    df = pd.DataFrame(data)
                    if file_path.endswith('.csv'):
                        df.to_csv(file_path, index=False, encoding='utf-8')
                    else:
                        df.to_excel(file_path, index=False)
                
                QMessageBox.information(self, "Export Complete", f"Progress history exported to:\n{file_path}")
                
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export progress history:\n{str(e)}")

    def generate_geo_plot_from_ui(self):
        """UI에서 지오플롯을 생성합니다."""
        try:
            if not GEO_PLOT_AVAILABLE:
                QMessageBox.warning(self, "Warning", 
                    "Geo plotting libraries not available.\n"
                    "Please install: pip install folium geopandas shapely")
                return
            
            # 현재 캔버스 중심 좌표 사용
            center_lat = self.sim_canvas.center_lat
            center_lon = self.sim_canvas.center_lon
            
            # 지오플롯 생성
            m = self.sim_canvas.generate_geo_plot(center_lat, center_lon)
            
            if m:
                self.geo_plot_status_label.setText("Status: Generated successfully")
                self.geo_plot_status_label.setStyleSheet("color: #28a745; font-size: 10px;")
                self.geo_plot_info_label.setText(
                    f"Geo Plot created for center: {center_lat:.6f}°, {center_lon:.6f}°\n"
                    "Click 'Save' to export as HTML file"
                )
                
                # 진행 상황에 기록
                self.add_progress_entry(f"🗺️ Geo plot generated for center: {center_lat:.6f}°, {center_lon:.6f}°")
                
                QMessageBox.information(self, "Success", 
                    "Geo plot generated successfully!\n"
                    "Click 'Save' to export as interactive HTML map.")
            else:
                self.geo_plot_status_label.setText("Status: Generation failed")
                self.geo_plot_status_label.setStyleSheet("color: #dc3545; font-size: 10px;")
                QMessageBox.warning(self, "Warning", "Failed to generate geo plot.")
                
        except Exception as e:
            self.geo_plot_status_label.setText("Status: Error occurred")
            self.geo_plot_status_label.setStyleSheet("color: #dc3545; font-size: 10px;")
            QMessageBox.critical(self, "Error", f"Error generating geo plot: {str(e)}")
    
    def generate_geo_plot_from_ui(self):
        """UI에서 지오플롯을 생성합니다."""
        try:
            if not GEO_PLOT_AVAILABLE:
                QMessageBox.warning(self, "Warning", 
                    "Geo plotting libraries not available.\n"
                    "Please install: pip install folium geopandas shapely")
                return
            
            # 지오플롯 생성
            self.geo_plot_status_label.setText("Status: Generating...")
            self.geo_plot_status_label.setStyleSheet("color: #ffc107; font-size: 10px;")
            
            # 현재 중심 좌표 사용
            center_lat = getattr(self.sim_canvas, 'center_lat', 37.5665)
            center_lon = getattr(self.sim_canvas, 'center_lon', 126.9780)
            
            # 지오플롯 생성
            geo_plot = self.sim_canvas.generate_geo_plot(center_lat, center_lon)
            
            if geo_plot:
                self.geo_plot_status_label.setText("Status: Generated successfully")
                self.geo_plot_status_label.setStyleSheet("color: #28a745; font-size: 10px;")
                
                # 진행 상황에 기록
                self.add_progress_entry(f"🗺️ Geo plot generated successfully at ({center_lat:.4f}, {center_lon:.4f})")
                
                QMessageBox.information(self, "Success", 
                    "Geo plot generated successfully!\n\n"
                    f"Center coordinates: ({center_lat:.4f}, {center_lon:.4f})\n"
                    "Use the Save button to save the plot as HTML file.")
            else:
                self.geo_plot_status_label.setText("Status: Generation failed")
                self.geo_plot_status_label.setStyleSheet("color: #dc3545; font-size: 10px;")
                QMessageBox.warning(self, "Warning", "Failed to generate geo plot.")
                
        except Exception as e:
            self.geo_plot_status_label.setText("Status: Error occurred")
            self.geo_plot_status_label.setStyleSheet("color: #dc3545; font-size: 10px;")
            QMessageBox.critical(self, "Error", f"Error generating geo plot: {str(e)}")
    
    def save_geo_plot_from_ui(self):
        """UI에서 지오플롯을 저장합니다."""
        try:
            if not GEO_PLOT_AVAILABLE:
                QMessageBox.warning(self, "Warning", 
                    "Geo plotting libraries not available.\n"
                    "Please install: pip plotting libraries not available.\n"
                    "Please install: pip install folium geopandas shapely")
                return
            
            # 파일 저장 대화상자
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save Geo Plot", 
                "electronic_chart.html", "HTML Files (*.html)"
            )
            
            if filename:
                # 지오플롯 저장
                success = self.sim_canvas.save_geo_plot(filename)
                
                if success:
                    self.geo_plot_status_label.setText("Status: Saved successfully")
                    self.geo_plot_status_label.setStyleSheet("color: #28a745; font-size: 10px;")
                    
                    # 진행 상황에 기록
                    self.add_progress_entry(f"💾 Geo plot saved as: {filename}")
                    
                    QMessageBox.information(self, "Success", 
                        f"Geo plot saved successfully!\n"
                        f"File: {filename}\n\n"
                        "Open the HTML file in a web browser to view the interactive map.")
                else:
                    self.geo_plot_status_label.setText("Status: Save failed")
                    self.geo_plot_status_label.setStyleSheet("color: #dc3545; font-size: 10px;")
                    QMessageBox.warning(self, "Warning", "Failed to save geo plot.")
                    
        except Exception as e:
            self.geo_plot_status_label.setText("Status: Error occurred")
            self.geo_plot_status_label.setStyleSheet("color: #dc3545; font-size: 10px;")
            QMessageBox.critical(self, "Error", f"Error saving geo plot: {str(e)}")

    def toggle_debug_mode(self):
        """디버그 모드를 토글합니다."""
        self.debug_mode = not self.debug_mode
        self.debug_button.setChecked(self.debug_mode)
        
        # 캔버스의 디버그 모드도 동기화
        if hasattr(self, 'sim_canvas'):
            self.sim_canvas.set_debug_mode(self.debug_mode)
        
        self.add_progress_entry("🐛 Debug mode toggled")

class WheelSteeringWidget(QWidget):
    def __init__(self, title, min_val, max_val, default_val, parent=None):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val
        self.current_val = default_val
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                color: #495057;
                font-weight: bold;
                font-size: 10px;
                text-align: center;
            }
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Wheel dial
        self.dial = QDial()
        self.dial.setMinimum(min_val)
        self.dial.setMaximum(max_val)
        self.dial.setValue(default_val)
        self.dial.setNotchesVisible(True)
        self.dial.setWrapping(True)
        self.dial.setStyleSheet("""
            QDial {
                background-color: #f8f9fa;
                border: 2px solid #dee2e6;
                border-radius: 40px;
            }
            QDial::handle {
                background-color: #007bff;
                border: 2px solid #007bff;
                border-radius: 6px;
                width: 12px;
                height: 12px;
            }
            QDial::handle:hover {
                background-color: #0056b3;
                border-color: #0056b3;
            }
        """)
        self.dial.setFixedSize(80, 80)
        layout.addWidget(self.dial, alignment=Qt.AlignCenter)
        
        # Value display
        self.value_label = QLabel(f"{default_val:.1f}")
        self.value_label.setStyleSheet("""
            QLabel {
                color: #007bff;
                font-weight: bold;
                font-size: 11px;
                text-align: center;
                background-color: #e9ecef;
                border-radius: 4px;
                padding: 2px;
            }
        """)
        self.value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.value_label)
        
        self.dial.valueChanged.connect(self.update_value)
    
    def update_value(self):
        self.current_val = self.dial.value()
        self.value_label.setText(f"{self.current_val:.1f}")
    
    def value(self):
        return self.current_val
    
    def setValue(self, value):
        self.dial.setValue(int(value))
        self.current_val = value
        self.value_label.setText(f"{value:.1f}")

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