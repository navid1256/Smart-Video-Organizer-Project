# 🎬 Smart-Video-Organizer-Project
This is a Smart Video Organizer Project for Organizing Movies And Series With Title Case Folders Features

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
```

---

## 📦 Building the .exe (for Windows)
You can bundle this application into a single standalone executable using PyInstaller. This allows it to run on any Windows computer without requiring Python to be installed.

### Step 1: Install PyInstaller
If you haven't already, install PyInstaller:

```bash
pip install pyinstaller
```
### Step 2: Prepare Your Application Icon
You will need an icon file for your application (like the main.jpg you provided).

You must convert this image to a valid .ico file. You can use an online tool like ICO Convert.

Save this new file as app_icon.ico in the same root folder as your Video Organizer.py script.

### Step 3: Final Project Structure
Your folder should now look like this:

Your-Project-Folder/
├── Video Organizer.py           <-- Your main Python script
├── app_icon.ico                 <-- Your new application icon
└── icons/                         <-- The folder of button icons
    ├── folder.ico
    ├── ... (etc.)
    
### Step 4: Run the PyInstaller Command
Open a terminal (Command Prompt or PowerShell) in your project's root directory (Your-Project-Folder) and run the following command:

```Bash

pyinstaller --name "SmartVideoOrganizer" --onefile --windowed --icon="app_icon.ico" --add-data "icons;icons" "Video Organizer.py"
```
**Command Breakdown:**

--name "SmartVideoOrganizer": Sets the name of your final .exe file.

--onefile: Bundles everything into a single executable.

--windowed: Prevents the black console window from appearing when you run the app.

--icon="app_icon.ico": Sets your custom icon for the .exe file.

--add-data "icons;icons": (Crucial Step) This bundles the icons folder into the .exe so the app can find the button icons.

"Video Organizer.py": The name of your script.

### Step 5: Find Your Executable
After the process completes, you will find your standalone application inside the newly created dist folder:

dist/SmartVideoOrganizer.exe

You can now share this single file with anyone.
