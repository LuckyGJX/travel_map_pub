import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.features import DivIcon
import numpy as np
from PIL import Image
import requests
import os
import datetime
# 创建文件保存目录
if not os.path.exists("site_icons"):
    os.makedirs("site_icons")

# 高德地图API
def get_lat_lon(addr):
    para = {
        'key': 'xxx',  # 请替换为你的高德地图API Key
        'address': addr
    }
    url = 'https://restapi.amap.com/v3/geocode/geo?'  # 高德地图地理编码API服务地址
    result = requests.get(url, para).json()
    if result['geocodes']:
        lon_lat = result['geocodes'][0]['location']
        lon, lat = lon_lat.split(',')
        return float(lat), float(lon)
    return None, None

def create_thumbnail(image, thumbnail_size=(36, 36)):
    image.thumbnail(thumbnail_size)
    return image

def bezier_curve(start, end, control, num_points=100):
    t = np.linspace(0, 1, num_points)
    curve = (1-t)**2 * np.array(start)[:, np.newaxis] + 2*(1-t)*t * np.array(control)[:, np.newaxis] + t**2 * np.array(end)[:, np.newaxis]
    return curve.T

def create_map(center, zoom_start=14):
    return folium.Map(location=center, zoom_start=zoom_start,
                      tiles='http://map.geoq.cn/ArcGIS/rest/services/ChinaOnlineCommunity/MapServer/tile/{z}/{y}/{x}',
                      attr='灰色版')

def add_points_and_routes_to_map(points, site_activities, routes, map_obj, route_color, layer_name):
    fg = folium.FeatureGroup(name=layer_name)
    for idx, (geo_name, display_name, activities, icon_path) in site_activities.items():
        coord = points[idx]
        if icon_path:
            thumbnail_image = create_thumbnail(icon_path)
            thumbnail_path = f"./site_icons/thumbnail_{display_name}.png"
            thumbnail_image.save(thumbnail_path)
            fg.add_child(folium.Marker(
                location=coord,
                icon=folium.CustomIcon(thumbnail_path, icon_size=(50, 50)),
                popup=display_name
            ))

    for start, end, time, distance in routes:
        start_coord = points[start]
        end_coord = points[end]
        control = [(start_coord[0] + end_coord[0]) / 2 + 0.001, (start_coord[1] + end_coord[1]) / 2 + 0.001]
        curve = bezier_curve(start_coord, end_coord, control)
        
        fg.add_child(folium.PolyLine(
            locations=curve.tolist(),
            color=route_color,
            weight=2.5,
            opacity=1
        ))
        midpoint = [(start_coord[0] + end_coord[0]) / 2, (start_coord[1] + end_coord[1]) / 2]
        fg.add_child(folium.Marker(
            location=midpoint,
            icon=DivIcon(
                icon_size=(250, 36),
                icon_anchor=(0, 0),
                html=f'<div style="font-size: 10pt; color : black">{distance}, {time}</div>',
            )
        ))
        geo_name, display_name, activities, _ = site_activities[start]
        activity_html = f'<b>{display_name}</b><br>'
        for activity, activity_time, activity_color in activities:
            activity_html += f'<span style="font-size: 10pt; color : {activity_color}">{activity} ({activity_time})</span><br>'
        fg.add_child(folium.Marker(
            location=start_coord,
            icon=DivIcon(
                icon_size=(250, 36),
                icon_anchor=(-20, 20),
                html=f'<div style="font-size: 12pt; color : black">{activity_html}</div>',
            )
        ))
    
    map_obj.add_child(fg)

# 计算地图中心点
def calculate_center(points):
    lats = [coord[0] for coord in points.values()]
    lons = [coord[1] for coord in points.values()]
    return [np.mean(lats), np.mean(lons)]

# Streamlit app
st.title("旅行行程地图生成器")

# 用户输入
days = st.number_input("请输入旅行天数", min_value=1, max_value=7, value=1, step=1)

sample_days = []
points_to_edit = st.checkbox("编辑地点经纬度")

for day in range(days):
    st.subheader(f"第 {day+1} 天")
    lay_name = st.text_input(f"第 {day+1} 天的行程名称", f"行程 {day+1}")
    route_color = st.color_picker(f"选择第 {day+1} 天路线的颜色", "#0000FF")

    points = {}
    site_activities = {}
    routes = []
    
    num_points = st.number_input(f"请输入第 {day+1} 天的地点数", min_value=1, max_value=10, value=3, step=1)
    for i in range(num_points):
        st.subheader(f"第 {day+1} 天的第 {i+1} 个地点")
        geo_name = st.text_input(f"第 {day+1} 天的第 {i+1} 个地点用于获取经纬度的名称", f"地点 {i+1}")
        display_name = st.text_input(f"第 {day+1} 天的第 {i+1} 个地点用于在地图上展示的名称", f"展示地点 {i+1}")
        uploaded_file = st.file_uploader(f"上传第 {day+1} 天的第 {i+1} 个地点的图标", type=["png", "jpg", "jpeg"])
        activities = st.text_area(f"第 {day+1} 天的第 {i+1} 个地点的活动 (格式: 活动,时间,颜色)", "活动1,时间1,颜色1\n活动2,时间2,颜色2")

        activity_list = [tuple(act.split(",")) for act in activities.split("\n")]
        lat, lon = get_lat_lon(geo_name)
        if lat and lon:
            points[i+1] = [lat, lon]
        else:
            st.error(f"无法获取 {geo_name} 的经纬度，请检查输入的名称是否正确。")
        
        if points_to_edit:
            edit_location = st.checkbox(f"编辑第 {day+1} 天的第 {i+1} 个地点的经纬度", key=f"edit_{day+1}_{i+1}")
            if edit_location:
                st_map = st_folium(create_map(center=points[i+1], zoom_start=14), width=700, height=450)
                if st_map:
                    clicked_lat_lon = st_map.get('last_clicked', None)
                    if clicked_lat_lon:
                        points[i+1] = [clicked_lat_lon['lat'], clicked_lat_lon['lng']]
                        st.success(f"已更新第 {day+1} 天的第 {i+1} 个地点的经纬度为: {points[i+1]}")
        
        if uploaded_file:
            image = Image.open(uploaded_file)
            site_activities[i+1] = (geo_name, display_name, activity_list, image)
        else:
            site_activities[i+1] = (geo_name, display_name, activity_list, None)
    
    num_routes = st.number_input(f"请输入第 {day+1} 天的路线数", min_value=0, max_value=10, value=2, step=1)
    for j in range(num_routes):
        st.subheader(f"第 {day+1} 天的第 {j+1} 条路线")
        start = st.number_input(f"第 {day+1} 天的第 {j+1} 条路线的起点编号", min_value=1, max_value=num_points, value=1, step=1)
        end = st.number_input(f"第 {day+1} 天的第 {j+1} 条路线的终点编号", min_value=1, max_value=num_points, value=2, step=1)
        time = st.text_input(f"第 {day+1} 天的第 {j+1} 条路线的步行时间", "步行14min")
        distance = st.text_input(f"第 {day+1} 天的第 {j+1} 条路线的距离", "1.2km")
        routes.append((start, end, time, distance))
    
    sample_days.append({
        "points": points,
        "site_activities": site_activities,
        "routes": routes,
        "route_color": route_color,
        "lay_name": lay_name
    })

# 计算所有天数的点的中心
all_points = {k: v for day_data in sample_days for k, v in day_data["points"].items()}
map_center = calculate_center(all_points)

# 创建地图
m = create_map(center=map_center)

for day_data in sample_days:
    layer_name = day_data["lay_name"] + '路线'
    add_points_and_routes_to_map(day_data["points"], day_data["site_activities"], day_data["routes"], m, day_data["route_color"], layer_name)

folium.LayerControl().add_to(m)
timestamp = int(datetime.datetime.now().timestamp())
if st.checkbox('是否下载'):
    file_name  = "travel{}.html".format(timestamp)  
    m.save(file_name)
    with open(file_name,'rb') as f:
            st.download_button('下载结果html文件', f,"travel_map.html")  # Defaults to 'text/plain'
st_folium(m,width = '1000')
