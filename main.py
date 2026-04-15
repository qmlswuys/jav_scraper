import os
import random
import re
import shutil
import time
import xml.etree.ElementTree as ET
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from xml.dom import minidom

from curl_cffi import requests
from dotenv import load_dotenv
from PIL import Image
from selectolax.lexbor import LexborHTMLParser


@dataclass
class JavInfo:
    title: str = ""
    code: str = ""
    release_date: str = ""
    duration: str = ""
    director: str = ""
    maker: str = ""
    publisher: str = ""
    series: str = ""
    rating: str = ""
    tags: list[str] = field(default_factory=list)
    actors: list[dict] = field(default_factory=list)

    def generate_nfo(self, file_path: str):
        movie = ET.Element("movie")
        ET.SubElement(movie, "title").text = self.code
        ET.SubElement(movie, "originaltitle").text = self.title
        ET.SubElement(movie, "premiered").text = self.release_date
        ET.SubElement(movie, "runtime").text = self.duration
        ET.SubElement(movie, "director").text = self.director
        ET.SubElement(movie, "studio").text = self.maker
        ET.SubElement(movie, "rating").text = self.rating

        if self.series:
            set_node = ET.SubElement(movie, "set")
            ET.SubElement(set_node, "name").text = self.series

        for tag in self.tags:
            ET.SubElement(movie, "genre").text = tag
            ET.SubElement(movie, "tag").text = tag

        for actor in self.actors:
            actor_el = ET.SubElement(movie, "actor")
            ET.SubElement(actor_el, "name").text = actor.get("name", "")
            ET.SubElement(actor_el, "thumb").text = actor.get("thumb", "")

        raw_xml = ET.tostring(movie, encoding="utf-8")
        pretty_xml = minidom.parseString(raw_xml).toprettyxml(
            indent="  ", encoding="utf-8"
        )
        with open(file_path, "wb") as f:
            f.write(pretty_xml)


class JavScraper:
    def __init__(self, base_url=None):
        self.base_url = base_url or os.getenv("JAV_BASE_URL", "https://javdb.com")
        self.base_url = self.base_url.rstrip("/")
        self.session = requests.Session(
            impersonate="chrome120", verify=False, timeout=15
        )
        self.rules = {
            "番號": "code",
            "日期": "release_date",
            "時長": "duration",
            "導演": "director",
            "片商": "maker",
            "系列": "series",
            "評分": "rating",
        }

    def get_tree(self, url):
        try:
            res = self.session.get(url)
            return LexborHTMLParser(res.content) if res.status_code == 200 else None
        except Exception as e:
            print(f"❌ 网络请求失败: {e}")
            return None

    def fetch_actor_thumb(self, href):
        tree = self.get_tree(f"{self.base_url}{href}?locale=zh")
        if not tree:
            return ""
        avatar = tree.css_first(".avatar")
        if avatar:
            style = avatar.attributes.get("style", "")
            match = re.search(r"url\((.*?)\)", style)
            return match.group(1).strip("'\"") if match else ""
        return ""

    def scrape_movie(self, code, save_dir):
        search_tree = self.get_tree(f"{self.base_url}/search?q={code}")
        if not search_tree:
            return None

        item = search_tree.css_first(".movie-list .item a")
        if not item:
            return None

        detail_url = f"{self.base_url}{item.attributes.get('href')}?locale=zh"
        detail_tree = self.get_tree(detail_url)
        if not detail_tree:
            return None

        data = {
            "title": " ".join(
                detail_tree.css_first(".video-detail .title").text().split()
            )
        }
        for panel in detail_tree.css(".panel.movie-panel-info .panel-block"):
            if not panel.css_first("strong"):
                break
            label = panel.css_first("strong").text(strip=True).replace(":", "")
            value_node = panel.css_first(".value")

            if label in self.rules:
                val = value_node.text(strip=True)
                data[self.rules[label]] = val.split("分")[0] if label == "評分" else val
            elif label == "類別":
                data["tags"] = [a.text(strip=True) for a in value_node.css("a")]
            elif label == "演員":
                actors = [
                    (a.text(strip=True), a.attributes.get("href"))
                    for a in value_node.css("a")
                ]
                data["actors"] = [
                    {"name": n, "thumb": self.fetch_actor_thumb(h)} for n, h in actors
                ]

        cover = detail_tree.css_first(".video-cover")
        if cover:
            self.download_images(cover.attributes.get("src"), save_dir)

        return JavInfo(**data)

    def download_images(self, url, save_path):
        try:
            content = self.session.get(url).content
            fanart_p = Path(save_path) / "fanart.jpg"
            poster_p = Path(save_path) / "poster.jpg"
            with open(fanart_p, "wb") as f:
                f.write(content)
            with Image.open(fanart_p) as img:
                w, h = img.size
                if w > 379:
                    img.crop((w - 379, 0, w, h)).save(poster_p, quality=95)
                else:
                    img.save(poster_p)
        except Exception as e:
            print(f"⚠️ 图片下载失败: {e}")


def get_clean_code(filename):
    pattern = r"([A-Z]{2,10})[-_ ]?(\d{3,5})"
    if m := re.search(pattern, filename.upper()):
        return f"{m.group(1)}-{m.group(2)}"
    return None


def organize_file(video_path, code, base_path):
    target_dir = base_path / code
    target_dir.mkdir(exist_ok=True)

    target_path = target_dir / f"{code}{video_path.suffix.lower()}"

    if video_path.absolute() != target_path.absolute():
        if video_path.parent == target_dir:
            temp_p = video_path.with_name(video_path.name + ".tmp")
            video_path.rename(temp_p)
            temp_p.rename(target_path)
        else:
            shutil.move(str(video_path), str(target_path))
            if video_path.parent != base_path:
                with suppress(Exception):
                    if not any(video_path.parent.iterdir()):
                        video_path.parent.rmdir()
        print(f"✨ 已整理: {target_path.name}")
    return target_dir, target_path


def run_scraper(base_dir):
    scraper = JavScraper()
    base_path = Path(base_dir)
    EXTS = {".mp4", ".mkv", ".avi", ".wmv", ".iso", ".rmvb", ".ts"}

    videos = (
        v
        for v in base_path.rglob("*")
        if v.suffix.lower() in EXTS and not v.with_suffix(".nfo").exists()
    )

    for vid in videos:
        code = get_clean_code(vid.name)
        if not code:
            continue

        print(f"🎬 正在处理: {vid.name}")

        final_dir, final_path = organize_file(vid, code, base_path)

        info = scraper.scrape_movie(code, str(final_dir))
        if info:
            info.generate_nfo(str(final_path.with_suffix(".nfo")))
            print(f"✅ 刮削完成: {code}")
            time.sleep(random.uniform(1, 3))
        else:
            print(f"❌ 未找到信息: {code}")


load_dotenv()
if __name__ == "__main__":
    try:
        path = os.getenv("JAV_BASE_DIR")
        if path and os.path.exists(path):
            run_scraper(path)
        else:
            print("错误：目标路径不存在！")
            print("检查是否正确配置.env文件！")
    finally:
        print("\n" + "=" * 30)
        input("按任意键结束")
