"""
Done:
have a menu listing the categories you can download (done)
file picker to choose the directory to save to

TODO:
have a text field offering with a prefix you can limit to
add a text field for regex as well
button that launches the download
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

class App(tk.Tk):

    def __init__(self, master, category_map):

        self.frame = tk.Frame(master)
        self.frame.pack()

        self.category_map = category_map

        platform_list = list(category_map.keys())
        max_width = max(len(x) for x in platform_list)
        self.platform_var = tk.StringVar()
        self.platform_var.set(platform_list[0])
        self.platform_drop = ttk.Combobox(self.frame,
                                          textvariable=self.platform_var,
                                          values=platform_list,
                                          state="readonly",
                                          width=max_width)
        self.platform_drop.bind("<<ComboboxSelected>>", self.choose_platform)
        self.platform_drop.pack(anchor="w")

        category_list = list(category_map[platform_list[0]].keys())
        max_width = max(max(len(x) for x in platform.keys())
                        for platform in category_map.values())
        self.category_var = tk.StringVar()
        self.category_var.set(category_list[0])
        self.category_drop = ttk.Combobox(self.frame,
                                          textvariable=self.category_var,
                                          values=category_list,
                                          state="readonly",
                                          width=max_width)
        self.category_drop.bind("<<ComboboxSelected>>", self.choose_category)
        self.category_drop.pack()

        directory_chooser = tk.Button(self.frame,
                                      text='askdirectory',
                                      command=self.ask_directory)
        directory_chooser.pack(anchor="w", side=tk.LEFT)
        self.directory_var = tk.StringVar()
        self.directory_var.set(os.getcwd())
        label = ttk.Label(self.frame, textvariable=self.directory_var)
        label.pack(side=tk.LEFT)

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
        print "%s: %s" % (self.platform_var.get(), self.category_var.get())
        # self.category_var.get(), self.platform_var.get()

category_map = scrape_category.cached_scrape_platforms()

root = tk.Tk()

app = App(root, category_map)

root.mainloop()

# root.destroy() # optional; see description below
