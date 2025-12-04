from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import os
import time
from datetime import datetime

# 导入自定义模块
try:
    from modules.astronomy import (
        get_sun_position,
        convert_lunar_to_solar, 
        match_zodiac_sign_interval,
        determine_solar_term,
        get_28_mansions_for_display,
        generate_solar_term_music_prompt,
        get_all_mansions_positions,
        # 保留兼容性
        calc_mansion, get_moon_position
    )
    from modules.wuxing import get_element
    from modules.mapping import map_to_params, get_full_music_config, get_solar_term_music_config
    from modules.generation import generate_music
except ImportError as e:
    print(f"模块导入错误: {e}")
    print("请确保modules目录下有所有必要的Python文件")
    exit(1)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="中国时间",
    description="基于传统中国天文学和十二星次的音乐生成系统",
    version="1.0.0"
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务
app.mount("/static", StaticFiles(directory="static"), name="static")

# 数据模型
class TimeSelection(BaseModel):
    year: int
    month: int
    day: int
    hour: int
    is_lunar: bool = False

class LocationSelection(BaseModel):
    latitude: float
    longitude: float
    address: Optional[str] = None

class AstronomyRequest(BaseModel):
    time_data: TimeSelection
    location_data: LocationSelection


# ==================== 页面路由 ====================
@app.get("/")
async def time_selector():
    """第一步：时间选择页面"""
    return FileResponse('static/time-selector.html')

@app.get("/location")
async def location_selector():
    """第二步：位置选择页面"""
    return FileResponse('static/location-selector.html')

@app.get("/sphere")
async def sphere():
    """第三步：太阳节气音乐页面"""
    return FileResponse('static/sphere.html')  # 太阳/节气版本

@app.get("/solar")
async def solar():
    """第三步：太阳节气音乐页面"""
    return FileResponse('static/solar.html')  # 太阳/节气版本

@app.get("/starmap")
async def starmap():
    """第三步：星图音乐页面"""
    return FileResponse('static/starmap.html')

# 🎯 添加这行
@app.get("/stellarium_test.html")
async def stellarium_test():
    """Stellarium测试页面"""
    return FileResponse('static/stellarium_test.html')

@app.get("/stellarium_web_engine.html")
async def stellarium_web_engine():
    """Stellarium Web Engine页面"""
    return FileResponse('static/stellarium_web_engine.html')

@app.get("/api/solar-longitude")
async def get_solar_longitude_api(
    year: int = Query(..., description="年份"),
    month: int = Query(..., description="月份"), 
    day: int = Query(..., description="日期"),
    hour: int = Query(12, description="小时")
):
    """获取精确的太阳黄经 - 直接使用astropy"""
    try:
        # 直接使用astropy计算
        from astropy.time import Time
        from astropy.coordinates import get_sun
        import warnings
        warnings.filterwarnings('ignore')
        
        time_str = f'{year}-{month:02d}-{day:02d} {hour:02d}:00:00'
        time = Time(time_str, format='iso', scale='utc')
        sun = get_sun(time)
        longitude = sun.geocentrictrueecliptic.lon.degree % 360
        
        return {"longitude": round(longitude, 2)}
        
    except Exception as e:
        logger.error(f"太阳黄经计算失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== API接口 ====================
@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "3.0.0"
    }

@app.get("/api/mansion") 
async def get_mansion_data(
    date: Optional[str] = Query(None, description="日期时间"),
    is_lunar: bool = Query(False, description="是否为农历"),
    mode: str = Query("music", description="模式: music(音乐生成), mansions(获取星宿), visualization(可视化)")
):
    """获取星宿数据 - 支持三种模式"""
    logger.info(f"🚀 ==================== API调用开始 ====================")
    logger.info(f"📋 [API] 接收到请求参数:")
    logger.info(f"    - 日期: {date}")
    logger.info(f"    - 是否农历: {is_lunar}")
    logger.info(f"    - 模式: {mode}")
    
    try:
        # ==================== 步骤1: 时间解析和转换 ====================
        logger.info(f"📅 [步骤1] 开始时间解析和转换...")
        
        if date:
            try:
                dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                year, month, day, hour = dt.year, dt.month, dt.day, dt.hour
                logger.info(f"✅ [步骤1] 日期解析成功: {year}-{month}-{day} {hour}:00")
            except ValueError:
                dt = datetime.now()
                year, month, day, hour = dt.year, dt.month, dt.day, dt.hour
                logger.warning(f"⚠️ [步骤1] 日期解析失败，使用当前时间: {year}-{month}-{day} {hour}:00")
        else:
            dt = datetime.now() 
            year, month, day, hour = dt.year, dt.month, dt.day, dt.hour
            logger.info(f"📅 [步骤1] 使用当前时间: {year}-{month}-{day} {hour}:00")
        
        # ==================== 步骤2: 农历转公历（如果需要） ====================
        if is_lunar:
            logger.info(f"🌙 [步骤2] 检测到农历标志，开始农历转公历...")
            year, month, day = convert_lunar_to_solar(year, month, day)
            dt = datetime(year, month, day, hour)
            logger.info(f"✅ [步骤2] 农历转换完成，最终日期: {year}-{month}-{day} {hour}:00")
        else:
            logger.info(f"📅 [步骤2] 公历日期，无需转换")
        
        timestamp = dt.timestamp()
        latitude, longitude = 22.3193, 114.1694
        logger.info(f"🌍 [步骤2] 最终时间戳: {timestamp}")
        logger.info(f"📍 [步骤2] 观测位置: 纬度{latitude}°, 经度{longitude}°")
        
        # ==================== 步骤3: astropy计算太阳黄经 ====================
        logger.info(f"☀️ [步骤3] 开始astropy计算太阳黄经...")
        sun_pos = get_sun_position(timestamp, latitude, longitude)
        if 'ecliptic_longitude' not in sun_pos:
            raise ValueError("无法获取太阳黄经数据")
        
        logger.info(f"✅ [步骤3] 太阳黄经计算完成: {sun_pos['ecliptic_longitude']:.2f}°")
        
        response_data = {
            "success": True,
            "timestamp": dt.isoformat(),
            "sun_position": sun_pos,
            "mode": mode
        }
        
        # ==================== 三分支处理 ====================
        logger.info(f"🔀 [分支选择] 进入模式: {mode}")
        
        if mode == "music":
            # ==================== 分支A: 音乐生成路径 ====================
            logger.info(f"🎵 [分支A] 音乐生成路径: 匹配十二星次区间 → 确定节气 → 生成音乐提示词 → 调用API → 播放联动")
            
            # 步骤4A: 匹配十二星次区间
            logger.info(f"🌟 [步骤4A] 开始匹配十二星次区间...")
            zodiac_sign, zodiac_data = match_zodiac_sign_interval(sun_pos['ecliptic_longitude'])
            logger.info(f"✅ [步骤4A] 十二星次匹配完成: {zodiac_sign}")
            
            # 步骤5A: 确定对应节气
            logger.info(f"🌱 [步骤5A] 开始确定对应节气...")
            solar_term = determine_solar_term(zodiac_data, sun_pos['ecliptic_longitude'])
            logger.info(f"✅ [步骤5A] 节气确定完成: {solar_term}")
            
            # 步骤6A: 生成节气音乐提示词
            logger.info(f"🎼 [步骤6A] 开始生成节气音乐提示词...")
            music_prompt = generate_solar_term_music_prompt(solar_term, zodiac_sign)
            logger.info(f"✅ [步骤6A] 音乐提示词生成完成")
            
            response_data.update({
                "zodiac_sign": zodiac_sign,
                "zodiac_longitude_range": {"start": zodiac_data["start"], "end": zodiac_data["end"]},
                "solar_term": solar_term,
                "music_prompt": music_prompt,
                "process": "solar_term_music_generation",
                # 兼容字段
                "mansion": solar_term,
                "element": "节气",
                "sun_ecliptic_lon": sun_pos['ecliptic_longitude'],
                "instrument": "传统民乐",
                "mode": "五声音阶"
            })
            
            logger.info(f"🎵 [分支A完成] 音乐生成路径完成，准备调用音乐API和播放联动")
            
        elif mode == "mansions":
            # ==================== 分支B: 获取星宿路径 ====================
            logger.info(f"🏛️ [分支B] 获取星宿路径: 匹配十二星次区间 → 获取28星宿")
            
            # 步骤4B: 匹配十二星次区间
            logger.info(f"🌟 [步骤4B] 开始匹配十二星次区间...")
            zodiac_sign, zodiac_data = match_zodiac_sign_interval(sun_pos['ecliptic_longitude'])
            logger.info(f"✅ [步骤4B] 十二星次匹配完成: {zodiac_sign}")
            
            # 步骤5B: 获取对应二十八星宿
            logger.info(f"🏛️ [步骤5B] 开始获取对应二十八星宿...")
            mansions_in_zodiac = get_28_mansions_for_display(zodiac_data)
            logger.info(f"✅ [步骤5B] 获取星宿完成: {mansions_in_zodiac}")
            
            response_data.update({
                "zodiac_sign": zodiac_sign,
                "zodiac_longitude_range": {"start": zodiac_data["start"], "end": zodiac_data["end"]},
                "mansions_in_zodiac": mansions_in_zodiac,
                "process": "get_mansions",
                # 兼容字段
                "mansion": f"{zodiac_sign}星次",
                "element": "星宿",
                "sun_ecliptic_lon": sun_pos['ecliptic_longitude'],
                "instrument": "星宿显示",
                "mode": "星宿数据"
            })
            
            logger.info(f"🏛️ [分支B完成] 获取星宿路径完成")
            
        elif mode == "visualization":
            # ==================== 分支C: Three.js可视化路径 ====================
            logger.info(f"🎭 [分支C] Three.js可视化路径: astropy计算太阳黄经 → Three.js渲染星图 → 黄道/星次/星宿可视化")
            
            # 步骤4C: 准备Three.js渲染数据（直接基于太阳黄经）
            logger.info(f"🎭 [步骤4C] 开始准备Three.js渲染数据...")
            
            # 为了可视化，我们仍需要星次和星宿数据
            zodiac_sign, zodiac_data = match_zodiac_sign_interval(sun_pos['ecliptic_longitude'])
            mansions_in_zodiac = get_28_mansions_for_display(zodiac_data)
            all_mansions_positions = get_all_mansions_positions(timestamp)
            
            logger.info(f"✅ [步骤4C] Three.js渲染数据准备完成")
            logger.info(f"🌟 [步骤4C] 黄道坐标: {sun_pos['ecliptic_longitude']:.2f}°")
            logger.info(f"🌟 [步骤4C] 当前星次: {zodiac_sign}")
            logger.info(f"🏛️ [步骤4C] 相关星宿: {mansions_in_zodiac}")
            
            response_data.update({
                "zodiac_sign": zodiac_sign,
                "zodiac_longitude_range": {"start": zodiac_data["start"], "end": zodiac_data["end"]},
                "mansions_in_zodiac": mansions_in_zodiac,
                "all_mansions_positions": all_mansions_positions,
                "ecliptic_data": {
                    "longitude": sun_pos['ecliptic_longitude'],
                    "latitude": sun_pos['ecliptic_latitude']
                },
                "process": "threejs_visualization",
                # 兼容字段
                "mansion": f"{zodiac_sign}星次",
                "element": "可视化",
                "sun_ecliptic_lon": sun_pos['ecliptic_longitude'],
                "instrument": "星图显示",
                "mode": "天文可视化"
            })
            
            logger.info(f"🎭 [分支C完成] Three.js可视化路径完成，准备黄道/星次/星宿可视化")
        
        else:
            logger.warning(f"⚠️ [分支选择] 未知模式: {mode}，使用默认音乐模式")
            # 默认走音乐路径
            zodiac_sign, zodiac_data = match_zodiac_sign_interval(sun_pos['ecliptic_longitude'])
            solar_term = determine_solar_term(zodiac_data, sun_pos['ecliptic_longitude'])
            music_prompt = generate_solar_term_music_prompt(solar_term, zodiac_sign)
            
            response_data.update({
                "zodiac_sign": zodiac_sign,
                "solar_term": solar_term,
                "music_prompt": music_prompt,
                "process": "default_music"
            })
        
        logger.info(f"✅ ==================== API调用成功完成 ====================")
        logger.info(f"📊 [最终结果] 模式: {mode}, 太阳黄经: {sun_pos['ecliptic_longitude']:.2f}°")
        return response_data
        
    except Exception as e:
        logger.error(f"❌ ==================== API调用失败 ====================")
        logger.error(f"💥 [错误] {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理错误: {str(e)}")

@app.post("/api/astronomy/calculate")
async def calculate_astronomy(request: AstronomyRequest):
    """根据指定时间和位置计算天文数据"""
    try:
        year, month, day, hour = request.time_data.year, request.time_data.month, request.time_data.day, request.time_data.hour
        
        # 检查农历转换
        if request.time_data.is_lunar:
            year, month, day = convert_lunar_to_solar(year, month, day)
        
        # 🔧 修复：直接使用ISO时间格式，与 /api/solar-longitude 保持一致
        from astropy.time import Time
        from astropy.coordinates import get_sun
        import warnings
        warnings.filterwarnings('ignore')
        
        time_str = f'{year}-{month:02d}-{day:02d} {hour:02d}:00:00'
        time = Time(time_str, format='iso', scale='utc')
        sun = get_sun(time)
        solar_longitude = sun.geocentrictrueecliptic.lon.degree % 360
        
        logger.info(f"直接计算太阳黄经: {solar_longitude:.2f}°")
        
        # 构造兼容的sun_pos格式
        sun_pos = {
            'ecliptic_longitude': solar_longitude,
            'ecliptic_latitude': float(sun.geocentrictrueecliptic.lat.degree),
            'ra': float(sun.ra.deg),
            'dec': float(sun.dec.deg),
            'distance': float(sun.distance.km),
            'timestamp': time.iso
        }
        
        dt = datetime(year, month, day, hour)  # 用于其他地方
        
        # 匹配星次和确定节气
        zodiac_sign, zodiac_data = match_zodiac_sign_interval(solar_longitude)
        solar_term = determine_solar_term(zodiac_data, solar_longitude)
        mansions_in_zodiac = get_28_mansions_for_display(zodiac_data)
        
        # 对于 mansions_positions，如果需要可以传递 time 对象
        try:
            mansions_positions = get_all_mansions_positions(dt.timestamp())
        except:
            mansions_positions = {}
        
        return {
            "success": True,
            "request_time": dt.isoformat(),
            "location": {
                "latitude": request.location_data.latitude,
                "longitude": request.location_data.longitude,
                "address": request.location_data.address
            },
            "sun_position": sun_pos,
            "zodiac_sign": zodiac_sign,
            "solar_term": solar_term,
            "mansions_in_zodiac": mansions_in_zodiac,
            "ecliptic_longitude": solar_longitude,  # ✅ 使用直接计算的结果
            "mansions_positions": mansions_positions,
            # 兼容字段
            "timestamp": dt.isoformat(),
            "mansion": f"{zodiac_sign}({solar_term})",
            "element": "节气",
            "sun_ecliptic_lon": solar_longitude,  # ✅ 使用直接计算的结果
            "instrument": "传统民乐",
            "mode": "五声音阶"
        }
        
    except Exception as e:
        logger.error(f"天文计算错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"天文计算失败: {str(e)}")


@app.post("/api/generate_music")
async def generate_music_api(request: dict):
    """音乐生成API - 使用节气提示词"""
    try:
        logger.info(f"收到音乐生成请求: {request}")
        
        # 获取参数
        date_str = request.get('date')
        is_lunar = request.get('is_lunar', False)
        duration = request.get('duration', 45)
        latitude = request.get('lat', 22.3193)
        longitude = request.get('lon', 114.1695)
        
        # 处理时间
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                year, month, day, hour = dt.year, dt.month, dt.day, dt.hour
                if is_lunar:
                    year, month, day = convert_lunar_to_solar(year, month, day)
                    dt = datetime(year, month, day, hour)
                timestamp = dt.timestamp()
            except ValueError:
                dt = datetime.now()
                timestamp = dt.timestamp()
        else:
            dt = datetime.now()
            timestamp = dt.timestamp()
        
        # 计算太阳黄经
        sun_pos = get_sun_position(timestamp, latitude, longitude)
        if 'ecliptic_longitude' not in sun_pos:
            raise ValueError("无法获取太阳黄经数据")
        
        # 匹配星次和确定节气
        zodiac_sign, zodiac_data = match_zodiac_sign_interval(sun_pos['ecliptic_longitude'])
        solar_term = determine_solar_term(zodiac_data, sun_pos['ecliptic_longitude'])
        
        # 生成节气音乐提示词
        music_prompt = generate_solar_term_music_prompt(solar_term, zodiac_sign, duration)
        
        # 调用音乐生成API
        music_result = generate_music(
            instrument="Traditional Chinese Orchestra",
            mode="Pentatonic",
            style=music_prompt,
            duration=duration
        )
        
        response_data = {
            "success": True,
            "astronomy": {
                "zodiac_sign": zodiac_sign,
                "solar_term": solar_term,
                "sun_ecliptic_longitude": sun_pos['ecliptic_longitude'],
                # 兼容字段
                "mansion": f"{zodiac_sign}({solar_term})",
                "element": "节气",
                "sun_ecliptic_lon": sun_pos['ecliptic_longitude']
            },
            "parameters": {
                "solar_term": solar_term,
                "zodiac_sign": zodiac_sign,
                "prompt": music_prompt,
                "duration": duration,
                "instrument": "Traditional Chinese Orchestra",
                "mode": "Pentatonic",
                "enhanced_prompt": music_prompt,
                # 兼容字段
                "element": "节气"
            },
            "music": music_result
        }
        
        logger.info(f"节气音乐生成完成: {solar_term}({zodiac_sign})")
        return response_data
        
    except Exception as e:
        logger.error(f"音乐生成失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"音乐生成错误: {str(e)}")

@app.post("/api/music/generate")
async def generate_music_query_api(
    instrument: str = Query(None, description="乐器类型"),
    mode: str = Query(None, description="音乐调式"),
    style: str = Query(default="cinematic, ethereal", description="音乐风格"),
    duration: int = Query(default=45, ge=15, le=180, description="音乐时长(秒)")
):
    """通过查询参数生成音乐"""
    try:
        logger.info(f"收到查询参数音乐生成请求: instrument={instrument}, mode={mode}, style={style}, duration={duration}")
        
        # 使用当前时间和默认位置
        dt = datetime.now()
        timestamp = dt.timestamp()
        latitude = 22.3193
        longitude = 114.1695
        
        # 获取天文数据
        sun_pos = get_sun_position(timestamp, latitude, longitude)
        if 'ecliptic_longitude' not in sun_pos:
            raise ValueError("无法获取太阳黄经数据")
        
        # 匹配星次和确定节气
        zodiac_sign, zodiac_data = match_zodiac_sign_interval(sun_pos['ecliptic_longitude'])
        solar_term = determine_solar_term(zodiac_data, sun_pos['ecliptic_longitude'])
        
        # 使用节气音乐配置，忽略传入的参数
        final_instrument = "Traditional Chinese Orchestra"
        final_mode = "Pentatonic"
        
        # 生成节气音乐提示词
        music_prompt = generate_solar_term_music_prompt(solar_term, zodiac_sign, duration)
        
        logger.info(f"最终音乐参数: instrument={final_instrument}, mode={final_mode}")
        
        # 生成音乐
        music_result = generate_music(
            instrument=final_instrument,
            mode=final_mode,
            style=music_prompt,
            duration=duration
        )
        
        logger.info(f"音乐生成原始结果: {music_result}")
        
        # 处理音乐结果
        processed_music = music_result
        if isinstance(music_result, str) and music_result.isdigit():
            processed_music = {
                "success": True,
                "id": music_result,
                "download_url": f"https://yue-inst.ngrok.app/download/{music_result}",
                "message": "音乐生成成功"
            }
        elif isinstance(music_result, dict):
            if 'success' not in music_result:
                processed_music['success'] = True
            if 'download_url' not in music_result and music_result.get('id'):
                processed_music['download_url'] = f"https://yue-inst.ngrok.app/download/{music_result['id']}"
        
        # 构造响应数据
        response_data = {
            "success": True,
            "astronomy": {
                "zodiac_sign": zodiac_sign,
                "solar_term": solar_term,
                "sun_ecliptic_longitude": sun_pos['ecliptic_longitude'],
                # 兼容字段
                "mansion": f"{zodiac_sign}({solar_term})",
                "element": "节气",
                "sun_ecliptic_lon": sun_pos['ecliptic_longitude']
            },
            "parameters": {
                "solar_term": solar_term,
                "zodiac_sign": zodiac_sign,
                "instrument": final_instrument,
                "mode": final_mode,
                "duration": duration,
                "enhanced_prompt": music_prompt,
                # 兼容字段
                "element": "节气"
            },
            "music": processed_music
        }
        
        logger.info(f"音乐生成完成: {zodiac_sign}星次, {solar_term}节气, {final_instrument}, {final_mode}")
        return response_data
        
    except Exception as e:
        logger.error(f"查询参数音乐生成失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"音乐生成错误: {str(e)}")

@app.get("/api/mansions")
async def get_all_mansions():
    """获取所有28星宿的信息"""
    try:
        from modules.astronomy import MANSIONS
        from modules.wuxing import MANSION_ELEMENT_MAP
        
        mansions_info = []
        for mansion in MANSIONS:
            element = get_element(mansion)
            mansions_info.append({
                "name": mansion,
                "element": element,
                "element_en": MANSION_ELEMENT_MAP.get(mansion, "Wood")
            })
        
        return {
            "success": True,
            "mansions": mansions_info,
            "total": len(mansions_info)
        }
    except Exception as e:
        logger.error(f"获取星宿信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 错误处理 ====================
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """404错误处理"""
    return JSONResponse(
        status_code=404,
        content={"error": "页面未找到", "status_code": 404}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """500错误处理"""
    logger.error(f"内部服务器错误: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "内部服务器错误", "status_code": 500}
    )

# ==================== 启动配置 ====================
if __name__ == "__main__":
    import uvicorn
    
    # 检查静态文件目录
    if not os.path.exists("static"):
        logger.warning("⚠️ static目录不存在，创建中...")
        os.makedirs("static")
    
    logger.info("🚀 ==================== 系统启动 ====================")
    logger.info("🎼 中国时间后端服务启动中...")
    logger.info("📊 版本: 1.0.0")
    logger.info("🌐 访问路径:")
    logger.info("   📅 时间选择: http://localhost:8000/")
    logger.info("   📍 位置选择: http://localhost:8000/location")
    logger.info("   🌟 星图音乐: http://localhost:8000/starmap")
    logger.info("   📚 API文档: http://localhost:8000/docs")
    logger.info("🔄 逻辑流程:")
    logger.info("   1️⃣ 用户输入时间/经纬度")
    logger.info("   2️⃣ 时间类型判断(农历/公历)")
    logger.info("   3️⃣ 农历转公历 | 公历直接转datetime")
    logger.info("   4️⃣ astropy计算太阳黄经")
    logger.info("   5️⃣ 三分支处理:")
    logger.info("       分支A: 匹配十二星次区间→确定节气→生成音乐提示词→调用API→播放联动")
    logger.info("       分支B: 匹配十二星次区间→获取28星宿")
    logger.info("       分支C: astropy计算太阳黄经→Three.js可视化→黄道/星次/星宿可视化")
    logger.info("✅ ==================== 启动完成 ====================")
    
    uvicorn.run(
        "backend_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
