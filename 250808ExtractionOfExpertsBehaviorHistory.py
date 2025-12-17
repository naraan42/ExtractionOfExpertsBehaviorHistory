import sys
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, 
    QFileDialog, QLabel, QSlider, QGroupBox, QMessageBox, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QSplitter, QTextEdit, QScrollArea, QTabWidget, QDial,
    QSpinBox, QComboBox, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QPointF, QTimer
from PyQt5.QtGui import QColor, QPainter, QBrush, QPen, QFont, QLinearGradient, QPixmap
import math
import os
import xml.etree.ElementTree as ET

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
        self.center_lat = 0  # 중심 위도
        self.center_lon = 0  # 중심 경도
        self.os_heading = 0  # OS heading 초기값 설정
        
        # 전자해도 관련 속성들
        self.zoom_level = 1.0  # 줌 레벨
        self.chart_data = {}  # 해도 데이터
        self.landmarks = []  # 지형지물
        self.depth_contours = []  # 등심선
        self.navigation_aids = []  # 항로표지
        self.dangerous_areas = []  # 위험구역
        
        # 레이더 모드 관련 속성들
        self.center_mode = True  # True: 센터 모드 (트루모션), False: 오프센터 모드 (상대운동)
        self.center_lat = 0  # 중심 위도
        self.center_lon = 0  # 중심 경도
        
        # 샘플 해도 데이터 초기화
        self.initialize_chart_data()
        
        # 마우스 이벤트 활성화
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
    
    def initialize_chart_data(self):
        """샘플 해도 데이터를 초기화합니다"""
        # 샘플 지형지물 (위도, 경도, 타입, 이름)
        self.landmarks = [
            (37.5665, 126.9780, 'lighthouse', '인천등대'),
            (37.4565, 126.5980, 'buoy', '인천항 부표'),
            (37.4565, 126.5980, 'rock', '암초'),
            (37.4565, 126.5980, 'wreck', '침몰선박'),
            (37.4565, 126.5980, 'bridge', '인천대교'),
            (37.4565, 126.5980, 'port', '인천항'),
            (37.4565, 126.5980, 'anchorage', '정박지'),
            (37.4565, 126.5980, 'restricted_area', '제한구역'),
            (37.4565, 126.5980, 'traffic_separation', '분리통항로'),
            (37.4565, 126.5980, 'depth_area', '수심구역')
        ]
        
        # 샘플 등심선 (위도, 경도, 깊이)
        self.depth_contours = [
            (37.4565, 126.5980, 5),   # 5m 등심선
            (37.4565, 126.5980, 10),  # 10m 등심선
            (37.4565, 126.5980, 20),  # 20m 등심선
            (37.4565, 126.5980, 50),  # 50m 등심선
        ]
        
        # 샘플 항로표지
        self.navigation_aids = [
            (37.4565, 126.5980, 'cardinal_north', '북방표지'),
            (37.4565, 126.5980, 'cardinal_south', '남방표지'),
            (37.4565, 126.5980, 'cardinal_east', '동방표지'),
            (37.4565, 126.5980, 'cardinal_west', '서방표지'),
            (37.4565, 126.5980, 'isolated_danger', '고립위험표지'),
            (37.4565, 126.5980, 'safe_water', '안전수역표지'),
        ]
        
        # 샘플 위험구역
        self.dangerous_areas = [
            (37.4565, 126.5980, 'military', '군사훈련구역'),
            (37.4565, 126.5980, 'fishing', '어업구역'),
            (37.4565, 126.5980, 'environmental', '환경보호구역'),
        ]

    def set_ships(self, ownship, ships):
        self.ownship = ownship
        self.ships = ships
        # OS heading 업데이트
        if ownship and isinstance(ownship, dict) and 'heading' in ownship:
            self.os_heading = ownship['heading']
        elif ownship and hasattr(ownship, 'heading'):
            self.os_heading = ownship.heading
        self.update()
    
    def set_center_coordinates(self, lat, lon):
        """중심 좌표를 설정합니다 (진모션용)"""
        self.center_lat = lat
        self.center_lon = lon
        self.update()
    
    def set_os_heading(self, heading):
        """OS heading을 설정합니다"""
        self.os_heading = heading
        self.update()

    def paintEvent(self, event):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        
        # 전자해도 스타일 배경 (어두운 바다 색상)
        qp.fillRect(self.rect(), QColor(10, 20, 40))
        
        # 화면 중심점 (자선 위치)
        center_x, center_y = self.width() // 2, self.height() // 2
        
        # 줌 레벨에 따른 스케일 계산
        scale = self.scale_factor * self.zoom_level
        
        # 해도 그리드 그리기
        self.draw_chart_grid(qp, center_x, center_y, scale)
        
        # 등심선 그리기
        self.draw_depth_contours(qp, center_x, center_y, scale)
        
        # 지형지물 그리기
        self.draw_landmarks(qp, center_x, center_y, scale)
        
        # 항로표지 그리기
        self.draw_navigation_aids(qp, center_x, center_y, scale)
        
        # 위험구역 그리기
        self.draw_dangerous_areas(qp, center_x, center_y, scale)
        
        # 레이더 모드에 따라 자선과 타겟 선박 그리기
        if self.center_mode:
            # 센터 모드 (트루모션): 자선이 중앙에 고정, 타겟 선박이 실제 위치에 표시
            if self.ownship:
                self.draw_ship(qp, center_x, center_y, self.os_heading, 'os', 0)
            
            # 타겟 선박을 실제 위치에 그리기
            self.draw_target_ships_true_motion(qp, center_x, center_y, scale)
        else:
            # 오프센터 모드 (상대운동): 자선이 중앙에 고정, 타겟 선박이 상대 위치에 표시
            if self.ownship:
                self.draw_ship(qp, center_x, center_y, self.os_heading, 'os', 0)
            
            # 타겟 선박을 상대 위치에 그리기
            self.draw_target_ships(qp, center_x, center_y, scale)
        
        # 거리 및 방위 정보 표시
        self.draw_navigation_info(qp, center_x, center_y)

    def draw_ship(self, qp, x, y, heading, color, bearing):
        qp.save()
        qp.translate(int(x), int(y))
        
        # 모든 선박은 heading 방향으로 배 모양 회전 (일관성 유지)
        qp.rotate(-heading)
        
        if color == 'os':
            pen_color = QColor(13, 110, 253)  # Modern blue
            brush_color = QColor(13, 110, 253, 180)
            size = 18
        else:
            pen_color = color
            brush_color = color
            size = 12
            
        # 날렵한 배 모양 (선박 형태) - 선수 방향이 위쪽(0도)
        ship_points = [
            QPointF(0, -size),                    # 뾰족한 앞부분 (선수)
            QPointF(-size * 0.3, -size * 0.5),   # 왼쪽 앞부분
            QPointF(-size * 0.4, size * 0.3),    # 왼쪽 중간
            QPointF(-size * 0.3, size * 0.8),    # 왼쪽 뒤
            QPointF(0, size),                     # 뒤쪽 끝 (선미)
            QPointF(size * 0.3, size * 0.8),     # 오른쪽 뒤
            QPointF(size * 0.4, size * 0.3),     # 오른쪽 중간
            QPointF(size * 0.3, -size * 0.5),    # 오른쪽 앞부분
        ]
        
        qp.setPen(QPen(pen_color, 3))
        qp.setBrush(QBrush(brush_color))
        qp.drawPolygon(*ship_points)
        
        # Ship shadow for depth
        qp.setPen(QPen(QColor(0, 0, 0, 30), 1))
        qp.setBrush(QBrush(QColor(0, 0, 0, 20)))
        shadow_points = [QPointF(p.x() + 2, p.y() + 2) for p in ship_points]
        qp.drawPolygon(*shadow_points)
        
        qp.restore()
        
        # 진행방향 벡터 (화살표) - 12분 후 도달 위치 표시
        qp.save()
        qp.translate(x, y)
        
        # 6분 후 도달 거리 계산 (속도 기반)
        # 1 knot = 1 NM/hour, 6분 = 0.1시간
        # 기본 속도 12 knots로 가정, 6분 = 12 * 0.1 = 1.2 NM
        # 화면에서 1NM = 약 80 pixels (canvas scale)
        time_minutes = 6  # 6분
        default_speed_knots = 12  # 기본 속도 (knots)
        distance_nm = (default_speed_knots * time_minutes) / 60.0  # NM
        pixels_per_nm = 80  # 화면에서 1NM당 픽셀 수
        arrow_len = distance_nm * pixels_per_nm
        
        # 최소/최대 길이 제한
        arrow_len = max(15, min(arrow_len, 60))  # 15-60 pixels 범위 (더 짧게)
        
        qp.setPen(QPen(QColor(33, 37, 41), 2, Qt.SolidLine))
        
        # 모든 선박은 heading 방향으로 화살표 표시 (일관성 유지)
        end_x = arrow_len * math.sin(math.radians(heading))
        end_y = -arrow_len * math.cos(math.radians(heading))
        arrow_rad = math.radians(heading)
            
        qp.drawLine(QPointF(0, 0), QPointF(end_x, end_y))
        # 화살촉
        head_size = max(4, arrow_len // 8)  # 화살표 길이에 비례한 화살촉 크기
        for angle in [math.pi / 6, -math.pi / 6]:
            hx = end_x - head_size * math.sin(arrow_rad + angle)
            hy = end_y + head_size * math.cos(arrow_rad + angle)
            qp.drawLine(QPointF(end_x, end_y), QPointF(hx, hy))
        qp.restore()
    
    def draw_chart_grid(self, qp, center_x, center_y, scale):
        """해도 그리드를 그립니다"""
        # 전자해도 스타일 그리드
        qp.setPen(QPen(QColor(50, 100, 150), 1))
        
        # 수직/수평 그리드 라인
        grid_spacing = scale // 2  # 0.5NM 간격
        for i in range(-10, 11):
            x = int(center_x + i * grid_spacing)
            y = int(center_y + i * grid_spacing)
            
            # 수직선
            if 0 <= x <= self.width():
                qp.drawLine(x, 0, x, self.height())
            
            # 수평선
            if 0 <= y <= self.height():
                qp.drawLine(0, y, self.width(), y)
        
        # 거리 원 그리기
        for r in [scale, scale * 2, scale * 3, scale * 4, scale * 5]:
            qp.setPen(QPen(QColor(50, 100, 150), 1, Qt.DashLine))
            qp.drawEllipse(QPointF(center_x, center_y), r, r)
            
            # 거리 라벨
            qp.setPen(QPen(QColor(100, 150, 200), 1))
            qp.setFont(QFont("Arial", 8))
            qp.drawText(QPointF(center_x + r + 5, center_y), f"{r/scale:.1f}NM")
    
    def draw_depth_contours(self, qp, center_x, center_y, scale):
        """등심선을 그립니다"""
        qp.setPen(QPen(QColor(0, 150, 255), 1, Qt.DashLine))
        
        for lat, lon, depth in self.depth_contours:
            # 위경도를 화면 좌표로 변환
            x, y = self.convert_latlon_to_xy(lat, lon, self.center_lat, self.center_lon)
            x = int(center_x + x * self.zoom_level)
            y = int(center_y + y * self.zoom_level)
            
            # 깊이에 따른 색상
            if depth <= 10:
                color = QColor(255, 255, 0)  # 노란색 (얕은 곳)
            elif depth <= 20:
                color = QColor(0, 255, 0)    # 초록색
            elif depth <= 50:
                color = QColor(0, 150, 255)  # 파란색
            else:
                color = QColor(0, 0, 255)    # 진한 파란색 (깊은 곳)
            
            qp.setPen(QPen(color, 2, Qt.DashLine))
            qp.drawEllipse(QPointF(x, y), 10, 10)
            
            # 깊이 라벨
            qp.setPen(QPen(color, 1))
            qp.setFont(QFont("Arial", 7))
            qp.drawText(QPointF(x + 15, y + 5), f"{depth}m")
    
    def draw_landmarks(self, qp, center_x, center_y, scale):
        """지형지물을 그립니다"""
        for lat, lon, landmark_type, name in self.landmarks:
            # 위경도를 화면 좌표로 변환
            x, y = self.convert_latlon_to_xy(lat, lon, self.center_lat, self.center_lon)
            x = int(center_x + x * self.zoom_level)
            y = int(center_y + y * self.zoom_level)
            
            # 지형지물 타입에 따른 색상과 모양
            if landmark_type == 'lighthouse':
                color = QColor(255, 255, 0)  # 노란색
                self.draw_lighthouse(qp, x, y)
            elif landmark_type == 'buoy':
                color = QColor(255, 0, 0)    # 빨간색
                self.draw_buoy(qp, x, y)
            elif landmark_type == 'rock':
                color = QColor(255, 0, 0)    # 빨간색
                self.draw_rock(qp, x, y)
            elif landmark_type == 'wreck':
                color = QColor(255, 0, 0)    # 빨간색
                self.draw_wreck(qp, x, y)
            elif landmark_type == 'bridge':
                color = QColor(150, 150, 150) # 회색
                self.draw_bridge(qp, x, y)
            elif landmark_type == 'port':
                color = QColor(0, 255, 0)    # 초록색
                self.draw_port(qp, x, y)
            elif landmark_type == 'anchorage':
                color = QColor(255, 255, 0)  # 노란색
                self.draw_anchorage(qp, x, y)
            elif landmark_type == 'restricted_area':
                color = QColor(255, 0, 255)  # 마젠타
                self.draw_restricted_area(qp, x, y)
            elif landmark_type == 'traffic_separation':
                color = QColor(0, 255, 255)  # 시안
                self.draw_traffic_separation(qp, x, y)
            elif landmark_type == 'depth_area':
                color = QColor(0, 150, 255)  # 파란색
                self.draw_depth_area(qp, x, y)
            
            # 이름 라벨
            qp.setPen(QPen(color, 1))
            qp.setFont(QFont("Arial", 8))
            qp.drawText(QPointF(x + 15, y + 5), name)
    
    def draw_navigation_aids(self, qp, center_x, center_y, scale):
        """항로표지를 그립니다"""
        for lat, lon, aid_type, name in self.navigation_aids:
            # 위경도를 화면 좌표로 변환
            x, y = self.convert_latlon_to_xy(lat, lon, self.center_lat, self.center_lon)
            x = int(center_x + x * self.zoom_level)
            y = int(center_x + y * self.zoom_level)
            
            # 항로표지 타입에 따른 그리기
            if 'cardinal' in aid_type:
                self.draw_cardinal_mark(qp, x, y, aid_type)
            elif aid_type == 'isolated_danger':
                self.draw_isolated_danger_mark(qp, x, y)
            elif aid_type == 'safe_water':
                self.draw_safe_water_mark(qp, x, y)
            
            # 이름 라벨
            qp.setPen(QPen(QColor(255, 255, 255), 1))
            qp.setFont(QFont("Arial", 7))
            qp.drawText(QPointF(x + 15, y + 5), name)
    
    def draw_dangerous_areas(self, qp, center_x, center_y, scale):
        """위험구역을 그립니다"""
        for lat, lon, area_type, name in self.dangerous_areas:
            # 위경도를 화면 좌표로 변환
            x, y = self.convert_latlon_to_xy(lat, lon, self.center_lat, self.center_lon)
            x = int(center_x + x * self.zoom_level)
            y = int(center_y + y * self.zoom_level)
            
            # 위험구역 타입에 따른 색상
            if area_type == 'military':
                color = QColor(255, 0, 0)    # 빨간색
            elif area_type == 'fishing':
                color = QColor(255, 165, 0)  # 주황색
            elif area_type == 'environmental':
                color = QColor(0, 255, 0)    # 초록색
            
            # 위험구역 표시
            qp.setPen(QPen(color, 2, Qt.DashLine))
            qp.setBrush(QBrush(color, Qt.DiagCrossPattern))
            qp.drawEllipse(QPointF(x, y), 20, 20)
            
            # 이름 라벨
            qp.setPen(QPen(color, 1))
            qp.setFont(QFont("Arial", 8))
            qp.drawText(QPointF(x + 25, y + 5), name)
    
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
                
                # 회전된 좌표로 TS 그리기 (상대 heading)
                relative_heading = (ship['heading'] - self.os_heading) % 360
                self.draw_ship(qp, center_x + rotated_x, center_y + rotated_y, 
                              relative_heading, ship['color'], relative_heading)
            elif isinstance(ship, tuple) and len(ship) == 5:
                # 튜플 형태의 경우도 동일하게 처리
                x, y, heading, color, bearing = ship
                rel_x = x - center_x
                rel_y = y - center_y
                
                cos_h = math.cos(math.radians(self.os_heading))
                sin_h = math.sin(math.radians(self.os_heading))
                rotated_x = rel_x * cos_h + rel_y * sin_h
                rotated_y = -rel_x * sin_h + rel_y * cos_h
                
                relative_heading = (heading - self.os_heading) % 360
                self.draw_ship(qp, center_x + rotated_x, center_y + rotated_y,
                              relative_heading, color, relative_heading)
    
    def draw_target_ships_true_motion(self, qp, center_x, center_y, scale):
        """타겟 선박을 그립니다 (트루모션)"""
        for ship in self.ships:
            if isinstance(ship, dict):
                # TS를 실제 위치에 그리기 (OS heading 회전 없음)
                self.draw_ship(qp, ship['x'], ship['y'], ship['heading'], ship['color'], ship['bearing'])
            elif isinstance(ship, tuple) and len(ship) == 5:
                # 튜플 형태의 경우도 동일하게 처리
                x, y, heading, color, bearing = ship
                self.draw_ship(qp, x, y, heading, color, bearing)
    
    def draw_navigation_info(self, qp, center_x, center_y):
        """항해 정보를 표시합니다"""
        # GPS 좌표 정보
        qp.setPen(QPen(QColor(255, 255, 255), 1))
        qp.setFont(QFont("Arial", 10))
        
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
            qp.drawText(QPointF(10, 70), f"Heading: {actual_heading:.1f}°")
            qp.drawText(QPointF(10, 90), f"Speed: {actual_speed:.1f} kts")
        else:
            # 기본값 표시
            qp.drawText(QPointF(10, 30), f"Lat: {self.center_lat:.6f}°")
            qp.drawText(QPointF(10, 50), f"Lon: {self.center_lon:.6f}°")
            qp.drawText(QPointF(10, 70), f"Heading: {self.os_heading:.1f}°")
            qp.drawText(QPointF(10, 90), f"Speed: -- kts")
        
        qp.drawText(QPointF(10, 110), f"Zoom: {self.zoom_level:.1f}x")
        
        # 컨트롤 모드 표시
        if hasattr(self, 'os_control_mode'):
            mode_text = "Manual Control" if self.os_control_mode else "AIS Auto"
            mode_color = QColor(220, 53, 69) if self.os_control_mode else QColor(40, 167, 69)
            qp.setPen(QPen(mode_color, 1))
            qp.setFont(QFont("Arial", 9, QFont.Bold))
            qp.drawText(QPointF(10, 130), f"Mode: {mode_text}")
        
        # 레이더 모드 표시
        if hasattr(self, 'center_mode'):
            radar_mode_text = "CEN (True Motion)" if self.center_mode else "OFF (Relative Motion)"
            radar_mode_color = QColor(0, 123, 255) if self.center_mode else QColor(253, 126, 20)
            qp.setPen(QPen(radar_mode_color, 1))
            qp.setFont(QFont("Arial", 9, QFont.Bold))
            qp.drawText(QPointF(10, 150), f"Radar: {radar_mode_text}")
        
        # 방위 정보
        qp.setPen(QPen(QColor(255, 255, 255), 1))
        qp.setFont(QFont("Arial", 10))
        qp.drawText(QPointF(10, 170), "N")
        qp.drawText(QPointF(center_x - 5, 20), "N")
        qp.drawText(QPointF(self.width() - 20, center_y + 5), "E")
        qp.drawText(QPointF(center_x - 5, self.height() - 10), "S")
        qp.drawText(QPointF(20, center_y + 5), "W")
    
    # 지형지물 그리기 헬퍼 메서드들
    def draw_lighthouse(self, qp, x, y):
        """등대를 그립니다"""
        qp.setPen(QPen(QColor(255, 255, 0), 2))
        qp.setBrush(QBrush(QColor(255, 255, 0)))
        qp.drawRect(x - 8, y - 8, 16, 16)
        qp.drawLine(x, y - 8, x, y - 15)
    
    def draw_buoy(self, qp, x, y):
        """부표를 그립니다"""
        qp.setPen(QPen(QColor(255, 0, 0), 2))
        qp.setBrush(QBrush(QColor(255, 0, 0)))
        qp.drawEllipse(QPointF(x, y), 6, 6)
    
    def draw_rock(self, qp, x, y):
        """암초를 그립니다"""
        qp.setPen(QPen(QColor(255, 0, 0), 2))
        qp.setBrush(QBrush(QColor(255, 0, 0)))
        qp.drawPolygon([QPointF(x-5, y+5), QPointF(x+5, y+5), QPointF(x, y-5)])
    
    def draw_wreck(self, qp, x, y):
        """침몰선박을 그립니다"""
        qp.setPen(QPen(QColor(255, 0, 0), 2))
        qp.drawLine(x-8, y+8, x+8, y-8)
        qp.drawLine(x-8, y-8, x+8, y+8)
    
    def draw_bridge(self, qp, x, y):
        """다리를 그립니다"""
        qp.setPen(QPen(QColor(150, 150, 150), 3))
        qp.drawLine(x-10, y, x+10, y)
    
    def draw_port(self, qp, x, y):
        """항구를 그립니다"""
        qp.setPen(QPen(QColor(0, 255, 0), 2))
        qp.setBrush(QBrush(QColor(0, 255, 0)))
        qp.drawRect(x - 10, y - 10, 20, 20)
    
    def draw_anchorage(self, qp, x, y):
        """정박지를 그립니다"""
        qp.setPen(QPen(QColor(255, 255, 0), 2))
        qp.setBrush(QBrush(QColor(255, 255, 0), Qt.DiagCrossPattern))
        qp.drawEllipse(QPointF(x, y), 15, 15)
    
    def draw_restricted_area(self, qp, x, y):
        """제한구역을 그립니다"""
        qp.setPen(QPen(QColor(255, 0, 255), 2, Qt.DashLine))
        qp.setBrush(QBrush(QColor(255, 0, 255), Qt.DiagCrossPattern))
        qp.drawEllipse(QPointF(x, y), 25, 25)
    
    def draw_traffic_separation(self, qp, x, y):
        """분리통항로를 그립니다"""
        qp.setPen(QPen(QColor(0, 255, 255), 2, Qt.DashLine))
        qp.drawLine(x-20, y, x+20, y)
        qp.drawLine(x, y-20, x, y+20)
    
    def draw_depth_area(self, qp, x, y):
        """수심구역을 그립니다"""
        qp.setPen(QPen(QColor(0, 150, 255), 2))
        qp.setBrush(QBrush(QColor(0, 150, 255), Qt.Dense4Pattern))
        qp.drawEllipse(QPointF(x, y), 20, 20)
    
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
        # 간단한 위경도 변환 (더 정확한 변환을 위해서는 프로젝션 라이브러리 사용 권장)
        lat_diff = lat - center_lat
        lon_diff = lon - center_lon
        
        # 1도 = 약 60NM, 1NM = 70 pixels
        x = lon_diff * 60 * 70  # 경도 차이를 픽셀로 변환
        y = -lat_diff * 60 * 70  # 위도 차이를 픽셀로 변환 (y축은 반대)
        
        return x, y
    
    def wheelEvent(self, event):
        """마우스 휠로 줌 인/아웃"""
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom_level = min(self.zoom_level * 1.2, 5.0)  # 최대 5배 줌
        else:
            self.zoom_level = max(self.zoom_level / 1.2, 0.2)  # 최소 0.2배 줌
        self.update()
    
    def mousePressEvent(self, event):
        """마우스 클릭 이벤트"""
        if event.button() == Qt.LeftButton:
            # 좌클릭으로 자선 위치 이동
            new_x = event.x()
            new_y = event.y()
            
            # 화면 중심을 기준으로 상대 위치 계산
            center_x = self.width() // 2
            center_y = self.height() // 2
            
            # 새로운 중심 좌표 계산 (위경도로 변환)
            rel_x = (new_x - center_x) / (self.scale_factor * self.zoom_level)
            rel_y = (new_y - center_y) / (self.scale_factor * self.zoom_level)
            
            # 위경도로 변환 (간단한 역변환)
            new_lat = self.center_lat - rel_y / (60 * 70)
            new_lon = self.center_lon + rel_x / (60 * 70)
            
            # 중심 좌표 업데이트
            self.center_lat = new_lat
            self.center_lon = new_lon
            self.update()
    
    def keyPressEvent(self, event):
        """키보드 이벤트"""
        if event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            # + 키로 줌 인
            self.zoom_level = min(self.zoom_level * 1.2, 5.0)
            self.update()
        elif event.key() == Qt.Key_Minus:
            # - 키로 줌 아웃
            self.zoom_level = max(self.zoom_level / 1.2, 0.2)
            self.update()
        elif event.key() == Qt.Key_0:
            # 0 키로 줌 리셋
            self.zoom_level = 1.0
            self.update()
        elif event.key() == Qt.Key_Up:
            # 화살표 키로 자선 위치 이동
            self.center_lat += 0.001
            self.update()
        elif event.key() == Qt.Key_Down:
            self.center_lat -= 0.001
            self.update()
        elif event.key() == Qt.Key_Left:
            self.center_lon -= 0.001
            self.update()
        elif event.key() == Qt.Key_Right:
            self.center_lon += 0.001
            self.update()

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
        # 간단한 위경도 변환 (더 정확한 변환을 위해서는 프로젝션 라이브러리 사용 권장)
        lat_diff = lat - center_lat
        lon_diff = lon - center_lon
        
        # 1도 = 약 60NM, 1NM = 70 pixels
        x = lon_diff * 60 * 70  # 경도 차이를 픽셀로 변환
        y = -lat_diff * 60 * 70  # 위도 차이를 픽셀로 변환 (y축은 반대)
        
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
        
        # 레이더 모드 관련 변수
        self.radar_center_mode = True  # True: 센터 모드 (트루모션), False: 오프센터 모드 (상대운동)
        
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
        
        # 초기 샘플 데이터 설정
        self.setup_sample_ships()
        
        # 초기 UI 상태 설정
        self.update_control_mode_ui()

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
        
        # 레이더 모드 선택 (하단에 작은 버튼으로)
        radar_separator = QLabel("─" * 20)
        radar_separator.setStyleSheet("color: #6c757d; font-size: 10px;")
        radar_separator.setAlignment(Qt.AlignCenter)
        control_layout.addWidget(radar_separator)
        
        # 레이더 모드 라벨
        radar_label = QLabel("Radar Mode:")
        radar_label.setStyleSheet("color: #495057; font-size: 9px; font-weight: bold;")
        radar_label.setAlignment(Qt.AlignCenter)
        control_layout.addWidget(radar_label)
        
        # 레이더 모드 버튼들
        radar_mode_layout = QHBoxLayout()
        
        self.center_mode_button = QPushButton("CEN")
        self.center_mode_button.setCheckable(True)
        self.center_mode_button.setChecked(True)  # 기본값
        self.center_mode_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                font-weight: bold;
                padding: 3px 6px;
                border-radius: 3px;
                font-size: 8px;
                min-width: 35px;
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
        self.center_mode_button.clicked.connect(lambda: self.set_radar_mode(True))
        radar_mode_layout.addWidget(self.center_mode_button)
        
        self.offcenter_mode_button = QPushButton("OFF")
        self.offcenter_mode_button.setCheckable(True)
        self.offcenter_mode_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                padding: 3px 6px;
                border-radius: 3px;
                font-size: 8px;
                min-width: 35px;
            }
            QPushButton:checked {
                background-color: #fd7e14;
                border: 2px solid #ffffff;
            }
            QPushButton:!checked {
                background-color: #6c757d;
            }
            QPushButton:hover {
                background-color: #e8690b;
            }
        """)
        self.offcenter_mode_button.clicked.connect(lambda: self.set_radar_mode(False))
        radar_mode_layout.addWidget(self.offcenter_mode_button)
        
        control_layout.addLayout(radar_mode_layout)
        
        # 레이더 모드 상태 표시
        self.radar_mode_label = QLabel("Mode: CEN")
        self.radar_mode_label.setStyleSheet("color: #007bff; font-weight: bold; font-size: 8px;")
        self.radar_mode_label.setAlignment(Qt.AlignCenter)
        control_layout.addWidget(self.radar_mode_label)
        
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
        
        parent_layout.addWidget(info_group)

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
    
    def apply_weather_to_ships(self, ownship, ships):
        """기상 효과를 선박에 적용합니다."""
        # 풍속에 따른 속도 영향
        wind_speed_effect = self.weather_data['wind_speed'] * 0.1
        ownship['speed'] += wind_speed_effect
        
        # 스트림에 따른 위치 변화
        stream_direction_angle = self.get_direction_angle(self.weather_data['stream_direction'])
        stream_speed_effect = self.weather_data['stream_speed'] * 0.05
        
        # 스트림 방향으로 위치 이동
        stream_x = math.cos(math.radians(stream_direction_angle)) * stream_speed_effect
        stream_y = math.sin(math.radians(stream_direction_angle)) * stream_speed_effect
        
        ownship['x'] += stream_x
        ownship['y'] += stream_y
        
        # 파고에 따른 안정성 영향 (속도 변화)
        wave_effect = self.weather_data['wave_height'] * 0.02
        ownship['speed'] *= (1 - wave_effect)
        
        # 시정에 따른 탐지 거리 영향
        visibility_effect = min(self.weather_data['visibility'], 20) / 20
        
        # 기상 효과를 행동 히스토리에 기록
        self.add_progress_entry(f"Weather applied to OS - Speed: {ownship['speed']:.1f} kts, Position: ({ownship['x']:.1f}, {ownship['y']:.1f}), Visibility: {visibility_effect:.2f}")
    
    def get_direction_angle(self, direction):
        """16방위법을 각도로 변환합니다."""
        direction_map = {
            "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5,
            "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
            "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
            "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5
        }
        return direction_map.get(direction, 0)

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
        
        # 시뮬레이션 초기화
        self.current_time = 0
        self.current_time_index = 0
        self.os_trajectory = []
        self.ts_trajectories = {}
        self.behavior_history = []
        
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
        
        # 초기 상태로 복원
        self.setup_sample_ships()
        self.os_initial_position_set = False
        
        self.add_progress_entry("⏹ Simulation stopped")

    def update_simulation(self):
        """시뮬레이션을 업데이트합니다."""
        if not self.ship_data:
            self.stop_simulation()
            return
        
        try:
            # 시나리오 종료 시간 확인
            if self.current_time >= self.scenario_end_time:
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
                    ownship = {
                        'x': self.os_manual_position['x'],
                        'y': self.os_manual_position['y'],
                        'heading': self.os_manual_position['heading'],
                        'speed': self.os_manual_position['speed'],
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
                    ownship = {
                        'x': center_x,
                        'y': center_y,
                        'heading': os_data['co'],
                        'speed': os_data['spd'],
                        'bearing': 0
                    }
                    center_lat, center_lon = os_data['lat'], os_data['lon']
                    
                    # 캔버스 중심 좌표 업데이트
                    self.sim_canvas.set_center_coordinates(center_lat, center_lon)
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
                    
                    ships.append({
                        'x': center_x + x,
                        'y': center_y + y,
                        'heading': ts_data['co'],
                        'speed': ts_data['spd'],
                        'color': ship_colors[i % len(ship_colors)],
                        'bearing': ts_data['co']
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
            
            # 진행률 업데이트
            self.current_time_index += 1
            self.current_time += 1
            progress = (self.current_time / self.scenario_end_time) * 100
            self.progress_bar.setValue(int(progress))
            
        except Exception as e:
            print(f"Simulation update error: {e}")
            self.stop_simulation()
    
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
        progress_percent = (self.current_time / self.scenario_end_time) * 100
        self.add_progress_entry(f"Scenario progress: {progress_percent:.1f}% ({self.current_time}/{self.scenario_end_time}s)")
    
    def complete_scenario(self):
        """시나리오를 완료합니다."""
        self.is_scenario_completed = True
        self.stop_simulation()
        
        # 시나리오 완료 메시지
        self.add_progress_entry("🎯 SCENARIO COMPLETED")
        self.add_progress_entry("✅ Scenario completed successfully")
        
        # 궤적 추출 버튼 활성화
        self.extract_trajectory_button.setEnabled(True)
        
        QMessageBox.information(self, "Scenario Complete", "Scenario has been completed successfully. You can now extract trajectory data.")

    def setup_sample_ships(self):
        """샘플 선박 데이터를 설정합니다."""
        center_x, center_y = self.sim_canvas.width() // 2, self.sim_canvas.height() // 2
        
        # Own ship at center only
        ownship = {
            'x': center_x,
            'y': center_y,
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
                
                # 초기 위치 설정
                center_x, center_y = self.sim_canvas.width() // 2, self.sim_canvas.height() // 2
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

    def set_radar_mode(self, is_center):
        """레이더 모드를 설정합니다."""
        self.radar_center_mode = is_center
        
        if is_center:
            # 센터 모드 (트루모션)
            self.center_mode_button.setChecked(True)
            self.offcenter_mode_button.setChecked(False)
            self.radar_mode_label.setText("Mode: CEN")
            self.radar_mode_label.setStyleSheet("color: #007bff; font-weight: bold; font-size: 8px;")
            
            # 캔버스 모드 업데이트
            self.sim_canvas.center_mode = True
            
            self.add_progress_entry("🎯 Switched to Center Mode (True Motion)")
        else:
            # 오프센터 모드 (상대운동)
            self.center_mode_button.setChecked(False)
            self.offcenter_mode_button.setChecked(True)
            self.radar_mode_label.setText("Mode: OFF")
            self.radar_mode_label.setStyleSheet("color: #fd7e14; font-weight: bold; font-size: 8px;")
            
            # 캔버스 모드 업데이트
            self.sim_canvas.center_mode = False
            
            self.add_progress_entry("🎯 Switched to Off-Center Mode (Relative Motion)")
        
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
        self.sim_canvas = SimCanvas()
        self.sim_canvas.setMinimumSize(900, 700)

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
                
                QMessageBox.information(self, "Success", f"{ship_id} data loaded successfully.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading {ship_id} file:\n{str(e)}")
    
    def update_data_info(self):
        """전체 데이터 정보를 업데이트합니다."""
        if not self.ship_data:
            self.data_info_label.setText("Data Info: None")
            return
        
        total_ships = len(self.ship_data)
        time_ranges = []
        
        for ship_id, data in self.ship_data.items():
            if 'time' in data.columns:
                time_range = f"{data['time'].min()} ~ {data['time'].max()}"
                time_ranges.append(f"{ship_id}: {time_range}")
        
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
    app = QApplication(sys.argv)
    window = SimulatorWindow()
    window.show()
    sys.exit(app.exec_()) 