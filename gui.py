# gui.py
import sys
import os
import logging
import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTextEdit, QLineEdit, QPushButton, QComboBox, QLabel, QGroupBox,
    QStackedWidget, QListWidget, QListWidgetItem, QDialog, QMessageBox,
    QFileDialog, QStyleFactory
)
from PyQt6.QtGui import QFont, QPalette, QColor, QPixmap, QBrush
from PyQt6.QtCore import Qt, QSize
from game_logic import (
    get_installed_models, get_ai_response, speak, remove_last_ai_response,
    sanitize_response, update_world_state, get_current_state, count_tokens
)
from game_data import get_role_starter, GENRES, PLAYER_CHOICES_TEMPLATE
from constants import DM_SYSTEM_PROMPTS, VOICE_OPTIONS, COMMAND_EMOJIS
from themes import apply_theme
from constants import MAX_CONTEXT_TOKENS

class RPGAdventureGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ollama_model = "llama3:instruct"
        self.last_ai_reply = ""
        self.conversation = ""
        self.character_name = ""
        self.selected_genre = ""
        self.role = ""
        self.adventure_started = False
        self.last_player_input = ""
        self.player_choices = PLAYER_CHOICES_TEMPLATE.copy()
        self.voice = VOICE_OPTIONS[0]
        self.dm_style = "Normal"
        self.custom_prompt = ""
        
        self.setWindowTitle("RPG Adventure Game")
        self.setGeometry(100, 100, 1000, 700)
        
        self.installed_models = get_installed_models()
        
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        
        self.main_layout = QVBoxLayout()
        self.main_widget.setLayout(self.main_layout)
        
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)
        
        self.setup_screen = QWidget()
        self.setup_layout = QVBoxLayout()
        self.setup_screen.setLayout(self.setup_layout)
        
        self.game_screen = QWidget()
        self.game_layout = QVBoxLayout()
        self.game_screen.setLayout(self.game_layout)
        
        self.stacked_widget.addWidget(self.setup_screen)
        self.stacked_widget.addWidget(self.game_screen)
        
        self.init_setup_screen()
        self.init_game_screen()
        
        self.stacked_widget.setCurrentIndex(0)
        self.apply_theme("Dark")
        self.check_saved_game()
    
    def init_setup_screen(self):
        title = QLabel("RPG Adventure Game")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setup_layout.addWidget(title)
        
        theme_group = QGroupBox("Select Theme")
        theme_layout = QHBoxLayout()
        theme_group.setLayout(theme_layout)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems([
            "Dark", "Light", "Futuristic", "Old Paper", "Fantasy", "Relaxing",
            "Midnight Blue", "Forest Green", "Sunset", "Ocean", "Desert",
            "High Contrast", "Purple Haze", "Crimson", "Matrix", "Winter"
        ])
        self.theme_combo.currentTextChanged.connect(self.apply_theme)
        theme_layout.addWidget(QLabel("Theme:"))
        theme_layout.addWidget(self.theme_combo)
        self.setup_layout.addWidget(theme_group)
        
        model_group = QGroupBox("Select AI Model")
        model_layout = QVBoxLayout()
        model_group.setLayout(model_layout)
        
        self.model_combo = QComboBox()
        if self.installed_models:
            self.model_combo.addItems(self.installed_models)
        else:
            self.model_combo.addItem("llama3:instruct")
        model_layout.addWidget(QLabel("Ollama Model:"))
        model_layout.addWidget(self.model_combo)
        
        self.refresh_models_btn = QPushButton("Refresh Models")
        self.refresh_models_btn.clicked.connect(self.refresh_models)
        model_layout.addWidget(self.refresh_models_btn)
        self.setup_layout.addWidget(model_group)
        
        # DM Style selection
        dm_style_group = QGroupBox("Dungeon Master Style")
        dm_style_layout = QVBoxLayout()
        dm_style_group.setLayout(dm_style_layout)
        
        self.dm_style_combo = QComboBox()
        self.dm_style_combo.addItems(["Normal", "Funny", "Custom"])
        self.dm_style_combo.currentTextChanged.connect(self.toggle_custom_prompt)
        dm_style_layout.addWidget(QLabel("Style:"))
        dm_style_layout.addWidget(self.dm_style_combo)
        
        self.custom_prompt_edit = QTextEdit()
        self.custom_prompt_edit.setPlaceholderText("Enter your custom DM prompt here...")
        self.custom_prompt_edit.setVisible(False)
        dm_style_layout.addWidget(self.custom_prompt_edit)
        
        self.setup_layout.addWidget(dm_style_group)
        
        genre_group = QGroupBox("Select Genre")
        genre_layout = QHBoxLayout()
        genre_group.setLayout(genre_layout)
        
        self.genre_combo = QComboBox()
        for key in GENRES:
            self.genre_combo.addItem(GENRES[key][0], key)
        self.genre_combo.currentIndexChanged.connect(self.update_roles)
        genre_layout.addWidget(QLabel("Genre:"))
        genre_layout.addWidget(self.genre_combo)
        self.setup_layout.addWidget(genre_group)
        
        role_group = QGroupBox("Select Role")
        role_layout = QHBoxLayout()
        role_group.setLayout(role_layout)
        
        self.role_combo = QComboBox()
        self.update_roles()
        role_layout.addWidget(QLabel("Role:"))
        role_layout.addWidget(self.role_combo)
        self.setup_layout.addWidget(role_group)
        
        name_group = QGroupBox("Character Name")
        name_layout = QHBoxLayout()
        name_group.setLayout(name_layout)
        
        self.name_edit = QLineEdit("Alex")
        name_layout.addWidget(QLabel("Name:"))
        name_layout.addWidget(self.name_edit)
        self.setup_layout.addWidget(name_group)
        
        voice_group = QGroupBox("Voice Selection")
        voice_layout = QHBoxLayout()
        voice_group.setLayout(voice_layout)
        
        self.voice_combo = QComboBox()
        self.voice_combo.addItems(VOICE_OPTIONS)
        voice_layout.addWidget(QLabel("Voice:"))
        voice_layout.addWidget(self.voice_combo)
        self.setup_layout.addWidget(voice_group)
        
        self.start_btn = QPushButton("Start Adventure")
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setFont(QFont("Arial", 14))
        self.start_btn.clicked.connect(self.start_adventure)
        self.setup_layout.addWidget(self.start_btn)
        
        self.setup_layout.addStretch()
    
    def init_game_screen(self):
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Arial", 12))
        self.game_layout.addWidget(self.chat_display, 3)
        
        input_layout = QHBoxLayout()
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter your action or command...")
        self.input_field.returnPressed.connect(self.process_input)
        input_layout.addWidget(self.input_field, 4)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.process_input)
        input_layout.addWidget(self.send_btn, 1)
        
        self.game_layout.addLayout(input_layout)
        
        command_layout = QHBoxLayout()
        
        for cmd, text in COMMAND_EMOJIS.items():
            btn = QPushButton(text)
            btn.setProperty("command", cmd)
            btn.clicked.connect(self.command_clicked)
            command_layout.addWidget(btn)
        
        self.game_layout.addLayout(command_layout)
        
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Theme:"))
        
        self.game_theme_combo = QComboBox()
        self.game_theme_combo.addItems([
            "Dark", "Light", "Futuristic", "Old Paper", "Fantasy", "Relaxing",
            "Midnight Blue", "Forest Green", "Sunset", "Ocean", "Desert",
            "High Contrast", "Purple Haze", "Crimson", "Matrix", "Winter"
        ])
        self.game_theme_combo.currentTextChanged.connect(self.apply_theme)
        theme_layout.addWidget(self.game_theme_combo)
        
        self.exit_btn = QPushButton("Exit")
        self.exit_btn.clicked.connect(self.close)
        theme_layout.addWidget(self.exit_btn)
        
        self.game_layout.addLayout(theme_layout)
    
    def toggle_custom_prompt(self, style):
        self.custom_prompt_edit.setVisible(style == "Custom")
    
    def update_roles(self):
        self.role_combo.clear()
        genre_key = self.genre_combo.currentData()
        if genre_key in GENRES:
            _, roles = GENRES[genre_key]
            self.role_combo.addItems(roles)
    
    def refresh_models(self):
        self.installed_models = get_installed_models()
        self.model_combo.clear()
        if self.installed_models:
            self.model_combo.addItems(self.installed_models)
        else:
            self.model_combo.addItem("llama3:instruct")
    
    def apply_theme(self, theme_name):
        palette = apply_theme(theme_name)
        self.setPalette(palette)
        QApplication.setPalette(palette)
        
        if hasattr(self, 'game_theme_combo'):
            self.game_theme_combo.setCurrentText(theme_name)
        if hasattr(self, 'theme_combo'):
            self.theme_combo.setCurrentText(theme_name)
    
    def check_saved_game(self):
        if os.path.exists("adventure.txt"):
            reply = QMessageBox.question(self, 'Load Adventure', 
                                        "A saved adventure exists. Load it now?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                self.load_adventure()
    
    def append_dm_message(self, text):
        """Append a Dungeon Master message to chat with theme-appropriate coloring"""
        theme = self.game_theme_combo.currentText()
        # Use white text for dark themes, black for light themes
        color = "white" if theme in ["Dark", "Matrix", "Midnight Blue"] else "black"
        self.chat_display.append(f"<b><font color='{color}'>Dungeon Master:</font></b> {text}")
    
    def start_adventure(self):
        self.ollama_model = self.model_combo.currentText()
        genre_key = self.genre_combo.currentData()
        self.selected_genre = GENRES[genre_key][0]
        self.role = self.role_combo.currentText()
        self.character_name = self.name_edit.text() or "Alex"
        self.voice = self.voice_combo.currentText()
        self.dm_style = self.dm_style_combo.currentText()
        
        if self.dm_style == "Custom":
            self.custom_prompt = self.custom_prompt_edit.toPlainText().strip()
        
        self.player_choices = PLAYER_CHOICES_TEMPLATE.copy()
        
        role_starter = get_role_starter(self.selected_genre, self.role)
        initial_context = (
            f"### Adventure Setting ###\n"
            f"Genre: {self.selected_genre}\n"
            f"Player Character: {self.character_name} the {self.role}\n"
            f"Starting Scenario: {role_starter}\n"
        )
        self.conversation = initial_context + "\n\nDungeon Master: "
        
        if self.dm_style == "Custom" and self.custom_prompt:
            system_prompt = self.custom_prompt
        else:
            system_prompt = DM_SYSTEM_PROMPTS.get(self.dm_style, DM_SYSTEM_PROMPTS["Normal"])
        
        ai_reply = get_ai_response(system_prompt + "\n\n" + self.conversation, self.ollama_model)
        if ai_reply:
            ai_reply = sanitize_response(ai_reply)
            self.conversation += ai_reply
            self.last_ai_reply = ai_reply
            self.player_choices['consequences'].append(f"Start: {ai_reply.split('.')[0]}")
        else:
            ai_reply = f"{self.character_name} stands ready. What will you do first?"
            self.conversation += ai_reply
            self.last_ai_reply = ai_reply
        
        self.chat_display.clear()
        self.chat_display.append(f"<b>--- Adventure Start: {self.character_name} the {self.role} ---</b>")
        self.chat_display.append(f"<b>Starting scenario:</b> {role_starter}")
        self.chat_display.append("")
        self.append_dm_message(ai_reply)
        
        speak(ai_reply, self.voice)
        
        self.stacked_widget.setCurrentIndex(1)
        self.adventure_started = True
        self.input_field.setFocus()
    
    def process_input(self):
        user_input = self.input_field.text().strip()
        self.input_field.clear()
        
        if not user_input:
            return
        
        if user_input.startswith("/"):
            self.process_command(user_input)
            return
        
        formatted_input = f"Player: {user_input}"
        self.last_player_input = user_input
        
        self.chat_display.append(f"<b><font color='green'>You:</font></b> {user_input}")
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())
        
        state_context = get_current_state(self.player_choices)
        
        if self.dm_style == "Custom" and self.custom_prompt:
            base_prompt = self.custom_prompt
        else:
            base_prompt = DM_SYSTEM_PROMPTS.get(self.dm_style, DM_SYSTEM_PROMPTS["Normal"])
        
        base_prompt += f"\n\n### Current World State ###\n{state_context}\n\n"
        variable_part = f"{self.conversation}\n{formatted_input}\nDungeon Master:"
        
        tokens = count_tokens(base_prompt + variable_part)
        
        if tokens > MAX_CONTEXT_TOKENS:
            self.conversation = self.conversation[-MAX_CONTEXT_TOKENS//2:]
            variable_part = f"{self.conversation}\n{formatted_input}\nDungeon Master:"
        
        full_conversation = base_prompt + variable_part
        
        ai_reply = get_ai_response(full_conversation, self.ollama_model)
        
        if ai_reply:
            ai_reply = sanitize_response(ai_reply)
            self.append_dm_message(ai_reply)
            self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())
            
            self.conversation += f"\n{formatted_input}\nDungeon Master: {ai_reply}"
            self.last_ai_reply = ai_reply
            
            update_world_state(user_input, ai_reply, self.player_choices)
            speak(ai_reply, self.voice)
    
    def process_command(self, command):
        if command.lower() in ["/?", "/help"]:
            self.show_help()
        elif command.lower() == "/redo":
            self.redo_last()
        elif command.lower() == "/save":
            self.save_adventure()
        elif command.lower() == "/load":
            self.load_adventure()
        elif command.lower() == "/consequences":
            self.show_consequences()
        elif command.lower() == "/state":
            self.show_state()
        elif command.lower() == "/exit":
            self.close()
        else:
            self.chat_display.append(f"<i>Unknown command: {command}. Type /help for available commands.</i>")
    
    def command_clicked(self):
        btn = self.sender()
        command = btn.property("command")
        self.process_command(command)
    
    def show_help(self):
        help_text = """
<b>Available commands:</b>
<b>❓ /help</b> - Show this help message
<b>🔄 /redo</b> - Repeat last AI response with a new generation
<b>💾 /save</b> - Save the full adventure to adventure.txt
<b>📂 /load</b> - Load the adventure from adventure.txt
<b>⚠️ /consequences</b> - Show recent consequences of your actions
<b>🌍 /state</b> - Show current world state
<b>/exit</b> - Exit the game

<b>Story Adaptation:</b>
Every action you take will permanently change the story:
  - Killing characters removes them permanently
  - Stealing items adds them to your inventory
  - Choices affect NPC attitudes and world events
  - Environments change based on your actions
  - Resources are permanently gained or lost
  - You can attempt ANY action, no matter how unconventional
  - The story adapts dynamically to your choices
"""
        self.chat_display.append(help_text)
    
    def redo_last(self):
        if self.last_ai_reply and self.last_player_input:
            original_length = len(self.conversation)
            self.conversation = remove_last_ai_response(self.conversation)
            
            state_context = get_current_state(self.player_choices)
            
            if self.dm_style == "Custom" and self.custom_prompt:
                base_prompt = self.custom_prompt
            else:
                base_prompt = DM_SYSTEM_PROMPTS.get(self.dm_style, DM_SYSTEM_PROMPTS["Normal"])
            
            full_conversation = (
                f"{base_prompt}\n\n"
                f"### Current World State ###\n{state_context}\n\n"
                f"{self.conversation}\n"
                f"Player: {self.last_player_input}\n"
                "Dungeon Master:"
            )
            
            ai_reply = get_ai_response(full_conversation, self.ollama_model)
            if ai_reply:
                ai_reply = sanitize_response(ai_reply)
                self.chat_display.append(f"<b><font color='purple'>[Redoing last response]</font></b>")
                self.append_dm_message(ai_reply)
                self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())
                
                self.conversation += f"\nPlayer: {self.last_player_input}\nDungeon Master: {ai_reply}"
                self.last_ai_reply = ai_reply
                
                update_world_state(self.last_player_input, ai_reply, self.player_choices)
                speak(ai_reply, self.voice)
            else:
                self.conversation = self.conversation[:original_length]
        else:
            self.chat_display.append("<i>Nothing to redo.</i>")
    
    def save_adventure(self):
        try:
            with open("adventure.txt", "w", encoding="utf-8") as f:
                f.write(self.conversation)
                f.write("\n\n### Persistent World State ###\n")
                f.write(get_current_state(self.player_choices))
            self.chat_display.append("<b><font color='green'>Adventure saved to adventure.txt</font></b>")
        except Exception as e:
            logging.error(f"Error saving adventure: {e}")
            self.chat_display.append("<b><font color='red'>Error saving adventure. Details logged.</font></b>")
    
    def load_adventure(self):
        if os.path.exists("adventure.txt"):
            try:
                self.player_choices = PLAYER_CHOICES_TEMPLATE.copy()
                
                with open("adventure.txt", "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Split into conversation and state
                if "### Persistent World State ###" in content:
                    conversation_part, state_part = content.split("### Persistent World State ###", 1)
                    self.conversation = conversation_part.strip()
                    self.parse_world_state(state_part.strip())
                else:
                    self.conversation = content
                
                self.chat_display.clear()
                self.chat_display.append("<b><font color='green'>Adventure loaded.</font></b>")
                
                # Extract character name and role
                if "Player Character:" in self.conversation:
                    char_line = self.conversation.split("Player Character:")[1].split("\n")[0].strip()
                    if "the" in char_line:
                        parts = char_line.split("the")
                        self.character_name = parts[0].strip()
                        self.role = parts[1].strip()
                
                # Find last DM response
                last_dm_pos = self.conversation.rfind("Dungeon Master:")
                if last_dm_pos != -1:
                    self.last_ai_reply = self.conversation[last_dm_pos + len("Dungeon Master:"):].strip()
                
                self.stacked_widget.setCurrentIndex(1)
                self.adventure_started = True
                
                # Theme-aware coloring for conversation history
                current_theme = self.game_theme_combo.currentText()
                color = "white" if current_theme in ["Dark", "Matrix", "Midnight Blue"] else "black"
                formatted_conversation = self.conversation.replace(
                    "Dungeon Master:", 
                    f"<b><font color='{color}'>Dungeon Master:</font></b>"
                )
                self.chat_display.append(formatted_conversation)
                self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())
                
            except Exception as e:
                logging.error(f"Error loading adventure: {e}")
                self.chat_display.append("<b><font color='red'>Error loading adventure. Details logged.</font></b>")
        else:
            self.chat_display.append("<b><font color='red'>No saved adventure found.</font></b>")
    
    def parse_world_state(self, state_text):
        """Parse the saved world state text into player choices dictionary"""
        lines = state_text.splitlines()
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Section headers
            if line == "Resources:":
                current_section = "resources"
                continue
            elif line == "Faction Relationships:":
                current_section = "factions"
                continue
            elif line == "Recent World Events:":
                current_section = "world_events"
                continue
            elif line == "Recent Consequences:":
                current_section = "consequences"
                continue
                
            # Key-value pairs
            if current_section is None:
                if line.startswith("Allies:"):
                    allies = line.split(":", 1)[1].strip()
                    if allies != "None":
                        self.player_choices["allies"] = [a.strip() for a in allies.split(",")]
                elif line.startswith("Enemies:"):
                    enemies = line.split(":", 1)[1].strip()
                    if enemies != "None":
                        self.player_choices["enemies"] = [e.strip() for e in enemies.split(",")]
                elif line.startswith("Reputation:"):
                    rep = line.split(":", 1)[1].strip()
                    try:
                        self.player_choices["reputation"] = int(rep)
                    except ValueError:
                        pass
                elif line.startswith("Active Quests:"):
                    quests = line.split(":", 1)[1].strip()
                    if quests != "None":
                        self.player_choices["active_quests"] = [q.strip() for q in quests.split(",")]
                elif line.startswith("Completed Quests:"):
                    quests = line.split(":", 1)[1].strip()
                    if quests != "None":
                        self.player_choices["completed_quests"] = [q.strip() for q in quests.split(",")]
            
            # Resource list
            elif current_section == "resources":
                if line.startswith("-"):
                    parts = line[1:].split(":", 1)
                    if len(parts) == 2:
                        resource = parts[0].strip()
                        amount = parts[1].strip()
                        try:
                            self.player_choices["resources"][resource] = int(amount)
                        except ValueError:
                            pass
            
            # Faction relationships
            elif current_section == "factions":
                if line.startswith("-"):
                    parts = line[1:].split(":", 1)
                    if len(parts) == 2:
                        faction = parts[0].strip()
                        level = parts[1].strip().replace('+', '').replace('-', '')
                        try:
                            self.player_choices["factions"][faction] = int(level)
                        except ValueError:
                            pass
            
            # World events
            elif current_section == "world_events":
                if line.startswith("-"):
                    event = line[1:].strip()
                    self.player_choices["world_events"].append(event)
            
            # Consequences
            elif current_section == "consequences":
                if line.startswith("-"):
                    consequence = line[1:].strip()
                    self.player_choices["consequences"].append(consequence)
    
    def show_consequences(self):
        if self.player_choices['consequences']:
            self.chat_display.append("<b>Recent Consequences of Your Actions:</b>")
            for i, cons in enumerate(self.player_choices['consequences'][-5:], 1):
                self.chat_display.append(f"{i}. {cons}")
        else:
            self.chat_display.append("<i>No consequences recorded yet.</i>")
    
    def show_state(self):
        self.chat_display.append("<b>Current World State:</b>")
        self.chat_display.append(get_current_state(self.player_choices))