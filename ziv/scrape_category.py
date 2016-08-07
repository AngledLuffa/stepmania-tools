import argparse
import codecs
import os
import sys
import urllib2
from HTMLParser import HTMLParser

# create a subclass and override the handler methods
class CategoryHTMLParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.simfileid = None
        self.title = None

    def handle_starttag(self, tag, attrs):
        if self.simfileid is None and tag == 'a':
            for attr in attrs:
                if attr[0] == "name":
                    self.simfileid = attr[1][3:]
                elif attr[0] == "title":
                    self.title = attr[1]
            if self.simfileid is None:
                raise RuntimeError("Link does not have name: {}".format(attrs))
            if self.title is None:
                raise RuntimeError("Link does not have title: {}".format(attrs))


class DownloadHTMLParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.link = None
        self.size = None

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return

        if self.link is not None:
            raise RuntimeError("Found more than one anchor!")

        for attr in attrs:
            if attr[0] == "href":
                self.link = attr[1]

        if self.link is None:
            raise RuntimeError("Found a link with no href: {}".format(attrs))

    def handle_data(self, data):
        if "MB" not in data:
            return

        if self.size is not None:
            raise RuntimeError("Found more than one size")
        data = data.strip()[1:-3]
        self.size = float(data) * 1024 * 1024


def get_content(url, split=True):
    connection = urllib2.urlopen(url)
    encoding = connection.headers.getparam('charset')
    if encoding is not None:
        content = connection.read().decode(encoding)
    else:
        content = connection.read()
    connection.close()

    if split:
        content = content.split("\n")

    return content


def get_category(category):
    """
    Returns a list of files in the category.

    The result is a list of pairs: simfile id, title.
    """
    url = "http://zenius-i-vanisher.com/v5.2/viewsimfilecategory.php?categoryid=%s" % category

    content = get_content(url)
    link_lines = [x for x in content if "viewsimfile.php?simfileid" in x]

    results = []
    for i in link_lines:
        parser = CategoryHTMLParser()
        parser.feed(i)
        results.append((parser.simfileid, parser.title))

    return results


def get_file_link(simfileid):
    """
    Gets the page for this particular simfile, extracts the link to
    the largest zip file on that link
    """
    url = "http://zenius-i-vanisher.com/v5.2/viewsimfile.php?simfileid=%s" % simfileid

    content = get_content(url)
    zip_lines = [x for x in content if "ZIP" in x]

    results = []
    for i in zip_lines:
        parser = DownloadHTMLParser()
        parser.feed(i)
        results.append((parser.link, parser.size))

    # sort by size, so we download the largest and presumably the most
    # interesting
    results.sort()
    link = results[-1][0]
    link = "http://zenius-i-vanisher.com/v5.2/%s" % link
    return link


def filter_titles(titles, prefix):
    return [x for x in titles if x[1].startswith(prefix)]


def get_simfile(simfileid, link):
    filename = "sim%s.zip" % simfileid
    if os.path.exists(filename):
        print "File already exists: %s" % filename
        return
    content = get_content(link, split=False)
    fout = open(filename, "wb")
    fout.write(content)
    fout.close()


if __name__ == "__main__":
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout)

    argparser = argparse.ArgumentParser(description='Download category')
    argparser.add_argument("--category", default="934",
                           help="Which category number to download")
    argparser.add_argument("--prefix", default="[Mid Speed]",
                           help="Only keep files with this prefix")
    args = argparser.parse_args()

    titles = get_category(args.category)
    if args.prefix:
        titles = filter_titles(titles, args.prefix)

    for simfile in titles:
        link = get_file_link(simfile[0])
        get_simfile(simfile[0], link)

