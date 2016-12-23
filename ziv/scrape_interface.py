"""
Done:
have a menu listing the categories you can download (done)
file picker to choose the directory to save to
have a text field offering with a prefix you can limit to
add a text field for regex as well
set defaults
button that launches the download

TODO:
button that reloads the categories

advanced:
a progress bar
remember the download directory between executions
"""

import os

import Tkinter as tk
import ttk
import tkFileDialog

import scrape_category

DEFAULT_PLATFORM="User"
DEFAULT_CATEGORY="Z-I-v Simfile Shuffle 2016"
DEFAULT_PREFIX="[Round B]"

class App(tk.Tk):

    def __init__(self, master, category_map):

        self.frame = tk.Frame(master)
        self.frame.pack()

        self.category_map = category_map

        # Add a dropdown chooser for the platform
        # eg Arcade, Wii, etc
        platform_list = list(category_map.keys())
        max_width = max(len(x) for x in platform_list)
        self.platform_var = tk.StringVar()
        self.platform_var.set(DEFAULT_PLATFORM)
        self.platform_drop = ttk.Combobox(self.frame,
                                          textvariable=self.platform_var,
                                          values=platform_list,
                                          state="readonly",
                                          width=max_width)
        self.platform_drop.bind("<<ComboboxSelected>>", self.choose_platform)
        self.platform_drop.pack(anchor="w")

        # Add a dropdown chooser for the category
        # When the platform changes, the list of available choices
        # will be updated
        category_list = list(category_map[self.platform_var.get()].keys())
        max_width = max(max(len(x) for x in platform.keys())
                        for platform in category_map.values())
        self.category_var = tk.StringVar()
        if DEFAULT_CATEGORY in category_list:
            self.category_var.set(DEFAULT_CATEGORY)
        else:
            self.category_var.set(category_list[0])
        self.category_drop = ttk.Combobox(self.frame,
                                          textvariable=self.category_var,
                                          values=category_list,
                                          state="readonly",
                                          width=max_width)
        self.category_drop.bind("<<ComboboxSelected>>", self.choose_category)
        self.category_drop.pack()

        # Build a frame for the directory chooser
        # Putting things in a small frame keeps them
        # coordinated visually
        # There is a button to show the chooser widget and a
        # label which shows the current directory
        directory_frame = tk.Frame(self.frame)
        directory_chooser = tk.Button(directory_frame,
                                      text='Destination directory',
                                      command=self.ask_directory)
        directory_chooser.pack(side=tk.LEFT)
        self.directory_var = tk.StringVar()
        self.directory_var.set(os.getcwd())
        label = ttk.Label(directory_frame, textvariable=self.directory_var)
        label.pack(side=tk.LEFT)
        directory_frame.pack(anchor="w")

        # Build a frame for the filters
        filter_frame = tk.Frame(self.frame)
        self.filter_choice = tk.IntVar()
        self.filter_choice.set(1)
        radio_none = tk.Radiobutton(filter_frame, text="No filter",
                                    variable=self.filter_choice, value=0)
        radio_none.grid(row=0, column=0, sticky=tk.W)

        radio_prefix = tk.Radiobutton(filter_frame, text="Prefix",
                                      variable=self.filter_choice, value=1)
        radio_prefix.grid(row=1, column=0, sticky=tk.W)
        self.prefix_entry = tk.Entry(filter_frame)
        self.prefix_entry.grid(row=1, column=1)
        self.prefix_entry.insert(0, DEFAULT_PREFIX)

        radio_regex = tk.Radiobutton(filter_frame, text="Regex",
                                     variable=self.filter_choice, value=2)
        radio_regex.grid(row=2, column=0, sticky=tk.W)
        self.regex_entry = tk.Entry(filter_frame)
        self.regex_entry.grid(row=2, column=1)
        filter_frame.pack(anchor="w")

        download_button = tk.Button(self.frame,
                                    text="DOWNLOAD!",
                                    command=self.download)
        download_button.pack(anchor="w")

    def ask_directory(self):
        new_dir = tkFileDialog.askdirectory(parent=self.frame,
                                            title="Directory to save simfiles")
        if new_dir:
            self.directory_var.set(new_dir)

    def choose_platform(self, event):
        platform = self.platform_var.get()
        print "Platform updated to %s" % platform
        new_category_list = list(category_map[platform].keys())
        self.category_drop['values'] = new_category_list
        self.category_var.set(new_category_list[0])

    def choose_category(self, event):
        print "Category updated to %s: %s" % (self.platform_var.get(),
                                              self.category_var.get())
        # self.category_var.get(), self.platform_var.get()

    def download(self):
        platform = self.platform_var.get()
        category = self.category_var.get()
        category_id = self.category_map[platform][category]
        download_directory = self.directory_var.get()
        print "Downloading %s to %s" % (category_id, download_directory)

        prefix = ""
        regex = ""
        if self.filter_choice.get() == 1:
            prefix = self.prefix_entry.get()
        elif self.filter_choice.get() == 2:
            regex = self.regex_entry.get()
        scrape_category.download_category(category_id, download_directory,
                                          prefix=prefix, regex=regex)


category_map = scrape_category.cached_scrape_platforms()

root = tk.Tk()

app = App(root, category_map)

root.mainloop()

# root.destroy() # optional; see description below
