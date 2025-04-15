import sys
import json
import os
import uuid
import wave
import pyaudio
import threading
import tempfile
import whisper
import subprocess
import zipfile
import shutil
from pathlib import Path
from datetime import datetime
from google import genai
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTextEdit, 
                           QVBoxLayout, QWidget,
                           QFileDialog, QMessageBox, QListWidget,
                           QHBoxLayout, QPushButton,
                           QLineEdit, QLabel, QFrame, QToolBar,
                           QListWidgetItem, QProgressDialog,
                           QFontComboBox, QSpinBox, QColorDialog,
                           QDialog)
from PyQt6.QtGui import (QAction, QFont, QTextCharFormat, 
                        QColor, QTextCursor, QTextListFormat)
from PyQt6.QtCore import Qt, QSettings, QSize, pyqtSignal, QThread
import dotenv
from secure_storage import SecureStorage

dotenv.load_dotenv()

class Summarizer:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)

    def summarize(self, text):
        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[f"""
                Summarize the following text:
                {text}
                Return the summary in a concise manner and make bullet points. if possible, add emojis to make it more engaging.
            """]
        )
        return response.text

class Constants:
    """Application constants"""
    APP_NAME = "EZ Notes"
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 700
    SIDEBAR_WIDTH = 280
    DEFAULT_FONT = "Segoe UI"
    DEFAULT_FONT_SIZE = 11
    CODE_FONT = "Consolas"
    CODE_BACKGROUND = "#f8f9fa"
    CODE_FOREGROUND = "#212529"
    NOTE_TITLE_FONT_SIZE = 24
    SEARCH_PLACEHOLDER = "Search notes..."

class FFmpegDownloader(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool)
    
    def run(self):
        try:
            self.progress.emit("Creating FFmpeg directory...")
            app_dir = get_app_directory()
            ffmpeg_dir = os.path.join(app_dir, 'ffmpeg')
            os.makedirs(ffmpeg_dir, exist_ok=True)
            
            self.progress.emit("Downloading FFmpeg...")
            # URL for the latest FFmpeg build
            url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
            zip_path = os.path.join(ffmpeg_dir, "ffmpeg.zip")
            
            # Download with progress tracking
            urllib.request.urlretrieve(url, zip_path)
            
            self.progress.emit("Extracting FFmpeg...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(ffmpeg_dir)
            
            # Move binaries to the correct location
            extracted_dir = next(Path(ffmpeg_dir).glob('ffmpeg-*'))
            bin_dir = os.path.join(extracted_dir, 'bin')
            for file in os.listdir(bin_dir):
                shutil.move(
                    os.path.join(bin_dir, file),
                    os.path.join(ffmpeg_dir, file)
                )
            
            # Clean up
            os.remove(zip_path)
            shutil.rmtree(extracted_dir)
            
            self.progress.emit("FFmpeg installation complete!")
            self.finished.emit(True)
            
        except Exception as e:
            self.progress.emit(f"Error: {str(e)}")
            self.finished.emit(False)

def get_app_directory():
    """Get or create application directory for storing FFmpeg"""
    app_dir = os.path.join(os.path.expanduser('~'), '.modernotepad')
    os.makedirs(app_dir, exist_ok=True)
    return app_dir

def get_ffmpeg_path():
    """Get the path to the FFmpeg executable"""
    app_dir = get_app_directory()
    ffmpeg_dir = os.path.join(app_dir, 'ffmpeg')
    if sys.platform == 'win32':
        ffmpeg_path = os.path.join(ffmpeg_dir, 'ffmpeg.exe')
    else:
        ffmpeg_path = os.path.join(ffmpeg_dir, 'ffmpeg')
    return ffmpeg_path

def check_ffmpeg():
    """Check if FFmpeg is available in the application directory"""
    ffmpeg_path = get_ffmpeg_path()
    if os.path.exists(ffmpeg_path):
        try:
            subprocess.run([ffmpeg_path, '-version'], capture_output=True, check=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    return False

class TranscriptionWorker(QThread):
    """Handles audio transcription in a separate thread"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, audio_file):
        super().__init__()
        self.audio_file = audio_file
        
    def run(self):
        """Run transcription process"""
        try:
            if not check_ffmpeg():
                self.error.emit("FFmpeg is not properly installed.")
                return
                
            os.environ["PATH"] = f"{os.path.dirname(get_ffmpeg_path())}{os.pathsep}{os.environ['PATH']}"
            
            processed_audio = self._preprocess_audio()
            if not processed_audio:
                self.error.emit("Failed to preprocess audio.")
                return
            
            model = whisper.load_model("base")
            result = model.transcribe(
                processed_audio,
                language="en",
                task="transcribe",
                fp16=False,
                temperature=0.0,
                best_of=5,
                beam_size=5,
                patience=1.0,
                length_penalty=1.0,
                suppress_tokens=[-1],
                initial_prompt="Transcribe the following audio accurately."
            )
            
            self.finished.emit(result["text"])
            self._cleanup_files(processed_audio)
                
        except Exception as e:
            self.error.emit(f"Transcription error: {str(e)}")
            
    def _preprocess_audio(self):
        """Preprocess audio file for better transcription quality"""
        try:
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            processed_audio = temp_file.name
            temp_file.close()
            
            ffmpeg_cmd = [
                get_ffmpeg_path(),
                '-i', self.audio_file,
                '-ac', '1',
                '-ar', '16000',
                '-af', 'highpass=f=200,lowpass=f=3000,volume=2.0',
                '-y',
                processed_audio
            ]
            
            subprocess.run(ffmpeg_cmd, capture_output=True, check=True)
            return processed_audio
            
        except Exception as e:
            print(f"Audio preprocessing error: {e}")
            return None

    def _cleanup_files(self, processed_audio):
        """Clean up temporary audio files"""
        try:
            if os.path.exists(processed_audio):
                os.remove(processed_audio)
            if os.path.exists(self.audio_file):
                os.remove(self.audio_file)
        except:
            pass

class AudioRecorder:
    """Handles audio recording functionality"""
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.frames = []
        self.is_recording = False
        self.record_thread = None

    def start_recording(self):
        """Start audio recording"""
        self.frames = []
        self.is_recording = True
        
        def record():
            try:
                self.stream = self.audio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=44100,
                    input=True,
                    frames_per_buffer=1024
                )
                
                while self.is_recording:
                    try:
                        data = self.stream.read(1024, exception_on_overflow=False)
                        self.frames.append(data)
                    except Exception as e:
                        print(f"Recording error: {e}")
                        break
            except Exception as e:
                print(f"Stream error: {e}")
        
        self.record_thread = threading.Thread(target=record)
        self.record_thread.start()

    def stop_recording(self):
        """Stop audio recording and save to file"""
        self.is_recording = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
        self.record_thread.join()
        
        temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        try:
            with wave.open(temp_file.name, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
                wf.setframerate(44100)
                wf.writeframes(b''.join(self.frames))
        except Exception as e:
            print(f"Error saving audio: {e}")
            return None
            
        return temp_file.name

class NoteItem(QListWidgetItem):
    """Custom list item for notes"""
    def __init__(self, title, note_id):
        super().__init__(title)
        self.note_id = note_id

class ModernNotepad(QMainWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        self.secure_storage = SecureStorage()
        self._initialize_ui()
        self._setup_audio_recording()
        self._load_notes()
        
        # Initialize secure storage with a default password first time
        if not os.path.exists(self.secure_storage.storage_path):
            try:
                # Create initial storage with default password
                self.secure_storage.initialize("default_password")
                
                # If there's an API key in .env, migrate it to secure storage
                if os.path.exists(".env"):
                    try:
                        with open(".env", "r") as f:
                            for line in f:
                                if line.startswith("GEMINI_API_KEY="):
                                    api_key = line.split("=")[1].strip()
                                    self.secure_storage.set_value("gemini_api_key", api_key)
                                    # Delete the .env file after migration
                                    os.remove(".env")
                                    break
                    except:
                        pass
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Storage Initialization Error",
                    f"Failed to initialize secure storage: {str(e)}"
                )
        else:
            # If storage exists, initialize with default password
            try:
                self.secure_storage.initialize("default_password")
            except:
                QMessageBox.warning(
                    self,
                    "Storage Access Error",
                    "Failed to access secure storage. Please check your settings."
                )
        
        # Initialize AI client
        try:
            api_key = self.secure_storage.get_value("gemini_api_key")
            if api_key:
                self.gen_ai = Summarizer(api_key)
            else:
                self.gen_ai = None
                # Show settings dialog if no API key is found
                self.show_settings()
        except Exception as e:
            QMessageBox.warning(
                self,
                "AI Initialization Error",
                f"Failed to initialize AI client: {str(e)}\nPlease check your API key in settings."
            )
            self.gen_ai = None
            self.show_settings()
        
    def _initialize_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle(Constants.APP_NAME)
        self.setGeometry(100, 100, Constants.WINDOW_WIDTH, Constants.WINDOW_HEIGHT)
        self._setup_styles()
        self._create_toolbars()
        self._create_layout()
        self._initialize_note_data()
        
    def _setup_styles(self):
        """Setup application styles"""
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: #f8f9fa;
            }}
            QToolBar {{
                background-color: #ffffff;
                border: none;
                border-bottom: 1px solid #e9ecef;
                padding: 8px;
            }}
            QToolButton {{
                background-color: transparent;
                border: none;
                padding: 6px;
                border-radius: 4px;
            }}
            QToolButton:hover {{
                background-color: #f1f3f5;
            }}
            QToolButton:pressed {{
                background-color: #e9ecef;
            }}
            QLineEdit {{
                border: none;
                background-color: transparent;
                padding: 8px;
                font-size: 16px;
                color: #212529;
            }}
            QLineEdit:focus {{
                background-color: #f1f3f5;
                border-radius: 4px;
            }}
            QTextEdit {{
                border: none;
                background-color: transparent;
                padding: 16px;
                font-size: 14px;
                color: #212529;
                line-height: 1.6;
            }}
            QListWidget {{
                border: none;
                background-color: transparent;
                padding: 8px;
            }}
            QListWidget::item {{
                padding: 8px 12px;
                border-radius: 4px;
                margin: 2px 0;
            }}
            QListWidget::item:selected {{
                background-color: #e9ecef;
                color: #212529;
            }}
            QListWidget::item:hover {{
                background-color: #f1f3f5;
            }}
            QFontComboBox, QSpinBox {{
                border: 1px solid #e9ecef;
                border-radius: 4px;
                padding: 4px;
                background-color: white;
            }}
            QFontComboBox:hover, QSpinBox:hover {{
                border-color: #ced4da;
            }}
            QFontComboBox:focus, QSpinBox:focus {{
                border-color: #339af0;
            }}
            QFrame#separator {{
                background-color: #e9ecef;
                max-width: 1px;
            }}
        """)

    def _create_toolbars(self):
        """Create application toolbars"""
        self._create_main_toolbar()
        self._create_format_toolbar()

    def _create_main_toolbar(self):
        """Create the main toolbar"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(toolbar)
        
        self._add_toolbar_action(toolbar, "＋", self.add_new_tab, 14)
        self.record_action = self._add_toolbar_action(toolbar, "🎤", self.toggle_recording, 14)
        self._add_toolbar_action(toolbar, "📁", self.upload_audio, 14)
        self._add_toolbar_action(toolbar, "🗑️", self.delete_current_note, 14)
        self._add_toolbar_action(toolbar, "⚙️", self.show_settings, 14)

    def _create_format_toolbar(self):
        """Create the formatting toolbar"""
        format_toolbar = QToolBar()
        format_toolbar.setMovable(False)
        format_toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(format_toolbar)
        
        self._add_font_controls(format_toolbar)
        format_toolbar.addSeparator()
        self._add_format_buttons(format_toolbar)

    def _add_toolbar_action(self, toolbar, text, callback, font_size=10):
        """Add an action to a toolbar"""
        action = QAction(text, self)
        action.setFont(QFont(Constants.DEFAULT_FONT, font_size))
        action.triggered.connect(callback)
        toolbar.addAction(action)
        return action

    def _add_font_controls(self, toolbar):
        """Add font controls to the formatting toolbar"""
        self.font_combo = QFontComboBox()
        self.font_combo.setFont(QFont(Constants.DEFAULT_FONT, 10))
        self.font_combo.currentFontChanged.connect(self.font_changed)
        toolbar.addWidget(self.font_combo)
        
        self.font_size = QSpinBox()
        self.font_size.setFont(QFont(Constants.DEFAULT_FONT, 10))
        self.font_size.setValue(Constants.DEFAULT_FONT_SIZE)
        self.font_size.setRange(8, 72)
        self.font_size.valueChanged.connect(self.font_size_changed)
        toolbar.addWidget(self.font_size)

    def _add_format_buttons(self, toolbar):
        """Add formatting buttons to the toolbar"""
        self._add_format_button(toolbar, "B", self.toggle_bold, True, QFont.Weight.Bold)
        self._add_format_button(toolbar, "I", self.toggle_italic, True, italic=True)
        self._add_format_button(toolbar, "U", self.toggle_underline, True, underline=True)
        toolbar.addSeparator()
        self._add_toolbar_action(toolbar, "🎨", self.change_text_color, 14)
        self._add_toolbar_action(toolbar, "•", self.toggle_bullet_list, 14)
        self._add_toolbar_action(toolbar, "1.", self.toggle_numbered_list, 10)
        self._add_toolbar_action(toolbar, "</>", self.toggle_code_block, 10)

    def _add_format_button(self, toolbar, text, callback, checkable=False, weight=None, italic=False, underline=False):
        """Add a formatting button to the toolbar"""
        action = QAction(text, self)
        font = QFont(Constants.DEFAULT_FONT, 10)
        if weight:
            font.setWeight(weight)
        if italic:
            font.setItalic(True)
        if underline:
            font.setUnderline(True)
        action.setFont(font)
        action.setCheckable(checkable)
        action.triggered.connect(callback)
        toolbar.addAction(action)
        return action

    def _create_layout(self):
        """Create the main layout"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self._create_sidebar(main_layout)
        self._create_content_area(main_layout)

    def _create_sidebar(self, main_layout):
        """Create the sidebar"""
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(Constants.SIDEBAR_WIDTH)
        self.sidebar.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border-right: 1px solid #e9ecef;
            }
        """)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(16)
        
        self._create_search_bar(sidebar_layout)
        self._create_notes_list(sidebar_layout)
        
        main_layout.addWidget(self.sidebar)
        self._add_separator(main_layout)

    def _create_search_bar(self, layout):
        """Create the search bar"""
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText(Constants.SEARCH_PLACEHOLDER)
        self.search_bar.setStyleSheet("""
            QLineEdit {
                background-color: #f1f3f5;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
            }
        """)
        self.search_bar.textChanged.connect(self.filter_notes)
        layout.addWidget(self.search_bar)

    def _create_notes_list(self, layout):
        """Create the notes list"""
        self.tabs_list = QListWidget()
        self.tabs_list.setFont(QFont(Constants.DEFAULT_FONT, 12))
        self.tabs_list.currentItemChanged.connect(self.switch_tab)
        layout.addWidget(self.tabs_list)

    def _add_separator(self, layout):
        """Add a vertical separator"""
        separator = QFrame()
        separator.setObjectName("separator")
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

    def _create_content_area(self, main_layout):
        """Create the content area"""
        self.content_area = QWidget()
        self.content_area.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
            }
        """)
        content_layout = QHBoxLayout(self.content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Create left (editable) area
        self._create_editable_area(content_layout)
        
        # Add vertical separator
        separator = QFrame()
        separator.setObjectName("separator")
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        content_layout.addWidget(separator)
        
        # Create right (preview) area
        self._create_preview_area(content_layout)
        
        main_layout.addWidget(self.content_area)

    def _create_editable_area(self, layout):
        """Create the editable content area"""
        editable_widget = QWidget()
        editable_layout = QVBoxLayout(editable_widget)
        editable_layout.setContentsMargins(32, 32, 16, 32)
        editable_layout.setSpacing(16)
        
        self._create_note_title(editable_layout)
        self._create_text_editor(editable_layout)
        
        layout.addWidget(editable_widget)

    def _create_preview_area(self, layout):
        """Create the AI summary area"""
        summary_widget = QWidget()
        summary_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
            }
        """)
        summary_layout = QVBoxLayout(summary_widget)
        summary_layout.setContentsMargins(16, 32, 32, 32)
        summary_layout.setSpacing(16)
        
        # Add summary title and button
        title_layout = QHBoxLayout()
        summary_title = QLabel("AI Summary")
        summary_title.setFont(QFont(Constants.DEFAULT_FONT, 16))
        summary_title.setStyleSheet("""
            QLabel {
                color: #495057;
                font-weight: bold;
            }
        """)
        title_layout.addWidget(summary_title)
        
        # Add summary button
        self.summary_button = QPushButton("Summarize")
        self.summary_button.setFont(QFont(Constants.DEFAULT_FONT, 10))
        self.summary_button.setStyleSheet("""
            QPushButton {
                background-color: #339af0;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #228be6;
            }
            QPushButton:pressed {
                background-color: #1c7ed6;
            }
        """)
        self.summary_button.clicked.connect(self.generate_summary)
        title_layout.addWidget(self.summary_button)
        
        summary_layout.addLayout(title_layout)
        
        # Add summary text area
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setFont(QFont(Constants.DEFAULT_FONT, Constants.DEFAULT_FONT_SIZE))
        self.summary_text.setStyleSheet("""
            QTextEdit {
                border: none;
                background-color: transparent;
                padding: 16px;
                font-size: 14px;
                color: #212529;
                line-height: 1.6;
            }
        """)
        summary_layout.addWidget(self.summary_text)
        
        layout.addWidget(summary_widget)

    def generate_summary(self):
        """Generate AI summary of the current note"""
        if not self.current_note_id:
            return
            
        content = self.tabs_data[self.current_note_id]['content']
        if not content.strip():
            self.summary_text.setPlainText("No content to summarize.")
            return
            
        # Show loading message with spinner
        self.summary_text.setPlainText("🔄 Generating summary...")
        self.summary_button.setEnabled(False)
        
        # Check if we already have a summary for this note
        if self.current_note_id in self.summaries:
            self.summary_text.setPlainText(self.summaries[self.current_note_id])
            self.summary_button.setEnabled(True)
            return
            
        try:
            # Generate new summary
            summary = self.gen_ai.summarize(content)
            self.summaries[self.current_note_id] = summary
            self.summary_text.setPlainText(summary)
        except Exception as e:
            self.summary_text.setPlainText(f"❌ Error generating summary: {str(e)}")
        finally:
            self.summary_button.setEnabled(True)
            self.save_tabs()  # Save the new summary

    def switch_tab(self, current, previous):
        """Handle tab switching and update summary"""
        self._is_switching_tab = True
        try:
            if current and isinstance(current, NoteItem):
                note_id = current.note_id
                if note_id in self.tabs_data:
                    self.current_note_id = note_id
                    self.note_title.setText(self.tabs_data[note_id]['title'])
                    self.text_edit.setText(self.tabs_data[note_id]['content'])
                    
                    # Load or prompt for summary
                    if note_id in self.summaries:
                        self.summary_text.setPlainText(self.summaries[note_id])
                    else:
                        self.summary_text.setPlainText("Click 'Summarize' to generate a summary of this note.")
        finally:
            self._is_switching_tab = False

    def _create_note_title(self, layout):
        """Create the note title editor"""
        self.note_title = QLineEdit()
        self.note_title.setFont(QFont(Constants.DEFAULT_FONT, Constants.NOTE_TITLE_FONT_SIZE))
        self.note_title.setPlaceholderText("Untitled Note")
        self.note_title.editingFinished.connect(self.on_title_edited)
        layout.addWidget(self.note_title)

    def _create_text_editor(self, layout):
        """Create the text editor"""
        self.text_edit = QTextEdit()
        self.text_edit.setFont(QFont(Constants.DEFAULT_FONT, Constants.DEFAULT_FONT_SIZE))
        self.text_edit.textChanged.connect(self.on_text_changed)
        self.text_edit.cursorPositionChanged.connect(self.update_format_buttons)
        layout.addWidget(self.text_edit)

    def _setup_audio_recording(self):
        """Setup audio recording functionality"""
        self.audio_recorder = AudioRecorder()
        self.is_recording = False

    def _initialize_note_data(self):
        """Initialize note data"""
        self.untitled_counter = 1
        self._is_switching_tab = False
        self.tabs_data = {}
        self.current_note_id = None
        self.summaries = {}  # Store summaries per note

    def _load_notes(self):
        """Load saved notes"""
        self.load_tabs()
        if self.tabs_list.count() == 0:
            self.add_new_tab()

    def filter_notes(self, text):
        search_text = text.lower()
        for i in range(self.tabs_list.count()):
            item = self.tabs_list.item(i)
            if isinstance(item, NoteItem):
                note_data = self.tabs_data[item.note_id]
                title_match = search_text in note_data['title'].lower()
                content_match = search_text in note_data['content'].lower()
                
                # Show item if either title or content matches
                item.setHidden(not (title_match or content_match))
                
                # If content matches but title doesn't, show preview
                if content_match and not title_match:
                    content = note_data['content'].lower()
                    # Find the position of the search text in content
                    pos = content.find(search_text)
                    # Get surrounding context (up to 30 chars before and after)
                    start = max(0, pos - 30)
                    end = min(len(content), pos + len(search_text) + 30)
                    
                    # Get the preview text
                    if start > 0:
                        preview = "..." + note_data['content'][start:end].strip()
                    else:
                        preview = note_data['content'][start:end].strip()
                    if end < len(content):
                        preview += "..."
                    
                    # Show title with preview
                    item.setText(f"{note_data['title']}\n{preview}")
                else:
                    # Reset to just showing the title
                    item.setText(note_data['title'])

    def add_new_tab(self):
        # Create new note with UUID
        note_id = str(uuid.uuid4())
        name = f"Untitled Note {self.untitled_counter}"
        self.untitled_counter += 1
        
        # Create new list item with UUID
        item = NoteItem(name, note_id)
        self.tabs_list.addItem(item)
        
        # Store note data
        self.tabs_data[note_id] = {
            'title': name,
            'content': '',
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'tags': []
        }
        
        self.tabs_list.setCurrentItem(item)
        self.save_tabs()

    def on_title_edited(self):
        if self.current_note_id and not self._is_switching_tab:
            new_title = self.note_title.text().strip()
            if new_title:
                # Update the title in both the list and data
                current_item = self.tabs_list.currentItem()
                if current_item and isinstance(current_item, NoteItem):
                    current_item.setText(new_title)
                    self.tabs_data[current_item.note_id]['title'] = new_title
                    self.save_tabs()
            else:
                # If title was cleared, restore the original title
                self.note_title.setText(self.tabs_data[self.current_note_id]['title'])

    def on_text_changed(self):
        """Update preview when text changes"""
        if self.current_note_id and not self._is_switching_tab:
            content = self.text_edit.toPlainText()
            self.tabs_data[self.current_note_id]['content'] = content
            
            # Update preview
            self.summary_text.setPlainText(content)
            
            # Update note title if it's the first line and untitled
            if content and self.tabs_data[self.current_note_id]['title'].startswith("Untitled Note"):
                first_line = content.split('\n')[0].strip()
                if first_line:
                    new_title = (first_line[:30] + '...') if len(first_line) > 30 else first_line
                    current_item = self.tabs_list.currentItem()
                    if current_item and isinstance(current_item, NoteItem):
                        current_item.setText(new_title)
                        self.note_title.setText(new_title)
                        self.tabs_data[current_item.note_id]['title'] = new_title
                        self.save_tabs()

    def save_all_tabs(self):
        if self.current_note_id and self.current_note_id in self.tabs_data:
            self.tabs_data[self.current_note_id]['content'] = self.text_edit.toPlainText()
        self.save_tabs()

    def save_tabs(self):
        """Save all notes and their summaries"""
        settings = QSettings("ModernNotepad", "Tabs")
        settings.setValue("tabs", json.dumps(self.tabs_data))
        settings.setValue("untitled_counter", self.untitled_counter)
        settings.setValue("summaries", json.dumps(self.summaries))

    def load_tabs(self):
        """Load saved notes and their summaries"""
        settings = QSettings("ModernNotepad", "Tabs")
        saved_tabs = settings.value("tabs", "{}")
        self.untitled_counter = settings.value("untitled_counter", 1)
        saved_summaries = settings.value("summaries", "{}")
        
        try:
            self.tabs_data = json.loads(saved_tabs)
            self.summaries = json.loads(saved_summaries)
            for note_id, note_data in self.tabs_data.items():
                item = NoteItem(note_data['title'], note_id)
                self.tabs_list.addItem(item)
        except:
            self.tabs_data = {}
            self.summaries = {}

    def closeEvent(self, event):
        self.save_all_tabs()
        event.accept()

    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        self.is_recording = True
        self.record_action.setText("⏺")
        self.audio_recorder.start_recording()
        
        # Show recording indicator
        QMessageBox.information(self, "Recording", "Recording started. Click the record button again to stop.")

    def stop_recording(self):
        self.is_recording = False
        self.record_action.setText("🎤")
        
        # Stop recording and get the file
        audio_file = self.audio_recorder.stop_recording()
        if not audio_file:
            QMessageBox.critical(self, "Error", "Failed to save audio recording.")
            return
            
        # Show transcription progress
        progress = QProgressDialog("Transcribing audio...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        # Start transcription in a separate thread
        self.transcription_worker = TranscriptionWorker(audio_file)
        self.transcription_worker.finished.connect(lambda text: self.handle_transcription(text, progress))
        self.transcription_worker.error.connect(lambda error: self.handle_transcription_error(error, progress))
        self.transcription_worker.start()

    def handle_transcription(self, text, progress):
        progress.close()
        
        # Create new note with transcribed text
        note_id = str(uuid.uuid4())
        name = "Transcribed Note"
        
        # Create new list item with UUID
        item = NoteItem(name, note_id)
        self.tabs_list.addItem(item)
        
        # Store note data
        self.tabs_data[note_id] = {
            'title': name,
            'content': text,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'tags': ['transcription']
        }
        
        self.tabs_list.setCurrentItem(item)
        self.save_tabs()

    def handle_transcription_error(self, error, progress):
        progress.close()
        QMessageBox.critical(self, "Transcription Error", error)

    def upload_audio(self):
        if not check_ffmpeg():
            QMessageBox.warning(self, "FFmpeg Missing", 
                              "FFmpeg is required for audio transcription.\n"
                              "Please install FFmpeg and try again.")
            return
            
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Upload Audio File",
            "",
            "Audio Files (*.mp3 *.wav *.m4a *.ogg);;All Files (*)"
        )
        
        if file_name:
            # Show transcription progress
            progress = QProgressDialog("Transcribing audio...", None, 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            
            # Start transcription in a separate thread
            self.transcription_worker = TranscriptionWorker(file_name)
            self.transcription_worker.finished.connect(lambda text: self.handle_transcription(text, progress))
            self.transcription_worker.error.connect(lambda error: self.handle_transcription_error(error, progress))
            self.transcription_worker.start()

    def install_ffmpeg(self):
        """Download and install FFmpeg"""
        reply = QMessageBox.question(
            self, 
            "FFmpeg Required",
            "FFmpeg is required for audio transcription and will be downloaded automatically. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            progress = QProgressDialog("Installing FFmpeg...", None, 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            
            self.ffmpeg_downloader = FFmpegDownloader()
            self.ffmpeg_downloader.progress.connect(progress.setLabelText)
            self.ffmpeg_downloader.finished.connect(
                lambda success: self.handle_ffmpeg_installation(success, progress)
            )
            
            progress.show()
            self.ffmpeg_downloader.start()

    def handle_ffmpeg_installation(self, success, progress):
        progress.close()
        if success:
            QMessageBox.information(self, "Success", "FFmpeg has been installed successfully!")
        else:
            QMessageBox.critical(self, "Error", "Failed to install FFmpeg. Audio features will not be available.")

    def font_changed(self, font):
        """Change the font of selected text"""
        self.text_edit.setFontFamily(font.family())

    def font_size_changed(self, size):
        """Change the font size of selected text"""
        self.text_edit.setFontPointSize(size)

    def toggle_bold(self, checked):
        """Toggle bold formatting"""
        if checked:
            self.text_edit.setFontWeight(QFont.Weight.Bold)
        else:
            self.text_edit.setFontWeight(QFont.Weight.Normal)

    def toggle_italic(self, checked):
        """Toggle italic formatting"""
        self.text_edit.setFontItalic(checked)

    def toggle_underline(self, checked):
        """Toggle underline formatting"""
        self.text_edit.setFontUnderline(checked)

    def change_text_color(self):
        """Open color picker and change text color"""
        color = QColorDialog.getColor()
        if color.isValid():
            self.text_edit.setTextColor(color)

    def toggle_bullet_list(self):
        """Toggle bullet list"""
        cursor = self.text_edit.textCursor()
        list_format = QTextListFormat()
        
        if cursor.currentList():
            cursor.beginEditBlock()
            cursor.createList(QTextListFormat())  # Remove list
            cursor.endEditBlock()
        else:
            list_format.setStyle(QTextListFormat.Style.ListDisc)
            cursor.beginEditBlock()
            cursor.createList(list_format)
            cursor.endEditBlock()

    def toggle_numbered_list(self):
        """Toggle numbered list"""
        cursor = self.text_edit.textCursor()
        list_format = QTextListFormat()
        
        if cursor.currentList():
            cursor.beginEditBlock()
            cursor.createList(QTextListFormat())  # Remove list
            cursor.endEditBlock()
        else:
            list_format.setStyle(QTextListFormat.Style.ListDecimal)
            cursor.beginEditBlock()
            cursor.createList(list_format)
            cursor.endEditBlock()

    def update_format_buttons(self):
        """Update formatting buttons based on current text format"""
        cursor = self.text_edit.textCursor()
        format = cursor.charFormat()
        
        # Update font combo box
        font = format.font()
        self.font_combo.setCurrentFont(font)
        self.font_size.setValue(int(font.pointSize()))
        
        # Update formatting buttons
        for action in self.findChildren(QAction):
            if action.text() == "B":
                action.setChecked(font.weight() == QFont.Weight.Bold)
            elif action.text() == "I":
                action.setChecked(font.italic())
            elif action.text() == "U":
                action.setChecked(font.underline())

    def toggle_code_block(self):
        """Toggle code block formatting"""
        cursor = self.text_edit.textCursor()
        format = QTextCharFormat()
        format.setFontFamily(Constants.CODE_FONT)
        format.setFontPointSize(Constants.DEFAULT_FONT_SIZE)
        format.setBackground(QColor(Constants.CODE_BACKGROUND))
        format.setForeground(QColor(Constants.CODE_FOREGROUND))
        
        # Get the current block
        block = cursor.block()
        current_text = block.text()
        
        # Check if we're already in a code block
        is_code_block = current_text.startswith("```") and current_text.endswith("```")
        
        if is_code_block:
            # Remove code block markers and formatting
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            text = cursor.selectedText()
            text = text[3:-3]  # Remove ``` markers
            cursor.removeSelectedText()
            cursor.insertText(text)
            
            # Reset formatting
            format = QTextCharFormat()
            format.setFontFamily(Constants.DEFAULT_FONT)
            format.setFontPointSize(Constants.DEFAULT_FONT_SIZE)
            cursor.mergeCharFormat(format)
        else:
            # Add code block markers and formatting
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            text = cursor.selectedText()
            cursor.removeSelectedText()
            cursor.insertText(f"```{text}```")
            
            # Apply code block formatting
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(format)
            
            # Move cursor to the end of the block
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
            cursor.insertText("\n")
            self.text_edit.setTextCursor(cursor)

    def delete_current_note(self):
        """Delete the current note with confirmation"""
        if not self.current_note_id:
            return
            
        current_item = self.tabs_list.currentItem()
        if not current_item:
            return
            
        # Get note title for confirmation message
        note_title = self.tabs_data[self.current_note_id]['title']
        
        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Delete Note",
            f"Are you sure you want to delete '{note_title}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Remove from data and summaries
            del self.tabs_data[self.current_note_id]
            if self.current_note_id in self.summaries:
                del self.summaries[self.current_note_id]
            
            # Remove from list
            row = self.tabs_list.row(current_item)
            self.tabs_list.takeItem(row)
            
            # Clear current note
            self.current_note_id = None
            self.note_title.clear()
            self.text_edit.clear()
            self.summary_text.clear()
            
            # Save changes
            self.save_tabs()
            
            # If no notes left, create a new one
            if self.tabs_list.count() == 0:
                self.add_new_tab()

    def show_settings(self, require_password=False):
        """Show settings dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setFixedSize(400, 220)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel {
                color: #1a1a1a;
                font-size: 13px;
            }
            QLabel[heading="true"] {
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 20px;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 13px;
                background-color: #ffffff;
                selection-background-color: #0078d4;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-size: 13px;
                min-height: 35px;
                margin-top: 20px;
            }
            QPushButton:hover {
                background-color: #006cbd;
            }
            QPushButton:pressed {
                background-color: #005ba1;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Settings")
        title.setProperty("heading", True)
        layout.addWidget(title)
        
        # API Key Section
        api_label = QLabel("Gemini API Key")
        layout.addWidget(api_label)
        
        api_key_input = QLineEdit()
        api_key_input.setPlaceholderText("Enter your Gemini API key")
        api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        try:
            current_key = self.secure_storage.get_value("gemini_api_key", "")
            if current_key:
                api_key_input.setText(current_key)
        except:
            pass
                
        layout.addWidget(api_key_input)
        
        # Add stretching space
        layout.addStretch()
        
        # Save Button
        save_button = QPushButton("Save Settings")
        save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        save_button.clicked.connect(lambda: self.save_settings(
            api_key_input.text(),
            dialog
        ))
        layout.addWidget(save_button)
        
        # Set focus to API key input
        api_key_input.setFocus()
        
        # Handle Enter key
        api_key_input.returnPressed.connect(lambda: self.save_settings(
            api_key_input.text(),
            dialog
        ))
        
        dialog.exec()

    def save_settings(self, api_key, dialog):
        """Save settings to secure storage"""
        try:
            # Save API key
            self.secure_storage.set_value("gemini_api_key", api_key)
            
            # Reinitialize the AI client with new key
            if api_key:
                self.gen_ai = Summarizer(api_key)
            else:
                self.gen_ai = None
            
            # Show success message
            QMessageBox.information(
                self,
                "Settings Saved",
                "Settings have been saved successfully."
            )
            
            dialog.accept()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save settings: {str(e)}"
            )

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ModernNotepad()
    window.show()
    sys.exit(app.exec()) 