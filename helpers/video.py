import os
import re
import logging
import subprocess

import cv2
import whisper
import Levenshtein
import pytesseract
import numpy as np
from tqdm import tqdm
from videohash import VideoHash, HashAlgorithm

from helpers.utilities import twos_complement, text_post_processing

logger = logging.getLogger("sauron-bot")

class VideoProcessor:
    def __init__(self, filename: str, storage_path: str) -> None:
        self.path = filename
        self.storage_path = storage_path
        self.video = cv2.VideoCapture(filename)

        if not self.video.isOpened():
            logger.error("Could not open video file")
            raise FileNotFoundError
        
        vhash = VideoHash(
            path=filename,
            storage_path=storage_path,
            hash_algorithm=HashAlgorithm.PHASH
        )
        self.hash = twos_complement(vhash.hash_hex, 64)

    def __del__(self) -> None:
        self.video.release()
    
    def __detect_blur_fft(self, image: cv2.Mat, size: int = 60, thresh: int = 10) -> bool:
        # grab the dimensions of the image and use the dimensions to
        # derive the center (x, y)-coordinates
        (h, w) = image.shape
        (cX, cY) = (int(w / 2.0), int(h / 2.0))

        # compute the FFT to find the frequency transform, then shift
        # the zero frequency component (i.e., DC component located at
        # the top-left corner) to the center where it will be more
        # easy to analyze
        fft = np.fft.fft2(image)
        fftShift = np.fft.fftshift(fft)
        
        # zero-out the center of the FFT shift (i.e., remove low
        # frequencies), apply the inverse shift such that the DC
        # component once again becomes the top-left, and then apply
        # the inverse FFT
        fftShift[cY - size:cY + size, cX - size:cX + size] = 0
        fftShift = np.fft.ifftshift(fftShift)
        recon = np.fft.ifft2(fftShift)

        # compute the magnitude spectrum of the reconstructed image,
        # then compute the mean of the magnitude values
        magnitude = 20 * np.log(np.abs(recon))
        mean = np.mean(magnitude)
        
        # the image will be considered "blurry" if the mean value of the
        # magnitudes is less than the threshold value
        return mean <= thresh

    def __detect_shot_transition(self, frame1: cv2.Mat, frame2: cv2.Mat, threshold: float = 0.1) -> bool:
        def calculate_chi_squared_distance(hist1, hist2):
            # Avoid division by zero
            eps = 1e-10
            
            # Calculate chi-squared distance
            chi_squared_distance = 0.5 * np.sum(((hist1 - hist2) ** 2) / (hist1 + hist2 + eps))
            
            return chi_squared_distance
        
        # Convert frames to HSV color space
        hsv1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2HSV)
        hsv2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2HSV)
        
        # Calculate histograms
        hist1 = cv2.calcHist([hsv1], [0, 1], None, [180, 256], [0, 180, 0, 256])
        hist2 = cv2.calcHist([hsv2], [0, 1], None, [180, 256], [0, 180, 0, 256])
        
        # Normalize histograms
        cv2.normalize(hist1, hist1, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(hist2, hist2, 0, 1, cv2.NORM_MINMAX)
        
        # Calculate chi-squared distance
        distance = calculate_chi_squared_distance(hist1, hist2)
        
        # Check if distance exceeds the threshold
        return distance > threshold

    def ocr(self) -> str:
        full_text = ""
        frame_count = 0
        last_frame_text = ""
        frames_text = []
        
        ret, last_frame = self.video.read()
        while True:
            # read a frame from the video
            ret, frame = self.video.read()
            frame_count += 1
            logger.debug(f"Frame [{frame_count}] read: {ret}")

            # break the loop if the video has ended
            if not ret:
                break

            # skip the frame if it is not a shot transition
            is_shot_transition = self.__detect_shot_transition(last_frame, frame)
            logger.debug(f"\tShot transition: {is_shot_transition}")
            if not is_shot_transition:
                continue

            # convert the frame to grayscale and detect if the frame is
            # considered blurry or not
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            is_blurry = self.__detect_blur_fft(gray, thresh=15)
            logger.debug(f"\tBlurry: {is_blurry}")

            # skip the frame if it is blurry
            if is_blurry:
                continue

            # swap channel ordering and OCR it
            text = pytesseract.image_to_string(frame)
            logger.debug(f"\tRaw OCR text: {text}")

            # skip the frame if the text is empty
            if text == "":
                continue
            
            # process the text
            text = text_post_processing(text)
            frames_text.append(text)
            logger.debug(f"\tProcessed OCR text: {text}")

            # skip the frame if the text is similar to the last frame
            dist = Levenshtein.distance(text, last_frame_text)
            logger.debug(f"\tLevenshtein distance to last frame: {dist}")
            if dist > 5:
                continue

            # append the text to the full text
            full_text += text + "\n"
            logger.debug(f"\tNew full text: {full_text}")
            
            # update the last frame text
            last_frame_text = text
            last_frame = frame
        
        print(frames_text)
        return full_text

    def transcribe(self) -> str:
        audio_path = os.path.join(self.storage_path, "".join(i for i in self.path.split("\\")[-1].split(".")[0:-1]) + ".wav")
        cmd = f"ffmpeg -y -i {self.path} -ab 160k -ac 2 -ar 44100 -vn {audio_path}"
        process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)

        progress_bar = None
        for line in process.stderr:
            if "Duration" in line:
                duration = re.search(r"Duration: (.*?),", line).group(1)
                h, m, s = map(float, duration.split(':'))
                total_seconds = h*3600 + m*60 + s
                progress_bar = tqdm(total=total_seconds, ncols=80, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}')

            if progress_bar and 'time=' in line:
                time = re.search(r"time=(.*?)[.]", line).group(1)
                h, m, s = map(float, time.split(':'))
                elapsed_seconds = h*3600 + m*60 + s
                progress_bar.n = elapsed_seconds
                progress_bar.refresh()

        if os.path.exists(audio_path):
            model: whisper.Whisper = whisper.load_model("base")
            result = model.transcribe(audio_path)
        else:
            result = {"text": ""}
        return result["text"]
    
    def check_hash_similarity(self, hash1: VideoHash, hash2: VideoHash, threshold: int = 10):
        hamming_distance = hash1 - hash2
        similar = hamming_distance <= threshold
        return similar
