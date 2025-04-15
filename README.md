# 📝 EZ Notes

A modern, feature-rich notepad application built with PyQt6, featuring a clean Airbnb-inspired design and powerful text editing capabilities.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)

## ✨ Features

- 🎨 **Modern UI Design**: Clean, intuitive interface inspired by Airbnb's design principles
- 📑 **Tab Management**: Persistent left-side tab system for organizing multiple notes
- 🔍 **Smart Search**: Full-text search across all notes with real-time preview
- 🏷️ **Note Tags**: Organize and categorize your notes with custom tags
- 💾 **Auto-Save**: Automatic saving of changes to prevent data loss
- 🎤 **Audio Recording**: Built-in audio recording with real-time transcription
- 📝 **Rich Text Formatting**: Support for bold, italic, bullet points, and text colors
- 💻 **Code Blocks**: Dedicated formatting for code snippets with syntax highlighting
- 🔒 **Secure Storage**: Encrypted storage for sensitive notes
- 📦 **Standalone Application**: No external dependencies required

## 🚀 Installation

### Option 1: Installer (Recommended)
1. Download the latest installer from the [Releases](../../releases) page
2. Run `EZNotes_Setup.exe`
3. Follow the installation wizard
4. Launch EZ Notes from your Start Menu or Desktop

### Option 2: Build from Source
```bash
# Clone the repository
git clone https://github.com/yourusername/ez-notes.git
cd ez-notes

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py

# Optional: Build executable
python build.bat
```

## 🎯 Usage

### Basic Operations
- Create a new note: Click the '+' button in the tab bar
- Save changes: All changes are automatically saved
- Switch between notes: Click on note tabs in the left sidebar
- Search notes: Use the search bar at the top of the window

### Text Formatting
- Use the formatting toolbar for:
  - Bold (Ctrl+B)
  - Italic (Ctrl+I)
  - Bullet Points
  - Text Colors
  - Code Blocks (```code```)

### Audio Features
- Click the microphone icon to start recording
- Audio is automatically transcribed in real-time
- Recordings are saved with your notes

## 🛠️ Technical Details

- **Framework**: PyQt6
- **Audio Processing**: PyAudio
- **Transcription**: OpenAI Whisper
- **Storage**: Encrypted local storage
- **Build System**: PyInstaller

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE.txt) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 🙏 Acknowledgments

- PyQt6 for the robust GUI framework
- OpenAI Whisper for audio transcription
- Airbnb's design principles for UI inspiration

---
Made with ❤️ using Python and PyQt6 