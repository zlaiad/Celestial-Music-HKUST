# 中国时间

> 当前版本聚焦于两个可用页面：交互式日晷时间选择器与星云/星图预览。适合演示日期时间拾取与基础星空可视化的前端效果。

## 项目概览
- **时间选择器（`/` 或 `/static/time-selector.html`）**：圆形日晷界面，通过拖拽同心圆选择年、月、日、小时，左侧信息面板实时回显选中的时间，并在确认后把数据写入 `sessionStorage`。
- **星云星图（`/starmap` 或 `/static/starmap.html`）**：从时间选择器读取时间与默认地点（香港）后展示，左侧面板可更新观测时间、切换显示选项（星宿标注、连线、背景星空），右侧区域嵌入星空视图容器与基础信息卡片。

## 快速开始
1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```
2. **启动本地服务**
   ```bash
   uvicorn backend_app:app --reload
   ```
3. **打开页面**
   - 访问 `http://localhost:8000/` 进入时间选择器，拖拽完成选择后点击“确认时间”。
   - 浏览器将跳转到 `http://localhost:8000/starmap`，根据上一页存储的时间与默认位置加载星云星图。

> 如无需后端，可直接双击 `static/time-selector.html` 或 `static/starmap.html` 打开静态页面预览（部分 API 功能将不可用）。

## 目录速览
- `backend_app.py`：FastAPI 入口，提供静态文件路由与健康检查接口。
- `static/time-selector.html`：日晷式时间选择页面的完整 HTML/CSS/JS。
- `static/starmap.html`：星云/星图展示页与控制面板逻辑。
- `static/js`, `static/css`, `static/imgs` 等：页面共用的脚本、样式与资源。

## 常见开发需求
- **调整默认地点**：在 `static/time-selector.html` 中修改 `DEFAULT_LOCATION` 常量即可影响跳转时写入的经纬度。
- **自定义跳转逻辑**：更新时间选择器中的 `confirmSelection()` 方法或星图页读取 `sessionStorage` 的逻辑。
- **嵌入其他星空引擎**：`static/starmap.html` 的星空区域预留了容器，可替换为自定义可视化组件或 API 渲染。

## 许可证
本项目采用 MIT License 发布，详情见仓库根目录的 `LICENSE` 文件。
