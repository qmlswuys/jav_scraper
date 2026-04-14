import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from xml.dom import minidom

from curl_cffi import requests
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
    poster: str = ""
    funart: str = ""

    def build_xml_element(self) -> ET.Element:
        movie = ET.Element("movie")
        ET.SubElement(movie, "title").text = self.code
        ET.SubElement(movie, "originaltitle").text = self.title
        ET.SubElement(movie, "premiered").text = self.release_date
        ET.SubElement(movie, "runtime").text = self.duration
        ET.SubElement(movie, "director").text = self.director
        ET.SubElement(movie, "studio").text = self.maker
        # ET.SubElement(movie, "publisher").text = self.publisher
        if self.series:
            set_node = ET.SubElement(movie, "set")
            ET.SubElement(set_node, "name").text = self.series

        ET.SubElement(movie, "rating").text = self.rating
        for tag in self.tags:
            ET.SubElement(movie, "genre").text = tag
            ET.SubElement(movie, "tag").text = tag
        for actor in self.actors:
            actors_element = ET.SubElement(movie, "actor")
            ET.SubElement(actors_element, "name").text = actor.get("name", "")
            ET.SubElement(actors_element, "thumb").text = actor.get("thumb", "")

        return movie

    def export_info(self, file_path: str):
        root = self.build_xml_element()
        raw_xml = ET.tostring(root, encoding="utf-8")
        pretty_xml = minidom.parseString(raw_xml).toprettyxml(
            indent="  ", encoding="utf-8"
        )
        with open(file_path, "wb") as f:
            f.write(pretty_xml)


FIELD_RULES = {
    "番號": ("code", lambda node: node.text(strip=True)),
    "日期": ("release_date", lambda node: node.text(strip=True)),
    "時長": ("duration", lambda node: node.text(strip=True)),
    "導演": ("director", lambda node: node.text(strip=True)),
    "片商": ("maker", lambda node: node.text(strip=True)),
    "發行": ("publisher", lambda node: node.text(strip=True)),
    "系列": ("series", lambda node: node.text(strip=True)),
    "評分": (
        "rating",
        lambda node: node.text(strip=True).split("分")[0],
    ),
    "類別": ("tags", lambda node: [a.text(strip=True) for a in node.css("a")]),
    "演員": (
        "actors",
        lambda node: [
            (a.text(strip=True), a.attributes.get("href")) for a in node.css("a")
        ],
    ),
}


base_url = "https://javdb.com/"


with requests.Session(proxies=None, impersonate="chrome120", verify=False) as session:
    response = session.get(url=f"{base_url}/search?q=jufe-114")
    print(response.status_code)
    if response.status_code == 200:
        tree = LexborHTMLParser(response.content)
        node = tree.css_first(".movie-list .item a")
        if node:
            link = node.attributes.get("href")
            response = session.get(f"{base_url}{link}?locale=zh")
            if response.status_code == 200:
                print("成功抓取详情页！")
                tree = LexborHTMLParser(response.content)
                title_node = tree.css_first(".video-detail .title")
                if title_node:
                    clean_title = " ".join(title_node.text().split())
                    print(f"影片标题：{clean_title}")

                nav_node = tree.css_first(".panel.movie-panel-info")
                panel_nodes = nav_node.css(".panel-block")

                if panel_nodes:
                    raw_data = {"title": clean_title}
                    for panel in panel_nodes:
                        strong_node = panel.css_first("strong")
                        value_node = panel.css_first(".value")
                        if strong_node and value_node:
                            print(
                                f"{strong_node.text(strip=True)} {value_node.text(strip=True)}"
                            )
                            label = strong_node.text(strip=True).replace(":", "")
                            if label in FIELD_RULES:
                                attr_name, func = FIELD_RULES[label]
                                raw_data[attr_name] = func(value_node)
                    actors = raw_data.pop("actors", [])
                    processed_actors = []
                    for name, href in actors:
                        print(f"演员：{name}，链接：{href}")
                        actor_item = {"name": name, "thumb": ""}
                        if href:
                            try:
                                actor_res = session.get(f"{base_url}{href}?locale=zh")
                                if actor_res.status_code == 200:
                                    a_tree = LexborHTMLParser(actor_res.content)
                                    avator_node = a_tree.css_first(".avatar")
                                    if avator_node:
                                        bg_image = avator_node.attributes.get(
                                            "style", ""
                                        )
                                        match = re.search(r"url\((.*?)\)", bg_image)
                                        if match:
                                            image_url = match.group(1).strip("'\"")
                                        actor_item["thumb"] = image_url
                            except Exception as e:
                                print(f"抓取演员{name}头像失败：{e}")
                        processed_actors.append(actor_item)
                    raw_data["actors"] = processed_actors
                    movie_info = JavInfo(**raw_data)
                    movie_info.export_info("movie.nfo")
                    print(movie_info)

                cover_node = tree.css_first(".video-cover")
                print(f"封面节点：{cover_node.html}")
                if cover_node:
                    cover_url = cover_node.attributes.get("src")
                    print(f"封面链接：{cover_url}")
                    if cover_url:
                        with open("funart.jpg", "wb") as f:
                            f.write(session.get(cover_url).content)
                        with Image.open("funart.jpg") as img:
                            width, height = img.size
                            left = width - 379
                            right = width
                            upper = 0
                            lower = height
                            poster = img.crop((left, upper, right, lower))
                            poster.save("poster.jpg", quality=95, optimize=True)
