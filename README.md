# Enhanced Image Converter

A powerful tool for removing backgrounds from images, inverting colors, and batch processing with multiple output formats.

![image](https://github.com/user-attachments/assets/73022e02-1720-49b3-be66-c63d4abf9e42)


## Features

- **Background Removal**: Automatically remove black, white, or custom color backgrounds
- **Color Inversion**: Invert colors of non-background areas
- **Transparency Control**: Adjust alpha channel for semi-transparent effects
- **Resize & Crop**: Easily resize and crop images
- **Background Replacement**: Replace transparent areas with custom colors
- **Batch Processing**: Process multiple images at once
- **Multiple Output Formats**: Save as PNG, JPEG, WebP, TIFF, or BMP
- **Custom Presets**: Save and load your favorite settings
- **Theme Support**: Light and dark interface themes

## Installation

1. Ensure you have Python 3.6 or higher installed
2. Install required dependencies:
   ```
   pip install Pillow
   ```
3. Download the latest release or clone the repository:
   ```
   git clone https://github.com/vinayhr5/enhanced-image-converter.git
   ```

## Usage

### Basic Usage

1. Run the application:
   ```
   python enhanced_image_converter.py
   ```
2. Open an image file using File > Open File or the "Open File" button
3. Select the background type (black, white, or custom color)
4. Adjust the tolerance slider to control how much of the background is removed
5. Check "Invert Colors" if you want to invert the colors of the non-background areas
6. Click "Process & Save" to save the processed image

### Advanced Features

#### Resize
- Check "Resize Image" and enter the desired width and height in pixels

#### Crop
- Check "Crop Image" and use the sliders to adjust the crop area

#### Transparency
- Check "Adjust Transparency" and use the slider to control the overall transparency

#### Background Replacement
- Check "Replace Background" and choose a color to replace the transparent areas

### Batch Processing

1. Add multiple files to the queue using File > Open Multiple Files
2. Configure your processing settings
3. Click "Process All" to process all files in the queue

### Presets

- Save your current settings as a preset using Edit > Presets > Save Current Settings as Preset
- Load a preset using Edit > Presets and selecting the preset name
- Default presets include:
  - Logo on Black
  - Logo on White
  - Product Image

### Output Options

- Choose the output format (PNG, JPEG, WebP, etc.)
- Adjust quality settings for JPEG and WebP
- Set custom output directory
- Configure file naming pattern with variables like {filename}, {date}, {time}, {counter}

## Configuration

The application saves your settings in `~/.image_converter_settings.json`, including:
- Recent files
- Presets
- Last output directory
- Theme preference
- Default output format

## Known Issues

- Drag and drop may not work on all platforms
- Large images may require significant processing time

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- Created by Vinay Ahari
- Uses Pillow library for image processing
