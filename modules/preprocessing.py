"""
Advanced Image Preprocessing Module
Handles illumination normalization and noise reduction
"""

import cv2
import numpy as np


class ImagePreprocessor:
    """
    Advanced preprocessing for face images
    - Illumination normalization (Histogram Equalization, Gamma Correction, MSR)
    - Noise reduction
    - Sharpening
    """
    
    def __init__(self, method='histogram'):
        """
        Args:
            method: 'histogram', 'gamma', 'clahe', 'msr', or 'weber'
        """
        self.method = method
        
    def normalize_illumination(self, image_rgb):
        """
        Normalize illumination in RGB image
        
        Args:
            image_rgb: RGB image (H, W, 3)
            
        Returns:
            Normalized RGB image
        """
        if self.method == 'histogram':
            return self._histogram_equalization(image_rgb)
        elif self.method == 'gamma':
            return self._gamma_correction(image_rgb)
        elif self.method == 'clahe':
            return self._clahe_equalization(image_rgb)
        elif self.method == 'msr':
            return self._multi_scale_retinex(image_rgb)
        elif self.method == 'weber':
            return self._weber_face(image_rgb)
        else:
            return image_rgb
    
    def _histogram_equalization(self, image_rgb):
        """Standard histogram equalization in YUV space"""
        yuv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2YUV)
        yuv[:,:,0] = cv2.equalizeHist(yuv[:,:,0])
        return cv2.cvtColor(yuv, cv2.COLOR_YUV2RGB)
    
    def _gamma_correction(self, image_rgb, gamma=1.2):
        """
        Gamma correction for brightness adjustment
        gamma > 1: brighten dark regions
        gamma < 1: darken bright regions
        """
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 
                          for i in range(256)]).astype("uint8")
        return cv2.LUT(image_rgb, table)
    
    def _clahe_equalization(self, image_rgb):
        """
        CLAHE (Contrast Limited Adaptive Histogram Equalization)
        Better than standard histogram equalization
        """
        lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)
        
        # Apply CLAHE to L channel
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        lab[:,:,0] = clahe.apply(lab[:,:,0])
        
        return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    
    def _multi_scale_retinex(self, image_rgb):
        """
        Multi-Scale Retinex (MSR) for illumination normalization
        Handles varying lighting conditions
        """
        def single_scale_retinex(img, sigma):
            """Single scale retinex"""
            retinex = np.log10(img + 1.0) - np.log10(cv2.GaussianBlur(img, (0, 0), sigma) + 1.0)
            return retinex
        
        # Convert to float
        img_float = image_rgb.astype(np.float32) + 1.0
        
        # Apply MSR on each channel
        scales = [15, 80, 250]
        msr = np.zeros_like(img_float)
        
        for channel in range(3):
            for sigma in scales:
                msr[:,:,channel] += single_scale_retinex(img_float[:,:,channel], sigma)
            msr[:,:,channel] /= len(scales)
        
        # Normalize to 0-255
        msr = (msr - msr.min()) / (msr.max() - msr.min()) * 255
        return msr.astype(np.uint8)
    
    def _weber_face(self, image_rgb):
        """
        Weber-face descriptor for illumination invariance
        Based on Weber's law of perception
        """
        gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
        
        # Compute local average using Gaussian blur
        local_avg = cv2.GaussianBlur(gray, (5, 5), 2)
        
        # Weber contrast
        weber = (gray - local_avg) / (local_avg + 1e-6)
        
        # Normalize
        weber = (weber - weber.min()) / (weber.max() - weber.min() + 1e-6) * 255
        weber = weber.astype(np.uint8)
        
        # Convert back to RGB
        return cv2.cvtColor(weber, cv2.COLOR_GRAY2RGB)
    
    def reduce_noise(self, image_rgb, method='bilateral'):
        """
        Reduce noise in image
        
        Args:
            image_rgb: RGB image
            method: 'bilateral', 'gaussian', 'nlmeans'
            
        Returns:
            Denoised image
        """
        if method == 'bilateral':
            # Preserves edges while smoothing
            return cv2.bilateralFilter(image_rgb, 9, 75, 75)
        
        elif method == 'gaussian':
            return cv2.GaussianBlur(image_rgb, (5, 5), 0)
        
        elif method == 'nlmeans':
            # Non-local means denoising (slower but better)
            return cv2.fastNlMeansDenoisingColored(image_rgb, None, 10, 10, 7, 21)
        
        return image_rgb
    
    def sharpen(self, image_rgb):
        """
        Sharpen image to enhance edges
        """
        kernel = np.array([[-1,-1,-1],
                          [-1, 9,-1],
                          [-1,-1,-1]])
        return cv2.filter2D(image_rgb, -1, kernel)
    
    def preprocess(self, image_rgb, denoise=True, sharpen=False):
        """
        Complete preprocessing pipeline
        
        Args:
            image_rgb: Input RGB image
            denoise: Apply denoising
            sharpen: Apply sharpening
            
        Returns:
            Preprocessed image
        """
        # Illumination normalization
        img = self.normalize_illumination(image_rgb)
        
        # Noise reduction
        if denoise:
            img = self.reduce_noise(img, method='bilateral')
        
        # Sharpening
        if sharpen:
            img = self.sharpen(img)
        
        return img
