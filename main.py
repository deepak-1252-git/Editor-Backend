from flask import Flask, request, send_from_directory, jsonify
from PIL import Image
from pdf2image import convert_from_path,pdfinfo_from_path
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from docx import Document
from pdf2docx import Converter  
from werkzeug.utils import secure_filename
from playwright.sync_api import sync_playwright 
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer, SquareModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
import zipfile
import os, time, uuid

app = Flask(__name__)
# ---Cors
from flask_cors import CORS
CORS(app, resources={r"/*": {"origins": "*"}}) 

# Security: Limit file size to 16MB
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  
UPLOAD_FOLDER = "/tmp"
OUTPUT_FOLDER = "/tmp"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'bmp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_size(size_kb):
    if size_kb < 1024:
        return f"{round(size_kb, 2)} KB"
    elif size_kb < 1024 * 1024:
        return f"{round(size_kb / 1024, 2)} MB"
    return f"{round(size_kb / (1024 * 1024), 2)} GB"

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

# ----------------- ROUTES ------------------------

@app.route('/')
def health_check():
    return jsonify({"status": "Backend is running lala!"})

# -----------------------------------------------------
@app.route('/resizer', methods=['POST'])
def resize_image():
    delete_old_files(OUTPUT_FOLDER)
     
    file = request.files.get('image')
    raw_width = request.form.get('width')
    raw_height = request.form.get('height')

    if not (file and raw_width and raw_height):
        return jsonify({"error": "Missing data"}), 400

    try:
        width, height = int(raw_width), int(raw_height)
        if width <= 0 or height <= 0: raise ValueError
        
        if allowed_file(file.filename):
            ext = os.path.splitext(file.filename)[1]
            unique_name = f"resized_{uuid.uuid4().hex}{ext}"
            output_path = os.path.join(OUTPUT_FOLDER, unique_name)
            
            img = Image.open(file)
            resized = img.resize((width, height), Image.Resampling.LANCZOS)
            resized.save(output_path)

            return jsonify({
                "filename": unique_name,
                "file_size": round(os.path.getsize(output_path) / 1024, 2),
                "resolution": resized.size
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 400
# ----------------------------------------------------
@app.route('/compressor', methods=['POST'])
def compress_image():
    delete_old_files(OUTPUT_FOLDER)
     
    file = request.files.get('image')
    target_size = request.form.get('target_size')

    if not file or not target_size:
        return jsonify({"error": "Missing data"}), 400
    
    try:
        target_size = int(target_size)
        img = Image.open(file)
        original_size_kb = len(file.read()) / 1024
        file.seek(0) # Reset file pointer after reading size

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        unique_name = f"comp_{uuid.uuid4().hex}.jpg"
        output_path = os.path.join(OUTPUT_FOLDER, unique_name)

        quality = 90
        while quality > 10:
            img.save(output_path, "JPEG", quality=quality, optimize=True)
            if os.path.getsize(output_path) / 1024 <= target_size:
                break
            quality -= 5

        comp_size_kb = os.path.getsize(output_path) / 1024
        return jsonify({
            "filename": unique_name,
            "original_size": format_size(original_size_kb),
            "compressed_size": format_size(comp_size_kb),
            "reduction": round(((original_size_kb - comp_size_kb) / original_size_kb) * 100, 2)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# ----------------------------------------------------------------
@app.route('/convertor', methods=['POST'])
def convert_all_types():
    delete_old_files(OUTPUT_FOLDER)
     
    files = request.files.getlist('image')
    convert_type = request.form.get('type')
    if not files or not convert_type: return jsonify({"error": "Missing data"}), 400

    output_files = []
    format_map = {
        'png-to-jpg': ('JPEG', 'jpg'),
        'jpg-to-png': ('PNG', 'png'),
        'to-webp': ('WEBP', 'webp'),
        'to-bmp': ('BMP', 'bmp'),
        'to-gif': ('GIF', 'gif'),
        'single_img_to_single_pdf': ('PDF', 'pdf'),
    }

    try:
        if convert_type == "multi_img_to_single_pdf":
            image_list = []
            for f in files:
                img = Image.open(f).convert("RGB")
                image_list.append(img)
            out_name = f"merged_{uuid.uuid4().hex}.pdf"
            image_list[0].save(os.path.join(OUTPUT_FOLDER, out_name), save_all=True, append_images=image_list[1:])
            output_files.append({"name": out_name, "type": "PDF"})

        elif convert_type == "html-to-pdf":
            for f in files:
                temp_path = os.path.join(UPLOAD_FOLDER, secure_filename(f.filename))
                f.save(temp_path)
                out_name = f"conv_{uuid.uuid4().hex}.pdf"
                out_path = os.path.join(OUTPUT_FOLDER, out_name)

                with sync_playwright() as p:
                    browser = p.chromium.launch()
                    page = browser.new_page()
                     
                    with open(temp_path, 'r', encoding='utf-8') as html_file:
                        page.set_content(html_file.read(), wait_until="networkidle")
                    page.pdf(path=out_path, format="A4")
                    browser.close()

                output_files.append({"name": out_name, "type": "pdf"})
                os.remove(temp_path)

        elif convert_type == "pdf-to-word":
            for f in files:
                temp_path = os.path.join(UPLOAD_FOLDER, secure_filename(f.filename))
                f.save(temp_path)
                out_name = f"doc_{uuid.uuid4().hex}.docx"
                out_path = os.path.join(OUTPUT_FOLDER, out_name)
                
                cv = Converter(temp_path)
                cv.convert(out_path, start=0, end=None)
                cv.close()
                
                output_files.append({"name": out_name, "type": "DOCX"})
                os.remove(temp_path)

        elif convert_type == "pdf-to-img":
            for f in files:
                temp_path = os.path.join(UPLOAD_FOLDER, secure_filename(f.filename))
                f.save(temp_path)

                info = pdfinfo_from_path(temp_path)
                max_pages = info["Pages"]

                images = convert_from_path(temp_path, first_page=1, last_page=max_pages)
                for i, image in enumerate(images):
                    out_name = f"conv_p{i+1}_{uuid.uuid4().hex}.jpg"
                    image.save(os.path.join(OUTPUT_FOLDER, out_name), "JPEG")
                    output_files.append({"name": out_name, "type": "JPG"})
                os.remove(temp_path)

        else:
            pill_format, extension = format_map.get(convert_type, (None, None))
            if pill_format:
                for f in files:
                    img = Image.open(f)
                    if pill_format in ["JPEG", "PDF"] and img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    out_name = f"conv_{uuid.uuid4().hex}.{extension}"
                    img.save(os.path.join(OUTPUT_FOLDER, out_name), pill_format)
                    output_files.append({"name": out_name, "type": extension.upper()})

            else : 
                return jsonify({"error": "Unsupported conversion type"}), 400

# --------------------for zip file--------------------------
        if len(output_files) > 1:
             
            zip_name = f"zip_export_{uuid.uuid4().hex}.zip"
            zip_path = os.path.join(OUTPUT_FOLDER, zip_name)
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for file_info in output_files:
                    file_path = os.path.join(OUTPUT_FOLDER, file_info['name'])
                    
                    zipf.write(file_path, arcname=file_info['name'])
            
            return jsonify({"files": [{"name": zip_name, "type": "ZIP"}]})
        else:
            return jsonify({"files": output_files})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
# --------------------------------------------------------------------
@app.route('/pdf_tool', methods=['POST'])
def pdf_tool():
    delete_old_files(OUTPUT_FOLDER)

    files = request.files.getlist('pdfs')
    pdf_type = request.form.get('type')
    try:
        output_filename = f"pdf_{uuid.uuid4().hex}.pdf"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        if pdf_type == "merge-pdf":
            merger = PdfMerger()
            for f in files: merger.append(f)
            merger.write(output_path)
            merger.close()

        elif pdf_type == "split-pdf":
            reader = PdfReader(files[0])
            writer = PdfWriter()
            page_val = request.form.get('page', '1')
            if '-' in page_val:
                start, end = map(int, page_val.split('-'))
                for i in range(start-1, min(end, len(reader.pages))):
                    writer.add_page(reader.pages[i])
            else:
                writer.add_page(reader.pages[int(page_val)-1])
            with open(output_path, "wb") as f: writer.write(f)

        elif pdf_type == "lock-pdf":
            reader = PdfReader(files[0])
            writer = PdfWriter()
            for page in reader.pages: writer.add_page(page)
            writer.encrypt(request.form.get('password'))
            with open(output_path, "wb") as f: writer.write(f)

        return jsonify({"filename": output_filename, "type": "PDF"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# ---------------------------------------------------------------
@app.route('/crop_rotate', methods=['POST'])
def crop_rotate():
    delete_old_files(OUTPUT_FOLDER)
     
    file = request.files.get('image')
    if file:
        try:
            img = Image.open(file)
            if img.mode != 'RGB': img = img.convert('RGB')
            name = f"edit_{uuid.uuid4().hex}.jpg"
            img.save(os.path.join(OUTPUT_FOLDER, name), "JPEG", quality=95)
            return jsonify({"filename": name})
        except Exception as e: return jsonify({"error": str(e)}), 500
# ---------------------------------------------------------------------
@app.route('/generate_qr', methods=['POST'])
def generate_qr():
    delete_old_files(OUTPUT_FOLDER)
    
    data = request.json 
    qr_text = data.get('text')
    fill_hex = data.get('color', '#000000')
    back_hex = data.get('bg_color', '#ffffff')
    qr_type = data.get('qr_type', 'square')
    
    if not qr_text:
        return jsonify({"error": "No text provided"}), 400
        
    try:
        fill_rgb = hex_to_rgb(fill_hex)
        back_rgb = hex_to_rgb(back_hex)

        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(qr_text)
        qr.make(fit=True)
        
        if qr_type == 'rounded':
            drawer = RoundedModuleDrawer()
        else:
            drawer = SquareModuleDrawer()

        img = qr.make_image(
            image_factory=StyledPilImage, 
            module_drawer=drawer,
            color_mask=SolidFillColorMask(back_color=back_rgb , fill_color=fill_rgb)
        )
        
        name = f"qr_{uuid.uuid4().hex}.png"
        img.save(os.path.join(OUTPUT_FOLDER, name))
        
        return jsonify({"filename": name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- SECURE SERVING ---
@app.route('/outputs/<filename>')
def get_output_file(filename):
    # secure_filename prevents path traversal attacks
    return send_from_directory(OUTPUT_FOLDER, secure_filename(filename))

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, secure_filename(filename), as_attachment=True)

def delete_old_files(folder_path, minutes=5):
    """Clean up old files to save disk space."""
    now = time.time()
    cutoff = now - (minutes * 60)
    try:
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff:
                os.remove(file_path)
    except Exception as e:
        print(f"Cleanup error: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)