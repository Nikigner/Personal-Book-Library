import os
import sys
import sqlite3
import shutil
import base64
import math
import subprocess
import PyPDF2
import time # Import time for potential performance measurement (optional)

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QFileDialog,
    QMessageBox, QGroupBox, QToolButton, QHeaderView, QStyledItemDelegate, QComboBox,
    QStyleOptionProgressBar, QStyle, QMenu, QAction, QInputDialog, QSizePolicy
)
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QPolygon, QDesktopServices
from PyQt5.QtCore import Qt, QEvent, QPoint, QSize, QUrl, QRectF, QVariant, QTimer, QThread, pyqtSignal, QModelIndex

import qdarkstyle

# --------------------------
# Database functions
# --------------------------
DB_FILE = 'library.db'
UPLOAD_FOLDER = 'books_library'

def init_db():
    """Initializes the database and creates the books table if it doesn't exist."""
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # Keep read_status in DB for potential future use, but remove from UI
        c.execute('''CREATE TABLE IF NOT EXISTS books
                     (id INTEGER PRIMARY KEY,
                      name TEXT UNIQUE, -- Ensure book names are unique
                      pdf_path TEXT,
                      read_status INTEGER,
                      star_rating INTEGER,
                      page_read INTEGER DEFAULT 0,
                      file_size INTEGER,
                      total_pages INTEGER DEFAULT 0)''')

        # Check and add missing columns if they exist from previous versions
        c.execute("PRAGMA table_info(books)")
        columns = [col[1] for col in c.fetchall()]

        # Add columns if they don't exist (more robust check)
        missing_columns = {
            'read_status': 'INTEGER DEFAULT 0',
            'star_rating': 'INTEGER DEFAULT 0',
            'page_read': 'INTEGER DEFAULT 0',
            'file_size': 'INTEGER',
            'total_pages': 'INTEGER DEFAULT 0'
        }
        for col_name, col_type in missing_columns.items():
            if col_name not in columns:
                try:
                    c.execute(f"ALTER TABLE books ADD COLUMN {col_name} {col_type}")
                    # print(f"Added missing column: {col_name}") # Removed logging
                except sqlite3.Error as e:
                    print(f"Error adding column {col_name}: {e}")


        # Populate missing file_size and total_pages for existing entries if needed
        # This can be time-consuming for large libraries, consider doing this in a separate process or on demand.
        # For now, keeping the original logic but adding error handling.
        if 'file_size' in columns:
             c.execute("SELECT id, pdf_path FROM books WHERE file_size IS NULL")
             for book_id, pdf_path in c.fetchall():
                 if os.path.exists(pdf_path):
                     try:
                         file_size = os.path.getsize(pdf_path)
                         c.execute("UPDATE books SET file_size = ? WHERE id = ?", (file_size, book_id))
                     except OSError as e:
                         print(f"Error getting file size for {pdf_path}: {e}")
                         c.execute("UPDATE books SET file_size = ? WHERE id = ?", (0, book_id)) # Set to 0 on error
        if 'total_pages' in columns:
             c.execute("SELECT id, pdf_path FROM books WHERE total_pages IS NULL OR total_pages = 0")
             for book_id, pdf_path in c.fetchall():
                 if os.path.exists(pdf_path):
                     try:
                         total_pages = get_pdf_total_pages(pdf_path)
                         c.execute("UPDATE books SET total_pages = ? WHERE id = ?", (total_pages, book_id))
                     except Exception as e: # Catch potential errors from get_pdf_total_pages
                         print(f"Error getting total pages for {pdf_path}: {e}")
                         c.execute("UPDATE books SET total_pages = ? WHERE id = ?", (0, book_id)) # Set to 0 on error


        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error during initialization: {e}")
    finally:
        if conn:
            conn.close()

def get_pdf_total_pages(pdf_path):
    """Gets the total number of pages from a PDF file."""
    if not os.path.exists(pdf_path):
        # print(f"PDF file not found: {pdf_path}") # Removed logging
        return 0
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            if reader.is_encrypted:
                try:
                    # Attempt decryption with an empty password or common default passwords
                    # For more robust handling, you might need to prompt the user for a password
                    reader.decrypt('')
                except PyPDF2.errors.FileCredentialsError:
                    # print(f"PDF is encrypted and cannot be decrypted without a password: {pdf_path}") # Removed logging
                    return 0 # Cannot get pages from encrypted PDF
            return len(reader.pages)
    except FileNotFoundError:
        # This case should ideally be caught by the os.path.exists check, but included for robustness
        # print(f"PDF file not found (during page count): {pdf_path}") # Removed logging
        return 0
    except PyPDF2.errors.PdfReadError as e:
        print(f"Error reading PDF file {pdf_path} for page count: {e}")
        return 0
    except Exception as e:
        print(f"An unexpected error occurred reading PDF pages from {pdf_path}: {e}")
        return 0

def add_book_to_db(name, pdf_path, file_size, total_pages):
    """Adds a new book to the database."""
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # read_status and star_rating default to 0
        c.execute("INSERT INTO books (name, pdf_path, read_status, star_rating, page_read, file_size, total_pages) VALUES (?, ?, 0, 0, 0, ?, ?)",
                  (name, pdf_path, file_size, total_pages))
        conn.commit()
        return c.lastrowid # Return the ID of the newly added book
    except sqlite3.IntegrityError:
        print(f"Book with name '{name}' already exists.")
        return None # Indicate that the book was not added due to duplicate name
    except sqlite3.Error as e:
        print(f"Database error adding book '{name}': {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_books():
    """Retrieves all books from the database."""
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, name, pdf_path, read_status, star_rating, page_read, file_size, total_pages FROM books")
        books = c.fetchall()
        return books
    except sqlite3.Error as e:
        print(f"Database error retrieving books: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_books_by_id(book_id):
    """Retrieves a single book's data by its ID."""
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, name, pdf_path, read_status, star_rating, page_read, file_size, total_pages FROM books WHERE id = ?", (book_id,))
        book = c.fetchone() # Use fetchone as we expect only one result
        return book
    except sqlite3.Error as e:
        print(f"Database error retrieving book with ID {book_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def update_book_in_db(book_id, read_status=None, star_rating=None, page_read=None):
    """Updates specific fields for a book in the database."""
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        updates = []
        params = []
        if read_status is not None:
            updates.append("read_status = ?")
            params.append(read_status)
        if star_rating is not None:
            updates.append("star_rating = ?")
            params.append(star_rating)
        if page_read is not None:
            updates.append("page_read = ?")
            params.append(page_read)

        if not updates:
            return # Nothing to update

        query = f"UPDATE books SET {', '.join(updates)} WHERE id = ?"
        params.append(book_id)

        c.execute(query, params)
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error updating book with ID {book_id}: {e}")
    finally:
        if conn:
            conn.close()

def delete_book_from_db(book_id):
    """Deletes a book from the database."""
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM books WHERE id = ?", (book_id,))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error deleting book with ID {book_id}: {e}")
    finally:
        if conn:
            conn.close()

def check_book_exists(name):
    """Returns True if a book with the given name exists."""
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM books WHERE name = ?", (name,))
        exists = c.fetchone()[0] > 0
        return exists
    except sqlite3.Error as e:
        print(f"Database error checking if book exists: {e}")
        return False
    finally:
        if conn:
            conn.close()

def load_icon_from_base64(b64_data):
    """Loads a QIcon from base64 encoded image data."""
    b64_data = "".join(b64_data.split())
    missing_padding = len(b64_data) % 4
    if missing_padding:
        b64_data += "=" * (4 - missing_padding)
    pixmap = QPixmap()
    try:
        data = base64.b64decode(b64_data)
        pixmap.loadFromData(data)
        return QIcon(pixmap)
    except Exception as e:
        print(f"Error loading icon from base64: {e}")
        return QIcon() # Return empty icon on error

# --------------------------
# Icons (Base64 encoded)
# --------------------------
SUN_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6"
    "JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAKlBMVEUAAAD/////////////////////////////////////////////////"
    "///////////////////////////////////////////////////////////////+7p5paAAAAAXRSTlMAQObYZgAAAEJJREFUGNNjYGBgYAAAAAUAAYVAYoAAAAASUVORK5CYII="
)

MOON_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6"
    "JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAKlBMVEUAAAD/////////////////////////////////////////////////"
    "///////////////////////////////////////////////////////////////+7p5paAAAAAXRSTlMAQObYZgAAAEZJREFUGNNjYGBgYAAAAAUAAarJ3sgAAAAASUVORK5CYII="
)

# --------------------------
# Star Rendering
# --------------------------
def create_star_polygon(outer_radius=10, inner_radius=5):
    """Generate a 5 pointed star as a QPolygon using trigonometry."""
    points = []
    for i in range(10):
        angle_deg = i * 36  # 360/10
        angle_rad = math.radians(angle_deg - 90)  # start at top
        r = outer_radius if i % 2 == 0 else inner_radius
        x = int(r * math.cos(angle_rad))
        y = int(r * math.sin(angle_rad))
        points.append(QPoint(x, y))
    return QPolygon(points)

class StarDelegate(QStyledItemDelegate):
    """Custom delegate for rendering and editing star ratings in the table."""
    def paint(self, painter, option, index):
        star_rating = index.data(Qt.EditRole)
        if star_rating is None:
            star_rating = 0
        painter.save()
        option.displayAlignment = Qt.AlignCenter
        star_polygon = create_star_polygon(outer_radius=10, inner_radius=5)
        star_width = option.rect.width() / 5
        for i in range(5):
            painter.setBrush(QColor("#3589f3") if i < star_rating else QColor("#D3D3D3"))
            center_x = option.rect.x() + star_width * i + star_width / 2
            center_y = option.rect.y() + option.rect.height() / 2
            painter.save()
            painter.translate(center_x, center_y)
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(star_polygon)
            painter.restore()
        painter.restore()

    def editorEvent(self, event, model, option, index):
        """Handles mouse click events for changing the star rating."""
        if event.type() == QEvent.MouseButtonRelease:
            pos = event.pos()
            relative_x = pos.x() - option.rect.x()
            star_width = option.rect.width() / 5
            new_rating = int(relative_x // star_width) + 1
            new_rating = max(0, min(new_rating, 5))
            # Update the model data, which will trigger the cellChanged signal
            model.setData(index, new_rating, Qt.EditRole)

            # The database update is now handled in the cell_changed slot in the main window
            # to centralize data update logic.

            return True
        return False

# --------------------------
# Custom QTableWidgetItem for sorting
# --------------------------
class SortableItem(QTableWidgetItem):
    """Custom QTableWidgetItem that stores original data for sorting."""
    def __init__(self, text, data=None):
        super().__init__(text)
        self._data = data # Store original data for sorting

    def data(self, role: int):
        if role == Qt.UserRole:
            return self._data
        return super().data(role)

    def __lt__(self, other):
        """Custom comparison for sorting."""
        if isinstance(other, SortableItem):
            # If original data is available and comparable, use it
            if self._data is not None and other._data is not None:
                try:
                    return self._data < other._data
                except TypeError:
                    # Fallback to text comparison if data is not directly comparable
                    return super().__lt__(other)
            # Fallback to text comparison if original data is not available
            return super().__lt__(other)
        # Fallback to default comparison if comparing with a non-SortableItem
        return super().__lt__(other)

# --------------------------
# Progress Bar Delegate
# --------------------------
from PyQt5.QtGui import QColor

class ProgressDelegate(QStyledItemDelegate):
    """Custom delegate for rendering a progress bar in the table."""
    def paint(self, painter, option, index):
        percentage = index.data(Qt.UserRole)
        if percentage is None:
            percentage = 0

        opt = QStyleOptionProgressBar()
        opt.rect = option.rect.adjusted(2, 2, -2, -2)
        opt.minimum = 0
        opt.maximum = 100
        opt.progress = percentage
        opt.textVisible = True
        opt.text = f"{percentage}%"
        opt.state = QStyle.State_Enabled | QStyle.State_Horizontal

        # Draw base progress bar background
        QApplication.style().drawControl(QStyle.CE_ProgressBar, opt, painter)

        # Custom drawing
        painter.save()
        painter.setPen(Qt.NoPen)
        if percentage >= 100:
            painter.setBrush(QColor("#3589f3"))  
        else:
            painter.setBrush(QColor("#5cd02a"))  

        progress_width = int(opt.rect.width() * (percentage / 100))
        progress_rect = QRectF(opt.rect.x(), opt.rect.y(), progress_width, opt.rect.height())
        painter.drawRect(progress_rect)

        # Draw text on top
        painter.setPen(Qt.white)
        painter.drawText(opt.rect, Qt.AlignCenter, opt.text)
        painter.restore()



# --------------------------
# Worker Thread for Background Tasks (e.g., adding books)
# --------------------------
class AddBookWorker(QThread):
    """Worker thread for adding books to avoid freezing the UI."""
    book_added = pyqtSignal(object) # Signal to emit when a book is successfully added
    error_occurred = pyqtSignal(str) # Signal to emit when an error occurs
    duplicate_found = pyqtSignal(str) # Signal to emit when a duplicate is found

    def __init__(self, pdf_paths):
        super().__init__()
        self.pdf_paths = pdf_paths

    def run(self):
        if not os.path.exists(UPLOAD_FOLDER):
            try:
                os.makedirs(UPLOAD_FOLDER)
            except OSError as e:
                self.error_occurred.emit(f"Could not create upload directory: {e}")
                return

        for pdf_path in self.pdf_paths:
            filename = os.path.basename(pdf_path)
            name, ext = os.path.splitext(filename)

            if check_book_exists(name):
                self.duplicate_found.emit(name)
                continue

            try:
                destination = os.path.join(UPLOAD_FOLDER, filename)
                shutil.copyfile(pdf_path, destination)
                file_size = os.path.getsize(destination)

                total_pages = 0
                if ext.lower() == '.pdf':
                    total_pages = get_pdf_total_pages(destination)

                book_id = add_book_to_db(name, destination, file_size, total_pages)
                if book_id is not None:
                    # Fetch the newly added book data to emit
                    new_book_data = get_books_by_id(book_id)
                    if new_book_data:
                        self.book_added.emit(new_book_data)

            except Exception as e:
                self.error_occurred.emit(f"Could not process file {filename}: {e}")
                # Clean up the copied file if it was copied before the error
                if os.path.exists(destination):
                    try:
                        os.remove(destination)
                    except OSError as cleanup_e:
                        print(f"Error cleaning up file {destination}: {cleanup_e}")
                continue # Continue with the next file


# --------------------------
# Main Application
# --------------------------
class LibraryApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Books Library")
        self.setGeometry(100, 100, 900, 650) # Adjusted window size again
        self.dark_mode = False
        self.icon_light = load_icon_from_base64(SUN_ICON_B64)
        self.icon_dark = load_icon_from_base64(MOON_ICON_B64)
        self.sort_order = Qt.AscendingOrder
        self.ignore_cell_changes = False  # Flag to ignore cellChanged events when refreshing

        # Dictionary to store opened book processes: {process_object: book_id}
        self.opened_books = {}
        # Timer to check for closed processes - Faster interval
        self.process_check_timer = QTimer(self)
        self.process_check_timer.timeout.connect(self.check_opened_books)
        self.process_check_timer.start(500) # Check every 500 milliseconds (less frequent might be fine)

        self.add_book_worker = None # To hold the worker thread instance

        self.setup_ui()
        init_db()
        self.load_books_into_table() # Initial load

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout()
        central_widget.setLayout(self.main_layout)

        top_bar = QHBoxLayout()
        self.theme_toggle_btn = QToolButton()
        self.theme_toggle_btn.setIcon(self.icon_light)
        self.theme_toggle_btn.setIconSize(QSize(24, 24))
        self.theme_toggle_btn.setToolTip("Toggle Theme")
        self.theme_toggle_btn.clicked.connect(self.toggle_theme)
        top_bar.addWidget(self.theme_toggle_btn)

        # Add Search Bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search books...")
        self.search_bar.textChanged.connect(self.search_books)
        self.search_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred) # Allow search bar to expand
        top_bar.addWidget(self.search_bar)

        # Add Search Filter Dropdown (removed Read Status)
        self.search_filter = QComboBox()
        self.search_filter.addItems(["All", "Name", "Star Rating", "Page Read", "Total Pages"])
        top_bar.addWidget(self.search_filter)

        top_bar.addStretch() # Push elements to the left
        self.main_layout.addLayout(top_bar)

        # Table columns:
        # 0 - Name, 1 - Star Rating, 2 - File Size (MB),
        # 3 - Page Read, 4 - Total Pages, 5 - Progress.
        self.book_table = QTableWidget()
        self.book_table.setColumnCount(6) # Reduced column count
        self.book_table.setHorizontalHeaderLabels([
            "Name", "Star Rating", "File Size (MB)", "Page Read", "Total Pages",
            "Progress"
        ])
        self.book_table.horizontalHeader().sectionClicked.connect(self.sort_books)
        self.book_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) # Stretch columns
        self.book_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive) # Allow Name column to be interactive
        self.book_table.setColumnWidth(0, 250)
        self.book_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive) # Fit Star Rating to contents
        self.book_table.setColumnWidth(1, 95) 
        self.book_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents) # Fit File Size to contents
        self.book_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents) # Fit Page Read to contents
        self.book_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents) # Fit Total Pages to contents
        self.book_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch) # Stretch Progress column

        self.book_table.installEventFilter(self) # Install event filter for Delete key
        self.book_table.setContextMenuPolicy(Qt.CustomContextMenu) # Enable custom context menu
        self.book_table.customContextMenuRequested.connect(self.show_context_menu) # Connect signal
        self.book_table.cellChanged.connect(self.cell_changed)
        self.book_table.setSortingEnabled(True) # Enable sorting initially
        self.main_layout.addWidget(self.book_table)

        add_group = QGroupBox("Add New Books")
        add_layout = QVBoxLayout()
        add_group.setLayout(add_layout)
        self.main_layout.addWidget(add_group)

        pdf_layout = QHBoxLayout()
        pdf_label = QLabel("PDF Files:")
        self.pdf_edit = QLineEdit()
        self.pdf_edit.setReadOnly(True)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_files)
        pdf_layout.addWidget(pdf_label)
        pdf_layout.addWidget(self.pdf_edit)
        pdf_layout.addWidget(self.browse_button)
        add_layout.addLayout(pdf_layout)

    def toggle_theme(self):
        """Toggles between dark and light themes."""
        if self.dark_mode:
            self.setStyleSheet("")
            self.theme_toggle_btn.setIcon(self.icon_light)
            self.dark_mode = False
        else:
            self.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
            self.theme_toggle_btn.setIcon(self.icon_dark)
            self.dark_mode = True

    def load_books_into_table(self, books=None):
        """Loads book data into the table widget. Optimized to update efficiently."""
        start_time = time.time() # For performance measurement

        if books is None:
            books = get_books()

        self.ignore_cell_changes = True # Ignore cellChanged signals during bulk update
        self.book_table.setSortingEnabled(False) # Disable sorting during update
        self.book_table.setRowCount(0) # Clear existing rows

        # Set delegates for the correct columns based on the new structure
        self.book_table.setItemDelegateForColumn(1, StarDelegate(self.book_table)) # Star Rating is column 1
        self.book_table.setItemDelegateForColumn(5, ProgressDelegate(self.book_table)) # Progress is column 5

        for book in books:
            # book: (id, name, pdf_path, read_status, star_rating, page_read, file_size, total_pages)
            row_position = self.book_table.rowCount()
            self.book_table.insertRow(row_position)

            book_id, name, pdf_path, read_status, star_rating, page_read, file_size, total_pages = book

            # Name item with extra book data (id, pdf_path)
            name_item = SortableItem(name, data={"id": book_id, "pdf_path": pdf_path})
            name_item.setFlags(name_item.flags() ^ Qt.ItemIsEditable) # Make name column non-editable
            self.book_table.setItem(row_position, 0, name_item)

            # Star rating item - Use SortableItem to store the integer value for sorting
            star_rating_item = SortableItem("", data=star_rating)
            star_rating_item.setData(Qt.EditRole, star_rating) # Store integer for delegate editing
            star_rating_item.setFlags(star_rating_item.flags() | Qt.ItemIsEditable) # Make editable for delegate
            self.book_table.setItem(row_position, 1, star_rating_item) # column 1

            # File size (bytes to MB) - Use SortableItem to store the raw size for sorting
            file_size_mb = file_size / (1024 * 1024) if file_size else 0
            file_size_item = SortableItem(f"{file_size_mb:.2f} MB", data=file_size)
            file_size_item.setFlags(file_size_item.flags() ^ Qt.ItemIsEditable) # Make non-editable
            self.book_table.setItem(row_position, 2, file_size_item) # column 2

            # Page Read column (editable to store current page progress) - Use SortableItem for sorting
            page_read = page_read if page_read is not None else 0
            page_read_item = SortableItem(str(page_read), data=page_read)
            page_read_item.setData(Qt.EditRole, page_read) # Store integer value for editing
            page_read_item.setFlags(page_read_item.flags() | Qt.ItemIsEditable)
            self.book_table.setItem(row_position, 3, page_read_item) # column 3

            # Total Pages column (read-only) - Use SortableItem for sorting
            total_pages = total_pages if total_pages is not None else 0
            total_pages_item = SortableItem(str(total_pages), data=total_pages)
            total_pages_item.setFlags(Qt.ItemIsEnabled) # Make it read-only
            self.book_table.setItem(row_position, 4, total_pages_item) # column 4

            # Progress Bar column (handled by delegate) - Use SortableItem to store percentage for sorting
            percentage = 0
            if total_pages > 0:
                 percentage = min(100, max(0, int((page_read / total_pages) * 100)))

            # Progress item is always created, even if total_pages is 0
            progress_item = SortableItem("", data=percentage) # Use SortableItem
            progress_item.setData(Qt.UserRole, percentage) # Store percentage for delegate/sorting
            progress_item.setFlags(Qt.ItemIsEnabled) # Make it read-only
            self.book_table.setItem(row_position, 5, progress_item) # column 5

        self.book_table.setSortingEnabled(True) # Re-enable sorting
        self.ignore_cell_changes = False # Re-enable cellChanged signals

        # print(f"load_books_into_table took: {end_time - start_time:.4f} seconds") # Removed logging


    def search_books(self, query):
        """Filters the book list based on the search query and filter type."""
        filter_type = self.search_filter.currentText()
        books = get_books() # Fetch all books for searching
        filtered_books = []

        # Normalize query for case-insensitive search
        query_lower = query.lower()

        for book in books:
            # book: (id, name, pdf_path, read_status, star_rating, page_read, file_size, total_pages)
            book_id, name, pdf_path, read_status, star_rating, page_read, file_size, total_pages = book

            # Prepare book data as lowercase strings for searching
            book_data_str = {
                "All": [str(item).lower() for item in book[1:] if item is not None], # All columns except id
                "Name": str(name).lower() if name is not None else "",
                "Star Rating": str(star_rating).lower() if star_rating is not None else "",
                "Page Read": str(page_read).lower() if page_read is not None else "",
                "Total Pages": str(total_pages).lower() if total_pages is not None else ""
            }

            if filter_type == "All":
                if any(query_lower in item for item in book_data_str["All"]):
                    filtered_books.append(book)
            elif filter_type in book_data_str:
                 # For specific columns, check if the query is a substring
                 if query_lower in book_data_str[filter_type]:
                     filtered_books.append(book)
            # Note: Numeric filters ("Star Rating", "Page Read", "Total Pages") are treated as text search here.
            # For true numeric filtering, you would need to convert the query to a number and compare numeric values.


        self.load_books_into_table(filtered_books) # Load filtered results

    def sort_books(self, column):
        """Sorts the table by the specified column."""
        # QTableWidget's built-in sortItems uses the __lt__ method of the QTableWidgetItem
        # Our custom SortableItem handles sorting based on the stored data.
        current_order = self.book_table.horizontalHeader().sortIndicatorOrder()
        # Toggle sort order if clicking the same column again
        if self.book_table.horizontalHeader().sortIndicatorSection() == column:
             self.sort_order = Qt.DescendingOrder if current_order == Qt.AscendingOrder else Qt.AscendingOrder
        else:
             self.sort_order = Qt.AscendingOrder # Default to ascending for a new column

        self.book_table.sortItems(column, self.sort_order)
        # Update the sort indicator in the header
        self.book_table.horizontalHeader().setSortIndicator(column, self.sort_order)


    def browse_files(self):
        """Opens a file dialog to select PDF or EPUB files and starts the add book process."""
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select PDF or EPUB Files", "", "PDF and EPUB Files (*.pdf *.epub)")
        if file_paths:
            self.pdf_edit.setText(", ".join(file_paths))
            self.start_add_books_worker(file_paths)


    def start_add_books_worker(self, pdf_paths):
        """Starts a worker thread to add books in the background."""
        if self.add_book_worker is not None and self.add_book_worker.isRunning():
            QMessageBox.warning(self, "Busy", "Please wait for the current book adding process to finish.")
            return

        self.add_book_worker = AddBookWorker(pdf_paths)
        self.add_book_worker.book_added.connect(self.handle_book_added)
        self.add_book_worker.error_occurred.connect(self.handle_add_book_error)
        self.add_book_worker.duplicate_found.connect(self.handle_duplicate_found)
        self.add_book_worker.finished.connect(self.handle_add_book_finished) # Connect to finished signal
        self.add_book_worker.start()
        # Disable browse button while adding books
        self.browse_button.setEnabled(False)


    def handle_book_added(self, book_data):
        """Handles the signal when a book is successfully added by the worker."""
        # book_data is a tuple: (id, name, pdf_path, read_status, star_rating, page_read, file_size, total_pages)
        self.add_book_row_to_table(book_data)
        # Re-sort the table after adding a new row
        current_sort_column = self.book_table.horizontalHeader().sortIndicatorSection()
        current_sort_order = self.book_table.horizontalHeader().sortIndicatorOrder()
        if current_sort_column != -1: # Only sort if a sort indicator is set
            self.book_table.sortItems(current_sort_column, current_sort_order)


    def handle_add_book_error(self, error_message):
        """Handles the signal when an error occurs during book adding."""
        QMessageBox.critical(self, "File Error", error_message)


    def handle_duplicate_found(self, book_name):
        """Handles the signal when a duplicate book is found during adding."""
        QMessageBox.warning(self, "Duplicate Book", f"The book '{book_name}' already exists and was not added.")

    def handle_add_book_finished(self):
        """Handles the signal when the add book worker thread finishes."""
        self.pdf_edit.clear() # Clear the file paths input field
        self.browse_button.setEnabled(True) # Re-enable browse button
        # A full refresh might still be needed if multiple books were added or other changes occurred
        # However, adding rows incrementally via handle_book_added is more efficient.
        # A small delay before a final refresh could be added if needed, but might not be necessary.
        # self.refresh_list() # Optional: uncomment for a final full refresh


    def add_book_row_to_table(self, book):
        """Adds a single book's data as a new row to the table."""
        self.ignore_cell_changes = True # Ignore cellChanged signals during this update
        self.book_table.setSortingEnabled(False) # Disable sorting during update

        row_position = self.book_table.rowCount()
        self.book_table.insertRow(row_position)

        book_id, name, pdf_path, read_status, star_rating, page_read, file_size, total_pages = book

        # Name item with extra book data (id, pdf_path)
        name_item = SortableItem(name, data={"id": book_id, "pdf_path": pdf_path})
        name_item.setFlags(name_item.flags() ^ Qt.ItemIsEditable) # Make name column non-editable
        self.book_table.setItem(row_position, 0, name_item)

        # Star rating item - Use SortableItem to store the integer value for sorting
        star_rating_item = SortableItem("", data=star_rating)
        star_rating_item.setData(Qt.EditRole, star_rating) # Store integer for delegate editing
        star_rating_item.setFlags(star_rating_item.flags() | Qt.ItemIsEditable) # Make editable for delegate
        self.book_table.setItem(row_position, 1, star_rating_item) # column 1

        # File size (bytes to MB) - Use SortableItem to store the raw size for sorting
        file_size_mb = file_size / (1024 * 1024) if file_size else 0
        file_size_item = SortableItem(f"{file_size_mb:.2f} MB", data=file_size)
        file_size_item.setFlags(file_size_item.flags() ^ Qt.ItemIsEditable) # Make non-editable
        self.book_table.setItem(row_position, 2, file_size_item) # column 2

        # Page Read column (editable to store current page progress) - Use SortableItem for sorting
        page_read = page_read if page_read is not None else 0
        page_read_item = SortableItem(str(page_read), data=page_read)
        page_read_item.setData(Qt.EditRole, page_read) # Store integer value for editing
        page_read_item.setFlags(page_read_item.flags() | Qt.ItemIsEditable)
        self.book_table.setItem(row_position, 3, page_read_item) # column 3

        # Total Pages column (read-only) - Use SortableItem for sorting
        total_pages = total_pages if total_pages is not None else 0
        total_pages_item = SortableItem(str(total_pages), data=total_pages)
        total_pages_item.setFlags(Qt.ItemIsEnabled) # Make it read-only
        self.book_table.setItem(row_position, 4, total_pages_item) # column 4

        # Progress Bar column (handled by delegate) - Use SortableItem to store percentage for sorting
        percentage = 0
        if total_pages > 0:
             percentage = min(100, max(0, int((page_read / total_pages) * 100)))

        # Progress item is always created, even if total_pages is 0
        progress_item = SortableItem("", data=percentage) # Use SortableItem
        progress_item.setData(Qt.UserRole, percentage) # Store percentage for delegate/sorting
        progress_item.setFlags(Qt.ItemIsEnabled) # Make it read-only
        self.book_table.setItem(row_position, 5, progress_item) # column 5

        self.book_table.setSortingEnabled(True) # Re-enable sorting
        self.ignore_cell_changes = False # Re-enable cellChanged signals


    def open_book(self):
        """Opens the selected book using the default system application."""
        sender = self.sender()
        book_id = None

        # Determine book_id based on sender (context menu action)
        if isinstance(sender, QAction):
             book_id = sender.data()

        if book_id is not None:
             book_data = get_books_by_id(book_id)
             if book_data:
                 pdf_path = book_data[2] # column 2 is pdf_path
             else:
                 QMessageBox.warning(self, "Error", "Book data not found in database.")
                 return

        if pdf_path and os.path.exists(pdf_path):
            try:
                # Launch the file using the default system application
                # Use QDesktopServices.openUrl which is generally preferred for opening files/urls
                success = QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))

                if success:
                     # Note: QDesktopServices.openUrl doesn't provide a process handle to track closure.
                     # The previous subprocess method allowed tracking for the page update prompt.
                     # If tracking is essential, the subprocess method with careful error handling
                     # and potentially a separate process for the subprocess call might be needed.
                     # For simplicity and potentially avoiding antivirus flags, QDesktopServices is used here.

                     # Prompt for page update immediately or rely on user manually editing the cell
                     # For now, relying on manual cell edit or a separate "Update Progress" action.
                     pass # No automatic page update prompt after opening with QDesktopServices

                else:
                    QMessageBox.critical(self, "Error Opening File", "Could not open file with default application.")

            except Exception as e:
                QMessageBox.critical(self, "Error Opening File", f"An unexpected error occurred: {e}")
        else:
            QMessageBox.warning(self, "Error", "Book file not found on disk.")

    def check_opened_books(self):
        """
        Periodically checks if launched PDF reader processes have finished.
        This method is primarily relevant if using subprocess.Popen for opening books
        and needing to prompt for page updates upon closure.
        With QDesktopServices.openUrl, this timer might not be needed unless
        you implement a different mechanism for tracking.
        Keeping the structure in case subprocess is re-introduced or for other uses.
        """
        finished_processes = []
        # Create a list of items to iterate over to avoid changing the dictionary while iterating
        for process, book_id in list(self.opened_books.items()):
            if process.poll() is not None: # poll() returns exit code if finished, None otherwise
                finished_processes.append((process, book_id))

        for process, book_id in finished_processes:
            # print(f"Process {process.pid} for book ID {book_id} finished.") # Removed logging
            del self.opened_books[process] # Remove from tracking

            # Prompt the user for the last read page
            book_data = get_books_by_id(book_id)
            if book_data:
                book_name = book_data[1] # column 1 is name
                current_page_read = book_data[5] # column 5 is page_read
                total_pages = book_data[7] # column 7 is total_pages

                title = f"Update Progress for '{book_name}'"
                label = f"Last page read (out of {total_pages}):"
                initial_value = current_page_read

                # Use getInt with min/max values for validation
                # Set max value to total_pages if > 0, otherwise a large number
                max_page = total_pages if total_pages > 0 else 999999
                page_read, ok = QInputDialog.getInt(self, title, label, initial_value, 0, max_page)

                if ok:
                    # Update the database and refresh the table row
                    update_book_in_db(book_id, page_read=page_read) # Use the updated update_book_in_db
                    self.update_book_row_in_table(book_id) # Update the specific row
                else:
                    # print("Page read update cancelled by user.") # Removed logging
                    pass # Do nothing if cancelled


    def update_book_row_in_table(self, book_id):
        """Finds the row for a given book_id and updates its items in the table."""
        for row in range(self.book_table.rowCount()):
            name_item = self.book_table.item(row, 0)
            book_data = name_item.data(Qt.UserRole)
            if book_data and book_data["id"] == book_id:
                # Fetch updated book data from the database
                updated_book_data = get_books_by_id(book_id)
                if updated_book_data:
                    book = updated_book_data
                    # book: (id, name, pdf_path, read_status, star_rating, page_read, file_size, total_pages)

                    # Update the relevant items in the row
                    book_id, name, pdf_path, read_status, star_rating, page_read, file_size, total_pages = book

                    # Page Read (column 3)
                    page_read = page_read if page_read is not None else 0
                    page_read_item = self.book_table.item(row, 3)
                    if isinstance(page_read_item, SortableItem):
                         page_read_item.setText(str(page_read))
                         page_read_item.setData(Qt.EditRole, page_read)
                         page_read_item.setData(Qt.UserRole, page_read) # Update data for sorting
                    else: # Fallback if item type is unexpected - replace the item
                         new_item = SortableItem(str(page_read), data=page_read)
                         new_item.setData(Qt.EditRole, page_read)
                         new_item.setFlags(new_item.flags() | Qt.ItemIsEditable)
                         self.book_table.setItem(row, 3, new_item)


                    # Star Rating (column 1) - Update data for delegate and sorting
                    star_rating = star_rating if star_rating is not None else 0
                    star_rating_item = self.book_table.item(row, 1)
                    if isinstance(star_rating_item, SortableItem):
                        star_rating_item.setData(Qt.EditRole, star_rating)
                        star_rating_item.setData(Qt.UserRole, star_rating) # Update data for sorting
                    else: # Fallback
                        new_item = SortableItem("", data=star_rating)
                        new_item.setData(Qt.EditRole, star_rating)
                        new_item.setFlags(new_item.flags() | Qt.ItemIsEditable)
                        self.book_table.setItem(row, 1, new_item)
                    # Trigger repaint for the star rating column
                    self.book_table.viewport().update(self.book_table.visualRect(self.book_table.model().index(row, 1)))


                    # Progress (column 5) - Trigger repaint and update data for sorting
                    progress_item = self.book_table.item(row, 5)
                    percentage = 0
                    if total_pages > 0:
                         percentage = min(100, max(0, int((page_read / total_pages) * 100)))
                    if isinstance(progress_item, SortableItem):
                         progress_item.setData(Qt.UserRole, percentage) # Update percentage for sorting
                    else: # Fallback
                         new_progress_item = SortableItem("", data=percentage)
                         new_progress_item.setData(Qt.UserRole, percentage)
                         new_progress_item.setFlags(Qt.ItemIsEnabled)
                         self.book_table.setItem(row, 5, new_progress_item)

                    # Get the model index for the progress cell
                    progress_index = self.book_table.model().index(row, 5)
                    # Emit dataChanged signal for the progress cell to trigger repaint
                    self.book_table.model().dataChanged.emit(progress_index, progress_index, [Qt.UserRole])


                break # Found the row, no need to continue searching


    def open_file_location(self):
        """Opens the containing folder of the selected book's file."""
        sender = self.sender()
        # This function is now only called from the context menu action
        # Get the book_id from the action's data
        book_id = sender.data()
        # Retrieve the pdf_path from the database using book_id
        book_data = get_books_by_id(book_id)
        if book_data:
            pdf_path = book_data[2] # book_data is a tuple, index 2 is pdf_path
        else:
            pdf_path = None

        if pdf_path and os.path.exists(pdf_path):
            # Use platform-specific methods to open the containing folder and select the file.
            # Note: Using subprocess for this on Windows is the most reliable way to
            # open the folder *and* select the file, but might be flagged by some antivirus.
            # QDesktopServices.openUrl is generally safer but might not select the file on all platforms.
            if sys.platform == "win32":
                try:
                    # Use explorer.exe /select, to open the folder and select the file
                    subprocess.Popen(f'explorer.exe /select,"{os.path.realpath(pdf_path)}"')
                except Exception as e:
                    QMessageBox.critical(self, "Error Opening Location", f"Could not open file location: {e}")
            elif sys.platform == "darwin":
                try:
                    # On macOS, 'open -R' reveals the file in Finder
                    subprocess.Popen(["open", "-R", pdf_path])
                except Exception as e:
                    QMessageBox.critical(self, "Error Opening Location", f"Could not open file location: {e}")
            elif sys.platform.startswith("linux"):
                try:
                    # On Linux, xdg-open opens the containing directory
                    subprocess.Popen(["xdg-open", os.path.dirname(pdf_path)])
                except Exception as e:
                    QMessageBox.critical(self, "Error Opening Location", f"Could not open file location: {e}")
        else:
            QMessageBox.warning(self, "Error", "Book file not found on disk.")


    def delete_book(self):
        """Deletes the selected book from the database and the file system."""
        sender = self.sender()
        # This function is now called from the context menu action or the Delete key event filter
        # Get the book_id from the action's data or the event filter
        if isinstance(sender, QAction):
            book_id = sender.data()
        elif isinstance(sender, int): # Assuming the event filter passes the book_id directly
             book_id = sender
        else:
             book_id = None # Should not happen with current logic

        if book_id is not None:
             # Add a confirmation dialog before deleting
             reply = QMessageBox.question(self, 'Confirm Delete', 'Are you sure you want to delete this book?',
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
             if reply == QMessageBox.Yes:
                # Get the file path before deleting from the database
                book_data = get_books_by_id(book_id)
                if book_data:
                    pdf_path = book_data[2] # Index 2 is pdf_path
                else:
                    pdf_path = None

                delete_book_from_db(book_id)
                # Remove the row from the table immediately for better responsiveness
                self.remove_book_row_from_table(book_id)

                # Attempt to delete the associated file
                if pdf_path and os.path.exists(pdf_path):
                    try:
                        os.remove(pdf_path)
                        # print(f"Deleted file: {pdf_path}") # Removed logging
                    except OSError as e:
                        print(f"Error deleting file {pdf_path}: {e}")
                        QMessageBox.warning(self, "File Deletion Error", f"Could not delete file:\n{pdf_path}\n{e}")


    def remove_book_row_from_table(self, book_id):
        """Removes a book's row from the table by book ID."""
        for row in range(self.book_table.rowCount()):
            name_item = self.book_table.item(row, 0)
            book_data = name_item.data(Qt.UserRole)
            if book_data and book_data["id"] == book_id:
                self.book_table.removeRow(row)
                break # Found and removed the row


    def eventFilter(self, source, event):
        """Filters events for the table widget, specifically for the Delete key."""
        # Support deletion of selected rows via the Delete key with confirmation.
        if event.type() == QEvent.KeyPress and source is self.book_table.viewport():
            if event.key() == Qt.Key_Delete:
                selected_rows = {item.row() for item in self.book_table.selectedItems()}
                if selected_rows:
                    # Add a single confirmation dialog for multiple deletions
                    reply = QMessageBox.question(self, 'Confirm Delete', f'Are you sure you want to delete {len(selected_rows)} selected book(s)?',
                                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        # Collect all book IDs and file paths to delete
                        books_to_delete = [] # List of (book_id, pdf_path)
                        rows_to_remove = sorted(list(selected_rows), reverse=True) # Remove from bottom up

                        for row in selected_rows:
                            name_item = self.book_table.item(row, 0)
                            book_data = name_item.data(Qt.UserRole)
                            if book_data:
                                book_id = book_data["id"]
                                # Fetch pdf_path before deleting from DB
                                book_info = get_books_by_id(book_id)
                                if book_info:
                                     books_to_delete.append((book_id, book_info[2])) # (book_id, pdf_path)


                        # Delete from database and file system, and remove rows from table
                        for book_id, pdf_path in books_to_delete:
                             delete_book_from_db(book_id)
                             # Attempt to delete the associated file
                             if pdf_path and os.path.exists(pdf_path):
                                 try:
                                     os.remove(pdf_path)
                                     # print(f"Deleted file: {pdf_path}") # Removed logging
                                 except OSError as e:
                                     print(f"Error deleting file {pdf_path}: {e}")
                                     QMessageBox.warning(self, "File Deletion Error", f"Could not delete file:\n{pdf_path}\n{e}")

                        # Remove rows from the table after database/file deletion
                        for row in rows_to_remove:
                            self.book_table.removeRow(row)

                    return True # Event handled
        return super().eventFilter(source, event)

    def cell_changed(self, row, column):
        """Handles changes to editable cells (e.g., Page Read, Star Rating)."""
        if self.ignore_cell_changes:
            # print(f"cell_changed ignored for row {row}, column {column}") # Removed logging
            return

        # print(f"cell_changed triggered for row {row}, column {column}") # Removed logging

        # --- Start of safeguard: Ignore changes to the Progress column ---
        if column == 5:
            # print(f"Ignoring direct change to Progress column (column 5) at row {row}.") # Removed logging
            return
        # --- End of safeguard ---

        name_item = self.book_table.item(row, 0)
        book_data = name_item.data(Qt.UserRole)
        if not book_data:
            # print(f"No book data found for row {row}") # Removed logging
            return # Should not happen if row has a valid name item

        book_id = book_data["id"]
        # print(f"Processing change for book ID: {book_id}") # Removed logging

        if column == 3: # Column 3 is Page Read
            item = self.book_table.item(row, column)
            try:
                page_read = int(item.text())
                # print(f"New page read value: {page_read}") # Removed logging
            except ValueError:
                page_read = 0 # Handle non-integer input
                item.setText(str(page_read)) # Reset cell text to 0 if invalid input
                item.setData(Qt.EditRole, page_read) # Update stored data
                item.setData(Qt.UserRole, page_read) # Update stored data for sorting
                # print(f"Invalid page read input, reset to: {page_read}") # Removed logging


            # Optional: Validate page_read against total_pages
            total_pages_item = self.book_table.item(row, 4) # Column 4 is Total Pages
            try:
                total_pages = int(total_pages_item.data(Qt.UserRole)) # Get total pages from stored data
                # print(f"Total pages for validation: {total_pages}") # Removed logging
                if total_pages > 0 and (page_read > total_pages or page_read < 0):
                     QMessageBox.warning(self, "Input Error", f"Invalid page number ({page_read}). Must be between 0 and {total_pages}.")
                     # Revert cell value to the last saved value from the database
                     current_book_data = get_books_by_id(book_id)
                     if current_book_data:
                         correct_page_read = current_book_data[5]
                         item.setText(str(correct_page_read))
                         item.setData(Qt.EditRole, correct_page_read)
                         item.setData(Qt.UserRole, correct_page_read)
                         # print(f"Invalid page number, reverted to: {correct_page_read}") # Removed logging
                     return # Do not update database

            except (ValueError, TypeError):
                # Handle cases where total_pages might not be a valid number
                # print("Could not get valid total pages for validation.") # Removed logging
                pass # Proceed with updating page_read without total_pages validation

            # Update the database
            update_book_in_db(book_id, page_read=page_read)
            # print(f"Database updated for book ID {book_id} with page read {page_read}") # Removed logging

            # --- Start of real-time progress bar update (replacing item) ---
            # Recalculate percentage based on potentially updated page_read and total_pages
            total_pages_for_progress = int(self.book_table.item(row, 4).data(Qt.UserRole)) if self.book_table.item(row, 4).data(Qt.UserRole) is not None else 0
            percentage = 0
            if total_pages_for_progress > 0:
                 percentage = min(100, max(0, int((page_read / total_pages_for_progress) * 100)))

            # print(f"Calculated percentage: {percentage}%") # Removed logging

            # Create a new ProgressItem with the updated percentage
            new_progress_item = SortableItem("", data=percentage)
            new_progress_item.setData(Qt.UserRole, percentage) # Store percentage for delegate/sorting
            new_progress_item.setFlags(Qt.ItemIsEnabled) # Make it read-only

            # Replace the old item with the new one
            self.book_table.setItem(row, 5, new_progress_item)
            # print(f"Replaced ProgressItem at row {row}, column 5 with new item containing percentage: {percentage}") # Removed logging

            # The setItem call should implicitly trigger a repaint, but we can keep the explicit
            # viewport update as a fallback, though it might be redundant now.
            progress_index = self.book_table.model().index(row, 5)
            self.book_table.viewport().update(self.book_table.visualRect(progress_index))
            # print(f"Requested viewport update for progress cell at row {row}, column 5 (after replacement)") # Removed logging
            # --- End of real-time progress bar update ---


        elif column == 1: # Column 1 is Star Rating
            star_rating_item = self.book_table.item(row, column)
            star_rating = star_rating_item.data(Qt.EditRole) # Get the integer value from EditRole
            # print(f"New star rating value: {star_rating}") # Removed logging

            # Read status is implicitly set based on star rating in StarDelegate now
            # We still need to update the DB with the star rating change
            # Fetch current read status from DB to avoid overwriting
            current_book_data = get_books_by_id(book_id)
            if current_book_data:
                read_status = current_book_data[3] # Get current read status from DB
            else:
                read_status = 0

            update_book_in_db(book_id, read_status=read_status, star_rating=star_rating)
            # print(f"Database updated for book ID {book_id} with star rating {star_rating}") # Removed logging

            # Update the SortableItem's data for sorting
            if isinstance(star_rating_item, SortableItem):
                 star_rating_item.setData(Qt.UserRole, star_rating)
                 # print(f"Updated StarRatingItem UserRole data to: {star_rating}") # Removed logging


    def show_context_menu(self, pos):
        """Displays the context menu for the table."""
        # Get the item at the clicked position
        item = self.book_table.itemAt(pos)
        if item:
            # Get the row of the clicked item
            row = item.row()
            # Get the book data (including id and pdf_path) from the Name column's UserRole
            name_item = self.book_table.item(row, 0)
            book_data = name_item.data(Qt.UserRole)

            if book_data:
                book_id = book_data["id"]

                menu = QMenu(self)

                # Add actions to the menu
                open_action = QAction("Open Book", self)
                open_action.triggered.connect(self.open_book)
                open_action.setData(book_id) # Store book_id in the action

                open_location_action = QAction("Open File Location", self)
                open_location_action.triggered.connect(self.open_file_location)
                open_location_action.setData(book_id) # Store book_id in the action

                # Add an "Update Progress" action for manual page update
                update_progress_action = QAction("Update Progress", self)
                update_progress_action.triggered.connect(self.prompt_update_progress)
                update_progress_action.setData(book_id) # Store book_id in the action


                # Placeholder for Edit Details action (functionality not implemented yet)
                edit_action = QAction("Edit Details (Coming Soon)", self)
                edit_action.setEnabled(False) # Disable for now

                delete_action = QAction("Delete Book", self)
                delete_action.triggered.connect(self.delete_book)
                delete_action.setData(book_id) # Store book_id in the action


                menu.addAction(open_action)
                menu.addAction(open_location_action)
                menu.addAction(update_progress_action) # Add the new action
                menu.addSeparator() # Add a separator line
                menu.addAction(edit_action)
                menu.addSeparator()
                menu.addAction(delete_action)

                # Show the context menu at the global position of the mouse cursor
                menu.exec_(self.book_table.viewport().mapToGlobal(pos))

    def prompt_update_progress(self):
        """Prompts the user to update the page read for a selected book."""
        sender = self.sender()
        book_id = sender.data()

        book_data = get_books_by_id(book_id)
        if book_data:
            book_name = book_data[1] # column 1 is name
            current_page_read = book_data[5] # column 5 is page_read
            total_pages = book_data[7] # column 7 is total_pages

            title = f"Update Progress for '{book_name}'"
            label = f"Last page read (out of {total_pages}):"
            initial_value = current_page_read

            max_page = total_pages if total_pages > 0 else 999999
            page_read, ok = QInputDialog.getInt(self, title, label, initial_value, 0, max_page)

            if ok:
                # Update the database and table row
                update_book_in_db(book_id, page_read=page_read) # Use the updated update_book_in_db
                self.update_book_row_in_table(book_id)
            else:
                # print("Page read update cancelled by user.") # Removed logging
                pass # Do nothing if cancelled


if __name__ == "__main__":
    # Ensure the upload directory exists on startup
    if not os.path.exists(UPLOAD_FOLDER):
        try:
            os.makedirs(UPLOAD_FOLDER)
        except OSError as e:
            print(f"Error creating upload directory on startup: {e}")
            # Decide how to handle this error - maybe show a critical message and exit
            sys.exit(1) # Exit if cannot create necessary directory

    app = QApplication(sys.argv)
    window = LibraryApp()
    window.show()
    sys.exit(app.exec_())
