# JAV Scraper

这是一个基于 Python 的 JAV 信息刮削工具，支持自动生成 NFO 文件。

## 功能特点
- 🔍 自动识别番號
- 📂 自动整理文件夹
- 🖼️ 自动下载封面 (Fanart & Poster)
- 📝 生成兼容 Kodi/Emby/Jellyfin 的 NFO 文件

## 快速开始
本项目使用 [uv](https://astral.sh) 进行包管理，无需手动配置虚拟环境。
1. git clone 
2. 复制 .env.example 并重命名为 .env，修改 JAV_BASE_DIR 为你的视频存储路径。
3. uv run main.py