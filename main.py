from dataclasses import dataclass, field

from curl_cffi import requests
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
    actors: list[str] = field(default_factory=list)
    poster: str = ""
    funart: str = ""


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
    "演員": ("actors", lambda node: [a.text(strip=True) for a in node.css("a")]),
}


proxies = {
    "http": "socks5h://127.0.0.1:3067",
    "https": "socks5h://127.0.0.1:3067",
}


with requests.Session(
    proxies=proxies, impersonate="firefox147", verify=False
) as session:
    response = session.get(url="https://javdb.com/search?q=JUFE-114&f=all")
    if response.status_code == 200:
        tree = LexborHTMLParser(response.content)
        node = tree.css_first(".movie-list .item a")
        if node:
            link = node.attributes.get("href")
            response = session.get(f"https://javdb.com{link}?locale=zh")
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
                    movie_info = JavInfo(**raw_data)
                    print(movie_info)

                cover_node = tree.css_first(".video-cover")
                print(f"封面节点：{cover_node.html}")
                if cover_node:
                    cover_url = cover_node.attributes.get("src")
                    print(f"封面链接：{cover_url}")
                    if cover_url:
                        with open("poster.jpg", "wb") as f:
                            f.write(session.get(cover_url).content)
