import argparse
import codecs
import os
import sys
import urllib2
import zipfile
from HTMLParser import HTMLParser

# create a subclass and override the handler methods
class CategoryHTMLParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.simfileid = None
        self.title = None
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if self.simfileid is None and tag == 'a':
            for attr in attrs:
                if attr[0] == "name":
                    self.simfileid = attr[1][3:]
            if self.simfileid is None:
                raise RuntimeError("Link does not have name: {}".format(attrs))
            self.in_title = True

    def handle_data(self, data):
        if self.in_title:
            if self.title is None:
                self.title = data
            else:
                # z-i-v doesn't properly write &amp; so we assume
                # the data is split on &
                self.title = self.title + "&" + data

    def handle_endtag(self, tag):
        if self.in_title:
            assert tag == "a"
            self.in_title = False

    def feed(self, data):
        HTMLParser.feed(self, data)
        assert self.title is not None
        assert self.simfileid is not None

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
    """
    Opens the URL, downloads the page.

    Respects encoding if possible.
    If split=True, splits the page on newlines.
    """
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

    print "Downloading category from:"
    print url

    content = get_content(url)
    link_lines = [x for x in content if "viewsimfile.php?simfileid" in x]

    results = []
    for i in link_lines:
        parser = CategoryHTMLParser()
        parser.feed(i)
        results.append((parser.simfileid, parser.title))

    print "Found %d simfiles" % len(results)

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


def simfile_already_downloaded(simfile, dest):
    simfileid, simfile_name = simfile
    filename = os.path.join(dest, simfile_name)
    if os.path.exists(filename):
        print "Directory already exists: %s" % filename
        return True

    filename = os.path.join(dest, "sim%s.zip" % simfileid)
    if os.path.exists(filename):
        print "Zip file already exists: %s" % filename
        return True
    return False


def valid_zipfile_directory_structure(filename):
    """
    Open the given file, then check its directory structure.

    Useful for testing from the interpreter or command line, for
    example, as you can pass in a filename instead of opening the zip
    yourself.
    """
    zip = None
    try:
        zip = zipfile.ZipFile(filename)
        result = valid_directory_structure(zip=zip)
        zip.close()
        return result
    except (zipfile.BadZipfile, IOError) as e:
        return False
    finally:
        if zip != None:
            zip.close()


def valid_directory_structure(zip):
    names = zip.namelist()
    if len(names) == 0:
        return False
    dirs = [x for x in names if x.endswith("/")]
    if len(dirs) > 1:
        return False
    elif len(dirs) == 1:
        directory = dirs[0]
    else:
        # No directory was zipped into the archive, but maybe all of
        # the files are in the same directory anyway
        slash_index = names[0].find("/")
        # if there is no "/" then this file is not in a subdirectory,
        # which is an invalid directory structure
        if slash_index < 0:
            return False
        directory = names[0][:slash_index]
    # All files have to be in the same subdirectory directory.
    # Obviously the subdirectory itself with startswith(itself)
    if any(not x.startswith(directory) for x in names):
        return False
    return True


def get_simfile(simfileid, link, dest, extract):
    filename = os.path.join(dest, "sim%s.zip" % simfileid)
    print "Downloading %s to %s" % (link, filename)
    content = get_content(link, split=False)
    fout = open(filename, "wb")
    fout.write(content)
    fout.close()

    if extract:
        zip = None
        try:
            zip = zipfile.ZipFile(filename)
            if not valid_directory_structure(zip):
                print "Invalid directory structure in %s" % filename
            else:
                zip.extractall()
        except (zipfile.BadZipfile, IOError) as e:
            print "Unable to extract %s" % filename
        if zip is not None:
            zip.close()


if __name__ == "__main__":
    # TODO: 
    # 29287 does not unzip correctly, zipfile.BadZipfile
    # 29303, 29295 do not have an inner folder.  Can we fix this?
    # 29308 also barfed - got an IOError
    # TODO features:
    # Clean up zips that are successfully extracted
    # Add a flag for dates to search for
    # Search all directories for the files, in case you are
    #   rearranging the files after downloading
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout)

    argparser = argparse.ArgumentParser(description='Download category')
    argparser.add_argument("--category", default="934",
                           help="Which category number to download")
    argparser.add_argument("--prefix", default="[Mid Speed]",
                           help="Only keep files with this prefix")
    argparser.add_argument("--dest", default="",
                           help="Where to put the simfiles.  Defaults to CWD")


    argparser.add_argument("--extract", dest="extract",
                           action="store_true",
                           help="Extract the zip files")
    argparser.add_argument("--no-extract", dest="extract",
                           action="store_false",
                           help="Don't extract the zip files")
    argparser.set_defaults(extract=True)

    args = argparser.parse_args()

    titles = get_category(args.category)
    if args.prefix:
        titles = filter_titles(titles, args.prefix)

    count = 0
    for simfile in titles:
        if not simfile_already_downloaded(simfile, args.dest):
            link = get_file_link(simfile[0])
            count = count + 1
            get_simfile(simfile[0], link, args.dest, args.extract)

    print "Downloaded %d simfiles" % count
