import os
import unicodedata
import markdown2
import time  # Import time for unique filenames
from flask import Flask, request, jsonify, send_file, render_template
from google import genai
from google.genai import types
from xhtml2pdf import pisa

app = Flask(__name__, template_folder='.')

# Ensure API key is stored securely
# API_KEY = os.environ.get("API_KEY")
API_KEY = "AIzaSyB6AcJTFLbIh3p4AMgFHze6QY7uChH8WR8"

# Directories for file storage
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def convert_html_to_pdf(html_string, pdf_path):
    """Converts HTML content to a PDF file."""
    with open(pdf_path, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(html_string, dest=pdf_file)
    return not pisa_status.err


def markdown_to_pdf(markdown_text, output_filename):
    """Converts Markdown content into a PDF file."""
    text = unicodedata.normalize("NFKD", markdown_text).encode("ascii", "ignore").decode("ascii")
    html_text = markdown2.markdown(text, extras=["tables", "fenced-code-blocks"])

    success = convert_html_to_pdf(html_text, output_filename)
    if success:
        print(f"[INFO] PDF successfully created: {output_filename}")
    else:
        print("[ERROR] PDF generation failed.")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate():
    """Handles requests to generate study notes from a user-uploaded PDF."""
    if "pdf_file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    pdf_file = request.files["pdf_file"]

    if pdf_file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    # Save uploaded file
    pdf_path = os.path.join(UPLOAD_FOLDER, pdf_file.filename)
    pdf_file.save(pdf_path)
    print(f"[INFO] File uploaded successfully: {pdf_path}")

    # Generate a unique output PDF filename
    timestamp = int(time.time())  # Get current time as an integer
    output_pdf = os.path.join(OUTPUT_FOLDER, f"Generated_Notes_{timestamp}.pdf")

    print("[INFO] Connecting to Google GenAI API...")
    client = genai.Client(api_key=API_KEY)

    print(f"[INFO] Uploading file to AI: {pdf_path}")
    files = [client.files.upload(file=pdf_path)]

    model = "gemini-2.0-flash"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_uri(file_uri=files[0].uri, mime_type=files[0].mime_type),
                types.Part.from_text(
                    text=(
                        "From the given PDF, create structured study notes for the subject "
                        "of the. Organize content module-wise, summarize complex topics, "
                        "highlight key points and concepts."
                    )
                ),
            ],
        ),
    ]

    print("[INFO] Generating content using AI model...")
    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        top_p=0.95,
        top_k=40,
        max_output_tokens=8192,
        response_mime_type="text/plain",
    )

    output = client.models.generate_content(model=model, contents=contents, config=generate_content_config)

    if not output.text:
        print("[ERROR] AI model did not generate content.")
        return jsonify({"error": "AI model did not generate any content."}), 500

    print("[INFO] Converting AI output to PDF...")
    markdown_to_pdf(output.text, output_pdf)

    print(f"[SUCCESS] PDF successfully created: {output_pdf}")
    return send_file(f"./output/Generated_Notes_{timestamp}.pdf", as_attachment=True)


if __name__ == "__main__":
    print("[INFO] Starting Flask server...")
    app.run(debug=False, host="0.0.0.0", port=5000)
