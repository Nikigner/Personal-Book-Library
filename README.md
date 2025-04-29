# 📚 Personal Book Library (PyQt5)

Manage your personal digital library of PDF/EPUB files with a user-friendly desktop app.  
Easily track your reading progress, rate books with stars, and manage everything in one place.

![screenshot](https://github.com/user-attachments/assets/5e9f87ba-fa5f-4004-a485-3d0be3c0d39e)


  
---

## ✨ Features

- 📂 Add and manage book files (PDF, EPUB)
- 🌟 Star-based rating system (editable)
- 📖 Track reading progress in pages + visual progress bar
- 🎨 Dark mode toggle (powered by `qdarkstyle`)
- 🔍 Real-time search & filtering
- 🧠 Remembers your reading and rating history
- 📁 Open book file location via context menu

---

        
## 🛠️ Requirements

- Python 3.8 or higher

Install dependencies:

```bash
pip install -r requirements.txt
```

    
    
## 🚀 Running the App

```bash
python Personal-book-library.py
```

    
    
## 📦 Build a Standalone EXE (Windows)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed pyqt5.py
```


## 🔐 Safety Note
This app is unsigned, so you may get a warning from Windows SmartScreen.
If that happens, click “More info” → “Run anyway” to launch it.
(This is expected for indie apps not published through Microsoft Store.)
    
    
    
## 📁 Project Structure

```
├── pyqt5.py            # Main application
├── library.db          # Auto-generated database (optional to share)
├── books_library/      # Folder for imported books
├── requirements.txt    # Python dependencies
├── LICENSE             # MIT License
├── README.md           # This file
└── .gitignore          # Git cleanup rules
```

    
    
## ✅ To-Do / Roadmap

-  Drag-and-drop support
-  Audio books Support
-  Cloud sync or backup option
-  Support multiple languages


    
    

## 🙏 Credits

- [PyQt5](https://pypi.org/project/PyQt5/)
- [QDarkStyle](https://pypi.org/project/qdarkstyle/)
- [PyPDF2](https://pypi.org/project/PyPDF2/)
- [EbookLib](https://pypi.org/project/EbookLib/)
---

    
    
## 🤝 Contribute

Contributions and ideas are welcome!  
Please open an issue or pull request.   
    
⭐️ If You Like It 










