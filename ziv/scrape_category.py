import argparse
import codecs
import os
import sys
import urllib2
import zipfile
from collections import namedtuple
from HTMLParser import HTMLParser

Simfile = namedtuple("Simfile", "simfileid name")

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

    The result is a list of Simfile tuples: simfile id, name.
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
        results.append(Simfile(parser.simfileid, parser.title))

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
    return [x for x in titles if x.name.startswith(prefix)]


def simfile_already_downloaded(simfile, dest):
    filename = os.path.join(dest, simfile.name)
    if os.path.exists(filename):
        print "Directory already exists: %s" % filename
        return True

    filename = os.path.join(dest, simfile.name.strip())
    if os.path.exists(filename):
        print "Directory already exists: %s" % filename
        return True

    filename = os.path.join(dest, "sim%s.zip" % simfile.simfileid)
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
    simzip = None
    try:
        simzip = zipfile.ZipFile(filename)
        result = valid_directory_structure(simzip=simzip)
        simzip.close()
        return result
    except (zipfile.BadZipfile, IOError) as e:
        return False
    finally:
        if simzip != None:
            simzip.close()


def valid_directory_structure(simzip):
    names = simzip.namelist()
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


def flat_directory_structure(simzip):
    """
    Returns True if the zip does not actually contain any directories,
    but is instead just a bunch of files.
    This isn't the way zips are supposed to be organized on z-i-v,
    but some people do submit zip files that way anyway, so it is
    good to compensate.
    """
    names = simzip.namelist()
    if len(names) == 0:
        return False
    for name in names:
        if name.find("/") >= 0:
            return False
    return True


def get_directory(simzip):
    """
    Assumes the directory structure inside the zip is valid,
    so it assumes there is exactly one directory and returns that.
    Eg, call valid_directory_structure before calling this function.
    """
    names = simzip.namelist()
    return names[0].split("/")[0]


def extract_fixing_spaces(simzip, dest, inner_directory):
    """
    Unfortunately, some files have spaces at the end of their
    directory names, and on Windows that screws everything up.  This
    method fixes it by reading the files manually and writing them to
    the correct location.
    """
    inner_directory = inner_directory.strip()
    directory = os.path.join(dest, inner_directory)
    os.mkdir(directory)

    for name in simzip.namelist():
        filename = name.split("/")[1].strip()
        if not filename:
            continue
        data = simzip.read(name)
        new_name = os.path.join(directory, filename)
        fout = open(new_name, "wb")
        fout.write(data)
        fout.close()


def extract_simfile(simfile, dest):
    """
    Given an (id, name) tuple and the destination arg, extract
    the simfile to the appropriate location.

    Tries to compensate for a couple error cases.
    If the zipfile does not contain a folder, a folder is created
    with the simfile's name.
    If the simfile's name has trailing or leading spaces, this
    causes IOErrors on Windows, but that is also fixable.
    """
    filename = os.path.join(dest, "sim%s.zip" % simfile.simfileid)

    simzip = None
    try:
        simzip = zipfile.ZipFile(filename)
        if flat_directory_structure(simzip):
            dest_dir = os.path.join(dest, simfile.name.strip())
            simzip.extractall(dest_dir)
        elif not valid_directory_structure(simzip):
            print "Invalid directory structure in %s" % filename
        else:
            inner_directory = get_directory(simzip)
            if inner_directory != inner_directory.strip():
                extract_fixing_spaces(simzip, dest, inner_directory)
            else:
                simzip.extractall()
    except (zipfile.BadZipfile, IOError) as e:
        print "Unable to extract %s" % filename
    if simzip is not None:
        simzip.close()


def get_simfile(simfileid, link, dest, extract):
    filename = os.path.join(dest, "sim%s.zip" % simfileid)
    print "Downloading %s to %s" % (link, filename)
    content = get_content(link, split=False)
    fout = open(filename, "wb")
    fout.write(content)
    fout.close()


if __name__ == "__main__":
    # If a file doesn't have an inner folder, such as 29303,
    # we extract the zip to the correct location.
    # If a directory has trailing whitespace, such as 29308,
    # the files are extracted manually to the correct location.
    # TODO: 
    # 29287 does not unzip correctly, zipfile.BadZipfile
    # 29343 extracts to a different name
    # TODO features:
    # Clean up zips that are successfully extracted
    # Add a flag for dates to search for
    # Search all directories for the files, in case you are
    #   rearranging the files after downloading?
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout)

    argparser = argparse.ArgumentParser(description='Download an entire category from z-i-v.  The prefix argument lets you set a prefix, such as for one week worth of simfile contests.')
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
            link = get_file_link(simfile.simfileid)
            count = count + 1
            get_simfile(simfile.simfileid, link, args.dest, args.extract)
            if args.extract:
                extract_simfile(simfile, args.dest)

    print "Downloaded %d simfiles" % count
