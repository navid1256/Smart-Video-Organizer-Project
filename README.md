# 🎬 Smart-Video-Organizer-Project
This is a Smart Video Organizer Project for Organizing Movies And Series With Title Case Folder Features

A simple yet powerful desktop application built with Python and CustomTkinter to automatically organize your movie and TV show collections into clean, structured folders.


<img width="1918" height="1037" alt="image" src="https://github.com/user-attachments/assets/550022b6-1cd1-4c21-9179-6e557aed4e07" />


---

## ✨ Key Features

* **Smart Detection:** Automatically distinguishes between movies and TV series (using `SxxExx` patterns).
* **Clean Titles:** Strips junk tags from filenames (e.g., `1080p`, `x265`, `WEB-DL`, `RARBG`, etc.).
* **Year Recognition:** Detects the release year and appends it to the movie folder (e.g., `My Movie (2023)`).
* **Smart File Matching:** Intelligently moves related files (like `.srt`, `.ass`, `.zip`) along with their corresponding video file.
* **Season Folders:** Optionally creates season subfolders (e.g., `Season 01`) for TV shows.
* **Safe & Reversible:**
    * **Scan & Preview:** Shows a preview of all planned file operations before you commit.
    * **Undo Last Operation:** Easily revert the last organization batch with a single click.
* **Utility Tools:** Includes a **Title Case** button to format existing folder names while preserving hyphens (e.g., `my-folder` -> `My-Folder`).
* **Modern UI:** Features a persistent Light/Dark mode toggle.

---

## 🚀 How to Use (End-User)

1.  Run the `SmartVideoOrganizer.exe` file.
2.  Click **Browse** and select the folder containing your messy video files.
3.  Check the options you want:
    * `Move archives and subtitles (zip/rar/srt)`
    * `Create season subfolders for series`
4.  Click **Scan & Preview** to see what changes will be made in the log window.
5.  If you're happy with the preview, click **Organize** to move the files.
6.  Use the **Undo** button if you make a mistake!

---

## 👨‍💻 Running from Source (For Developers)

### 1. Prerequisites

First, clone the repository and install the required Python libraries. It is highly recommended to do this within a virtual environment.

```bash
git clone [https://github.com/navid1256/Smart-Video-Organizer-Project.git](https://github.com/navid1256/Smart-Video-Organizer-Project.git)
cd Smart-Video-Organizer-Project
pip install customtkinter pillow
