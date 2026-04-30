#!/usr/bin/env python3
"""
Web-based face registration with HTTPS support
Access from phone: https://pi_ip:5000
"""

from flask import Flask, render_template_string, request, jsonify
from face_recognizer import FaceRecognizer
import cv2
import numpy as np
import base64
from io import BytesIO
from PIL import Image
import os

app = Flask(__name__)

# Initialize face recognizer
recognizer = FaceRecognizer(
    model_path="models/mobilefacenet.tflite",
    detection_confidence=0.7,
    recognition_threshold=0.7,
    use_averaged_embedding=True,
    strict_quality_check=False
)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Face Registration - Phone Camera</title>
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            color: white;
            min-height: 100vh;
            padding: 10px;
        }
        
        .container {
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        
        h1 { 
            color: #00ff88; 
            text-align: center;
            margin-bottom: 10px;
            font-size: 28px;
        }
        
        .subtitle {
            text-align: center;
            color: #888;
            margin-bottom: 30px;
            font-size: 14px;
        }
        
        .input-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            color: #00ff88;
            font-weight: 600;
        }
        
        input[type="text"] { 
            width: 100%;
            padding: 15px;
            font-size: 16px;
            border: 2px solid #4d4d4d;
            border-radius: 10px;
            background: #2d2d2d;
            color: white;
        }
        
        input[type="text"]:focus {
            outline: none;
            border-color: #00ff88;
        }
        
        .camera-container {
            position: relative;
            width: 100%;
            max-width: 500px;
            margin: 20px auto;
            border-radius: 15px;
            overflow: hidden;
            border: 3px solid #00ff88;
            background: #000;
        }
        
        video, canvas {
            width: 100%;
            height: auto;
            display: block;
        }
        
        canvas { display: none; }
        
        .camera-overlay {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 70%;
            height: 70%;
            border: 3px dashed rgba(0, 255, 136, 0.5);
            border-radius: 50%;
            pointer-events: none;
        }
        
        .instruction {
            text-align: center;
            padding: 15px;
            background: rgba(0, 255, 136, 0.1);
            border-radius: 10px;
            margin: 20px 0;
            font-size: 18px;
            font-weight: 600;
            color: #00ff88;
        }
        
        .progress {
            text-align: center;
            font-size: 24px;
            margin: 15px 0;
            color: #fff;
        }
        
        .progress .count {
            color: #00ff88;
            font-weight: bold;
            font-size: 32px;
        }
        
        button { 
            width: 100%;
            padding: 18px;
            font-size: 18px;
            font-weight: bold;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            margin: 10px 0;
            transition: all 0.3s;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #00ff88 0%, #00cc77 100%);
            color: #1a1a1a;
            box-shadow: 0 4px 15px rgba(0, 255, 136, 0.3);
        }
        
        .btn-primary:active {
            transform: scale(0.98);
        }
        
        .btn-secondary {
            background: #4d4d4d;
            color: white;
        }
        
        .btn-capture {
            background: linear-gradient(135deg, #4a90e2 0%, #357abd 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(74, 144, 226, 0.3);
        }
        
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        #status { 
            padding: 20px;
            margin: 20px 0;
            border-radius: 12px;
            text-align: center;
            font-size: 16px;
            min-height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .status-success {
            background: rgba(0, 255, 136, 0.2);
            border: 2px solid #00ff88;
            color: #00ff88;
        }
        
        .status-error {
            background: rgba(255, 68, 68, 0.2);
            border: 2px solid #ff4444;
            color: #ff4444;
        }
        
        .status-warning {
            background: rgba(245, 166, 35, 0.2);
            border: 2px solid #f5a623;
            color: #f5a623;
        }
        
        .status-info {
            background: rgba(74, 144, 226, 0.2);
            border: 2px solid #4a90e2;
            color: #4a90e2;
        }
        
        .hidden { display: none !important; }
        
        .preview-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 10px;
            margin: 20px 0;
        }
        
        .preview-item {
            aspect-ratio: 1;
            border-radius: 8px;
            overflow: hidden;
            border: 2px solid #4d4d4d;
            position: relative;
        }
        
        .preview-item.captured {
            border-color: #00ff88;
        }
        
        .preview-item img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .preview-item.empty {
            background: #2d2d2d;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            color: #4d4d4d;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .capturing {
            animation: pulse 0.5s ease-in-out;
        }

        .permission-help {
            background: rgba(245, 166, 35, 0.2);
            border: 2px solid #f5a623;
            color: #f5a623;
            padding: 15px;
            border-radius: 10px;
            margin: 15px 0;
            font-size: 14px;
        }

        .permission-help strong {
            display: block;
            margin-bottom: 10px;
            font-size: 16px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📸 Face Registration</h1>
        <div class="subtitle">Use your phone camera</div>
        
        <!-- Step 1: Enter Name -->
        <div id="step1">
            <div class="input-group">
                <label>👤 Person's Name</label>
                <input type="text" id="personName" placeholder="Enter full name" autocomplete="off">
            </div>
            <button class="btn-primary" onclick="requestCameraPermission()">📷 Start Camera</button>
            
            <div id="permissionHelp" class="permission-help hidden">
                <strong>⚠️ Camera Permission Required</strong>
                <p>Please allow camera access when your browser asks.</p>
                <p>If blocked, click the 🔒 lock icon in your browser's address bar to allow camera.</p>
            </div>
        </div>
        
        <!-- Step 2: Capture Photos -->
        <div id="step2" class="hidden">
            <div class="instruction" id="instruction">
                📸 Look straight at camera
            </div>
            
            <div class="progress">
                <span class="count"><span id="captureCount">0</span>/5</span> samples captured
            </div>
            
            <div class="preview-grid" id="previewGrid">
                <div class="preview-item empty">1</div>
                <div class="preview-item empty">2</div>
                <div class="preview-item empty">3</div>
                <div class="preview-item empty">4</div>
                <div class="preview-item empty">5</div>
            </div>
            
            <div class="camera-container">
                <video id="video" autoplay playsinline></video>
                <div class="camera-overlay"></div>
                <canvas id="canvas"></canvas>
            </div>
            
            <button class="btn-capture" id="captureBtn" onclick="capturePhoto()">
                📸 CAPTURE
            </button>
            <button class="btn-secondary" onclick="cancelRegistration()">
                ❌ Cancel
            </button>
        </div>
        
        <div id="status"></div>
    </div>
    
    <script>
        let video, canvas, ctx;
        let capturedImages = [];
        let currentStep = 0;
        let personName = '';
        
        const instructions = [
            "📸 Look straight at camera",
            "⬅️ Turn your head LEFT",
            "➡️ Turn your head RIGHT",
            "⬆️ Tilt your head UP slightly",
            "⬇️ Tilt your head DOWN slightly"
        ];
        
        async function requestCameraPermission() {
            personName = document.getElementById('personName').value.trim();
            
            if (!personName) {
                showStatus('Please enter a name first!', 'error');
                return;
            }

            // Show permission help
            document.getElementById('permissionHelp').classList.remove('hidden');
            showStatus('⏳ Requesting camera permission...', 'info');
            
            try {
                // Request camera permission explicitly
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: {
                        facingMode: 'user',
                        width: { ideal: 1280 },
                        height: { ideal: 960 }
                    },
                    audio: false
                });
                
                // Permission granted!
                startCamera(stream);
                
            } catch (error) {
                console.error('Camera error:', error);
                
                let errorMessage = '';
                
                if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
                    errorMessage = '❌ Camera permission denied! Please click "Allow" when asked.';
                } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
                    errorMessage = '❌ No camera found on your device!';
                } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
                    errorMessage = '❌ Camera is in use by another app. Please close other camera apps.';
                } else if (error.name === 'OverconstrainedError') {
                    errorMessage = '❌ Camera does not support required settings.';
                } else if (error.name === 'SecurityError') {
                    errorMessage = '❌ HTTPS required for camera access. Ask admin to enable SSL.';
                } else {
                    errorMessage = `❌ Camera error: ${error.message}`;
                }
                
                showStatus(errorMessage, 'error');
                document.getElementById('permissionHelp').classList.remove('hidden');
            }
        }
        
        function startCamera(stream) {
            video = document.getElementById('video');
            canvas = document.getElementById('canvas');
            ctx = canvas.getContext('2d');
            
            video.srcObject = stream;
            
            document.getElementById('step1').classList.add('hidden');
            document.getElementById('step2').classList.remove('hidden');
            
            showStatus('✅ Camera ready! Position your face and tap CAPTURE', 'success');
        }
        
        async function capturePhoto() {
            if (!video || !video.srcObject) {
                showStatus('❌ Camera not ready!', 'error');
                return;
            }
            
            // Animate capture
            document.querySelector('.camera-container').classList.add('capturing');
            setTimeout(() => {
                document.querySelector('.camera-container').classList.remove('capturing');
            }, 500);
            
            // Capture image
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            ctx.drawImage(video, 0, 0);
            
            const imageData = canvas.toDataURL('image/jpeg', 0.9);
            
            // Show in preview
            updatePreview(currentStep, imageData);
            
            showStatus('⏳ Validating quality...', 'info');
            
            // Send to server for validation
            try {
                const response = await fetch('/validate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        image: imageData.split(',')[1],
                        step: currentStep
                    })
                });
                
                const result = await response.json();
                
                if (result.valid) {
                    // Accept sample
                    capturedImages.push(imageData);
                    currentStep++;
                    
                    document.getElementById('captureCount').textContent = currentStep;
                    
                    showStatus(`✅ Sample ${currentStep}/5 accepted! (Quality: ${result.quality})`, 'success');
                    
                    if (currentStep < 5) {
                        document.getElementById('instruction').textContent = instructions[currentStep];
                    } else {
                        // All samples captured - submit
                        await submitRegistration();
                    }
                } else {
                    // Reject sample - retry same step
                    showStatus(`❌ ${result.message} - Please retake!`, 'error');
                    
                    // Remove from preview
                    setTimeout(() => {
                        updatePreview(currentStep, null);
                    }, 1500);
                }
                
            } catch (error) {
                showStatus('❌ Error validating image', 'error');
            }
        }
        
        function updatePreview(index, imageData) {
            const previewItem = document.querySelectorAll('.preview-item')[index];
            
            if (imageData) {
                previewItem.innerHTML = `<img src="${imageData}" alt="Sample ${index + 1}">`;
                previewItem.classList.add('captured');
            } else {
                previewItem.innerHTML = index + 1;
                previewItem.classList.remove('captured');
            }
        }
        
        async function submitRegistration() {
            showStatus('💾 Saving to database...', 'info');
            document.getElementById('captureBtn').disabled = true;
            
            try {
                const response = await fetch('/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        name: personName,
                        images: capturedImages.map(img => img.split(',')[1])
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showStatus(`🎉 Successfully registered ${personName}!`, 'success');
                    
                    // Stop camera
                    if (video && video.srcObject) {
                        video.srcObject.getTracks().forEach(track => track.stop());
                    }
                    
                    // Reset after 3 seconds
                    setTimeout(() => {
                        location.reload();
                    }, 3000);
                } else {
                    showStatus(`❌ Registration failed: ${result.message}`, 'error');
                    document.getElementById('captureBtn').disabled = false;
                }
                
            } catch (error) {
                showStatus('❌ Error submitting registration', 'error');
                document.getElementById('captureBtn').disabled = false;
            }
        }
        
        function cancelRegistration() {
            if (video && video.srcObject) {
                video.srcObject.getTracks().forEach(track => track.stop());
            }
            location.reload();
        }
        
        function showStatus(message, type) {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = `status-${type}`;
        }

        // Check camera permission on page load
        window.addEventListener('load', async () => {
            try {
                const result = await navigator.permissions.query({ name: 'camera' });
                
                if (result.state === 'denied') {
                    document.getElementById('permissionHelp').classList.remove('hidden');
                }
                
                result.addEventListener('change', () => {
                    if (result.state === 'granted') {
                        document.getElementById('permissionHelp').classList.add('hidden');
                    }
                });
            } catch (e) {
                // Permission API not supported
                console.log('Permission API not supported');
            }
        });
    </script>
</body>
</html>
'''

# [Keep all the route handlers the same as before]
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/validate', methods=['POST'])
def validate_image():
    try:
        data = request.json
        image_base64 = data['image']
        
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(BytesIO(image_bytes))
        image_rgb = np.array(image.convert('RGB'))
        
        faces = recognizer.detect_faces(image_rgb)
        
        if not faces:
            return jsonify({'valid': False, 'message': 'No face detected', 'quality': '0%'})
        
        face = max(faces, key=lambda f: f['bbox'][2] * f['bbox'][3])
        face_img = recognizer.extract_face_region(image_rgb, face['bbox'])
        
        is_valid, message, quality = recognizer.validate_face_sample(face_img)
        
        return jsonify({
            'valid': is_valid,
            'message': message,
            'quality': f'{int(quality * 100)}%'
        })
        
    except Exception as e:
        return jsonify({'valid': False, 'message': f'Error: {str(e)}', 'quality': '0%'})

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.json
        name = data['name']
        images_base64 = data['images']
        
        face_images = []
        
        for img_base64 in images_base64:
            image_bytes = base64.b64decode(img_base64)
            image = Image.open(BytesIO(image_bytes))
            image_rgb = np.array(image.convert('RGB'))
            
            faces = recognizer.detect_faces(image_rgb)
            if faces:
                face = max(faces, key=lambda f: f['bbox'][2] * f['bbox'][3])
                face_img = recognizer.extract_face_region(image_rgb, face['bbox'])
                if face_img is not None:
                    face_images.append(face_img)
        
        if len(face_images) >= 3:
            success = recognizer.add_faces(face_images, name)
            
            if success:
                return jsonify({'success': True, 'message': f'Registered {name}'})
        
        return jsonify({'success': False, 'message': 'Not enough valid samples'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


def generate_self_signed_cert():
    """Generate self-signed SSL certificate"""
    from OpenSSL import crypto
    
    # Create key pair
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)
    
    # Create certificate
    cert = crypto.X509()
    cert.get_subject().C = "IN"
    cert.get_subject().O = "EAMS"
    cert.get_subject().CN = "localhost"
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(365*24*60*60)  # Valid for 1 year
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(key, 'sha256')
    
    # Save certificate and key
    with open("cert.pem", "wb") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    
    with open("key.pem", "wb") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
    
    print("✓ SSL certificate generated")


if __name__ == '__main__':
    print("=" * 60)
    print("🌐 Phone Camera Registration Server with HTTPS")
    print("=" * 60)
    
    # Check if SSL certificate exists
    if not os.path.exists('cert.pem') or not os.path.exists('key.pem'):
        print("\n🔐 Generating SSL certificate...")
        try:
            generate_self_signed_cert()
        except ImportError:
            print("❌ PyOpenSSL not installed. Installing...")
            os.system("pip install pyopenssl")
            generate_self_signed_cert()
    
    print(f"\n📱 Access from phone:")
    print(f"   https://YOUR_PI_IP:5000")
    print(f"\n⚠️  Browser will show security warning - click 'Advanced' → 'Proceed'")
    print(f"🔧 Server starting...\n")
    
    # Run with SSL
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        ssl_context=('cert.pem', 'key.pem')
    )
