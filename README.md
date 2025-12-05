[中文版](./README_CN.md) | English

## Introduction

When practicing on LeetCode, you often encounter problems similar to ones you've solved before, but forget the solution approach. [Anki](https://apps.ankiweb.net/) is a cross-platform memory tool based on the forgetting curve, supporting Mac, Linux, Windows, iOS, and Android platforms. While Anki is an excellent memory tool, it requires manual card creation, which is tedious and time-consuming.

> Invest some time to automate or simplify a process to save more time in the future

**This project aims to automatically fetch your accepted LeetCode problems and generate Anki decks to help you remember them.**

The crawled data includes:

1. Problem title, difficulty, and description.
2. Official solutions (Premium solutions require a subscription to fetch).
3. Your accepted submission code.

## DEMO

|            Front            |           Back           |
| :------------------------: | :----------------------: |
| ![front](./demo/front.JPG) | ![back](./demo/back.JPG) |

Example [Deck](https://github.com/Peng-YM/LeetCode-Anki/blob/master/data/LeetCode.apkg?raw=true)

## Usage

First, clone the repository and install Python dependencies:
```bash
git clone https://github.com/tabloomoo/LeetCode-Anki.git
cd LeetCode-Anki
pip3 install -r requirements.txt
```

Run the crawler and output the Anki deck to `./data/LeetCode.apkg` (as specified in `project.conf`):

```bash
python3 main.py
```

For LeetCode.cn support:
```bash
python3 main_cn.py
```

On the first run, you need to obtain cookies. Running `main.py` will open a Chrome window where you manually enter your username and password to log in once.

> ⚠️ Note:
> 1. If you need to re-login via browser, simply delete the `cookie.dat` file in the directory.
> 2. If the browser driver is outdated (currently V86.0), please [download the Chrome Selenium driver](https://chromedriver.chromium.org/downloads) and replace the old driver in the `vendor` directory.

Enjoy using Anki to review the problems you've solved!

## Customization

If you don't like the default Anki card style, you can modify the following three parameters in `project.conf` to customize the generated Anki cards:

```properties
[DB]
path = ./data
debug = False

[Anki]
front = ./templates/front-side.html
back = ./templates/back-side.html
css = ./templates/style.css
output = ./data/LeetCode.apkg
```

- `front`: The format of the card front side.
- `back`: The format of the card back side.
- `css`: The CSS style for the cards.

## LICENSE

This project is licensed under the GPL V3 open source license.

## Acknowledgements

This project is based on many excellent open source projects:

- [genanki: A Library for Generating Anki Decks](https://github.com/kerrickstaley/genanki)

- [Python Markdown: Python implementation of John Gruber's Markdown](https://github.com/Python-Markdown/markdown)
