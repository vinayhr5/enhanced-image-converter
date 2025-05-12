import tkinter as tk
from tkinter import filedialog, messagebox, StringVar, IntVar, BooleanVar, Radiobutton, Label, Entry, Frame, Button, \
    ttk, colorchooser, Menu, Scale, HORIZONTAL, simpledialog
from PIL import Image, ImageTk, ImageOps
import os
import json
import threading
import time
import shutil
from datetime import datetime
import webbrowser
import sys

# Global variables
RECENT_FILES = []
MAX_RECENT = 10
PRESETS = {}
APP_VERSION = "1.0.0"
DEFAULT_SETTINGS = {
    "recent_files": [],
    "recent_folders": [],
    "presets": {},
    "last_output_dir": "",
    "theme": "light",
    "preserve_metadata": True,
    "overwrite_existing": False,
    "custom_naming": "{filename}_converted",
    "default_format": "png"
}
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".image_converter_settings.json")


# Load settings
def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        return DEFAULT_SETTINGS.copy()
    except Exception as e:
        print(f"Error loading settings: {e}")
        return DEFAULT_SETTINGS.copy()


# Save settings
def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"Error saving settings: {e}")


# Initialize settings
settings = load_settings()


class ImageProcessor:
    def __init__(self):
        self.preview_image = None
        self.original_image = None
        self.processed_image = None
        self.processing_thread = None
        self.stop_processing = False

    def load_image(self, image_path):
        try:
            self.original_image = Image.open(image_path).convert("RGBA")
            return self.original_image
        except Exception as e:
            raise Exception(f"Failed to load image: {str(e)}")

    def process_image(self, image, options):
        """Process an image with the given options"""
        try:
            # Make a copy to avoid modifying the original
            img = image.copy()

            # Resize if needed
            if options["resize"] and options["width"] > 0 and options["height"] > 0:
                img = img.resize((options["width"], options["height"]), Image.LANCZOS)

            # Crop if needed
            if options["crop"]:
                img = img.crop((options["crop_left"], options["crop_top"],
                                options["crop_right"], options["crop_bottom"]))

            # Process transparency and colors
            if options["background_mode"] == "custom":
                # Custom color transparency
                bg_color = options["custom_color"]
                tolerance = options["tolerance"] / 100.0

                new_data = []
                for item in img.getdata():
                    r, g, b, a = item

                    # Calculate color distance (simple Euclidean distance)
                    distance = (
                                       ((r - bg_color[0]) / 255) ** 2 +
                                       ((g - bg_color[1]) / 255) ** 2 +
                                       ((b - bg_color[2]) / 255) ** 2
                               ) ** 0.5

                    if distance < tolerance:
                        # Background → transparent
                        new_data.append((0, 0, 0, 0))
                    elif options["invert_colors"]:
                        # Invert non-background colors if requested
                        new_data.append((255 - r, 255 - g, 255 - b, a))
                    else:
                        # Keep original colors
                        new_data.append((r, g, b, a))
            else:
                # Black or white background
                new_data = []

                if options["background_mode"] == "black":
                    # Black background
                    tolerance = options["tolerance"]
                    for item in img.getdata():
                        r, g, b, a = item
                        # Check if pixel is close to black
                        if r <= tolerance and g <= tolerance and b <= tolerance:
                            # Black background → transparent
                            new_data.append((0, 0, 0, 0))
                        elif options["invert_colors"]:
                            if r > 240 and g > 240 and b > 240:
                                # White → black
                                new_data.append((0, 0, 0, 255))
                            else:
                                # Other colors → invert
                                new_data.append((255 - r, 255 - g, 255 - b, a))
                        else:
                            # Keep original colors
                            new_data.append((r, g, b, a))
                else:
                    # White background
                    tolerance = 255 - options["tolerance"]
                    for item in img.getdata():
                        r, g, b, a = item
                        # Check if pixel is close to white
                        if r >= tolerance and g >= tolerance and b >= tolerance:
                            # White background → transparent
                            new_data.append((0, 0, 0, 0))
                        elif options["invert_colors"]:
                            if r < 15 and g < 15 and b < 15:
                                # Black → white
                                new_data.append((255, 255, 255, 255))
                            else:
                                # Other colors → invert
                                new_data.append((255 - r, 255 - g, 255 - b, a))
                        else:
                            # Keep original colors
                            new_data.append((r, g, b, a))

            img.putdata(new_data)

            # Apply alpha adjustment if needed
            if options["adjust_alpha"] and options["alpha_value"] < 255:
                alpha_value = options["alpha_value"]
                alpha_data = []
                for item in img.getdata():
                    r, g, b, a = item
                    if a > 0:  # Only adjust non-transparent pixels
                        new_alpha = min(a, alpha_value)
                        alpha_data.append((r, g, b, new_alpha))
                    else:
                        alpha_data.append((r, g, b, a))
                img.putdata(alpha_data)

            # Apply background replacement if needed
            if options["replace_background"]:
                bg_img = Image.new("RGBA", img.size, options["replacement_color"])
                img = Image.alpha_composite(bg_img, img)

            return img

        except Exception as e:
            raise Exception(f"Error processing image: {str(e)}")

    def get_image_preview(self, image, max_size=(300, 300)):
        """Create a thumbnail preview of the image"""
        if image is None:
            return None

        # Create a copy to avoid modifying the original
        img = image.copy()
        img.thumbnail(max_size)
        return ImageTk.PhotoImage(img)

    def save_image(self, image, output_path, format_option, quality=95, optimize=True, preserve_metadata=False):
        """Save the processed image"""
        try:
            # Get the appropriate format and extension
            format_map = {
                "png": "PNG",
                "jpg": "JPEG",
                "jpeg": "JPEG",
                "webp": "WEBP",
                "tiff": "TIFF",
                "bmp": "BMP"
            }

            format_name = format_map.get(format_option.lower(), "PNG")

            # Ensure the output path has the correct extension
            base, _ = os.path.splitext(output_path)
            output_path = f"{base}.{format_option.lower()}"

            # Handle JPEG format (no alpha channel)
            if format_name == "JPEG":
                # Create a white background
                bg = Image.new("RGB", image.size, (255, 255, 255))
                bg.paste(image, (0, 0), image)

                # Save with quality setting
                bg.save(output_path, format=format_name, quality=quality, optimize=optimize)
            else:
                # Save with appropriate settings for the format
                if format_name == "PNG":
                    image.save(output_path, format=format_name, optimize=optimize)
                elif format_name == "WEBP":
                    image.save(output_path, format=format_name, quality=quality, lossless=quality > 90)
                else:
                    image.save(output_path, format=format_name)

            return output_path
        except Exception as e:
            raise Exception(f"Failed to save image: {str(e)}")


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Background Remover and Color Inverter")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)

        # Set icon if available
        try:
            if os.name == 'nt':  # Windows
                self.root.iconbitmap('icon.ico')
            else:  # Linux/Mac
                icon = tk.PhotoImage(file='icon.png')
                self.root.iconphoto(True, icon)
        except:
            pass

        # Initialize the image processor
        self.processor = ImageProcessor()

        # Initialize variables
        self.init_variables()

        # Create the UI
        self.create_menu()
        self.create_main_ui()

        # Apply theme
        self.apply_theme(settings.get("theme", "light"))

        # Set up drag and drop
        self.setup_drag_drop()

        # Update recent files menu
        self.update_recent_files_menu()

        # Create processing queue
        self.processing_queue = []
        self.is_processing = False

        # Add creator info
        self.add_creator_info()

    def init_variables(self):
        """Initialize all variables used in the application"""
        # Background mode
        self.bg_mode_var = StringVar(value="black")

        # Custom color
        self.custom_color_var = StringVar(value="#000000")
        self.custom_color_rgb = (0, 0, 0)

        # Tolerance
        self.tolerance_var = IntVar(value=15)

        # Resize options
        self.resize_var = BooleanVar(value=False)
        self.width_var = StringVar(value="")
        self.height_var = StringVar(value="")

        # Crop options
        self.crop_var = BooleanVar(value=False)
        self.crop_left_var = IntVar(value=0)
        self.crop_top_var = IntVar(value=0)
        self.crop_right_var = IntVar(value=100)
        self.crop_bottom_var = IntVar(value=100)

        # Color options
        self.invert_colors_var = BooleanVar(value=True)

        # Alpha options
        self.adjust_alpha_var = BooleanVar(value=False)
        self.alpha_value_var = IntVar(value=255)

        # Background replacement
        self.replace_bg_var = BooleanVar(value=False)
        self.replacement_color_var = StringVar(value="#FFFFFF")
        self.replacement_color_rgb = (255, 255, 255)

        # Output options
        self.output_format_var = StringVar(value=settings.get("default_format", "png"))
        self.output_quality_var = IntVar(value=95)
        self.output_optimize_var = BooleanVar(value=True)
        self.preserve_metadata_var = BooleanVar(value=settings.get("preserve_metadata", True))
        self.overwrite_var = BooleanVar(value=settings.get("overwrite_existing", False))
        self.custom_output_var = BooleanVar(value=False)
        self.output_dir_var = StringVar(value=settings.get("last_output_dir", ""))
        self.naming_pattern_var = StringVar(value=settings.get("custom_naming", "{filename}_converted"))

        # Preview
        self.preview_var = BooleanVar(value=True)

        # Current file/folder
        self.current_file = None
        self.current_folder = None

        # Preview images
        self.original_preview = None
        self.processed_preview = None

    def create_menu(self):
        """Create the application menu"""
        self.menu_bar = Menu(self.root)

        # File menu
        self.file_menu = Menu(self.menu_bar, tearoff=0)
        self.file_menu.add_command(label="Open File...", command=self.open_file, accelerator="Ctrl+O")
        self.file_menu.add_command(label="Open Folder...", command=self.open_folder, accelerator="Ctrl+Shift+O")
        self.file_menu.add_command(label="Open Multiple Files...", command=self.open_multiple_files)

        # Recent files submenu
        self.recent_menu = Menu(self.file_menu, tearoff=0)
        self.file_menu.add_cascade(label="Recent Files", menu=self.recent_menu)

        self.file_menu.add_separator()
        self.file_menu.add_command(label="Save Current Image...", command=self.save_current_image, accelerator="Ctrl+S")
        self.file_menu.add_command(label="Save All", command=self.process_queue, accelerator="Ctrl+Shift+S")
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.root.quit, accelerator="Alt+F4")

        self.menu_bar.add_cascade(label="File", menu=self.file_menu)

        # Edit menu
        self.edit_menu = Menu(self.menu_bar, tearoff=0)
        self.edit_menu.add_command(label="Clear Queue", command=self.clear_queue)
        self.edit_menu.add_separator()

        # Presets submenu
        self.presets_menu = Menu(self.edit_menu, tearoff=0)
        self.presets_menu.add_command(label="Save Current Settings as Preset...", command=self.save_preset)
        self.presets_menu.add_command(label="Manage Presets...", command=self.manage_presets)
        self.presets_menu.add_separator()

        # Add default presets
        self.presets_menu.add_command(label="Logo on Black", command=lambda: self.load_preset("logo_black"))
        self.presets_menu.add_command(label="Logo on White", command=lambda: self.load_preset("logo_white"))
        self.presets_menu.add_command(label="Product Image", command=lambda: self.load_preset("product"))

        self.edit_menu.add_cascade(label="Presets", menu=self.presets_menu)
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Preferences...", command=self.show_preferences)

        self.menu_bar.add_cascade(label="Edit", menu=self.edit_menu)

        # View menu
        self.view_menu = Menu(self.menu_bar, tearoff=0)
        self.view_menu.add_checkbutton(label="Show Preview", variable=self.preview_var,
                                       command=self.toggle_preview)

        # Theme submenu
        self.theme_menu = Menu(self.view_menu, tearoff=0)
        self.theme_menu.add_command(label="Light", command=lambda: self.apply_theme("light"))
        self.theme_menu.add_command(label="Dark", command=lambda: self.apply_theme("dark"))

        self.view_menu.add_cascade(label="Theme", menu=self.theme_menu)

        self.menu_bar.add_cascade(label="View", menu=self.view_menu)

        # Help menu
        self.help_menu = Menu(self.menu_bar, tearoff=0)
        self.help_menu.add_command(label="Documentation", command=self.show_documentation)
        self.help_menu.add_command(label="About", command=self.show_about)

        self.menu_bar.add_cascade(label="Help", menu=self.help_menu)

        self.root.config(menu=self.menu_bar)

        # Keyboard shortcuts
        self.root.bind("<Control-o>", lambda event: self.open_file())
        self.root.bind("<Control-Shift-O>", lambda event: self.open_folder())
        self.root.bind("<Control-s>", lambda event: self.save_current_image())
        self.root.bind("<Control-Shift-S>", lambda event: self.process_queue())

    def create_main_ui(self):
        """Create the main user interface"""
        # Main container with two columns
        self.main_frame = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left column - Settings
        self.settings_frame = ttk.Frame(self.main_frame)
        self.main_frame.add(self.settings_frame, weight=40)

        # Right column - Preview
        self.preview_frame = ttk.Frame(self.main_frame)
        self.main_frame.add(self.preview_frame, weight=60)

        # Create settings UI
        self.create_settings_ui()

        # Create preview UI
        self.create_preview_ui()

        # Create status bar
        self.create_status_bar()

    def create_settings_ui(self):
        """Create the settings panel UI"""
        # Use a notebook for tabs
        self.settings_notebook = ttk.Notebook(self.settings_frame)
        self.settings_notebook.pack(fill=tk.BOTH, expand=True)

        # Basic tab
        self.basic_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.basic_frame, text="Basic")

        # Advanced tab
        self.advanced_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.advanced_frame, text="Advanced")

        # Output tab
        self.output_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.output_frame, text="Output")

        # Batch tab
        self.batch_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.batch_frame, text="Batch")

        # Fill the basic tab
        self.create_basic_settings()

        # Fill the advanced tab
        self.create_advanced_settings()

        # Fill the output tab
        self.create_output_settings()

        # Fill the batch tab
        self.create_batch_settings()

    def create_basic_settings(self):
        """Create basic settings UI"""
        # Background mode frame
        bg_frame = ttk.LabelFrame(self.basic_frame, text="Background Detection")
        bg_frame.pack(fill=tk.X, padx=10, pady=5)

        # Background mode radio buttons
        ttk.Radiobutton(bg_frame, text="Black Background", variable=self.bg_mode_var,
                        value="black", command=self.update_preview).pack(anchor="w", padx=10, pady=2)
        ttk.Radiobutton(bg_frame, text="White Background", variable=self.bg_mode_var,
                        value="white", command=self.update_preview).pack(anchor="w", padx=10, pady=2)
        ttk.Radiobutton(bg_frame, text="Custom Color", variable=self.bg_mode_var,
                        value="custom", command=self.update_preview).pack(anchor="w", padx=10, pady=2)

        # Custom color picker
        color_frame = ttk.Frame(bg_frame)
        color_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(color_frame, text="Custom Color:").pack(side=tk.LEFT, padx=5)
        self.color_preview = ttk.Label(color_frame, text="      ", background="#000000")
        self.color_preview.pack(side=tk.LEFT, padx=5)
        ttk.Button(color_frame, text="Pick Color", command=self.pick_color).pack(side=tk.LEFT, padx=5)

        # Tolerance slider
        tolerance_frame = ttk.Frame(bg_frame)
        tolerance_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(tolerance_frame, text="Tolerance:").pack(side=tk.LEFT, padx=5)
        ttk.Scale(tolerance_frame, from_=0, to=100, orient=HORIZONTAL,
                  variable=self.tolerance_var, command=lambda _: self.update_preview()).pack(side=tk.LEFT, fill=tk.X,
                                                                                             expand=True, padx=5)
        ttk.Label(tolerance_frame, textvariable=self.tolerance_var).pack(side=tk.LEFT, padx=5)

        # Color options frame
        color_options_frame = ttk.LabelFrame(self.basic_frame, text="Color Options")
        color_options_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Checkbutton(color_options_frame, text="Invert Colors", variable=self.invert_colors_var,
                        command=self.update_preview).pack(anchor="w", padx=10, pady=5)

        # Resize frame
        resize_frame = ttk.LabelFrame(self.basic_frame, text="Resize")
        resize_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Checkbutton(resize_frame, text="Resize Image", variable=self.resize_var,
                        command=self.toggle_resize).pack(anchor="w", padx=10, pady=2)

        # Width and height inputs
        size_frame = ttk.Frame(resize_frame)
        size_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(size_frame, text="Width:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Entry(size_frame, textvariable=self.width_var, width=8).grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(size_frame, text="pixels").grid(row=0, column=2, padx=5, pady=2, sticky="w")

        ttk.Label(size_frame, text="Height:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        ttk.Entry(size_frame, textvariable=self.height_var, width=8).grid(row=1, column=1, padx=5, pady=2)
        ttk.Label(size_frame, text="pixels").grid(row=1, column=2, padx=5, pady=2, sticky="w")

        # Action buttons
        action_frame = ttk.Frame(self.basic_frame)
        action_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(action_frame, text="Open File", command=self.open_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Open Folder", command=self.open_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Process & Save", command=self.process_current).pack(side=tk.LEFT, padx=5)

    def create_advanced_settings(self):
        """Create advanced settings UI"""
        # Crop frame
        crop_frame = ttk.LabelFrame(self.advanced_frame, text="Crop")
        crop_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Checkbutton(crop_frame, text="Crop Image", variable=self.crop_var,
                        command=self.toggle_crop).pack(anchor="w", padx=10, pady=2)

        # Crop controls
        crop_controls = ttk.Frame(crop_frame)
        crop_controls.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(crop_controls, text="Left:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Scale(crop_controls, from_=0, to=100, orient=HORIZONTAL,
                  variable=self.crop_left_var, command=lambda _: self.update_preview()).grid(row=0, column=1, padx=5,
                                                                                             pady=2, sticky="ew")

        ttk.Label(crop_controls, text="Top:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        ttk.Scale(crop_controls, from_=0, to=100, orient=HORIZONTAL,
                  variable=self.crop_top_var, command=lambda _: self.update_preview()).grid(row=1, column=1, padx=5,
                                                                                            pady=2, sticky="ew")

        ttk.Label(crop_controls, text="Right:").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        ttk.Scale(crop_controls, from_=0, to=100, orient=HORIZONTAL,
                  variable=self.crop_right_var, command=lambda _: self.update_preview()).grid(row=2, column=1, padx=5,
                                                                                              pady=2, sticky="ew")

        ttk.Label(crop_controls, text="Bottom:").grid(row=3, column=0, padx=5, pady=2, sticky="w")
        ttk.Scale(crop_controls, from_=0, to=100, orient=HORIZONTAL,
                  variable=self.crop_bottom_var, command=lambda _: self.update_preview()).grid(row=3, column=1, padx=5,
                                                                                               pady=2, sticky="ew")

        crop_controls.columnconfigure(1, weight=1)

        # Alpha adjustment frame
        alpha_frame = ttk.LabelFrame(self.advanced_frame, text="Transparency")
        alpha_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Checkbutton(alpha_frame, text="Adjust Transparency", variable=self.adjust_alpha_var,
                        command=self.toggle_alpha).pack(anchor="w", padx=10, pady=2)

        # Alpha slider
        alpha_slider_frame = ttk.Frame(alpha_frame)
        alpha_slider_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(alpha_slider_frame, text="Alpha:").pack(side=tk.LEFT, padx=5)
        ttk.Scale(alpha_slider_frame, from_=0, to=255, orient=HORIZONTAL,
                  variable=self.alpha_value_var, command=lambda _: self.update_preview()).pack(side=tk.LEFT, fill=tk.X,
                                                                                               expand=True, padx=5)
        ttk.Label(alpha_slider_frame, textvariable=self.alpha_value_var).pack(side=tk.LEFT, padx=5)

        # Background replacement frame
        bg_replace_frame = ttk.LabelFrame(self.advanced_frame, text="Background Replacement")
        bg_replace_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Checkbutton(bg_replace_frame, text="Replace Background", variable=self.replace_bg_var,
                        command=self.toggle_bg_replacement).pack(anchor="w", padx=10, pady=2)

        # Background color picker
        bg_color_frame = ttk.Frame(bg_replace_frame)
        bg_color_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(bg_color_frame, text="Background Color:").pack(side=tk.LEFT, padx=5)
        self.bg_color_preview = ttk.Label(bg_color_frame, text="      ", background="#FFFFFF")
        self.bg_color_preview.pack(side=tk.LEFT, padx=5)
        ttk.Button(bg_color_frame, text="Pick Color", command=self.pick_bg_color).pack(side=tk.LEFT, padx=5)

    def create_output_settings(self):
        """Create output settings UI"""
        # Format frame
        format_frame = ttk.LabelFrame(self.output_frame, text="Output Format")
        format_frame.pack(fill=tk.X, padx=10, pady=5)

        formats = [("PNG (with transparency)", "png"),
                   ("JPEG (no transparency)", "jpg"),
                   ("WebP (with transparency)", "webp"),
                   ("TIFF (with transparency)", "tiff"),
                   ("BMP (no transparency)", "bmp")]

        for text, value in formats:
            ttk.Radiobutton(format_frame, text=text, variable=self.output_format_var,
                            value=value).pack(anchor="w", padx=10, pady=2)

        # Quality settings (for JPEG/WebP)
        quality_frame = ttk.Frame(format_frame)
        quality_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(quality_frame, text="Quality:").pack(side=tk.LEFT, padx=5)
        ttk.Scale(quality_frame, from_=1, to=100, orient=HORIZONTAL,
                  variable=self.output_quality_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Label(quality_frame, textvariable=self.output_quality_var).pack(side=tk.LEFT, padx=5)

        ttk.Checkbutton(format_frame, text="Optimize File Size",
                        variable=self.output_optimize_var).pack(anchor="w", padx=10, pady=2)

        # Output location frame
        location_frame = ttk.LabelFrame(self.output_frame, text="Output Location")
        location_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Radiobutton(location_frame, text="Save to 'converted' subfolder",
                        variable=self.custom_output_var, value=False).pack(anchor="w", padx=10, pady=2)
        ttk.Radiobutton(location_frame, text="Save to custom location",
                        variable=self.custom_output_var, value=True).pack(anchor="w", padx=10, pady=2)

        # Custom output directory
        dir_frame = ttk.Frame(location_frame)
        dir_frame.pack(fill=tk.X, padx=10, pady=5)

        self.output_dir_entry = ttk.Entry(dir_frame, textvariable=self.output_dir_var)
        self.output_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(dir_frame, text="Browse...", command=self.browse_output_dir).pack(side=tk.LEFT, padx=5)

        # File naming frame
        naming_frame = ttk.LabelFrame(self.output_frame, text="File Naming")
        naming_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(naming_frame, text="Pattern:").pack(anchor="w", padx=10, pady=2)
        ttk.Entry(naming_frame, textvariable=self.naming_pattern_var).pack(fill=tk.X, padx=10, pady=2)

        ttk.Label(naming_frame, text="Available variables: {filename}, {date}, {time}, {counter}").pack(anchor="w",
                                                                                                        padx=10, pady=2)

        # File handling options
        options_frame = ttk.Frame(self.output_frame)
        options_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Checkbutton(options_frame, text="Preserve metadata",
                        variable=self.preserve_metadata_var).pack(anchor="w", padx=10, pady=2)
        ttk.Checkbutton(options_frame, text="Overwrite existing files",
                        variable=self.overwrite_var).pack(anchor="w", padx=10, pady=2)

    def create_batch_settings(self):
        """Create batch processing UI"""
        # Queue frame
        queue_frame = ttk.LabelFrame(self.batch_frame, text="Processing Queue")
        queue_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Queue list
        self.queue_list = ttk.Treeview(queue_frame, columns=("path", "status"), show="headings")
        self.queue_list.heading("path", text="File Path")
        self.queue_list.heading("status", text="Status")
        self.queue_list.column("path", width=300)
        self.queue_list.column("status", width=100)
        self.queue_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Scrollbar for queue list
        scrollbar = ttk.Scrollbar(queue_frame, orient="vertical", command=self.queue_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.queue_list.configure(yscrollcommand=scrollbar.set)

        # Queue controls
        controls_frame = ttk.Frame(self.batch_frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(controls_frame, text="Add Files", command=self.open_multiple_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Remove Selected", command=self.remove_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Clear Queue", command=self.clear_queue).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Process All", command=self.process_queue).pack(side=tk.LEFT, padx=5)

    def create_preview_ui(self):
        """Create the preview panel UI"""
        # Preview container
        preview_container = ttk.Frame(self.preview_frame)
        preview_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Original image preview
        original_frame = ttk.LabelFrame(preview_container, text="Original Image")
        original_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=5, pady=5)

        self.original_canvas = tk.Canvas(original_frame, bg="#f0f0f0")
        self.original_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Processed image preview
        processed_frame = ttk.LabelFrame(preview_container, text="Processed Image")
        processed_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=5, pady=5)

        self.processed_canvas = tk.Canvas(processed_frame, bg="#f0f0f0")
        self.processed_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Preview controls
        controls_frame = ttk.Frame(self.preview_frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(controls_frame, text="Update Preview", command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(controls_frame, text="Auto Preview", variable=self.preview_var).pack(side=tk.LEFT, padx=5)

    def create_status_bar(self):
        """Create the status bar"""
        self.status_bar = ttk.Frame(self.root, relief=tk.SUNKEN, borderwidth=1)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(self.status_bar, text="Ready")
        self.status_label.pack(side=tk.LEFT, padx=5, pady=2)

        self.progress_bar = ttk.Progressbar(self.status_bar, orient="horizontal", length=200, mode="determinate")
        self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=2)

    def add_creator_info(self):
        """Add creator information to the status bar"""
        creator_label = ttk.Label(self.status_bar, text="Created by Vinay Ahari")
        creator_label.pack(side=tk.RIGHT, padx=10, pady=2)

    def setup_drag_drop(self):
        """Set up drag and drop functionality"""
        try:
            # This will only work on Windows with additional libraries
            if os.name == 'nt':
                self.root.drop_target_register("DND_Files")
                self.root.dnd_bind('<<Drop>>', self.handle_drop)
        except:
            # If drag and drop is not available, just pass
            pass

    def handle_drop(self, event):
        """Handle drag and drop events"""
        files = self.root.tk.splitlist(event.data)
        for file in files:
            if os.path.isfile(file) and file.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp")):
                self.add_to_queue(file)
            elif os.path.isdir(file):
                self.process_folder_path(file)

    def update_recent_files_menu(self):
        """Update the recent files menu"""
        # Clear the menu
        self.recent_menu.delete(0, tk.END)

        # Add recent files
        recent_files = settings.get("recent_files", [])
        if recent_files:
            for file in recent_files:
                self.recent_menu.add_command(label=os.path.basename(file),
                                             command=lambda f=file: self.open_recent_file(f))

            self.recent_menu.add_separator()
            self.recent_menu.add_command(label="Clear Recent Files", command=self.clear_recent_files)
        else:
            self.recent_menu.add_command(label="No Recent Files", state=tk.DISABLED)

    def apply_theme(self, theme_name):
        """Apply the selected theme"""
        if theme_name == "dark":
            # Set dark theme colors
            self.root.configure(bg="#2d2d2d")
            style = ttk.Style()
            style.theme_use("clam")
            style.configure(".", background="#2d2d2d", foreground="#ffffff")
            style.configure("TFrame", background="#2d2d2d")
            style.configure("TLabel", background="#2d2d2d", foreground="#ffffff")
            style.configure("TButton", background="#3d3d3d", foreground="#ffffff")
            style.configure("TCheckbutton", background="#2d2d2d", foreground="#ffffff")
            style.configure("TRadiobutton", background="#2d2d2d", foreground="#ffffff")
            style.configure("TNotebook", background="#2d2d2d", foreground="#ffffff")
            style.configure("TNotebook.Tab", background="#3d3d3d", foreground="#ffffff")

            # Update canvas colors
            self.original_canvas.configure(bg="#3d3d3d")
            self.processed_canvas.configure(bg="#3d3d3d")
        else:
            # Set light theme colors
            self.root.configure(bg="#f0f0f0")
            style = ttk.Style()
            style.theme_use("clam")
            style.configure(".", background="#f0f0f0", foreground="#000000")
            style.configure("TFrame", background="#f0f0f0")
            style.configure("TLabel", background="#f0f0f0", foreground="#000000")
            style.configure("TButton", background="#e0e0e0", foreground="#000000")
            style.configure("TCheckbutton", background="#f0f0f0", foreground="#000000")
            style.configure("TRadiobutton", background="#f0f0f0", foreground="#000000")
            style.configure("TNotebook", background="#f0f0f0", foreground="#000000")
            style.configure("TNotebook.Tab", background="#e0e0e0", foreground="#000000")

            # Update canvas colors
            self.original_canvas.configure(bg="#ffffff")
            self.processed_canvas.configure(bg="#ffffff")

        # Save the theme setting
        settings["theme"] = theme_name
        save_settings(settings)

    # File operations
    def open_file(self):
        """Open a single image file"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.webp;*.tiff;*.bmp")]
        )

        if file_path:
            self.load_image(file_path)
            self.add_to_recent_files(file_path)

    def open_folder(self):
        """Open a folder of images"""
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.process_folder_path(folder_path)

    def open_multiple_files(self):
        """Open multiple image files"""
        file_paths = filedialog.askopenfilenames(
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.webp;*.tiff;*.bmp")]
        )

        if file_paths:
            for file_path in file_paths:
                self.add_to_queue(file_path)

            # Load the first image for preview
            if not self.current_file:
                self.load_image(file_paths[0])

    def open_recent_file(self, file_path):
        """Open a file from the recent files list"""
        if os.path.exists(file_path):
            self.load_image(file_path)
        else:
            messagebox.showerror("File Not Found", f"The file {file_path} no longer exists.")
            # Remove from recent files
            recent_files = settings.get("recent_files", [])
            if file_path in recent_files:
                recent_files.remove(file_path)
                settings["recent_files"] = recent_files
                save_settings(settings)
                self.update_recent_files_menu()

    def add_to_recent_files(self, file_path):
        """Add a file to the recent files list"""
        recent_files = settings.get("recent_files", [])

        # Remove if already exists
        if file_path in recent_files:
            recent_files.remove(file_path)

        # Add to the beginning
        recent_files.insert(0, file_path)

        # Limit to MAX_RECENT
        recent_files = recent_files[:MAX_RECENT]

        # Save to settings
        settings["recent_files"] = recent_files
        save_settings(settings)

        # Update menu
        self.update_recent_files_menu()

    def clear_recent_files(self):
        """Clear the recent files list"""
        settings["recent_files"] = []
        save_settings(settings)
        self.update_recent_files_menu()

    def load_image(self, file_path):
        """Load an image for editing"""
        try:
            self.current_file = file_path
            self.original_image = self.processor.load_image(file_path)

            # Update status
            self.status_label.config(text=f"Loaded: {os.path.basename(file_path)}")

            # Update preview
            self.update_preview()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {str(e)}")

    def process_folder_path(self, folder_path):
        """Process all images in a folder"""
        count = 0
        for filename in os.listdir(folder_path):
            if filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp")):
                file_path = os.path.join(folder_path, filename)
                self.add_to_queue(file_path)
                count += 1

        if count > 0:
            self.status_label.config(text=f"Added {count} images from folder to queue")

            # Load the first image for preview if no image is currently loaded
            if not self.current_file and count > 0:
                for filename in os.listdir(folder_path):
                    if filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp")):
                        self.load_image(os.path.join(folder_path, filename))
                        break
        else:
            messagebox.showinfo("No Images", "No supported image files found in the selected folder.")

    def add_to_queue(self, file_path):
        """Add a file to the processing queue"""
        # Check if already in queue
        for item in self.queue_list.get_children():
            if self.queue_list.item(item, "values")[0] == file_path:
                return

        # Add to queue
        self.queue_list.insert("", "end", values=(file_path, "Pending"))

    def remove_selected(self):
        """Remove selected items from the queue"""
        selected = self.queue_list.selection()
        for item in selected:
            self.queue_list.delete(item)

    def clear_queue(self):
        """Clear the processing queue"""
        for item in self.queue_list.get_children():
            self.queue_list.delete(item)

    def process_queue(self):
        """Process all files in the queue"""
        if self.is_processing:
            messagebox.showinfo("Processing", "Already processing files. Please wait.")
            return

        # Get all files from queue
        files = []
        for item in self.queue_list.get_children():
            file_path = self.queue_list.item(item, "values")[0]
            files.append((item, file_path))

        if not files:
            messagebox.showinfo("Empty Queue", "No files in the processing queue.")
            return

        # Start processing thread
        self.is_processing = True
        threading.Thread(target=self.process_files_thread, args=(files,), daemon=True).start()

    def process_files_thread(self, files):
        """Process files in a separate thread"""
        total = len(files)
        processed = 0
        errors = 0

        # Update progress bar max
        self.root.after(0, lambda: self.progress_bar.configure(maximum=total))

        for item_id, file_path in files:
            if not os.path.exists(file_path):
                self.root.after(0,
                                lambda id=item_id: self.queue_list.item(id, values=(file_path, "File not found")))
                errors += 1
                continue

            try:
                # Update status
                self.root.after(0, lambda: self.status_label.config(
                    text=f"Processing {os.path.basename(file_path)}..."))
                self.root.after(0, lambda id=item_id: self.queue_list.item(id, values=(file_path, "Processing")))

                # Load image
                img = self.processor.load_image(file_path)

                # Get processing options
                options = self.get_processing_options()

                # Process image
                result = self.processor.process_image(img, options)

                # Get output path
                output_path = self.get_output_path(file_path)

                # Save image
                self.processor.save_image(
                    result,
                    output_path,
                    self.output_format_var.get(),
                    self.output_quality_var.get(),
                    self.output_optimize_var.get(),
                    self.preserve_metadata_var.get()
                )

                # Update queue item
                self.root.after(0, lambda id=item_id: self.queue_list.item(id, values=(file_path, "Completed")))
                processed += 1

            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")
                self.root.after(0, lambda id=item_id, err=str(e): self.queue_list.item(id, values=(
                    file_path, f"Error: {err[:20]}...")))
                errors += 1

            # Update progress
            self.root.after(0, lambda p=processed: self.progress_bar.configure(value=p))

        # Update status when done
        status_text = f"Completed: {processed} files processed"
        if errors > 0:
            status_text += f", {errors} errors"

        self.root.after(0, lambda: self.status_label.config(text=status_text))
        self.is_processing = False

    def process_current(self):
        """Process and save the current image"""
        if not self.current_file:
            messagebox.showinfo("No Image", "Please open an image first.")
            return

        try:
            # Get processing options
            options = self.get_processing_options()

            # Process image
            result = self.processor.process_image(self.original_image, options)

            # Get output path
            output_path = self.get_output_path(self.current_file)

            # Save image
            saved_path = self.processor.save_image(
                result,
                output_path,
                self.output_format_var.get(),
                self.output_quality_var.get(),
                self.output_optimize_var.get(),
                self.preserve_metadata_var.get()
            )

            messagebox.showinfo("Success", f"Image saved to:\n{saved_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process image: {str(e)}")

    def save_current_image(self):
        """Save the current processed image"""
        if not self.current_file or not self.processor.processed_image:
            messagebox.showinfo("No Image", "Please open and process an image first.")
            return

        try:
            # Get default filename
            directory = os.path.dirname(self.current_file)
            filename = os.path.basename(self.current_file)
            base_name, _ = os.path.splitext(filename)
            default_filename = f"{base_name}_converted.{self.output_format_var.get()}"

            # Ask for save location
            output_path = filedialog.asksaveasfilename(
                initialdir=directory,
                initialfile=default_filename,
                defaultextension=f".{self.output_format_var.get()}",
                filetypes=[
                    ("PNG files", "*.png"),
                    ("JPEG files", "*.jpg"),
                    ("WebP files", "*.webp"),
                    ("TIFF files", "*.tiff"),
                    ("BMP files", "*.bmp"),
                    ("All files", "*.*")
                ]
            )

            if output_path:
                # Save image
                self.processor.save_image(
                    self.processor.processed_image,
                    output_path,
                    self.output_format_var.get(),
                    self.output_quality_var.get(),
                    self.output_optimize_var.get(),
                    self.preserve_metadata_var.get()
                )

                messagebox.showinfo("Success", f"Image saved to:\n{output_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save image: {str(e)}")

    def get_processing_options(self):
        """Get all processing options as a dictionary"""
        try:
            width = int(self.width_var.get()) if self.resize_var.get() and self.width_var.get() else 0
            height = int(self.height_var.get()) if self.resize_var.get() and self.height_var.get() else 0
        except ValueError:
            width, height = 0, 0

        return {
            "background_mode": self.bg_mode_var.get(),
            "custom_color": self.custom_color_rgb,
            "tolerance": self.tolerance_var.get(),
            "resize": self.resize_var.get(),
            "width": width,
            "height": height,
            "crop": self.crop_var.get(),
            "crop_left": self.crop_left_var.get(),
            "crop_top": self.crop_top_var.get(),
            "crop_right": self.crop_right_var.get(),
            "crop_bottom": self.crop_bottom_var.get(),
            "invert_colors": self.invert_colors_var.get(),
            "adjust_alpha": self.adjust_alpha_var.get(),
            "alpha_value": self.alpha_value_var.get(),
            "replace_background": self.replace_bg_var.get(),
            "replacement_color": self.replacement_color_rgb
        }

    def get_output_path(self, input_path):
        """Generate output path based on settings"""
        directory = os.path.dirname(input_path)
        filename = os.path.basename(input_path)
        base_name, _ = os.path.splitext(filename)

        # Get output directory
        if self.custom_output_var.get() and self.output_dir_var.get():
            output_dir = self.output_dir_var.get()
            # Save the last used directory
            settings["last_output_dir"] = output_dir
            save_settings(settings)
        else:
            output_dir = os.path.join(directory, "converted")

        # Create directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Generate filename using pattern
        pattern = self.naming_pattern_var.get()
        if not pattern:
            pattern = "{filename}_converted"

        # Replace variables in pattern
        now = datetime.now()
        counter = 1

        output_filename = pattern.replace("{filename}", base_name)
        output_filename = output_filename.replace("{date}", now.strftime("%Y%m%d"))
        output_filename = output_filename.replace("{time}", now.strftime("%H%M%S"))
        output_filename = output_filename.replace("{counter}", str(counter))

        # Add extension
        output_filename = f"{output_filename}.{self.output_format_var.get()}"

        # Full path
        output_path = os.path.join(output_dir, output_filename)

        # Handle file exists
        if not self.overwrite_var.get() and os.path.exists(output_path):
            counter = 1
            while os.path.exists(output_path):
                output_filename = pattern.replace("{filename}", base_name)
                output_filename = output_filename.replace("{date}", now.strftime("%Y%m%d"))
                output_filename = output_filename.replace("{time}", now.strftime("%H%M%S"))
                output_filename = output_filename.replace("{counter}", str(counter))
                output_filename = f"{output_filename}.{self.output_format_var.get()}"
                output_path = os.path.join(output_dir, output_filename)
                counter += 1

        return output_path

    # UI event handlers
    def update_preview(self):
        """Update the image preview"""
        if not self.current_file or not self.original_image:
            return

        if not self.preview_var.get():
            return

        try:
            # Clear canvases
            self.original_canvas.delete("all")
            self.processed_canvas.delete("all")

            # Get original preview
            original_preview = self.processor.get_image_preview(self.original_image)
            if original_preview:
                self.original_preview = original_preview  # Keep reference to prevent garbage collection
                self.original_canvas.create_image(
                    self.original_canvas.winfo_width() // 2,
                    self.original_canvas.winfo_height() // 2,
                    image=self.original_preview
                )

            # Process image with current settings
            options = self.get_processing_options()
            processed = self.processor.process_image(self.original_image, options)
            self.processor.processed_image = processed  # Store for later use

            # Get processed preview
            processed_preview = self.processor.get_image_preview(processed)
            if processed_preview:
                self.processed_preview = processed_preview  # Keep reference to prevent garbage collection
                self.processed_canvas.create_image(
                    self.processed_canvas.winfo_width() // 2,
                    self.processed_canvas.winfo_height() // 2,
                    image=self.processed_preview
                )

        except Exception as e:
            print(f"Preview error: {str(e)}")

    def toggle_preview(self):
        """Toggle automatic preview"""
        if self.preview_var.get():
            self.update_preview()

    def toggle_resize(self):
        """Enable/disable resize fields"""
        state = "normal" if self.resize_var.get() else "disabled"
        for widget in self.settings_frame.winfo_children():
            if isinstance(widget, ttk.Entry) and (
                    widget.winfo_name() == "width" or widget.winfo_name() == "height"):
                widget.configure(state=state)

        self.update_preview()

    def toggle_crop(self):
        """Enable/disable crop controls"""
        state = "normal" if self.crop_var.get() else "disabled"
        # Enable/disable crop sliders
        for widget in self.advanced_frame.winfo_children():
            if isinstance(widget, ttk.Scale) and widget.winfo_name().startswith("crop_"):
                widget.configure(state=state)

        self.update_preview()

    def toggle_alpha(self):
        """Enable/disable alpha slider"""
        state = "normal" if self.adjust_alpha_var.get() else "disabled"
        # Enable/disable alpha slider
        for widget in self.advanced_frame.winfo_children():
            if isinstance(widget, ttk.Scale) and widget.winfo_name() == "alpha":
                widget.configure(state=state)

        self.update_preview()

    def toggle_bg_replacement(self):
        """Enable/disable background replacement controls"""
        state = "normal" if self.replace_bg_var.get() else "disabled"
        # Enable/disable background color picker
        for widget in self.advanced_frame.winfo_children():
            if isinstance(widget, ttk.Button) and widget.winfo_name() == "bg_color_picker":
                widget.configure(state=state)

        self.update_preview()

    def pick_color(self):
        """Open color picker for background color"""
        color = colorchooser.askcolor(initialcolor=self.custom_color_var.get())
        if color[1]:  # If color is selected (not canceled)
            self.custom_color_var.set(color[1])
            self.custom_color_rgb = color[0]
            self.color_preview.configure(background=color[1])
            self.update_preview()

    def pick_bg_color(self):
        """Open color picker for replacement background color"""
        color = colorchooser.askcolor(initialcolor=self.replacement_color_var.get())
        if color[1]:  # If color is selected (not canceled)
            self.replacement_color_var.set(color[1])
            self.replacement_color_rgb = color[0]
            self.bg_color_preview.configure(background=color[1])
            self.update_preview()

    def browse_output_dir(self):
        """Browse for output directory"""
        directory = filedialog.askdirectory(initialdir=self.output_dir_var.get() or os.path.expanduser("~"))
        if directory:
            self.output_dir_var.set(directory)

    # Preset management
    def save_preset(self):
        """Save current settings as a preset"""
        preset_name = simpledialog.askstring("Save Preset", "Enter a name for this preset:")
        if preset_name:
            # Get current settings
            preset = {
                "background_mode": self.bg_mode_var.get(),
                "custom_color": self.custom_color_var.get(),
                "tolerance": self.tolerance_var.get(),
                "invert_colors": self.invert_colors_var.get(),
                "resize": self.resize_var.get(),
                "width": self.width_var.get(),
                "height": self.height_var.get(),
                "crop": self.crop_var.get(),
                "crop_left": self.crop_left_var.get(),
                "crop_top": self.crop_top_var.get(),
                "crop_right": self.crop_right_var.get(),
                "crop_bottom": self.crop_bottom_var.get(),
                "adjust_alpha": self.adjust_alpha_var.get(),
                "alpha_value": self.alpha_value_var.get(),
                "replace_background": self.replace_bg_var.get(),
                "replacement_color": self.replacement_color_var.get(),
                "output_format": self.output_format_var.get(),
                "output_quality": self.output_quality_var.get(),
                "output_optimize": self.output_optimize_var.get()
            }

            # Save to settings
            presets = settings.get("presets", {})
            presets[preset_name] = preset
            settings["presets"] = presets
            save_settings(settings)

            # Update presets menu
            self.update_presets_menu()

            messagebox.showinfo("Preset Saved", f"Preset '{preset_name}' has been saved.")

    def load_preset(self, preset_name):
        """Load a preset"""
        presets = settings.get("presets", {})

        # Default presets
        default_presets = {
            "logo_black": {
                "background_mode": "black",
                "tolerance": 15,
                "invert_colors": True,
                "resize": False,
                "crop": False,
                "adjust_alpha": False,
                "replace_background": False,
                "output_format": "png",
                "output_quality": 95,
                "output_optimize": True
            },
            "logo_white": {
                "background_mode": "white",
                "tolerance": 15,
                "invert_colors": True,
                "resize": False,
                "crop": False,
                "adjust_alpha": False,
                "replace_background": False,
                "output_format": "png",
                "output_quality": 95,
                "output_optimize": True
            },
            "product": {
                "background_mode": "white",
                "tolerance": 25,
                "invert_colors": False,
                "resize": True,
                "width": "800",
                "height": "800",
                "crop": False,
                "adjust_alpha": False,
                "replace_background": True,
                "replacement_color": "#FFFFFF",
                "output_format": "png",
                "output_quality": 90,
                "output_optimize": True
            }
        }

        # Get preset (from saved or default)
        preset = presets.get(preset_name, default_presets.get(preset_name))

        if not preset:
            messagebox.showerror("Error", f"Preset '{preset_name}' not found.")
            return

        # Apply preset settings
        self.bg_mode_var.set(preset.get("background_mode", "black"))
        self.custom_color_var.set(preset.get("custom_color", "#000000"))
        self.tolerance_var.set(preset.get("tolerance", 15))
        self.invert_colors_var.set(preset.get("invert_colors", True))
        self.resize_var.set(preset.get("resize", False))
        self.width_var.set(preset.get("width", ""))
        self.height_var.set(preset.get("height", ""))
        self.crop_var.set(preset.get("crop", False))
        self.crop_left_var.set(preset.get("crop_left", 0))
        self.crop_top_var.set(preset.get("crop_top", 0))
        self.crop_right_var.set(preset.get("crop_right", 100))
        self.crop_bottom_var.set(preset.get("crop_bottom", 100))
        self.adjust_alpha_var.set(preset.get("adjust_alpha", False))
        self.alpha_value_var.set(preset.get("alpha_value", 255))
        self.replace_bg_var.set(preset.get("replace_background", False))
        self.replacement_color_var.set(preset.get("replacement_color", "#FFFFFF"))
        self.output_format_var.set(preset.get("output_format", "png"))
        self.output_quality_var.set(preset.get("output_quality", 95))
        self.output_optimize_var.set(preset.get("output_optimize", True))

        # Update UI states
        self.toggle_resize()
        self.toggle_crop()
        self.toggle_alpha()
        self.toggle_bg_replacement()

        # Update preview
        self.update_preview()

        self.status_label.config(text=f"Loaded preset: {preset_name}")

    def update_presets_menu(self):
        """Update the presets menu with saved presets"""
        # Clear user presets
        for i in range(self.presets_menu.index("end") - 3):
            self.presets_menu.delete(3)

        # Add saved presets
        presets = settings.get("presets", {})
        for preset_name in presets:
            self.presets_menu.add_command(label=preset_name,
                                          command=lambda name=preset_name: self.load_preset(name))

    def manage_presets(self):
        """Open a dialog to manage presets"""
        presets = settings.get("presets", {})
        if not presets:
            messagebox.showinfo("No Presets", "You don't have any saved presets.")
            return

        # Create preset manager dialog
        preset_manager = tk.Toplevel(self.root)
        preset_manager.title("Manage Presets")
        preset_manager.geometry("300x300")
        preset_manager.resizable(False, False)
        preset_manager.transient(self.root)
        preset_manager.grab_set()

        # Create listbox for presets
        preset_list = tk.Listbox(preset_manager)
        preset_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Add presets to listbox
        for preset_name in presets:
            preset_list.insert(tk.END, preset_name)

        # Create buttons
        button_frame = ttk.Frame(preset_manager)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Load",
                   command=lambda: self.load_preset_from_manager(preset_list, preset_manager)).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete",
                   command=lambda: self.delete_preset(preset_list)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close",
                   command=preset_manager.destroy).pack(side=tk.RIGHT, padx=5)

    def load_preset_from_manager(self, preset_list, manager):
        """Load a preset from the preset manager"""
        selection = preset_list.curselection()
        if selection:
            preset_name = preset_list.get(selection[0])
            manager.destroy()
            self.load_preset(preset_name)

    def delete_preset(self, preset_list):
        """Delete a preset"""
        selection = preset_list.curselection()
        if selection:
            preset_name = preset_list.get(selection[0])
            confirm = messagebox.askyesno("Confirm Delete",
                                          f"Are you sure you want to delete the preset '{preset_name}'?")
            if confirm:
                presets = settings.get("presets", {})
                if preset_name in presets:
                    del presets[preset_name]
                    settings["presets"] = presets
                    save_settings(settings)
                    preset_list.delete(selection[0])
                    self.update_presets_menu()

    # Preferences and help
    def show_preferences(self):
        """Show preferences dialog"""
        prefs = tk.Toplevel(self.root)
        prefs.title("Preferences")
        prefs.geometry("400x300")
        prefs.resizable(False, False)
        prefs.transient(self.root)
        prefs.grab_set()

        # Create notebook for preference tabs
        pref_notebook = ttk.Notebook(prefs)
        pref_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # General tab
        general_frame = ttk.Frame(pref_notebook)
        pref_notebook.add(general_frame, text="General")

        # Theme selection
        theme_frame = ttk.LabelFrame(general_frame, text="Theme")
        theme_frame.pack(fill=tk.X, padx=10, pady=5)

        theme_var = StringVar(value=settings.get("theme", "light"))
        ttk.Radiobutton(theme_frame, text="Light Theme", variable=theme_var,
                        value="light").pack(anchor="w", padx=10, pady=2)
        ttk.Radiobutton(theme_frame, text="Dark Theme", variable=theme_var,
                        value="dark").pack(anchor="w", padx=10, pady=2)

        # Default format
        format_frame = ttk.LabelFrame(general_frame, text="Default Output Format")
        format_frame.pack(fill=tk.X, padx=10, pady=5)

        format_var = StringVar(value=settings.get("default_format", "png"))
        ttk.Radiobutton(format_frame, text="PNG", variable=format_var,
                        value="png").pack(anchor="w", padx=10, pady=2)
        ttk.Radiobutton(format_frame, text="JPEG", variable=format_var,
                        value="jpg").pack(anchor="w", padx=10, pady=2)
        ttk.Radiobutton(format_frame, text="WebP", variable=format_var,
                        value="webp").pack(anchor="w", padx=10, pady=2)

        # File handling tab
        file_frame = ttk.Frame(pref_notebook)
        pref_notebook.add(file_frame, text="File Handling")

        # Metadata option
        metadata_var = BooleanVar(value=settings.get("preserve_metadata", True))
        ttk.Checkbutton(file_frame, text="Preserve image metadata by default",
                        variable=metadata_var).pack(anchor="w", padx=10, pady=5)

        # Overwrite option
        overwrite_var = BooleanVar(value=settings.get("overwrite_existing", False))
        ttk.Checkbutton(file_frame, text="Overwrite existing files by default",
                        variable=overwrite_var).pack(anchor="w", padx=10, pady=5)

        # Default naming pattern
        naming_frame = ttk.LabelFrame(file_frame, text="Default Naming Pattern")
        naming_frame.pack(fill=tk.X, padx=10, pady=5)

        naming_var = StringVar(value=settings.get("custom_naming", "{filename}_converted"))
        ttk.Entry(naming_frame, textvariable=naming_var).pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(naming_frame, text="Available variables: {filename}, {date}, {time}, {counter}").pack(
            anchor="w", padx=10, pady=2)

        # Save button
        def save_preferences():
            settings["theme"] = theme_var.get()
            settings["default_format"] = format_var.get()
            settings["preserve_metadata"] = metadata_var.get()
            settings["overwrite_existing"] = overwrite_var.get()
            settings["custom_naming"] = naming_var.get()
            save_settings(settings)

            # Apply theme
            self.apply_theme(theme_var.get())

            # Update variables
            self.output_format_var.set(format_var.get())
            self.preserve_metadata_var.set(metadata_var.get())
            self.overwrite_var.set(overwrite_var.get())
            self.naming_pattern_var.set(naming_var.get())

            prefs.destroy()
            messagebox.showinfo("Preferences", "Preferences have been saved.")

        ttk.Button(prefs, text="Save", command=save_preferences).pack(side=tk.RIGHT, padx=10, pady=10)
        ttk.Button(prefs, text="Cancel", command=prefs.destroy).pack(side=tk.RIGHT, padx=0, pady=10)

    def show_documentation(self):
        """Show documentation"""
        # Try to open documentation in web browser
        try:
            webbrowser.open("https://github.com/vinayahari/image-converter/docs")
        except:
            # If web browser can't be opened, show documentation in a dialog
            doc = tk.Toplevel(self.root)
            doc.title("Documentation")
            doc.geometry("600x500")
            doc.transient(self.root)

            # Create text widget with scrollbar
            text_frame = ttk.Frame(doc)
            text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            scrollbar = ttk.Scrollbar(text_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            text = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set)
            text.pack(fill=tk.BOTH, expand=True)
            scrollbar.config(command=text.yview)

            # Add documentation text
            documentation = """
                            # Background Remover and Color Inverter

    ## Basic Usage

    1. Open an image file using File > Open File or the "Open File" button.
    2. Select the background type (black, white, or custom color).
    3. Adjust the tolerance slider to control how much of the background is removed.
    4. Check "Invert Colors" if you want to invert the colors of the non-background areas.
    5. Click "Process & Save" to save the processed image.

    ## Advanced Features

        ### Resize

    Check "Resize Image" and enter the desired width and height in pixels.

    ### Crop

    Check "Crop Image" and use the sliders to adjust the crop area.

    ### Transparency

    Check "Adjust Transparency" and use the slider to control the overall transparency.

    ### Background Replacement

    Check "Replace Background" and choose a color to replace the transparent areas.

    ## Batch Processing

    1. Add multiple files to the queue using File > Open Multiple Files.
    2. Configure your processing settings.
    3. Click "Process All" to process all files in the queue.

    ## Presets

    Save your current settings as a preset using Edit > Presets > Save Current Settings as Preset.
    Load a preset using Edit > Presets and selecting the preset name.

    ## Output Options

    - Choose the output format (PNG, JPEG, WebP, etc.)
    - Adjust quality settings for JPEG and WebP
    - Set custom output directory
    - Configure file naming pattern
            """

            text.insert(tk.END, documentation)
            text.config(state=tk.DISABLED)

            ttk.Button(doc, text="Close", command=doc.destroy).pack(pady=10)

    def show_about(self):
        """Show about dialog"""
        about = tk.Toplevel(self.root)
        about.title("About")
        about.geometry("400x300")
        about.resizable(False, False)
        about.transient(self.root)
        about.grab_set()

        # App icon
        try:
            if os.name == 'nt':  # Windows
                logo = tk.PhotoImage(file='icon.png')
                logo_label = ttk.Label(about, image=logo)
                logo_label.image = logo  # Keep a reference
                logo_label.pack(pady=10)
            else:  # Linux/Mac
                logo = tk.PhotoImage(file='icon.png')
                logo_label = ttk.Label(about, image=logo)
                logo_label.image = logo  # Keep a reference
                logo_label.pack(pady=10)
        except:
            pass

        # App info
        ttk.Label(about, text="Background Remover and Color Inverter",
                  font=("Helvetica", 14, "bold")).pack(pady=5)
        ttk.Label(about, text=f"Version {APP_VERSION}").pack()
        ttk.Label(about, text="Created by Vinay Ahari").pack(pady=5)

        # Description
        description = ttk.Label(about, text="A tool for removing backgrounds from images and inverting colors.",
                                wraplength=350, justify="center")
        description.pack(pady=10)

        # Close button
        ttk.Button(about, text="Close", command=about.destroy).pack(pady=10)


def main():
    root = tk.Tk()
    app = App(root)
    root.mainloop()

    # Save settings on exit
    save_settings(settings)


if __name__ == "__main__":
    main()