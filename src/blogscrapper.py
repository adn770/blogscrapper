#!/usr/bin/env python3
#
# MIT License
#
# Copyright (c) 2022 Josep Torra
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

"""
blogscrapper


Usage:
    blogscrapper [options] scrap <URL>
    blogscrapper [options] mdfy [CACHEDDIR]
    blogscrapper [options] clean [CACHEDDIR]

Commands:
    scrap                 Download content from specified <URL>
    mdfy                  Convert to markdown
    clean                 Clean html on the cached data

Options:
    -f --force            Force the operation
    -h --help             Show this message
    --version             Show version
    --log-level=LEVEL     Level of logging to produce [default: INFO]
    --log-file=PATH       Specify a file to write the log
    -v --verbose          Verbose logging (equivalent to --log-level=DEBUG)

Log levels:  DEBUG INFO WARNING ERROR CRITICAL

"""

import sys
import time
import logging
import requests
import mdformat

from enum import Enum
from glob import glob
from pathlib import Path
from docopt import docopt
from random import randrange
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter


# Create shorthand method for conversion
def md(content, **options):
    return MarkdownConverter(**options).convert_soup(content)

def clean_html(content):
    for to_remove in content.find_all("div", class_="sharedaddy"):
        to_remove.decompose()
    for to_remove in content.find_all("div", class_="entry-meta"):
        to_remove.decompose()
    for to_remove in content.find_all("div", id="comments"):
        to_remove.decompose()
    for to_remove in content.find_all("script"):
        to_remove.decompose()
    for to_remove in content.find_all("small"):
        to_remove.decompose()
    for to_remove in content.find_all("footer"):
        to_remove.decompose()
    return content

def mdfy(filename="unknown", force = False):
    ofilename = str(filename).replace("cache", "md").replace(".html", ".md")
    if not force and Path(ofilename).is_file():
        return

    with open(filename, "r") as fhandle:
        content = BeautifulSoup(fhandle, features="html.parser")
        if force:
            content = clean_html(content)
        with open(ofilename, "w") as fhandle:
            content = md(content, heading_style="ATX")
            content = mdformat.text(content, options={"number": True, "wrap": 70})
            fhandle.write(content)

def do_mdfy(cached_files, force=False):
    logging.info("+--.-- search pattern: %s", cached_files)
    for filename in sorted(glob(cached_files)):
        logging.info("   :···> mdfy: %s", filename)
        mdfy(filename, force)


def do_clean(cached_files, force=False):
    logging.info("+--.--[ search pattern: %s ]", cached_files)
    for filename in sorted(glob(cached_files)):
        logging.info("   :···> clean: %s", filename)
        content = None
        with open(filename, "r") as fhandle:
            content = BeautifulSoup(fhandle, features="html.parser")
        if content:
            content = clean_html(content)
            with open(filename, "w") as fhandle:
                fhandle.write(content.prettify(formatter='html'))

def has_id_as_meta(id, content):
    for meta in content.find_all("meta"):
        logging.debug("meta: %s", meta)
        if meta.has_key('content') and id in meta['content'].lower():
            return True
    return False

def is_blogspot(content):
    for link in content.find_all("link"):
        if "blogger" in link['href']:
            return True
    return False

def is_wordpress(content):
    if has_id_as_meta('wordpress', content):
        return True
    for link in content.find_all("a"):
        if link.has_key('href') and "wordpress" in link['href']:
            return True
    if content.find_all("article"):
        return True

    return False


class Mode(Enum):
    UNKNOWN = 0
    BLOGSPOT = 1
    WORDPRESS = 2


class Scrapper():
    HTML = """
              <html>
                  <head>
                  </head>
                  <body>
                  </body>
              </html>
           """

    def __init__(self, url = '', pausedtime = 1):
        self.counter = 0
        self.mode = Mode.UNKNOWN
        self.pausedtime = pausedtime
        self.url = url.rstrip("/")
        self.rootname = url.rsplit('/', 1)[-1]
        self.basepath = Path("cache", self.rootname)
        self.mdpath = Path("md", self.rootname)
        self.basepath.mkdir(parents=True, exist_ok=True)
        self.mdpath.mkdir(parents=True, exist_ok=True)

    def scrap(self, force=False):
        url = self.url

        while url:
            logging.debug("* Scrapping at url: %s", url)
            response = requests.get(url)
            content = BeautifulSoup(response.content, features="html.parser")
            self.autoconfigure(content)
            for article in self.articles(content):
                self.scrap_page(article, force)
            url = self.extract_next_url(content)

    def extract_next_url(self, content):
        url = None
        link = None
        if self.mode == Mode.BLOGSPOT:
            link = content.find("a", "blog-pager-older-link")
        elif self.mode == Mode.WORDPRESS:
            div = content.find("div", ["content-nav", "nav-previous", "navigation"])
            if div:
                link = div.find("a")
            if not link:
                link = content.find("a", class_="next")
            if not link:
                link = content.find("a", class_="page-numbers")
            if not link:
                link = content.find("a", class_="pagination__item--next")

        if link:
            url = link['href']
        else:
            logging.debug("next url not found, content:\n%s", content.prettify())

        time.sleep(self.pausedtime + randrange(3))
        return url

    def autoconfigure(self, content):
        if self.mode == Mode.UNKNOWN:
            logging.debug("content:\n%s", content.prettify())
            if "blogspot" in self.url or is_blogspot(content):
                self.mode = Mode.BLOGSPOT
                logging.info("* Mode: blogspot")
            elif "wordpress" in self.url or is_wordpress(content):
                self.mode = Mode.WORDPRESS
                logging.info("* Mode: wordpress")
            logging.info("   .------.")

    def articles(self, content):
        articles = []
        if self.mode == Mode.BLOGSPOT:
            articles = content.find_all("h3", ["post-title", "entry-title"])
        elif self.mode == Mode.WORDPRESS:
            articles = content.find_all("article")
            if not articles:
                articles = content.find_all("div", ["post", "type-post", "item entry"])
        return articles


    def saveat(self, filename="unknown"):
        self.counter = self.counter + 1
        return Path(self.basepath, filename)

    def extract_post(self, content):
        post = None
        if self.mode == Mode.BLOGSPOT:
            post = content.find("div", class_="post-body entry-content")
            if not post:
                post = content.find("div", class_="post")
        elif self.mode == Mode.WORDPRESS:
            post = content.find("div", class_="post-entry")
            if not post:
                post = content.find("div", class_="content")
            if not post:
                post = content.find("div", class_="entry-content")
            if not post:
                post = content.find("div", class_="content-area")
            if not post:
                post = content.find("div", class_="storycontent")
        #if not post:
        #    logging.warning("post not found, content:\n%s", content.prettify())
        return post

    def scrap_page(self, content, force=False):
        link = content.find("a")
        if not link:
            logging.warning("link not found, content:\n%s", content.prettify())
            return

        url = link['href']
        if url[-1]  == "/":
            url = url[:-1]
        if link.has_key('title'):
            title = link['title']
        else:
            title = link.text

        filename = url.split("/", 3)[-1].replace("/", "-")
        if not filename[-5:] == ".html":
            filename = filename + ".html"

        saveat = self.saveat(filename)

        logging.debug("filename: %s", filename)
        logging.debug("saveat: %s", saveat)
        logging.info("+--| %04d |_.·-[ %s ]", self.counter, title.strip())

        if not force and saveat.is_file():
            logging.info("   `------´ `--<: %s", url)
            logging.info("   .------.")
            return

        response = requests.get(url)
        content = BeautifulSoup(response.content, features="html.parser")
        post = self.extract_post(content)
        if post:
            logging.info("   `------´ \.--<: %s", url)
            logging.info("   .------.  `------:> Saving: %s", saveat)
            opost = BeautifulSoup(self.HTML, features="html.parser")
            opost = clean_html(opost)
            title_tag = content.new_tag("title")
            title_tag.string = title
            opost.head.append(title_tag)
            opost.html.body.append(post)
            self.save(opost, saveat)
        else:
            logging.info("   `------´ \.--<: %s", url)
            logging.info("             `------[ Post not found ]")
            # logging.warning("Post not found, content:\n%s", content.prettify())
            logging.info("   .------.")
            return

        mdfy(saveat)

    def save(self, content, saveat="unknown"):
        with open(saveat, "w") as fhandle:
            fhandle.write(content.prettify(formatter='html'))
        time.sleep(self.pausedtime + randrange(3))


def main():
    """main"""
    args = docopt(__doc__, version="0.1")

    if args.pop('--verbose'):
        loglevel = 'DEBUG'
    else:
        loglevel = args.pop('--log-level').upper()

    logging.basicConfig(filename=args.pop('--log-file'), filemode='w',
                        level=loglevel, format='%(levelname)s: %(message)s')

    # Check python version
    is_min_python_3_6 = sys.version_info[0] == 3 and sys.version_info[1] >= 6
    if not is_min_python_3_6:
        logging.error('The bot was developed for Python 3. Please use '
                      'Version 3.6 or higher.')
        sys.exit(1)

    force = args.pop('--force')
    cacheddir = args.pop('CACHEDDIR') or "*"
    cached_files = f"cache/{cacheddir}/*.html"
    if args.pop('scrap'):
        scrapper = Scrapper(args.pop('<URL>'))
        scrapper.scrap(force)
    elif args.pop('mdfy'):
        do_mdfy(cached_files, force)
    elif args.pop('clean'):
        do_clean(cached_files, force)


if __name__ == '__main__':
    main()

