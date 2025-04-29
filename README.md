# 📚 Personal Book Library (PyQt5)

Manage your personal digital library of PDF/EPUB files with a sleek, user-friendly desktop app.  
Easily track your reading progress, rate books with stars, and manage everything in one place.

![screenshot](https://imgur.com/a/BGXqQDb)  


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
python pyqt5.py
```

    
    
## 📦 Build a Standalone EXE (Windows)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed pyqt5.py
```

    
    
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
-  Metadata extraction for EPUB files
-  Support multiple languages
-  Cloud sync or backup option

    
    

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










