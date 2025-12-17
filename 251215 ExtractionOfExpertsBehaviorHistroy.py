# -*- coding: utf-8 -*-
"""
Expert Behavior History Extraction Tool for Inverse Reinforcement Learning
Streamlit-based web application for extracting and editing expert ship trajectories
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

# Fix encoding issues on Windows with non-ASCII paths
import sys
import os

if sys.platform == 'win32':
    # Set UTF-8 encoding for Windows
    try:
        if hasattr(sys, 'setdefaultencoding'):
            sys.setdefaultencoding('utf-8')
    except AttributeError:
        # Python 3 doesn't have setdefaultencoding
        pass
    
    # Fix path encoding issues
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['STREAMLIT_SERVER_ENCODING'] = 'utf-8'
    
    # Fix for paths with non-ASCII characters (Korean, etc.)
    # Get the script's directory and set it as working directory
    # This ensures all relative paths work correctly regardless of where Streamlit is launched from
    try:
        # Get the absolute path of the script file
        script_file = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_file)
        
        # Change to script directory to ensure relative paths work
        if os.path.exists(script_dir):
            os.chdir(script_dir)
            # Store script directory for later use
            SCRIPT_DIR = script_dir
        else:
            # Fallback to current directory
            SCRIPT_DIR = os.getcwd()
    except (UnicodeDecodeError, OSError, Exception) as e:
        # If path encoding fails, try to use current directory
        try:
            SCRIPT_DIR = os.getcwd()
        except:
            SCRIPT_DIR = "."
else:
    # Non-Windows: also set script directory
    try:
        script_file = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_file)
        if os.path.exists(script_dir):
            os.chdir(script_dir)
            SCRIPT_DIR = script_dir
        else:
            SCRIPT_DIR = os.getcwd()
    except:
        SCRIPT_DIR = os.getcwd() if os.path.exists(os.getcwd()) else "."

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time
import math
from datetime import datetime
from scipy.interpolate import interp1d
import requests
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
import json

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="Ship Collision Avoidance IRL Tool", layout="wide")

# KHOA API 인증키 설정
# 국립해양조사원(KHOA) 전자해도 API
# API 문서: http://www.khoa.go.kr/oceanmap/main.do
KHOA_API_KEY = "C944511B6F85ECFC156B34455"
# KHOA API는 여러 URL 형식을 지원할 수 있습니다
KHOA_TILE_BASE_URL_OPTIONS = [
    "https://www.khoa.go.kr/api/oceanmap/tiles",  # 옵션 1
    "https://api.khoa.go.kr/oceanmap/tiles",      # 옵션 2
    "https://www.khoa.go.kr/oceanmap/tiles"       # 옵션 3
]
# 참고: KHOA API 타일 레이어는 "ENC", "chart", "haareum" 등을 사용할 수 있습니다.

# 데이터 저장소 폴더 생성 (스크립트 디렉토리 기준)
# Create save directory using absolute path
# 기본 저장 경로 설정
DEFAULT_SAVE_DIR = os.path.join(SCRIPT_DIR, "expert_data")
if not os.path.exists(DEFAULT_SAVE_DIR):
    try:
        os.makedirs(DEFAULT_SAVE_DIR, exist_ok=True)
    except Exception as e:
        # If creation fails, try current directory
        try:
            SCRIPT_DIR = os.getcwd()
            DEFAULT_SAVE_DIR = os.path.join(SCRIPT_DIR, "expert_data")
            os.makedirs(DEFAULT_SAVE_DIR, exist_ok=True)
        except:
            # Last resort: use relative path
            DEFAULT_SAVE_DIR = "expert_data"
            os.makedirs(DEFAULT_SAVE_DIR, exist_ok=True)

# session_state에 저장 경로 초기화 (사용자가 수정 가능)
if 'save_directory' not in st.session_state:
    st.session_state['save_directory'] = DEFAULT_SAVE_DIR

# 저장 경로를 가져오는 헬퍼 함수
def get_save_dir():
    """현재 설정된 저장 경로를 반환하고, 없으면 생성"""
    save_dir = st.session_state.get('save_directory', DEFAULT_SAVE_DIR)
    if not os.path.exists(save_dir):
        try:
            os.makedirs(save_dir, exist_ok=True)
        except Exception as e:
            st.warning(f"⚠️ 저장 경로 생성 실패: {save_dir}. 기본 경로를 사용합니다.")
            save_dir = DEFAULT_SAVE_DIR
            if not os.path.exists(save_dir):
                os.makedirs(save_dir, exist_ok=True)
    return save_dir


# --- 2. 데이터 처리 함수 ---
def test_khoa_tile_url(tile_url):
    """KHOA 타일 URL이 유효한지 테스트"""
    try:
        response = requests.get(tile_url, timeout=5)
        if response.status_code == 200:
            return True, "✅ 타일 로드 성공"
        else:
            return False, f"❌ HTTP {response.status_code}: {response.reason}"
    except requests.exceptions.RequestException as e:
        return False, f"❌ 연결 오류: {str(e)}"

def parse_time_column(time_series):
    """시간 컬럼을 초 단위로 변환"""
    try:
        # datetime 형식인 경우
        if isinstance(time_series.iloc[0], str):
            time_series = pd.to_datetime(time_series)
        # datetime을 초 단위로 변환 (첫 시간을 0초로 설정)
        time_seconds = (time_series - time_series.iloc[0]).dt.total_seconds()
        return time_seconds.values
    except:
        # 이미 숫자형인 경우
        return time_series.values

def load_excel_trajectory(file, ship_identifier):
    """엑셀 파일에서 특정 선박의 항적 데이터 로드"""
    try:
        df = pd.read_excel(file)
        
        # 필요한 컬럼 확인
        required_cols = ['time', 'lat', 'lon']
        if not all(col in df.columns for col in required_cols):
            return None, f"Required columns not found: {required_cols}"
        
        # 선박 식별 (mmsi 또는 shipname 기준)
        if 'mmsi' in df.columns:
            ship_data = df[df['mmsi'] == ship_identifier].copy()
        elif 'shipname' in df.columns:
            ship_data = df[df['shipname'] == ship_identifier].copy()
        else:
            return None, "No ship identifier column (mmsi or shipname) found"
        
        if len(ship_data) == 0:
            return None, f"No data found for ship: {ship_identifier}"
        
        # 시간 정렬
        ship_data = ship_data.sort_values('time').reset_index(drop=True)
        
        # 시간을 초 단위로 변환
        time_seconds = parse_time_column(ship_data['time'])
        
        # 데이터프레임 구성 (lat, lon을 x, y로 사용)
        trajectory_df = pd.DataFrame({
            'time': time_seconds,
            'x': ship_data['lon'].values,  # 경도를 x로
            'y': ship_data['lat'].values,  # 위도를 y로
            'lat': ship_data['lat'].values,
            'lon': ship_data['lon'].values,
            'co': ship_data['co'].values if 'co' in ship_data.columns else None,
            'spd': ship_data['spd'].values if 'spd' in ship_data.columns else None,
            'mmsi': ship_data['mmsi'].values if 'mmsi' in ship_data.columns else None,
            'shipname': ship_data['shipname'].values if 'shipname' in ship_data.columns else None,
        })
        
        return trajectory_df, None
    except Exception as e:
        return None, f"Error loading file: {str(e)}"

def get_ship_list_from_excel(file):
    """엑셀 파일에서 선박 목록 추출"""
    try:
        df = pd.read_excel(file)
        
        if 'mmsi' in df.columns:
            ships = df['mmsi'].unique().tolist()
            ship_type = 'mmsi'
        elif 'shipname' in df.columns:
            ships = df['shipname'].unique().tolist()
            ship_type = 'shipname'
        else:
            return [], None
        
        return ships, ship_type
    except Exception as e:
        return [], None

def calculate_feasible_waypoint_range(prev_lon, prev_lat, current_lon, current_lat, next_lon, next_lat, 
                                       speed, time_interval, max_angle_deg=3):
    """
    속도를 고려하여 웨이포인트의 가능한 이동 범위 계산
    좌현/우현 각 3도 정도의 범위로 제한
    """
    
    # 현재 방향 계산 (이전 포인트에서 현재 포인트로)
    if prev_lon is not None and prev_lat is not None:
        dx = current_lon - prev_lon
        dy = current_lat - prev_lat
        current_heading = math.atan2(dy, dx)  # 라디안
    else:
        # 다음 포인트 방향 사용
        if next_lon is not None and next_lat is not None:
            dx = next_lon - current_lon
            dy = next_lat - current_lat
            current_heading = math.atan2(dy, dx)
        else:
            return None, None, None  # 범위 계산 불가
    
    # 속도 기반 최대 이동 거리 (노트를 m/s로 변환 후 거리 계산)
    # 1 knot = 0.514 m/s, 위도 1도 ≈ 111km, 경도는 위도에 따라 다름
    speed_ms = speed * 0.514  # m/s
    max_distance_m = speed_ms * time_interval  # 미터
    max_distance_deg_lat = max_distance_m / 111000  # 위도 차이
    # 경도 차이는 위도에 따라 다름 (대략적으로)
    max_distance_deg_lon = max_distance_m / (111000 * math.cos(math.radians(current_lat)))
    
    # 각도 제한 (좌현/우현 각 3도)
    max_angle_rad = math.radians(max_angle_deg)
    
    # 가능한 범위 계산
    min_heading = current_heading - max_angle_rad
    max_heading = current_heading + max_angle_rad
    
    # 범위 내 좌표 계산
    feasible_lons = []
    feasible_lats = []
    
    # 좌현 방향
    feasible_lons.append(current_lon + max_distance_deg_lon * math.cos(min_heading))
    feasible_lats.append(current_lat + max_distance_deg_lat * math.sin(min_heading))
    
    # 현재 방향
    feasible_lons.append(current_lon + max_distance_deg_lon * math.cos(current_heading))
    feasible_lats.append(current_lat + max_distance_deg_lat * math.sin(current_heading))
    
    # 우현 방향
    feasible_lons.append(current_lon + max_distance_deg_lon * math.cos(max_heading))
    feasible_lats.append(current_lat + max_distance_deg_lat * math.sin(max_heading))
    
    return feasible_lons, feasible_lats, current_heading

def initialize_waypoints_from_trajectory(trajectory_df, num_waypoints=None):
    """
    항적 데이터에서 적절한 간격으로 웨이포인트 초기화
    시간 간격을 고려하여 균등하게 배치
    """
    if len(trajectory_df) < 2:
        return trajectory_df.copy()
    
    if num_waypoints is None:
        # 항적 길이에 따라 적절한 개수 결정 (최소 3개, 최대 10개)
        num_waypoints = min(max(3, len(trajectory_df) // 20), 10)
    
    # 시간 범위 계산
    min_time = trajectory_df['time'].min()
    max_time = trajectory_df['time'].max()
    
    # 시간 간격으로 균등하게 배치
    if num_waypoints == 1:
        time_points = [min_time]
    else:
        time_points = np.linspace(min_time, max_time, num_waypoints)
    
    # 각 시간에 가장 가까운 항적 포인트 찾기
    waypoints_list = []
    for t in time_points:
        # 가장 가까운 시간 인덱스 찾기
        idx = np.searchsorted(trajectory_df['time'].values, t)
        idx = min(idx, len(trajectory_df) - 1)
        
        waypoint = trajectory_df.iloc[idx].copy()
        waypoint['time'] = t  # 정확한 시간 설정
        waypoints_list.append(waypoint)
    
    waypoints_df = pd.DataFrame(waypoints_list)
    return waypoints_df

def redistribute_waypoints_on_path(waypoints_df, interpolated_path, num_waypoints=None):
    """
    수정된 항적에 따라 웨이포인트 재배치
    """
    if len(interpolated_path) < 2:
        return waypoints_df
    
    if num_waypoints is None:
        num_waypoints = len(waypoints_df)
    
    # 시간 범위 계산
    min_time = interpolated_path['time'].min()
    max_time = interpolated_path['time'].max()
    
    # 시간 간격으로 균등하게 배치
    if num_waypoints == 1:
        time_points = [min_time]
    else:
        time_points = np.linspace(min_time, max_time, num_waypoints)
    
    # 각 시간에 가장 가까운 항적 포인트 찾기
    waypoints_list = []
    for t in time_points:
        idx = np.searchsorted(interpolated_path['time'].values, t)
        idx = min(idx, len(interpolated_path) - 1)
        
        waypoint = interpolated_path.iloc[idx].copy()
        waypoint['time'] = t
        waypoints_list.append(waypoint)
    
    waypoints_df = pd.DataFrame(waypoints_list)
    return waypoints_df

def interpolate_path(waypoints_df, total_time_steps, os_data=None):
    """웨이포인트(수정점)를 기반으로 부드러운 경로 생성 (공간 좌표 기반, 시계열 제거)"""
    if len(waypoints_df) < 2:
        return waypoints_df
    
    # 시간 정렬 제거 - 원래 순서 유지
    # waypoints_df = waypoints_df.sort_values('time').reset_index(drop=True)
    
    # lat/lon이 있으면 사용, 없으면 x/y 사용
    if 'lat' in waypoints_df.columns and 'lon' in waypoints_df.columns:
        x_points = waypoints_df['lon'].values
        y_points = waypoints_df['lat'].values
        has_latlon = True
    else:
        x_points = waypoints_df['x'].values
        y_points = waypoints_df['y'].values
        has_latlon = False
    
    # 속도 제약 코드 제거 - 경로만 수정
    
    # 공간 좌표 기반 보간 (시간 대신 거리/인덱스 기반)
    # 각 웨이포인트 사이의 누적 거리를 계산하여 보간 파라미터로 사용
    cumulative_distances = [0.0]
    for i in range(1, len(x_points)):
        dx = x_points[i] - x_points[i-1]
        dy = y_points[i] - y_points[i-1]
        dist = np.sqrt(dx*dx + dy*dy)
        cumulative_distances.append(cumulative_distances[-1] + dist)
    
    cumulative_distances = np.array(cumulative_distances)
    
    # 3차 스플라인 보간 (거리 기반)
    kind = 'cubic' if len(waypoints_df) > 3 else 'linear'
    
    f_x = interp1d(cumulative_distances, x_points, kind=kind, fill_value="extrapolate")
    f_y = interp1d(cumulative_distances, y_points, kind=kind, fill_value="extrapolate")
    
    # 총 거리를 total_time_steps 개의 점으로 보간
    new_distances = np.linspace(cumulative_distances[0], cumulative_distances[-1], total_time_steps)
    new_x = f_x(new_distances)
    new_y = f_y(new_distances)
    
    # os_data가 있으면 원본 시간 사용, 없으면 인덱스 기반 시간 생성
    if os_data is not None and 'time' in os_data.columns:
        new_t = os_data['time'].values
        if len(new_t) != total_time_steps:
            # 시간 보간
            original_times = os_data['time'].values
            t_indices = np.linspace(0, len(original_times) - 1, total_time_steps)
            f_t = interp1d(np.arange(len(original_times)), original_times, kind='linear', fill_value="extrapolate")
            new_t = f_t(t_indices)
    else:
        # 시간 정보가 없으면 인덱스 기반
        new_t = np.arange(total_time_steps)
    
    result_df = pd.DataFrame({'time': new_t, 'x': new_x, 'y': new_y})
    
    # lat/lon 컬럼 추가
    result_df['lon'] = new_x
    result_df['lat'] = new_y
    
    return result_df

# --- [추가/수정] 헬퍼 함수: 그려진 경로를 원본 엑셀 포맷의 시계열 데이터로 변환 ---
def convert_drawing_to_dataframe(draw_coordinates, original_df=None):
    """
    지도에서 그린 좌표(List)를 원본 데이터와 동일한 구조의 DataFrame으로 변환
    (시간, 속도, 코스 등을 자동 계산 및 보간)
    """
    if not draw_coordinates:
        return None

    # 1. 그려진 좌표를 기반으로 기본 DataFrame 생성
    drawn_df = pd.DataFrame(draw_coordinates, columns=['lon', 'lat'])
    
    # 2. 시간(time) 할당 로직
    # 원본 데이터가 있다면 원본의 총 시간 범위를 기준으로 등분할
    if original_df is not None and 'time' in original_df.columns:
        start_time = original_df['time'].min()
        end_time = original_df['time'].max()
        # 그려진 점들의 개수가 적다면(단순 스케치), 원본 데이터 개수만큼 리샘플링(보간) 필요
        # 여기서는 일단 그려진 점 사이를 채우는 로직 구현 (간단히 선형 보간 예시)
        
        # 원본 데이터의 평균 속도를 구함
        avg_speed = original_df['spd'].mean() if 'spd' in original_df.columns else 10.0
        
        # 총 거리 계산 후 시간 배분 (고도화 가능)
        total_dist = 0
        dists = [0]
        for i in range(1, len(drawn_df)):
            # 간이 거리 계산 (피타고라스 근사)
            d = np.sqrt((drawn_df.iloc[i]['lon'] - drawn_df.iloc[i-1]['lon'])**2 + 
                        (drawn_df.iloc[i]['lat'] - drawn_df.iloc[i-1]['lat'])**2)
            total_dist += d
            dists.append(total_dist)
            
        # 거리에 비례하여 시간 할당
        if total_dist > 0:
            drawn_df['time'] = start_time + (np.array(dists) / total_dist) * (end_time - start_time)
        else:
            drawn_df['time'] = np.linspace(start_time, end_time, len(drawn_df))
            
    else:
        # 원본 없으면 0부터 10초 간격
        drawn_df['time'] = np.arange(0, len(drawn_df) * 10, 10)

    # 3. 데이터 고밀도화 (Excel처럼 1초 단위나 조밀한 데이터로 리샘플링)
    # 큐빅 스플라인 보간을 통해 부드러운 곡선 및 조밀한 데이터 생성
    target_points = len(original_df) if original_df is not None else len(drawn_df) * 10
    
    t_new = np.linspace(drawn_df['time'].min(), drawn_df['time'].max(), target_points)
    
    # 보간 함수 생성
    f_lon = interp1d(drawn_df['time'], drawn_df['lon'], kind='linear', fill_value='extrapolate') # 그리기 점이 적으면 linear 권장
    f_lat = interp1d(drawn_df['time'], drawn_df['lat'], kind='linear', fill_value='extrapolate')
    
    new_lon = f_lon(t_new)
    new_lat = f_lat(t_new)
    
    # 결과 DataFrame 생성
    result_df = pd.DataFrame({
        'time': t_new,
        'lat': new_lat,
        'lon': new_lon,
        'x': new_lon, # 호환성 유지
        'y': new_lat  # 호환성 유지
    })
    
    # 4. 속도(spd), 코스(co) 자동 계산
    # 좌표 변화량을 통해 속도와 코스 역산
    result_df['spd'] = 0.0
    result_df['co'] = 0.0
    
    # MMSI, ShipName 등 메타데이터 복사
    if original_df is not None:
        if 'mmsi' in original_df.columns:
            result_df['mmsi'] = original_df.iloc[0]['mmsi']
        if 'shipname' in original_df.columns:
            result_df['shipname'] = original_df.iloc[0]['shipname']
            
    return result_df

def parse_folium_draw_output(draw_output, original_trajectory_df=None):
    """
    Parse folium Draw plugin output (JSON) and convert to pandas DataFrame
    
    Args:
        draw_output: Output from st_folium() containing drawn geometries
        original_trajectory_df: Original trajectory DataFrame to match time and other columns
    
    Returns:
        DataFrame with trajectory data (lat, lon, time, etc.)
    """
    if draw_output is None or 'all_drawings' not in draw_output:
        return None
    
    all_drawings = draw_output.get('all_drawings', [])
    if not all_drawings:
        return None
    
    # Extract coordinates from drawings
    # Draw plugin can create multiple geometries (polylines, polygons, markers)
    trajectory_points = []
    
    for drawing in all_drawings:
        geometry = drawing.get('geometry', {})
        geometry_type = geometry.get('type', '')
        coordinates = geometry.get('coordinates', [])
        
        if geometry_type == 'LineString':
            # Polyline - extract all points
            for coord in coordinates:
                # Coordinates are in [lon, lat] format
                trajectory_points.append({
                    'lon': coord[0],
                    'lat': coord[1]
                })
        elif geometry_type == 'Polygon':
            # Polygon - extract first ring (exterior)
            if len(coordinates) > 0:
                for coord in coordinates[0]:
                    trajectory_points.append({
                        'lon': coord[0],
                        'lat': coord[1]
                    })
        elif geometry_type == 'Point':
            # Single point
            trajectory_points.append({
                'lon': coordinates[0],
                'lat': coordinates[1]
            })
    
    if len(trajectory_points) == 0:
        return None
    
    # Create DataFrame
    edited_df = pd.DataFrame(trajectory_points)
    
    # If original trajectory exists, try to match time and other attributes
    if original_trajectory_df is not None and len(original_trajectory_df) > 0:
        # Interpolate time based on original trajectory
        # Match the number of points to original trajectory or use proportional time
        if len(edited_df) >= 2:
            # Use same number of points as original, or interpolate if needed
            if len(edited_df) != len(original_trajectory_df):
                # Interpolate edited path to match original trajectory time points
                original_times = original_trajectory_df['time'].values
                min_time = original_times[0]
                max_time = original_times[-1]
                
                # Create interpolator for edited path
                edited_lons = edited_df['lon'].values
                edited_lats = edited_df['lat'].values
                edited_indices = np.linspace(0, len(edited_df) - 1, len(edited_df))
                new_indices = np.linspace(0, len(edited_df) - 1, len(original_trajectory_df))
                
                f_lon = interp1d(edited_indices, edited_lons, kind='linear', fill_value='extrapolate')
                f_lat = interp1d(edited_indices, edited_lats, kind='linear', fill_value='extrapolate')
                
                new_lons = f_lon(new_indices)
                new_lats = f_lat(new_indices)
                
                edited_df = pd.DataFrame({
                    'time': original_times,
                    'lon': new_lons,
                    'lat': new_lats,
                    'x': new_lons,
                    'y': new_lats
                })
            else:
                # Same number of points - use original time
                edited_df['time'] = original_trajectory_df['time'].values
                edited_df['x'] = edited_df['lon']
                edited_df['y'] = edited_df['lat']
        else:
            # Too few points - use original time but expand edited points
            original_times = original_trajectory_df['time'].values
            edited_df['time'] = original_times[:len(edited_df)]
            edited_df['x'] = edited_df['lon']
            edited_df['y'] = edited_df['lat']
        
        # Copy other columns from original if they exist (interpolate if needed)
        for col in ['spd', 'co', 'mmsi', 'shipname']:
            if col in original_trajectory_df.columns:
                if len(edited_df) == len(original_trajectory_df):
                    edited_df[col] = original_trajectory_df[col].values
                else:
                    # Interpolate or use nearest
                    original_values = original_trajectory_df[col].values
                    if pd.api.types.is_numeric_dtype(original_trajectory_df[col]):
                        f_interp = interp1d(
                            np.linspace(0, 1, len(original_values)),
                            original_values,
                            kind='linear',
                            fill_value='extrapolate'
                        )
                        edited_df[col] = f_interp(np.linspace(0, 1, len(edited_df)))
                    else:
                        # For non-numeric, use first value
                        edited_df[col] = original_values[0]
    else:
        # No original trajectory - create simple time column
        edited_df['time'] = np.linspace(0, len(edited_df) - 1, len(edited_df))
        edited_df['x'] = edited_df['lon']
        edited_df['y'] = edited_df['lat']
    
    return edited_df

# --- 3. 메인 화면 구성 ---
st.title("🚢 Expert Behavior History Extraction Tool for Inverse Reinforcement Learning")

# 사이드바: 저장 경로 설정
st.sidebar.header("📁 저장 경로 설정")
save_path_input = st.sidebar.text_input(
    "저장 경로 (Save Directory Path)",
    value=st.session_state.get('save_directory', DEFAULT_SAVE_DIR),
    key="save_path_input",
    help="Expert 데이터가 저장될 폴더 경로를 입력하세요. 절대 경로 또는 상대 경로를 사용할 수 있습니다."
)

# 경로 변경 확인 및 적용
if save_path_input != st.session_state.get('save_directory', DEFAULT_SAVE_DIR):
    # 경로 유효성 검사
    if save_path_input.strip():
        # 절대 경로인지 확인
        if os.path.isabs(save_path_input):
            new_path = save_path_input
        else:
            # 상대 경로인 경우 스크립트 디렉토리 기준으로 변환
            new_path = os.path.join(SCRIPT_DIR, save_path_input)
        
        # 경로 정규화
        new_path = os.path.normpath(new_path)
        
        # 디렉토리 생성 시도
        try:
            os.makedirs(new_path, exist_ok=True)
            st.session_state['save_directory'] = new_path
            st.sidebar.success(f"✅ 경로 설정됨: {new_path}")
        except Exception as e:
            st.sidebar.error(f"❌ 경로 생성 실패: {str(e)}")
            st.sidebar.info(f"기본 경로 사용: {DEFAULT_SAVE_DIR}")
            st.session_state['save_directory'] = DEFAULT_SAVE_DIR
    else:
        # 빈 경로인 경우 기본 경로로 복원
        st.session_state['save_directory'] = DEFAULT_SAVE_DIR

# 현재 저장 경로 표시
current_save_dir = get_save_dir()
st.sidebar.info(f"📂 현재 저장 경로:\n`{current_save_dir}`")

st.sidebar.divider()

# 사이드바: 모드 선택
mode = st.sidebar.radio("Mode Selection", ["Expert Input Mode", "Admin Review Mode"])

if mode == "Expert Input Mode":
    st.sidebar.header("1. Scenario Settings")
    
    # 데이터 로드 (실제 파일 업로드 기능)
    uploaded_file = st.sidebar.file_uploader("Upload Scenario (Excel/CSV)", type=['xlsx', 'csv'])
    
    # 엑셀 파일에서 선박 목록 가져오기
    if uploaded_file is not None:
        ship_list, ship_type = get_ship_list_from_excel(uploaded_file)
        
        if len(ship_list) > 0:
            st.sidebar.success(f"Found {len(ship_list)} ship(s) in file")
            
            # 자선(Own Ship) 선택
            st.sidebar.subheader("Select Own Ship (OS)")
            os_ship = st.sidebar.selectbox("Own Ship", ship_list, key="os_select")
            
            # 상대선박(Target Ships) 선택 (최대 4척)
            # OS로 선택된 선박은 TS 선택지에서 제외
            ts_ship_list = [ship for ship in ship_list if ship != os_ship]
            st.sidebar.subheader("Select Target Ships (TS) - Max 4")
            ts_ships = st.sidebar.multiselect("Target Ships", ts_ship_list, max_selections=4, key="ts_select")
            
            # 데이터 로드 버튼
            if st.sidebar.button("Load Trajectories"):
                # 이전 데이터 완전히 삭제
                if 'waypoints' in st.session_state:
                    del st.session_state['waypoints']
                if 'os_data' in st.session_state:
                    del st.session_state['os_data']
                if 'ts_list' in st.session_state:
                    del st.session_state['ts_list']
                
                # 자선 데이터 로드
                os_data, os_error = load_excel_trajectory(uploaded_file, os_ship)
                if os_error:
                    st.sidebar.error(f"OS Error: {os_error}")
                else:
                    st.session_state['os_data'] = os_data
                    # 웨이포인트 완전히 새로 초기화 - 원본 OS 데이터를 그대로 사용하여 Expert Path 초기화
                    # Control Point는 적절한 간격으로 배치하되, Expert Path는 원본 데이터 기반으로 표시
                    waypoints_init = initialize_waypoints_from_trajectory(os_data, num_waypoints=5)
                    st.session_state['waypoints'] = waypoints_init
                    st.session_state['num_waypoints'] = len(waypoints_init)
                    # Expert Path 초기화 플래그 설정 (원본 데이터 사용)
                    st.session_state['use_original_path'] = True
                    # Control Point 수정 이력 초기화
                    st.session_state['cp_modification_history'] = []
                    st.sidebar.success(f"OS loaded: {len(os_data)} points, {len(waypoints_init)} waypoints")
                    
                    # 새로운 데이터 로드 시 애니메이션 상태 초기화
                    min_time = float(os_data['time'].min())
                    max_time = float(os_data['time'].max())
                    st.session_state['current_time'] = min_time
                    st.session_state['is_playing'] = False
                    st.session_state['min_time'] = min_time
                    st.session_state['max_time'] = max_time
                    st.session_state['selected_waypoint_idx'] = None  # 선택된 웨이포인트 초기화
                
                # 상대선박 데이터 로드
                ts_list = []
                for i, ts_ship in enumerate(ts_ships):
                    ts_data, ts_error = load_excel_trajectory(uploaded_file, ts_ship)
                    if ts_error:
                        st.sidebar.warning(f"TS{i+1} Error: {ts_error}")
                    else:
                        ts_list.append(ts_data)
                        st.sidebar.success(f"TS{i+1} loaded: {len(ts_data)} points")
                
                st.session_state['ts_list'] = ts_list
                st.rerun()
        else:
            st.sidebar.error("No ships found in file")
    
    # 데이터가 없으면 안내 메시지 표시
    if 'os_data' not in st.session_state:
        st.info("📁 Please upload an Excel file to load scenario data.")
        st.stop()

    # --- 애니메이션 제어 패널 ---
    st.sidebar.header("2. Animation Control")
    
    # 현재 시간 초기화 (데이터의 실제 시간 범위 사용)
    os_data = st.session_state['os_data']
    min_time = float(os_data['time'].min())
    max_time = float(os_data['time'].max())
    
    if 'current_time' not in st.session_state:
        st.session_state['current_time'] = min_time
        st.session_state['is_playing'] = False
    
    # 시간 범위를 항상 최신 데이터로 업데이트
    st.session_state['min_time'] = min_time
    st.session_state['max_time'] = max_time
    
    # 속도 조절
    playback_speed = st.sidebar.slider("Playback Speed", 0.1, 5.0, 1.0, 0.1, key="speed_slider")
    
    # 시간 제어 버튼
    col_time1, col_time2, col_time3 = st.sidebar.columns(3)
    with col_time1:
        if st.button("⏮️ Reset", key="reset_btn"):
            st.session_state['current_time'] = st.session_state.get('min_time', 0.0)
            st.session_state['is_playing'] = False
            st.rerun()
    with col_time2:
        if st.button("⏯️ Play/Pause", key="play_btn"):
            st.session_state['is_playing'] = not st.session_state.get('is_playing', False)
            st.rerun()
    with col_time3:
        if st.button("⏭️ Step +1s", key="step_btn"):
            new_time = min(st.session_state['current_time'] + 1.0, st.session_state['max_time'])
            st.session_state['current_time'] = new_time
            st.rerun()
    
    # 자동 재생 처리 (슬라이더보다 먼저 처리하여 충돌 방지)
    auto_play_placeholder = st.sidebar.empty()
    is_playing = st.session_state.get('is_playing', False)
    
    if is_playing:
        if st.session_state['current_time'] < st.session_state['max_time']:
            # 다음 프레임으로 이동 (재생 속도에 따라) - 더 스무스하게
            time_step = 0.1 * playback_speed  # 더 작은 단위로 부드럽게 (0.1초 단위)
            new_time = min(st.session_state['current_time'] + time_step, st.session_state['max_time'])
            st.session_state['current_time'] = new_time
            
            # 진행 상태 표시
            progress_pct = (new_time - st.session_state.get('min_time', 0.0)) / (st.session_state['max_time'] - st.session_state.get('min_time', 0.0) + 0.001)
            auto_play_placeholder.progress(progress_pct, text=f"⏯️ Playing: {new_time:.1f}s / {st.session_state['max_time']:.1f}s (Speed: {playback_speed:.1f}x)")
            
            # 자동 새로고침 (재생 속도에 따라 지연 시간 조정) - 더 빠른 업데이트
            delay = max(0.03, 0.1 / playback_speed)  # 더 빠른 업데이트로 부드러운 애니메이션
            time.sleep(delay)
            st.rerun()
        else:
            # 끝에 도달하면 정지
            st.session_state['is_playing'] = False
            auto_play_placeholder.empty()
            st.rerun()
    else:
        auto_play_placeholder.empty()
    
    # 시간 슬라이더
    current_time = st.sidebar.slider(
        "Time (seconds)", 
        float(st.session_state.get('min_time', 0.0)), 
        float(st.session_state['max_time']), 
        float(st.session_state['current_time']),
        step=0.1,
        key="time_slider"
    )
    
    # 슬라이더 값이 변경되면 current_time 업데이트 (재생 중이 아닐 때만)
    # 재생 중에는 슬라이더 변경을 무시하여 재생이 중단되지 않도록 함
    if not is_playing and 'time_slider' in st.session_state:
        # 슬라이더 값이 실제로 변경되었는지 확인
        slider_value = st.session_state['time_slider']
        current_value = st.session_state.get('current_time', 0)
        if abs(slider_value - current_value) > 0.01:
            st.session_state['current_time'] = slider_value
    
    # --- 2D 시각화 (애니메이션) ---
    st.subheader("2D Trajectory Animation (Real-time Playback)")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # 지도 배경 선택
        map_background = st.selectbox(
            "Map Background",
            ["OpenStreetMap + KHOA Electronic Chart", "OpenStreetMap Only", "KHOA Electronic Chart Only"],
            index=0,
            help="지도 배경을 선택하세요. OpenStreetMap + KHOA는 두 레이어를 함께 표시합니다."
        )
        st.session_state['map_background'] = map_background
        
        # KHOA 해도 설정 (KHOA가 포함된 경우에만 표시)
        if "KHOA" in map_background:
            col_layer, col_url = st.columns(2)
            with col_layer:
                khoa_layer = st.selectbox(
                    "KHOA Layer Type", 
                    ["haareum", "ENC", "chart", "haareum2024"],
                    index=1,  # ENC를 기본값으로
                    help="KHOA 해도 레이어 타입을 선택하세요."
                )
                st.session_state['khoa_layer'] = khoa_layer
            
            with col_url:
                url_option_idx = st.session_state.get('khoa_url_option', 2)  # Option 3을 기본값으로
                khoa_url_option = st.selectbox(
                    "KHOA URL Option",
                    [f"Option {i+1}: {url.split('/')[-2] if '/' in url else url}" for i, url in enumerate(KHOA_TILE_BASE_URL_OPTIONS)],
                    index=url_option_idx,
                    help="KHOA API URL 옵션을 선택하세요. DNS 오류가 발생하면 다른 옵션을 시도하세요."
                )
                selected_url_idx = [f"Option {i+1}: {url.split('/')[-2] if '/' in url else url}" for i, url in enumerate(KHOA_TILE_BASE_URL_OPTIONS)].index(khoa_url_option)
                st.session_state['khoa_url_option'] = selected_url_idx
                selected_base_url = KHOA_TILE_BASE_URL_OPTIONS[selected_url_idx]
        
        # Plotly 그래프 생성
        fig = go.Figure()
        
        # 현재 시간까지의 인덱스 찾기
        os_data = st.session_state['os_data']
        os_time = os_data['time'].values
        current_idx = np.searchsorted(os_time, current_time, side='right')
        current_idx = min(current_idx, len(os_data) - 1)
        
        # 배경 지도 추가
        center_lon = os_data['lon'].iloc[current_idx] if 'lon' in os_data.columns else os_data['x'].iloc[current_idx]
        center_lat = os_data['lat'].iloc[current_idx] if 'lat' in os_data.columns else os_data['y'].iloc[current_idx]
        
        # 지도 배경 설정
        map_background = st.session_state.get('map_background', 'OpenStreetMap + KHOA Electronic Chart')
        layers = []
        
        # OpenStreetMap + KHOA 해도 조합
        if map_background == "OpenStreetMap + KHOA Electronic Chart":
            # OpenStreetMap을 기본 스타일로 사용
            base_style = "open-street-map"
            
            # KHOA 해도 레이어 추가
            selected_layer = st.session_state.get('khoa_layer', 'ENC')
            selected_base_url = KHOA_TILE_BASE_URL_OPTIONS[st.session_state.get('khoa_url_option', 2)]
            tile_url_template = f"{selected_base_url}/{selected_layer}/{{z}}/{{x}}/{{y}}.png?key={KHOA_API_KEY}"
            
            layers.append({
                "sourcetype": "raster",
                "source": tile_url_template,
                "below": "traces",
                "opacity": 0.7,  # 반투명으로 표시하여 OpenStreetMap과 함께 보이도록
                "type": "raster"
            })
            
            # 디버깅 정보 표시
            with st.expander("🔧 KHOA API Debug Info", expanded=False):
                st.code(f"Layer: {selected_layer}")
                st.code(f"Tile URL Template: {tile_url_template}")
                example_url = tile_url_template.format(z=12, x=2000, y=1000)
                st.code(f"Example URL (z=12, x=2000, y=1000):\n{example_url}")
                
                if st.button("🧪 Test Tile URL", key="test_khoa_tile"):
                    with st.spinner("타일 URL 테스트 중..."):
                        is_valid, message = test_khoa_tile_url(example_url)
                        if is_valid:
                            st.success(message)
                            st.info("✅ 타일이 정상적으로 로드됩니다. 지도에 표시되어야 합니다.")
                        else:
                            st.error(message)
                            st.warning("⚠️ 타일을 로드할 수 없습니다.")
                            with st.expander("💡 로컬 환경에서 해도 타일 사용 안내", expanded=True):
                                st.markdown("""
                                **로컬 환경에서 KHOA 해도 타일을 사용하려면:**
                                
                                1. **인터넷 연결 필요**: KHOA API 서버에 접근할 수 있어야 합니다
                                2. **방화벽 설정**: 방화벽이 `www.khoa.go.kr` 또는 `api.khoa.go.kr`을 차단하지 않아야 합니다
                                3. **DNS 해결**: 도메인 이름이 정상적으로 해결되어야 합니다
                                4. **API 키 유효성**: 발급받은 API 키가 활성 상태여야 합니다
                                5. **서버 배포 권장**: 로컬에서 접근이 어려운 경우 서버에 배포하면 더 안정적으로 작동합니다
                                
                                **대안**: OpenStreetMap을 사용하거나, "OpenStreetMap + KHOA Electronic Chart" 옵션을 선택하여 
                                해도가 로드되지 않아도 OpenStreetMap은 표시됩니다.
                                """)
                
                st.info("💡 브라우저 개발자 도구(F12) → Network 탭에서 타일 요청을 확인할 수 있습니다.")
        
        elif map_background == "KHOA Electronic Chart Only":
            # KHOA 해도만 사용
            base_style = "white-bg"
            selected_layer = st.session_state.get('khoa_layer', 'ENC')
            selected_base_url = KHOA_TILE_BASE_URL_OPTIONS[st.session_state.get('khoa_url_option', 2)]
            tile_url_template = f"{selected_base_url}/{selected_layer}/{{z}}/{{x}}/{{y}}.png?key={KHOA_API_KEY}"
            
            layers.append({
                "sourcetype": "raster",
                "source": tile_url_template,
                "below": "traces",
                "opacity": 1.0,
                "type": "raster"
            })
            
            # 디버깅 정보 표시
            with st.expander("🔧 KHOA API Debug Info", expanded=False):
                st.code(f"Layer: {selected_layer}")
                st.code(f"Tile URL Template: {tile_url_template}")
                example_url = tile_url_template.format(z=12, x=2000, y=1000)
                st.code(f"Example URL (z=12, x=2000, y=1000):\n{example_url}")
                
                if st.button("🧪 Test Tile URL", key="test_khoa_tile"):
                    with st.spinner("타일 URL 테스트 중..."):
                        is_valid, message = test_khoa_tile_url(example_url)
                        if is_valid:
                            st.success(message)
                        else:
                            st.error(message)
                            st.info("💡 **로컬 환경에서 해도 타일 사용:**\n- 인터넷 연결이 필요합니다\n- KHOA API 서버가 접근 가능해야 합니다")
        
        else:  # OpenStreetMap Only
            base_style = "open-street-map"
        
        # 지도 레이아웃 설정
        try:
            fig.update_layout(
                mapbox=dict(
                    style=base_style,
                    center=dict(lon=center_lon, lat=center_lat),
                    zoom=12,
                    layers=layers if layers else None
                )
            )
        except Exception as e:
            # 오류 발생 시 OpenStreetMap으로 폴백
            st.warning(f"⚠️ 지도 설정 오류: {str(e)}. OpenStreetMap으로 전환합니다.")
            fig.update_layout(
                mapbox=dict(
                    style="open-street-map",
                    center=dict(lon=center_lon, lat=center_lat),
                    zoom=12
                )
            )
        
        # 1. Target Ships - 전체 항적 (연한 빨간색) + 현재 위치 (진한 빨간색)
        for idx, ts in enumerate(st.session_state['ts_list']):
            ts_lon = ts['lon'] if 'lon' in ts.columns else ts['x']
            ts_lat = ts['lat'] if 'lat' in ts.columns else ts['y']
            ts_time = ts['time'].values
            
            # 전체 항적 (연한 색) - 첫 번째 TS만 레전드에 표시
            # Hover 정보를 위한 customdata 준비
            ts_speed = ts['spd'].values if 'spd' in ts.columns else np.zeros(len(ts_lon))
            ts_course = ts['co'].values if 'co' in ts.columns else np.zeros(len(ts_lon))
            ts_customdata = np.column_stack((
                [f'TS{idx+1}'] * len(ts_lon),
                ts_time,
                ts_speed,
                ts_course
            ))
            
            fig.add_trace(go.Scattermapbox(
                lon=ts_lon,
                lat=ts_lat,
                mode='lines',
                name='TS Trajectory' if idx == 0 else None,  # 첫 번째만 레전드에 표시
                line=dict(color='rgba(255,0,0,0.3)', width=2),
                showlegend=True if idx == 0 else False,  # 첫 번째만 레전드에 표시
                customdata=ts_customdata,
                hovertemplate='<b>%{customdata[0]}</b><br>Time: %{customdata[1]:.1f}s<br>Speed: %{customdata[2]:.1f} kn<br>Course: %{customdata[3]:.1f}°<br>Lat: %{lat:.6f}<br>Lon: %{lon:.6f}<extra></extra>'
            ))
            
            # 현재 시간의 위치
            ts_current_idx = np.searchsorted(ts_time, current_time, side='right')
            ts_current_idx = min(ts_current_idx, len(ts) - 1)
            
            # 선박 방향 계산 (이전 포인트에서 현재 포인트로)
            if ts_current_idx > 0:
                prev_lon = ts_lon.iloc[ts_current_idx-1] if isinstance(ts_lon, pd.Series) else ts_lon[ts_current_idx-1]
                prev_lat = ts_lat.iloc[ts_current_idx-1] if isinstance(ts_lat, pd.Series) else ts_lat[ts_current_idx-1]
                curr_lon = ts_lon.iloc[ts_current_idx] if isinstance(ts_lon, pd.Series) else ts_lon[ts_current_idx]
                curr_lat = ts_lat.iloc[ts_current_idx] if isinstance(ts_lat, pd.Series) else ts_lat[ts_current_idx]
                heading = np.arctan2(curr_lat - prev_lat, curr_lon - prev_lon) * 180 / np.pi
            else:
                heading = 0
            
            # 배 모양 마커 (triangle 사용)
            ts_curr_lon = ts_lon.iloc[ts_current_idx] if isinstance(ts_lon, pd.Series) else ts_lon[ts_current_idx]
            ts_curr_lat = ts_lat.iloc[ts_current_idx] if isinstance(ts_lat, pd.Series) else ts_lat[ts_current_idx]
            
            # Scattermapbox를 사용하여 지도 위에 마커 표시
            fig.add_trace(go.Scattermapbox(
                lon=[ts_curr_lon],
                lat=[ts_curr_lat],
                mode='markers',
                name='TS (Ship)' if idx == 0 else None,  # 첫 번째만 레전드에 표시
                marker=dict(
                    size=20,
                    color='red',
                    symbol='circle',  # 원형 마커 사용
                    allowoverlap=True
                ),
                showlegend=True if idx == 0 else False,  # 첫 번째만 레전드에 표시
                hovertemplate=f'<b>TS{idx+1} (Ship)</b><br>Time: {current_time:.1f}s<br>Lat: %{{lat:.6f}}<br>Lon: %{{lon:.6f}}<br>Heading: {heading:.1f}°<extra></extra>'
            ))

        # 2. Original OS Trajectory (회색 점선) - 항상 표시하여 비교 가능하게
        os_lon_orig = os_data['lon'] if 'lon' in os_data.columns else os_data['x']
        os_lat_orig = os_data['lat'] if 'lat' in os_data.columns else os_data['y']
        
        # 원본 항적 표시 (수정된 경우에만)
        show_original = not st.session_state.get('use_original_path', True)
        if show_original:
            fig.add_trace(go.Scattermapbox(
                lon=os_lon_orig,
                lat=os_lat_orig,
                mode='lines',
                name='Original OS Trajectory',
                line=dict(color='rgba(128,128,128,0.5)', width=2),
                showlegend=True,
                hovertemplate='<b>Original OS</b><br>Lat: %{lat:.6f}<br>Lon: %{lon:.6f}<extra></extra>'
            ))
        
        # 3. Expert Path (OS) - 전체 항적 (연한 파란색) + 현재 위치 (진한 파란색)
        # 데이터 로드 직후에는 원본 OS 데이터를 사용, Control Point 수정 후에는 보간된 경로 사용
        # 그린 경로가 있으면 그린 경로를 사용
        use_drawn_path = st.session_state.get('use_drawn_path', False)
        drawn_path_df = st.session_state.get('drawn_path', None)
        
        # 간단한 편집 모드: 편집 포인트가 있으면 이를 기반으로 경로 생성
        simple_edit_points = st.session_state.get('simple_edit_points', [])
        
        simple_edit_mode = st.session_state.get('simple_edit_mode', False)
        if simple_edit_mode and len(simple_edit_points) > 0:
            # 편집 포인트를 waypoint로 변환
            edit_waypoints_list = []
            for ep in simple_edit_points:
                edit_waypoints_list.append({
                    'time': ep.get('time', 0),
                    'lon': ep['lon'],
                    'lat': ep['lat'],
                    'x': ep['lon'],
                    'y': ep['lat']
                })
            edit_waypoints_df = pd.DataFrame(edit_waypoints_list)
            # 시간 순으로 정렬
            edit_waypoints_df = edit_waypoints_df.sort_values('time').reset_index(drop=True)
            # 편집 포인트 기반으로 보간된 경로 생성
            expert_path = interpolate_path(edit_waypoints_df, len(os_data), os_data=os_data)
        elif use_drawn_path and drawn_path_df is not None:
            # 그린 경로를 Expert Path로 사용
            expert_path = drawn_path_df.copy()
        else:
            use_original = st.session_state.get('use_original_path', True)
            
            if use_original:
                # 원본 OS 데이터를 그대로 사용 (데이터 로드 시 초기화)
                expert_path = os_data.copy()
            else:
                # Control Point가 수정되었으므로 보간된 경로 사용
                # waypoints가 업데이트되었는지 확인
                current_waypoints = st.session_state.get('waypoints', None)
                if current_waypoints is not None and len(current_waypoints) > 0:
                    expert_path = interpolate_path(current_waypoints, len(os_data), os_data=os_data)
                else:
                    # waypoints가 없으면 원본 데이터 사용
                    expert_path = os_data.copy()
                    st.session_state['use_original_path'] = True
        
        if 'lat' in expert_path.columns and 'lon' in expert_path.columns:
            expert_lon = expert_path['lon']
            expert_lat = expert_path['lat']
        else:
            expert_lon = expert_path['x']
            expert_lat = expert_path['y']
        
        # 전체 항적 (연한 색)
        # Hover 정보를 위한 customdata 준비 (CP 수정 이력 포함)
        expert_customdata = []
        cp_history = st.session_state.get('cp_modification_history', [])
        
        for i in range(len(expert_path)):
            time_val = expert_path.iloc[i]['time']
            lon_val = expert_lon.iloc[i] if isinstance(expert_lon, pd.Series) else expert_lon[i]
            lat_val = expert_lat.iloc[i] if isinstance(expert_lat, pd.Series) else expert_lat[i]
            
            # 해당 시간에 CP 수정 이력이 있는지 확인
            cp_mods = [m for m in cp_history if abs(m['time'] - time_val) < 1.0]  # 1초 이내 수정 이력
            cp_info = f"{len(cp_mods)} modification(s)" if cp_mods else "Original"
            
            speed_val = os_data.iloc[min(i, len(os_data)-1)]['spd'] if 'spd' in os_data.columns else 0
            course_val = os_data.iloc[min(i, len(os_data)-1)]['co'] if 'co' in os_data.columns else 0
            
            expert_customdata.append([
                'OS (Expert Path)',
                time_val,
                speed_val,
                course_val,
                cp_info
            ])
        
        expert_customdata = np.array(expert_customdata)
        
        # OS 항적 라인 - 간단한 편집 모드에서는 클릭 가능하게
        trajectory_trace = go.Scattermapbox(
            lon=expert_lon,
            lat=expert_lat,
            mode='lines',
            name='OS Trajectory (Expert Path)',
            line=dict(color='rgba(0,0,255,0.5)' if simple_edit_mode else 'rgba(0,0,255,0.3)', width=3 if simple_edit_mode else 2),
            showlegend=True,
            customdata=expert_customdata,
            hovertemplate='<b>%{customdata[0]}</b><br>Time: %{customdata[1]:.1f}s<br>Speed: %{customdata[2]:.1f} kn<br>Course: %{customdata[3]:.1f}°<br>CP Status: %{customdata[4]}<br>Lat: %{lat:.6f}<br>Lon: %{lon:.6f}' + ('<br><i>Click to add edit point</i>' if simple_edit_mode else '') + '<extra></extra>'
        )
        fig.add_trace(trajectory_trace)
        
        # 간단한 편집 모드: 편집 포인트 표시
        if simple_edit_mode:
            edit_points = st.session_state.get('simple_edit_points', [])
            selected_edit_idx = st.session_state.get('selected_edit_point_idx', None)
            
            if len(edit_points) > 0:
                edit_lons = [p['lon'] for p in edit_points]
                edit_lats = [p['lat'] for p in edit_points]
                edit_times = [p.get('time', 0) for p in edit_points]
                
                # 선택된 포인트와 선택되지 않은 포인트를 구분
                marker_colors = ['red' if i == selected_edit_idx else 'green' for i in range(len(edit_points))]
                marker_sizes = [18 if i == selected_edit_idx else 12 for i in range(len(edit_points))]
                
                # 편집 포인트 마커
                fig.add_trace(go.Scattermapbox(
                    lon=edit_lons,
                    lat=edit_lats,
                    mode='markers',
                    name='Edit Points',
                    marker=dict(
                        size=marker_sizes,
                        color=marker_colors,
                        symbol='circle',
                        line=dict(width=2, color='darkgreen' if selected_edit_idx is None else 'darkred')
                    ),
                    showlegend=True,
                    customdata=edit_times,
                    hovertemplate='<b>Edit Point %{pointNumber}</b><br>Time: %{customdata:.1f}s<br>Lat: %{lat:.6f}<br>Lon: %{lon:.6f}<br><i>Click to select, then click map to move</i><extra></extra>'
                ))
        
        # 현재 시간의 OS 위치
        expert_time = expert_path['time'].values
        expert_current_idx = np.searchsorted(expert_time, current_time, side='right')
        expert_current_idx = min(expert_current_idx, len(expert_path) - 1)
        
        # 선박 방향 계산 (이전 포인트에서 현재 포인트로)
        if expert_current_idx > 0:
            prev_lon = expert_lon.iloc[expert_current_idx-1] if isinstance(expert_lon, pd.Series) else expert_lon[expert_current_idx-1]
            prev_lat = expert_lat.iloc[expert_current_idx-1] if isinstance(expert_lat, pd.Series) else expert_lat[expert_current_idx-1]
            curr_lon = expert_lon.iloc[expert_current_idx] if isinstance(expert_lon, pd.Series) else expert_lon[expert_current_idx]
            curr_lat = expert_lat.iloc[expert_current_idx] if isinstance(expert_lat, pd.Series) else expert_lat[expert_current_idx]
            heading = np.arctan2(curr_lat - prev_lat, curr_lon - prev_lon) * 180 / np.pi
        else:
            heading = 0
        
        # 배 모양 마커 (triangle 사용)
        os_curr_lon = expert_lon.iloc[expert_current_idx] if isinstance(expert_lon, pd.Series) else expert_lon[expert_current_idx]
        os_curr_lat = expert_lat.iloc[expert_current_idx] if isinstance(expert_lat, pd.Series) else expert_lat[expert_current_idx]
        
        # Scattermapbox를 사용하여 지도 위에 마커 표시
        fig.add_trace(go.Scattermapbox(
            lon=[os_curr_lon],
            lat=[os_curr_lat],
            mode='markers',
            name='OS (Ship)',
            marker=dict(
                size=25,
                color='blue',
                symbol='circle',  # 원형 마커 사용
                allowoverlap=True
            ),
            showlegend=True,
            hovertemplate='<b>OS (Ship)</b><br>Time: {:.1f}s<br>Lat: %{{lat:.6f}}<br>Lon: %{{lon:.6f}}<br>Heading: {:.1f}°<extra></extra>'.format(current_time, heading)
        ))

        # 3. Waypoints (수정 가능한 점들) - 클릭/드래그로 간단하게 이동 가능
        waypoints = st.session_state['waypoints']
        
        # 선택된 웨이포인트 인덱스 초기화
        if 'selected_waypoint_idx' not in st.session_state:
            st.session_state['selected_waypoint_idx'] = None
        
        if 'lat' in waypoints.columns and 'lon' in waypoints.columns:
            waypoint_lon = waypoints['lon'].values
            waypoint_lat = waypoints['lat'].values
        else:
            waypoint_lon = waypoints['x'].values
            waypoint_lat = waypoints['y'].values
        
        # 웨이포인트가 있는지 확인
        if len(waypoints) > 0:
            # 선택된 웨이포인트는 다른 색으로 표시 (더 크고 눈에 띄게)
            selected_idx = st.session_state.get('selected_waypoint_idx', None)
            marker_colors = ['red' if i == selected_idx else 'yellow' for i in range(len(waypoints))]
            marker_sizes = [20 if i == selected_idx else 15 for i in range(len(waypoints))]  # 더 크게 만들어 클릭하기 쉽게
            
            # Control Points 마커 추가
            fig.add_trace(go.Scattermapbox(
                lon=waypoint_lon,
                lat=waypoint_lat,
                mode='markers+text',
                name='Control Points (OS Waypoints)',
                marker=dict(
                    size=marker_sizes,
                    color=marker_colors,
                    symbol='circle',
                    opacity=0.9
                ),
                text=[f"WP{i}" for i in range(len(waypoints))],
                textposition="top center",
                textfont=dict(size=12, color='black', family='Arial Black'),
                hovertemplate='<b>Control Point %{text}</b><br>Lat: %{lat:.6f}<br>Lon: %{lon:.6f}<br><i>Click to select, then click map to move</i><extra></extra>'
            ))
        
        # 그린 경로 포인트 표시
        drawn_points = st.session_state.get('drawn_path_points', [])
        if len(drawn_points) > 0:
            drawn_lons = [p['lon'] for p in drawn_points]
            drawn_lats = [p['lat'] for p in drawn_points]
            
            # 그린 경로 선 표시
            if len(drawn_points) > 1:
                fig.add_trace(go.Scattermapbox(
                    lon=drawn_lons,
                    lat=drawn_lats,
                    mode='lines+markers',
                    name='Drawn Path',
                    line=dict(color='green', width=3),
                    marker=dict(size=8, color='green'),
                    showlegend=True,
                    hovertemplate='<b>Drawn Path Point</b><br>Lat: %{lat:.6f}<br>Lon: %{lon:.6f}<extra></extra>'
                ))
            else:
                # 포인트가 1개만 있을 때는 마커만 표시
                fig.add_trace(go.Scattermapbox(
                    lon=drawn_lons,
                    lat=drawn_lats,
                    mode='markers',
                    name='Drawn Path Point',
                    marker=dict(size=10, color='green'),
                    showlegend=True,
                    hovertemplate='<b>Drawn Path Point</b><br>Lat: %{lat:.6f}<br>Lon: %{lon:.6f}<extra></extra>'
                ))
        
        # 클릭한 위치 마커 표시 (수정된 좌표 반영)
        # 경로 그리기 모드는 나중에 정의되므로 여기서는 session_state에서 가져옴
        draw_mode_check = st.session_state.get('draw_path_mode', False)
        clicked_lon = st.session_state.get('clicked_lon', None)
        clicked_lat = st.session_state.get('clicked_lat', None)
        if clicked_lon is not None and clicked_lat is not None and not draw_mode_check:
            # 수정된 좌표 사용 (number_input에서 수정 가능)
            display_lon = clicked_lon
            display_lat = clicked_lat
            fig.add_trace(go.Scattermapbox(
                lon=[display_lon],
                lat=[display_lat],
                mode='markers',
                name='Clicked Location',
                marker=dict(
                    size=15,
                    color='orange',
                    symbol='circle',
                    opacity=0.8
                ),
                hovertemplate=f'<b>Clicked Location</b><br>Lat: {display_lat:.6f}<br>Lon: {display_lon:.6f}<br><i>Click "Move CP Here" to move selected Control Point</i><extra></extra>'
            ))

        # 그래프 레이아웃 설정 (드래그 모드 활성화)
        # mapbox 설정이 이미 위에서 설정되었으므로 레이아웃만 업데이트
        # 지도 중심을 고정하여 CP 이동 시 화면이 이동하지 않도록 함
        fig.update_layout(
            height=700,
            margin=dict(r=0, b=0, l=0, t=50),
            hovermode='closest',
            legend=dict(
                x=0.02, 
                y=0.98, 
                bgcolor='rgba(255,255,255,0.9)',
                bordercolor='black',
                borderwidth=1,
                font=dict(size=10)
            ),
            dragmode='pan',  # 드래그로 지도 이동
            clickmode='event+select',  # 클릭 이벤트 활성화
            uirevision='fixed_view'  # UI 상태 유지 (지도 중심 고정)
        )
        
        # 편집 모드 선택
        col_draw, col_simple, col_debug = st.columns(3)
        with col_draw:
            # Streamlit 위젯은 자동으로 session_state를 관리하므로 수동 설정 불필요
            draw_mode = st.checkbox("✏️ Draw Path Mode", key="draw_path_mode", help="클릭으로 경로 포인트를 추가하여 Expert Path를 생성합니다")
        
        with col_simple:
            # 간단한 편집 모드: 기존 항적을 클릭해서 수정
            simple_edit_mode = st.checkbox("🖱️ Simple Edit Mode", key="simple_edit_mode", help="기존 OS 항적을 클릭해서 직접 수정합니다. 가장 간단한 방법입니다!")
        
        with col_debug:
            debug_cp = st.checkbox("🔧 Debug CP Movement", key="debug_cp_movement", help="Control Point 이동 디버깅 정보 표시")
        
        # 편집 모드 안내
        if simple_edit_mode:
            st.success("🖱️ **Simple Edit Mode Active:** 파란색 OS 항적 라인을 클릭하면 해당 위치에 편집 포인트가 추가됩니다. 포인트를 클릭하고 지도를 클릭하면 이동합니다. 포인트를 삭제하려면 우클릭하세요.")
        elif draw_mode:
            st.info("✏️ **Draw Path Mode Active:** 지도를 클릭하여 경로 포인트를 추가하세요. 여러 점을 클릭하면 경로가 생성됩니다. 'Clear Drawn Path' 버튼으로 초기화할 수 있습니다.")
        
        # 간단한 편집 모드용 포인트 초기화
        if 'simple_edit_points' not in st.session_state:
            st.session_state['simple_edit_points'] = []  # [{'lon': float, 'lat': float, 'time': float, 'idx': int}]
        
        # 그린 경로 포인트 초기화
        if 'drawn_path_points' not in st.session_state:
            st.session_state['drawn_path_points'] = []
        
        # Plotly 차트 표시 - 클릭 이벤트 활성화
        # Streamlit의 on_select는 선택 이벤트를 처리하지만, mapbox의 클릭 좌표는 제한적일 수 있음
        chart_event = st.plotly_chart(fig, width='stretch', key="trajectory_chart", on_select="rerun", use_container_width=True)
        
        # 클릭/선택 이벤트 처리 - 맵 클릭 및 경로 그리기
        if chart_event is not None:
            try:
                # 디버깅: 이벤트 데이터 구조 확인
                if debug_cp:
                    st.json(chart_event)
                    st.info("위 JSON 데이터를 확인하여 이벤트 구조를 파악하세요.")
                
                if isinstance(chart_event, dict):
                    # Streamlit의 on_select는 selection 객체를 반환
                    selected_points = []
                    
                    # 형식 1: selection.points (Streamlit의 표준 형식)
                    selection = chart_event.get('selection', {})
                    if isinstance(selection, dict):
                        selected_points = selection.get('points', [])
                    
                    # 형식 2: 직접 points
                    if not selected_points and 'points' in chart_event:
                        selected_points = chart_event.get('points', [])
                    
                    # 형식 3: clickData (클릭 이벤트)
                    if not selected_points:
                        click_data = chart_event.get('clickData', {})
                        if click_data and 'points' in click_data:
                            selected_points = click_data.get('points', [])
                    
                    if debug_cp:
                        st.write(f"Selected points count: {len(selected_points)}")
                        if selected_points:
                            st.write("First point data:", selected_points[0])
                    
                    if selected_points:
                        # 간단한 편집 모드 처리
                        if simple_edit_mode:
                            clicked_lon = None
                            clicked_lat = None
                            trace_name_str = ''
                            point_idx = None
                            
                            # 모든 포인트에서 좌표와 trace 정보 추출
                            for point in selected_points:
                                # trace_name 확인 (여러 방법 시도)
                                trace_name = (point.get('trace_name', '') or 
                                            point.get('data', {}).get('name', '') or
                                            point.get('name', '') or
                                            point.get('fullData', {}).get('name', '') or
                                            point.get('curveNumber', None))
                                if trace_name and not trace_name_str:
                                    trace_name_str = str(trace_name)
                                
                                # 좌표 추출 (여러 방법 시도)
                                if clicked_lon is None:
                                    clicked_lon = (point.get('lon') or 
                                                  point.get('x') or 
                                                  point.get('lng') or 
                                                  point.get('longitude'))
                                if clicked_lat is None:
                                    clicked_lat = (point.get('lat') or 
                                                  point.get('y') or 
                                                  point.get('latitude'))
                                
                                # point index 추출
                                if point_idx is None:
                                    point_idx = (point.get('pointIndex', None) or 
                                               point.get('point_index', None) or
                                               point.get('pointNumber', None) or
                                               point.get('point_number', None))
                            
                            # 좌표를 찾았는지 확인
                            if clicked_lon is not None and clicked_lat is not None:
                                edit_points = st.session_state.get('simple_edit_points', [])
                                selected_edit_idx = st.session_state.get('selected_edit_point_idx', None)
                                
                                # Edit Point 클릭 확인
                                if 'Edit Points' in trace_name_str or 'Edit Point' in trace_name_str:
                                    # Edit Point 클릭: 선택/해제
                                    if point_idx is not None and point_idx < len(edit_points):
                                        if selected_edit_idx == point_idx:
                                            # 같은 포인트 재클릭: 선택 해제
                                            st.session_state['selected_edit_point_idx'] = None
                                        else:
                                            # 다른 포인트 선택
                                            st.session_state['selected_edit_point_idx'] = point_idx
                                        st.rerun()
                                
                                # 선택된 편집 포인트가 있고, Edit Point가 아닌 곳을 클릭: 포인트 이동
                                elif selected_edit_idx is not None:
                                    # 선택된 편집 포인트를 클릭한 위치로 이동
                                    if selected_edit_idx < len(edit_points):
                                        edit_points[selected_edit_idx]['lon'] = clicked_lon
                                        edit_points[selected_edit_idx]['lat'] = clicked_lat
                                        st.session_state['simple_edit_points'] = edit_points
                                        st.session_state['selected_edit_point_idx'] = None
                                        st.success(f"✅ Edit point moved to ({clicked_lon:.6f}, {clicked_lat:.6f})")
                                        st.rerun()
                                
                                # OS Trajectory 라인 클릭 또는 지도 클릭: 편집 포인트 추가
                                # trace_name이 비어있거나 OS Trajectory 관련이면 항적 라인 클릭으로 간주
                                else:
                                    # 항적 라인 클릭 또는 지도 클릭: 해당 위치에 편집 포인트 추가
                                    # 현재 expert_path 사용 (이미 위에서 계산됨)
                                    expert_lon = expert_path['lon'] if 'lon' in expert_path.columns else expert_path['x']
                                    expert_lat = expert_path['lat'] if 'lat' in expert_path.columns else expert_path['y']
                                    expert_time = expert_path['time'].values
                                    
                                    # 클릭한 위치에 가장 가까운 항적 포인트 찾기
                                    if isinstance(expert_lon, pd.Series):
                                        distances = np.sqrt((expert_lon - clicked_lon)**2 + (expert_lat - clicked_lat)**2)
                                        closest_idx = distances.idxmin()
                                        closest_time = expert_time.iloc[closest_idx] if isinstance(expert_time, pd.Series) else expert_time[closest_idx]
                                    else:
                                        distances = np.sqrt((expert_lon - clicked_lon)**2 + (expert_lat - clicked_lat)**2)
                                        closest_idx = np.argmin(distances)
                                        closest_time = expert_time[closest_idx] if isinstance(expert_time, np.ndarray) else expert_time.iloc[closest_idx]
                                    
                                    new_edit_point = {
                                        'lon': clicked_lon,
                                        'lat': clicked_lat,
                                        'time': closest_time,
                                        'idx': closest_idx
                                    }
                                    
                                    edit_points.append(new_edit_point)
                                    st.session_state['simple_edit_points'] = edit_points
                                    st.success(f"✅ Edit point added at ({clicked_lon:.6f}, {clicked_lat:.6f})")
                                    st.rerun()
                            else:
                                # 좌표를 찾지 못한 경우 디버깅 정보 표시
                                if debug_cp:
                                    st.warning(f"Could not extract coordinates. Trace: {trace_name_str}, Points: {len(selected_points)}")
                                    if selected_points:
                                        st.json(selected_points[0])
                        
                        # 경로 그리기 모드: 클릭한 위치에 포인트 추가
                        elif draw_mode:
                            # 클릭한 위치의 좌표 추출
                            clicked_lon = None
                            clicked_lat = None
                            
                            for point in selected_points:
                                # mapbox에서 lon/lat 추출 시도
                                if 'lon' in point:
                                    clicked_lon = point.get('lon')
                                if 'lat' in point:
                                    clicked_lat = point.get('lat')
                                
                                if clicked_lon is not None and clicked_lat is not None:
                                    break
                                
                                # 대안: x/y 사용
                                if clicked_lon is None and 'x' in point:
                                    clicked_lon = point.get('x')
                                if clicked_lat is None and 'y' in point:
                                    clicked_lat = point.get('y')
                            
                            # 좌표를 찾았으면 그린 경로 포인트에 추가
                            if clicked_lon is not None and clicked_lat is not None:
                                # 기존 포인트 목록 가져오기
                                drawn_points = st.session_state.get('drawn_path_points', [])
                                
                                # 새 포인트 추가
                                new_point = {
                                    'lon': clicked_lon,
                                    'lat': clicked_lat,
                                    'time': len(drawn_points) * 10.0  # 임시 시간 (나중에 조정 가능)
                                }
                                drawn_points.append(new_point)
                                st.session_state['drawn_path_points'] = drawn_points
                                
                                st.success(f"✅ 경로 포인트 추가됨 ({len(drawn_points)}개): ({clicked_lon:.6f}, {clicked_lat:.6f})")
                                st.rerun()
                        
                        # 일반 모드: Control Point 클릭 및 맵 클릭 처리
                        else:
                            cp_clicked = False
                            
                            # 1단계: Control Point 클릭 확인
                            for point in selected_points:
                                # trace_name 확인 (다양한 형식 지원)
                                trace_name = (point.get('trace_name', '') or 
                                            point.get('data', {}).get('name', '') or
                                            point.get('name', '') or
                                            point.get('fullData', {}).get('name', '') or
                                            point.get('curveNumber', None))
                                trace_name_str = str(trace_name) if trace_name else ''
                                
                                if debug_cp:
                                    st.write(f"Trace name: {trace_name_str}, Point data keys: {list(point.keys())}")
                                
                                # Control Points 트레이스인지 확인
                                if 'Control Points' in trace_name_str or 'Waypoints' in trace_name_str:
                                    # point index 확인
                                    point_idx = (point.get('pointIndex', None) or 
                                               point.get('point_index', None) or
                                               point.get('pointNumber', None) or
                                               point.get('point_number', None) or
                                               point.get('pointIndexes', [None])[0] if isinstance(point.get('pointIndexes'), list) else None)
                                    
                                    if point_idx is not None and point_idx < len(waypoints):
                                        # Control Point 클릭: 선택 상태 토글
                                        if st.session_state.get('selected_waypoint_idx') == point_idx:
                                            # 같은 포인트 재클릭 시 선택 해제
                                            st.session_state['selected_waypoint_idx'] = None
                                            if debug_cp:
                                                st.success(f"Control Point {point_idx} deselected")
                                        else:
                                            # 다른 포인트 선택
                                            st.session_state['selected_waypoint_idx'] = point_idx
                                            if debug_cp:
                                                st.success(f"Control Point {point_idx} selected")
                                        cp_clicked = True
                                        st.rerun()
                                        break
                            
                            # 2단계: Control Point가 클릭되지 않았으면 맵 클릭으로 간주하여 좌표 저장
                            if not cp_clicked:
                                # 모든 선택된 포인트에서 좌표 추출 시도
                                clicked_lon = None
                                clicked_lat = None
                                
                                for point in selected_points:
                                    # mapbox에서 lon/lat 추출 시도
                                    if 'lon' in point:
                                        clicked_lon = point.get('lon')
                                    if 'lat' in point:
                                        clicked_lat = point.get('lat')
                                    
                                    # lon/lat을 찾았으면 중단
                                    if clicked_lon is not None and clicked_lat is not None:
                                        break
                                    
                                    # 대안: x/y 사용 (일반 scatter의 경우)
                                    if clicked_lon is None and 'x' in point:
                                        clicked_lon = point.get('x')
                                    if clicked_lat is None and 'y' in point:
                                        clicked_lat = point.get('y')
                                    
                                    # 대안: lon/lat이 다른 키에 있을 수 있음
                                    if clicked_lon is None:
                                        clicked_lon = point.get('lng') or point.get('longitude')
                                    if clicked_lat is None:
                                        clicked_lat = point.get('latitude')
                                
                                if debug_cp:
                                    st.write(f"Clicked coordinates: lon={clicked_lon}, lat={clicked_lat}")
                                
                                # 좌표를 찾았으면 session_state에 저장 (UI에서 표시 및 이동 버튼 사용)
                                if clicked_lon is not None and clicked_lat is not None:
                                    st.session_state['clicked_lon'] = clicked_lon
                                    st.session_state['clicked_lat'] = clicked_lat
                                    if debug_cp:
                                        st.success(f"Coordinates saved: ({clicked_lon:.6f}, {clicked_lat:.6f})")
                                    st.rerun()
                                elif debug_cp:
                                    st.warning("좌표를 찾을 수 없습니다. 지도의 항적 라인을 클릭해보세요.")
                            
            except Exception as e:
                # 오류 발생 시 디버깅 정보 표시
                st.error(f"⚠️ Event handling error: {str(e)}")
                if debug_cp:
                    import traceback
                    st.code(traceback.format_exc())
                pass
        
        # 현재 시간 표시
        min_time = st.session_state.get('min_time', 0.0)
        max_time = st.session_state['max_time']
        st.info(f"⏱️ Current Time: {current_time:.1f}s / Range: {min_time:.1f}s - {max_time:.1f}s")
        
        # 클릭한 위치 좌표 표시 및 Control Point 이동
        selected_cp_idx = st.session_state.get('selected_waypoint_idx', None)
        clicked_lon = st.session_state.get('clicked_lon', None)
        clicked_lat = st.session_state.get('clicked_lat', None)
        
        # 좌표 표시 및 이동 UI
        if clicked_lon is not None and clicked_lat is not None:
            st.markdown("### 📍 Clicked Location Coordinates")
            col_coord1, col_coord2 = st.columns(2)
            with col_coord1:
                # 좌표를 수정 가능하게 입력
                edited_lon = st.number_input("Longitude", value=float(clicked_lon), format="%.6f", key="edit_clicked_lon")
                st.session_state['clicked_lon'] = edited_lon
            with col_coord2:
                edited_lat = st.number_input("Latitude", value=float(clicked_lat), format="%.6f", key="edit_clicked_lat")
                st.session_state['clicked_lat'] = edited_lat
            
            if selected_cp_idx is not None:
                col_btn1, col_btn2 = st.columns([1, 1])
                with col_btn1:
                    if st.button("✅ Move CP Here", key="move_cp_to_clicked", use_container_width=True):
                        # 선택된 Control Point를 클릭한 위치로 이동
                        point_idx = selected_cp_idx
                        final_lon = st.session_state.get('clicked_lon', clicked_lon)
                        final_lat = st.session_state.get('clicked_lat', clicked_lat)
                        
                        # waypoints 복사본 생성 (원본 데이터 보호)
                        waypoints_df = st.session_state['waypoints'].copy()
                        
                        # 이전 위치 저장 (수정 이력용)
                        old_lon = waypoints_df.iloc[point_idx]['lon'] if 'lon' in waypoints_df.columns else waypoints_df.iloc[point_idx]['x']
                        old_lat = waypoints_df.iloc[point_idx]['lat'] if 'lat' in waypoints_df.columns else waypoints_df.iloc[point_idx]['y']
                        cp_time = waypoints_df.iloc[point_idx]['time'] if 'time' in waypoints_df.columns else 0
                        
                        # 선택된 CP만 업데이트 (다른 CP는 그대로 유지)
                        if 'lon' in waypoints_df.columns:
                            waypoints_df.iloc[point_idx, waypoints_df.columns.get_loc('lon')] = final_lon
                        if 'lat' in waypoints_df.columns:
                            waypoints_df.iloc[point_idx, waypoints_df.columns.get_loc('lat')] = final_lat
                        if 'x' in waypoints_df.columns:
                            waypoints_df.iloc[point_idx, waypoints_df.columns.get_loc('x')] = final_lon
                        if 'y' in waypoints_df.columns:
                            waypoints_df.iloc[point_idx, waypoints_df.columns.get_loc('y')] = final_lat
                        
                        # 업데이트된 waypoints를 session_state에 저장
                        st.session_state['waypoints'] = waypoints_df
                        
                        # Control Point 수정 이력 기록
                        if 'cp_modification_history' not in st.session_state:
                            st.session_state['cp_modification_history'] = []
                        
                        # 수정 이력 추가
                        modification = {
                            'cp_id': point_idx,
                            'time': cp_time,
                            'old_lon': old_lon,
                            'old_lat': old_lat,
                            'new_lon': final_lon,
                            'new_lat': final_lat,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        st.session_state['cp_modification_history'].append(modification)
                        
                        # 보간된 경로 사용하도록 설정 (예상 항적 업데이트)
                        st.session_state['use_original_path'] = False
                        st.session_state['clicked_lon'] = None
                        st.session_state['clicked_lat'] = None
                        
                        st.success(f"✅ Control Point {point_idx} moved to ({final_lon:.6f}, {final_lat:.6f})")
                        st.rerun()
                with col_btn2:
                    if st.button("❌ Clear", key="clear_clicked_coords", use_container_width=True):
                        st.session_state['clicked_lon'] = None
                        st.session_state['clicked_lat'] = None
                        st.rerun()
            else:
                if st.button("❌ Clear", key="clear_clicked_coords_no_cp"):
                    st.session_state['clicked_lon'] = None
                    st.session_state['clicked_lat'] = None
                    st.rerun()
        
        # Control Point 선택 상태 및 경로 업데이트 상태 표시
        if selected_cp_idx is not None:
            st.success(f"📍 **Control Point {selected_cp_idx} is selected (RED).** Click on the map (or trajectory lines) to see coordinates. You can edit the coordinates and click 'Move CP Here' to move it.")
        else:
            st.info("💡 **How to move Control Points:** 1) Click a yellow Control Point (WP0, WP1, ...) to select it (turns RED), 2) Click anywhere on the map to see coordinates (green marker), 3) Edit coordinates if needed, 4) Click 'Move CP Here' button to move the selected point.")
        
        # 경로 업데이트 상태 표시
        simple_edit_points = st.session_state.get('simple_edit_points', [])
        
        if simple_edit_mode:
            if len(simple_edit_points) > 0:
                st.success(f"🖱️ **Simple Edit Mode Active:** {len(simple_edit_points)} edit point(s) added. The blue trajectory is updated based on your edits.")
                # 편집 포인트 관리 UI
                col_clear_edit, col_apply_edit = st.columns(2)
                with col_clear_edit:
                    selected_edit_idx = st.session_state.get('selected_edit_point_idx', None)
                    if selected_edit_idx is not None:
                        if st.button("🗑️ Delete Selected Point", key="delete_selected_edit_point", use_container_width=True):
                            edit_points.pop(selected_edit_idx)
                            st.session_state['simple_edit_points'] = edit_points
                            st.session_state['selected_edit_point_idx'] = None
                            st.success("✅ Edit point deleted")
                            st.rerun()
                    else:
                        if st.button("🗑️ Clear All Edit Points", key="clear_edit_points", use_container_width=True):
                            st.session_state['simple_edit_points'] = []
                            st.session_state['selected_edit_point_idx'] = None
                            st.success("✅ All edit points cleared")
                            st.rerun()
                with col_apply_edit:
                    if st.button("✅ Apply Edit Points to Expert Path", key="apply_edit_points", use_container_width=True):
                        # 편집 포인트를 waypoint로 변환하여 저장
                        if len(simple_edit_points) > 0:
                            edit_waypoints_list = []
                            for ep in simple_edit_points:
                                edit_waypoints_list.append({
                                    'time': ep.get('time', 0),
                                    'lon': ep['lon'],
                                    'lat': ep['lat'],
                                    'x': ep['lon'],
                                    'y': ep['lat']
                                })
                            edit_waypoints_df = pd.DataFrame(edit_waypoints_list)
                            edit_waypoints_df = edit_waypoints_df.sort_values('time').reset_index(drop=True)
                            st.session_state['waypoints'] = edit_waypoints_df
                            st.session_state['use_original_path'] = False
                            st.session_state['simple_edit_mode'] = False
                            st.session_state['simple_edit_points'] = []
                            st.success(f"✅ {len(edit_waypoints_df)} edit points applied to Expert Path!")
                            st.rerun()
            else:
                st.info("🖱️ **Simple Edit Mode Active:** Click on the blue OS trajectory line to add edit points.")
        elif st.session_state.get('use_drawn_path', False):
            drawn_points = st.session_state.get('drawn_path_points', [])
            st.success(f"✏️ **Drawn Path Active:** {len(drawn_points)} points drawn. Click 'Convert to Expert Path' to apply.")
        elif not st.session_state.get('use_original_path', True):
            cp_mod_count = len(st.session_state.get('cp_modification_history', []))
            st.info(f"🔄 **Path Updated:** {cp_mod_count} Control Point(s) modified. The expert path (blue line) shows the interpolated trajectory based on modified Control Points.")
        else:
            st.info("📊 **Original Path:** Using the original OS trajectory. Modify Control Points to create a custom expert path.")
        
        # 그린 경로 관리 UI
        drawn_points = st.session_state.get('drawn_path_points', [])
        if len(drawn_points) > 0:
            st.subheader("✏️ Drawn Path Management")
            col_convert, col_clear, col_export = st.columns(3)
            
            with col_convert:
                if st.button("✅ Convert to Expert Path", key="convert_drawn_path", use_container_width=True):
                    # 그린 경로를 Expert Path로 변환
                    drawn_lons = [p['lon'] for p in drawn_points]
                    drawn_lats = [p['lat'] for p in drawn_points]
                    
                    # 시간 데이터 생성 (원본 OS 데이터의 시간 범위 사용)
                    min_time = st.session_state.get('min_time', 0.0)
                    max_time = st.session_state.get('max_time', 3600.0)
                    drawn_times = np.linspace(min_time, max_time, len(drawn_points))
                    
                    # 그린 경로를 Expert Path로 저장
                    drawn_path_df = pd.DataFrame({
                        'time': drawn_times,
                        'lon': drawn_lons,
                        'lat': drawn_lats,
                        'x': drawn_lons,
                        'y': drawn_lats
                    })
                    
                    # 원본 OS 데이터의 속도/코스 정보 복사 (가능한 경우)
                    if 'spd' in os_data.columns:
                        drawn_speeds = []
                        for i, (lon, lat) in enumerate(zip(drawn_lons, drawn_lats)):
                            distances = np.sqrt((os_data['lon'] - lon)**2 + (os_data['lat'] - lat)**2)
                            closest_idx = distances.idxmin()
                            drawn_speeds.append(os_data.iloc[closest_idx]['spd'])
                        drawn_path_df['spd'] = drawn_speeds
                    
                    if 'co' in os_data.columns:
                        drawn_courses = []
                        for i, (lon, lat) in enumerate(zip(drawn_lons, drawn_lats)):
                            distances = np.sqrt((os_data['lon'] - lon)**2 + (os_data['lat'] - lat)**2)
                            closest_idx = distances.idxmin()
                            drawn_courses.append(os_data.iloc[closest_idx]['co'])
                        drawn_path_df['co'] = drawn_courses
                    
                    # 그린 경로를 session_state에 저장
                    st.session_state['drawn_path'] = drawn_path_df
                    st.session_state['use_drawn_path'] = True
                    st.session_state['use_original_path'] = False
                    
                    st.success(f"✅ 경로가 Expert Path로 변환되었습니다! {len(drawn_points)}개의 좌표 포인트가 적용되었습니다.")
                    st.rerun()
            
            with col_clear:
                if st.button("🗑️ Clear Drawn Path", key="clear_drawn_path", use_container_width=True):
                    st.session_state['drawn_path_points'] = []
                    st.session_state['use_drawn_path'] = False
                    st.session_state['drawn_path'] = None
                    st.success("✅ 그린 경로가 초기화되었습니다.")
                    st.rerun()
            
            with col_export:
                # 그린 경로를 엑셀로 저장
                drawn_lons = [p['lon'] for p in drawn_points]
                drawn_lats = [p['lat'] for p in drawn_points]
                drawn_times = [p['time'] for p in drawn_points]
                
                export_df = pd.DataFrame({
                    'time': drawn_times,
                    'lon': drawn_lons,
                    'lat': drawn_lats,
                    'x': drawn_lons,
                    'y': drawn_lats
                })
                
                # 엑셀 파일로 변환
                from io import BytesIO
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    export_df.to_excel(writer, index=False, sheet_name='Drawn Path')
                output.seek(0)
                
                st.download_button(
                    label="📥 Export to Excel",
                    data=output.getvalue(),
                    file_name=f"drawn_path_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="export_drawn_path",
                    use_container_width=True
                )

    # --- Bidirectional Path Editor (Map ↔ Excel Grid) ---
    st.divider()
    st.subheader("🗺️ & ▦ Bidirectional Path Editor (Map ↔ Excel Grid)")
    st.info("""
    **양방향 편집 모드 사용법:**
    1. **지도에서 그리기:** 지도 왼쪽 'Polyline' 도구로 대략적인 경로를 그리면 아래 엑셀 그리드에 데이터가 생성됩니다.
    2. **엑셀처럼 수정:** 생성된 데이터 표(Grid)에서 위도/경도/시간 값을 직접 수정하면 지도에 즉시 반영됩니다.
    3. **내보내기:** 수정이 완료되면 우측 상단 'Download' 버튼으로 원본과 동일한 형식을 받습니다.
    """)

    # Check if OS data is available
    if 'os_data' in st.session_state:
        os_data = st.session_state['os_data']
        
        col_map, col_grid = st.columns([1, 1])

        # 1. 지도 영역 (Map View)
        with col_map:
            st.markdown("#### 1. Map View (Draw Here)")
            
            # 지도 초기화
            if 'lat' in os_data.columns and 'lon' in os_data.columns:
                center_lat = os_data['lat'].mean()
                center_lon = os_data['lon'].mean()
            else:
                center_lat = os_data['y'].mean()
                center_lon = os_data['x'].mean()

            m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
            
            # KHOA 차트 추가
            selected_base_url = KHOA_TILE_BASE_URL_OPTIONS[2]
            khoa_tile_url = f"{selected_base_url}/ENC/{{z}}/{{x}}/{{y}}.png?key={KHOA_API_KEY}"
            folium.TileLayer(tiles=khoa_tile_url, attr='KHOA', name='KHOA ENC', overlay=True).add_to(m)

            # Draw 플러그인 설정
            draw = Draw(
                export=False,
                position='topleft',
                draw_options={'polyline': True, 'polygon': False, 'rectangle': False, 'circle': False, 'marker': False},
                edit_options={'edit': True, 'remove': True}
            )
            draw.add_to(m)

            # 현재 Grid에 있는 데이터가 있다면 지도에 표시 (Grid -> Map 동기화)
            if 'grid_df' in st.session_state and st.session_state['grid_df'] is not None:
                grid_points = list(zip(st.session_state['grid_df']['lat'], st.session_state['grid_df']['lon']))
                if len(grid_points) > 1:
                    folium.PolyLine(locations=grid_points, color='red', weight=4, opacity=0.8, tooltip="Edited Path").add_to(m)
                    # 시작/끝 마커
                    folium.Marker(grid_points[0], popup="Start", icon=folium.Icon(color='green')).add_to(m)
                    folium.Marker(grid_points[-1], popup="End", icon=folium.Icon(color='red')).add_to(m)

            # 지도 출력 및 그리기 이벤트 수신
            map_output = st_folium(m, width='100%', height=600, key="folium_map", returned_objects=["all_drawings"])

        # 2. 로직 처리: 지도에서 그림 -> Grid 데이터로 변환
        if map_output and map_output.get("all_drawings"):
            # 가장 마지막에 그려진 도형 가져오기
            last_drawing = map_output["all_drawings"][-1]
            geometry_type = last_drawing['geometry']['type']
            
            if geometry_type == 'LineString':
                coords = last_drawing['geometry']['coordinates'] # [[lon, lat], ...]
                # 주의: Folium Draw는 [lon, lat] 순서임
                coords_corrected = [[c[0], c[1]] for c in coords] # lon, lat
                
                # 그리기 이벤트가 발생했고, 기존 Grid 데이터와 다를 경우 업데이트
                # (무한 루프 방지를 위해 세션 상태 관리 필요)
                if 'last_draw_coords' not in st.session_state or st.session_state['last_draw_coords'] != coords_corrected:
                    st.session_state['last_draw_coords'] = coords_corrected
                    
                    # 변환 로직 실행
                    new_grid_df = convert_drawing_to_dataframe(coords_corrected, os_data)
                    st.session_state['grid_df'] = new_grid_df
                    st.session_state['drawn_path'] = new_grid_df
                    st.session_state['use_drawn_path'] = True
                    st.session_state['use_original_path'] = False
                    st.rerun()

        # 3. 엑셀 그리드 영역 (Grid View)
        with col_grid:
            st.markdown("#### 2. Excel Grid View (Edit Here)")
            
            if 'grid_df' not in st.session_state:
                # 초기값: 원본 데이터 혹은 빈 데이터
                st.session_state['grid_df'] = os_data.copy()

            # 데이터 에디터 (Excel 처럼 동작)
            # num_rows="dynamic"을 주어 행 추가/삭제 가능하게 함
            edited_df = st.data_editor(
                st.session_state['grid_df'],
                key="data_editor_grid",
                num_rows="dynamic",
                use_container_width=True,
                height=600,
                column_config={
                    "time": st.column_config.NumberColumn("Time (s)", format="%.1f"),
                    "lat": st.column_config.NumberColumn("Latitude", format="%.6f"),
                    "lon": st.column_config.NumberColumn("Longitude", format="%.6f"),
                    "spd": st.column_config.NumberColumn("Speed (kt)", format="%.1f"),
                    "co": st.column_config.NumberColumn("Course (°)", format="%.1f"),
                }
            )

            # Grid 수정 감지 -> 지도 업데이트 (Grid -> Map 동기화)
            # st.data_editor는 수정된 dataframe을 리턴하므로, 이를 세션에 반영
            if not edited_df.equals(st.session_state['grid_df']):
                st.session_state['grid_df'] = edited_df
                st.session_state['drawn_path'] = edited_df
                st.session_state['use_drawn_path'] = True
                st.session_state['use_original_path'] = False
                st.rerun() # 지도 업데이트를 위해 리로드

        # 4. 내보내기 버튼 (원본 형식 유지)
        st.divider()
        col_exp1, col_exp2 = st.columns([4, 1])
        with col_exp2:
            if 'grid_df' in st.session_state and st.session_state['grid_df'] is not None:
                # 엑셀 변환
                from io import BytesIO
                output = BytesIO()
                
                # 저장할 데이터프레임 정리 (불필요한 컬럼 제거 및 순서 정렬)
                save_df = st.session_state['grid_df'].copy()
                
                # 필수 컬럼 보장
                target_cols = ['time', 'lat', 'lon', 'spd', 'co', 'mmsi', 'shipname']
                final_cols = [c for c in target_cols if c in save_df.columns]
                
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    save_df[final_cols].to_excel(writer, index=False, sheet_name='Edited_Trajectory')
                output.seek(0)
                
                st.download_button(
                    label="📥 Download as Excel",
                    data=output.getvalue(),
                    file_name=f"Edited_Trajectory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    else:
        st.warning("⚠️ Please load OS data first from the sidebar.")
    
    # Expert Path 저장 섹션
    if 'os_data' in st.session_state:
        st.divider()
        st.subheader("💾 Save Expert Behavior")
        expert_name = st.text_input("Expert Name", "Expert_01", key="expert_name")
        scenario_name = st.text_input("Scenario Name", "Scenario_01", key="scenario_name")
        
        # 저장 전 미리보기
        st.markdown("#### 📋 Trajectory Preview")
        os_data = st.session_state['os_data']
        
        # 현재 Expert Path 결정 (저장될 경로)
        use_drawn_path = st.session_state.get('use_drawn_path', False)
        drawn_path_df = st.session_state.get('drawn_path', None)
        
        if use_drawn_path and drawn_path_df is not None:
            preview_path = drawn_path_df.copy()
            path_source = "Drawn Path"
        else:
            use_original = st.session_state.get('use_original_path', True)
            if use_original:
                preview_path = os_data.copy()
                path_source = "Original Trajectory"
            else:
                current_waypoints = st.session_state.get('waypoints', None)
                if current_waypoints is not None and len(current_waypoints) > 0:
                    preview_path = interpolate_path(current_waypoints, len(os_data), os_data=os_data)
                    path_source = "Interpolated from Control Points"
                else:
                    preview_path = os_data.copy()
                    path_source = "Original Trajectory"
        
        # 미리보기 정보 표시
        col_info1, col_info2, col_info3 = st.columns(3)
        with col_info1:
            st.metric("Path Source", path_source)
        with col_info2:
            st.metric("Data Points", len(preview_path))
        with col_info3:
            time_range = f"{preview_path['time'].min():.1f}s - {preview_path['time'].max():.1f}s"
            st.metric("Time Range", time_range)
        
        # 수정 이력 요약
        cp_history = st.session_state.get('cp_modification_history', [])
        if len(cp_history) > 0:
            st.info(f"📝 **Modification Summary:** {len(cp_history)} Control Point modification(s) recorded")
        
        # 저장 버튼
        if st.button("💾 Save Expert Trajectory", key="save_expert_trajectory", use_container_width=True):
            try:
                # 최종 Expert Path 결정 (preview_path 사용)
                expert_path = preview_path.copy()
                
                # 원본 OS 데이터의 속도/코스 정보가 있으면 유지
                if 'spd' not in expert_path.columns and 'spd' in os_data.columns:
                    # 시간 기반으로 매칭
                    expert_speeds = []
                    for t in expert_path['time'].values:
                        closest_idx = np.argmin(np.abs(os_data['time'].values - t))
                        expert_speeds.append(os_data.iloc[closest_idx]['spd'])
                    expert_path['spd'] = expert_speeds
                
                if 'co' not in expert_path.columns and 'co' in os_data.columns:
                    expert_courses = []
                    for t in expert_path['time'].values:
                        closest_idx = np.argmin(np.abs(os_data['time'].values - t))
                        expert_courses.append(os_data.iloc[closest_idx]['co'])
                    expert_path['co'] = expert_courses
                
                # 메타데이터 추가
                expert_path['expert_name'] = expert_name
                expert_path['scenario_name'] = scenario_name
                expert_path['timestamp'] = datetime.now().strftime('%Y%m%d_%H%M%S')
                expert_path['path_source'] = path_source
                expert_path['num_modifications'] = len(cp_history)
                
                # 수정 이력 정보 추가 (JSON 형태로)
                if len(cp_history) > 0:
                    import json
                    expert_path['modification_history'] = json.dumps(cp_history)
                
                # 파일명 생성
                filename = f"{expert_name}_{scenario_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                filepath = os.path.join(get_save_dir(), filename)
                
                # 저장
                expert_path.to_csv(filepath, index=False)
                
                st.success(f"✅ Saved successfully as {filename}")
                st.info(f"📊 **Saved Path Info:** {path_source}, {len(expert_path)} points, {len(cp_history)} modifications")
                st.info("This trajectory will be used for Inverse Reinforcement Learning training.")
                
                # 저장 후 선택적으로 초기화
                if st.checkbox("Reset after save", key="reset_after_save", value=False):
                    st.session_state['use_original_path'] = True
                    st.session_state['use_drawn_path'] = False
                    st.session_state['drawn_path'] = None
                    st.session_state['drawn_path_points'] = []
                    st.session_state['cp_modification_history'] = []
                    if 'waypoints' in st.session_state:
                        waypoints_init = initialize_waypoints_from_trajectory(os_data, num_waypoints=5)
                        st.session_state['waypoints'] = waypoints_init
                    st.rerun()
                    
            except Exception as e:
                st.error(f"❌ Error saving trajectory: {str(e)}")
                st.exception(e)

elif mode == "Admin Review Mode":
    st.sidebar.header("📂 Saved Expert Data")
    
    # 저장된 파일 목록 불러오기
    save_dir = get_save_dir()
    try:
        files = [f for f in os.listdir(save_dir) if f.endswith('.csv')]
    except Exception as e:
        st.sidebar.error(f"❌ 저장 경로 접근 오류: {str(e)}")
        files = []
    
    if not files:
        st.warning("No expert data saved yet.")
    else:
        selected_file = st.sidebar.selectbox("Select File", files)
        
        if selected_file:
            st.subheader(f"Reviewing: {selected_file}")
            
            # 데이터 로드
            save_dir = get_save_dir()
            df = pd.read_csv(os.path.join(save_dir, selected_file))
            
            # 지도 배경 선택
            map_background_review = st.selectbox(
                "Map Background",
                ["OpenStreetMap + KHOA Electronic Chart", "OpenStreetMap Only", "KHOA Electronic Chart Only"],
                index=0,
                key="map_background_review",
                help="지도 배경을 선택하세요."
            )
            
            # KHOA 해도 설정 (KHOA가 포함된 경우에만 표시)
            if "KHOA" in map_background_review:
                col_layer_review, col_url_review = st.columns(2)
                with col_layer_review:
                    khoa_layer_review = st.selectbox(
                        "KHOA Layer Type", 
                        ["haareum", "ENC", "chart", "haareum2024"],
                        index=1,  # ENC를 기본값으로
                        key="khoa_layer_review",
                        help="KHOA 해도 레이어 타입을 선택하세요."
                    )
                    st.session_state['khoa_layer_review'] = khoa_layer_review
                
                with col_url_review:
                    url_option_idx_review = st.session_state.get('khoa_url_option_review', 0)
                    khoa_url_option_review = st.selectbox(
                        "KHOA URL Option",
                        [f"Option {i+1}: {url.split('/')[-2] if '/' in url else url}" for i, url in enumerate(KHOA_TILE_BASE_URL_OPTIONS)],
                        index=url_option_idx_review,
                        key="khoa_url_option_review_select",
                        help="KHOA API URL 옵션을 선택하세요."
                    )
                    selected_url_idx_review = [f"Option {i+1}: {url.split('/')[-2] if '/' in url else url}" for i, url in enumerate(KHOA_TILE_BASE_URL_OPTIONS)].index(khoa_url_option_review)
                    st.session_state['khoa_url_option_review'] = selected_url_idx_review
            
            # 2D 그래프 시각화 (시간에 따른 색상 그라데이션)
            fig = go.Figure()
            
            # lat, lon이 있으면 사용, 없으면 x, y를 lat, lon으로 사용
            if 'lat' in df.columns and 'lon' in df.columns:
                plot_lon = df['lon']
                plot_lat = df['lat']
            else:
                plot_lon = df['x']
                plot_lat = df['y']
            
            # 전체 항적 (연한 파란색)
            fig.add_trace(go.Scattermapbox(
                lon=plot_lon,
                lat=plot_lat,
                mode='lines',
                name='Expert Path Trajectory',
                line=dict(color='rgba(0,0,255,0.5)', width=3),
                showlegend=True,
                hoverinfo='skip'
            ))
            
            center_lon = np.mean(plot_lon)
            center_lat = np.mean(plot_lat)
            
            # 지도 배경 설정
            layers_review = []
            
            # OpenStreetMap + KHOA 해도 조합
            if map_background_review == "OpenStreetMap + KHOA Electronic Chart":
                base_style_review = "open-street-map"
                selected_layer = st.session_state.get('khoa_layer_review', 'ENC')
                selected_base_url_review = KHOA_TILE_BASE_URL_OPTIONS[st.session_state.get('khoa_url_option_review', 2)]
                tile_url_template = f"{selected_base_url_review}/{selected_layer}/{{z}}/{{x}}/{{y}}.png?key={KHOA_API_KEY}"
                
                layers_review.append({
                    "sourcetype": "raster",
                    "source": tile_url_template,
                    "below": "traces",
                    "opacity": 0.7,
                    "type": "raster"
                })
            
            elif map_background_review == "KHOA Electronic Chart Only":
                base_style_review = "white-bg"
                selected_layer = st.session_state.get('khoa_layer_review', 'ENC')
                selected_base_url_review = KHOA_TILE_BASE_URL_OPTIONS[st.session_state.get('khoa_url_option_review', 2)]
                tile_url_template = f"{selected_base_url_review}/{selected_layer}/{{z}}/{{x}}/{{y}}.png?key={KHOA_API_KEY}"
                
                layers_review.append({
                    "sourcetype": "raster",
                    "source": tile_url_template,
                    "below": "traces",
                    "opacity": 1.0,
                    "type": "raster"
                })
            
            else:  # OpenStreetMap Only
                base_style_review = "open-street-map"
            
            # 지도 레이아웃 설정
            try:
                fig.update_layout(
                    mapbox=dict(
                        style=base_style_review,
                        center=dict(lon=center_lon, lat=center_lat),
                        zoom=12,
                        layers=layers_review if layers_review else None
                    ),
                )
            except Exception as e:
                st.warning(f"⚠️ 지도 설정 오류: {str(e)}. OpenStreetMap으로 전환합니다.")
                fig.update_layout(
                    mapbox=dict(
                        style="open-street-map",
                        center=dict(lon=center_lon, lat=center_lat),
                        zoom=12
                    ),
                )
                
            fig.update_layout(
                height=600,
                margin=dict(r=0, b=0, l=0, t=50),
                hovermode='closest'
            )
            st.plotly_chart(fig, width='stretch')
            
            # 데이터 다운로드 버튼
            save_dir = get_save_dir()
            with open(os.path.join(save_dir, selected_file), "rb") as f:
                st.download_button("Download CSV", f, file_name=selected_file)