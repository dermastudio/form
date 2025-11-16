import os
import smtplib
import io
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS  # برای اجازه دادن به گیت‌هاب که با Render صحبت کند
from PIL import Image

# --- برای ارسال ایمیل ---
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

app = Flask(__name__)

# --- تنظیمات امنیتی (CORS) ---
# به سایت شما اجازه می‌دهد تا از این بک‌اند استفاده کند
# !!! آدرس دامنه اصلی سایت خود را اینجا وارد کنید
ALLOWED_ORIGINS = ["https://dermastudiofficial.com", "http://127.0.0.1:5500"]
CORS(app, resources={r"/submit": {"origins": ALLOWED_ORIGINS}})


# --- تنظیمات ایمیل (از متغیرهای محیطی خوانده می‌شود) ---
# این مقادیر را مستقیماً در کد وارد نکنید!
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = os.environ.get('studiodermaofficial@gmail.com') # ایمیل فرستنده (مثلاً جیمیل شما)
EMAIL_PASS = os.environ.get('EMAIL_PASS') # پسورد اپلیکیشن جیمیل (App Password)
EMAIL_RECEIVER = os.environ.get('studiodermaofficial@gmail.com') # ایمیلی که می‌خواهید فرم را دریافت کند

MAX_FILE_SIZE_MB = 2
COMPRESS_QUALITY = 75 # کیفیت فشرده‌سازی (بین ۰ تا ۹۵)


def compress_image(file_storage):
    """
    فایل تصویر را دریافت می‌کند، اگر بزرگتر از حد مجاز بود،
    آن را فشرده می‌کند و به صورت بایت برمی‌گرداند.
    """
    # فایل را در حافظه (RAM) می‌خوانیم
    img_bytes = file_storage.read()
    file_storage.seek(0) # پوینتر فایل را برای خواندن‌های بعدی ریست می‌کنیم

    # اگر حجم فایل کمتر از حد مجاز بود، همان را برگردان
    if len(img_bytes) / (1024 * 1024) <= MAX_FILE_SIZE_MB:
        print("Image size is OK. No compression needed.")
        return img_bytes, file_storage.filename

    print(f"Image is too large. Compressing...")
    
    try:
        img = Image.open(io.BytesIO(img_bytes))
        
        # اگر فرمت‌هایی مثل GIF بود که ممکن است پیچیده باشند، به JPEG تبدیل کن
        if img.format not in ['JPEG', 'PNG', 'WEBP']:
            img = img.convert('RGB')

        # فایل را در حافظه فشرده می‌کنیم
        output_buffer = io.BytesIO()
        img.save(output_buffer, format='JPEG', quality=COMPRESS_QUALITY, optimize=True)
        
        compressed_bytes = output_buffer.getvalue()
        
        # نام فایل جدید با پسوند .jpg
        original_filename = os.path.splitext(file_storage.filename)[0]
        new_filename = f"{original_filename}_compressed.jpg"

        print(f"Original size: {len(img_bytes) / (1024*1024):.2f} MB")
        print(f"Compressed size: {len(compressed_bytes) / (1024*1024):.2f} MB")
        
        return compressed_bytes, new_filename
    
    except Exception as e:
        print(f"Error compressing image: {e}")
        # اگر فشرده‌سازی شکست خورد، همان فایل اصلی را برگردان
        return img_bytes, file_storage.filename


def send_email_with_attachment(form_data, file_bytes, filename):
    """
    اطلاعات فرم و فایل پیوست را ایمیل می‌کند.
    """
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = f"رزرو وقت جدید از سایت: {form_data.get('نام کامل', 'ناشناس')}"

        # --- ساخت بدنه ایمیل از روی اطلاعات فرم ---
        body = "یک فرم رزرو جدید ثبت شد:\n\n"
        for key, value in form_data.items():
            body += f"{key}: {value}\n"
        
        msg.attach(MIMEText(body, 'plain', 'utf-8')) # مهم: utf-8 برای فارسی

        # --- پیوست کردن فایل ---
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(file_bytes)
        encoders.encode_base64(part)
        # مهم: برای نمایش صحیح نام فایل فارسی در ایمیل
        part.add_header('Content-Disposition', 'attachment', filename=('utf-8', '', filename))
        msg.attach(part)

        # --- ارسال ایمیل ---
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, EMAIL_RECEIVER, msg.as_string())
        server.quit()
        
        print("Email sent successfully!")
        return True
    
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


@app.route('/submit', methods=['POST'])
def handle_form():
    if not all([EMAIL_USER, EMAIL_PASS, EMAIL_RECEIVER]):
        return jsonify({"error": "تنظیمات سمت سرور کامل نیست."}), 500

    try:
        # ۱. دریافت اطلاعات متنی فرم
        form_data = request.form.to_dict()

        # ۲. دریافت فایل تصویر
        if 'فیش واریزی' not in request.files:
            return jsonify({"error": "فیش واریزی ارسال نشده است."}), 400
        
        file = request.files['فیش واریزی']
        
        if file.filename == '':
            return jsonify({"error": "فایل انتخاب نشده است."}), 400

        # ۳. فشرده‌سازی تصویر (اگر لازم باشد)
        compressed_bytes, new_filename = compress_image(file)

        # ۴. ارسال ایمیل
        success = send_email_with_attachment(form_data, compressed_bytes, new_filename)

        if success:
            # ۵. کاربر را به صفحه تشکر برگردان
            # !!! این آدرس را به صفحه "thankyou.html" خود تغییر دهید
            return redirect("https://dermastudiofficial.com/thankyou.html", code=302)
        else:
            return jsonify({"error": "خطا در ارسال ایمیل."}), 500

    except Exception as e:
        print(f"Server error: {e}")
        return jsonify({"error": "خطای داخلی سرور."}), 500

if __name__ == '__main__':
    # این خط فقط برای تست روی سیستم خودتان است
    # Render از gunicorn برای اجرای برنامه استفاده خواهد کرد
    app.run(debug=True, port=5000)