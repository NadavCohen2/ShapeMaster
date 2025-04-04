import cv2
import numpy as np
import time
import os
import random
import math
from PIL import Image
import pygame

# Initialize pygame mixer for audio handling
pygame.mixer.init()

# Music files used during different time intervals in the game
music_5sec = "music_5sec.mp3"
music_20sec = "music_20sec.mp3"

#############################################################################
#                               PARAMETERS
#############################################################################

WINDOW_NAME = "Game Interface"  # Name of the main window
TIME_LIMIT = 15  # Time limit (seconds) for each stage
BOTTOM_BAR_RATIO = 0.1  # Percentage of the screen height reserved for the bottom bar

DRAW_COLOR = (0, 0, 0)  # Color used when drawing (black)
ERASE_COLOR = (255, 255, 255)  # Color used when erasing (white)
ERASE_RADIUS = 10  # Radius of the eraser effect

STAGES = ["easy", "medium", "hard"]  # Game difficulty stages
face_cascade = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")  # Face detection classifier

# Global flag used to show debug windows (masks, etc.) if desired
show_debug = False


#############################################################################
#                     PERFORMANCE MESSAGE HELPERS
#############################################################################

# Returns a message describing performance at the end of each stage
def get_stage_performance_message(stage, stage_score):
    # Check score thresholds and return an encouraging message
    if stage_score >= 80:
        return f"Masterful! Your skills shine!"
    elif stage_score >= 50:
        return f"Nice work! You're getting there!"
    else:
        return f"Keep practicing! Improvement is on the way!"


# Returns a final message based on total accumulated score
def get_final_performance_message(total_score):
    # Check total score thresholds for a final performance message
    if total_score >= 250:
        return "Legendary performance! You're a true artist!"
    elif total_score >= 150:
        return "Great job! You're on the right track!"
    else:
        return "Keep honing your skills and try again!"


#############################################################################
#                       TEXT DISPLAY UTILITY
#############################################################################

# Draws text with a simple shadow effect on the given image
def draw_interesting_text(img, text, pos, font_scale, color, thickness=2):
    shadow_color = (0, 0, 0)  # Shadow color is black
    shadow_offset = (2, 2)  # Slight offset for the shadow
    shadow_pos = (pos[0] + shadow_offset[0], pos[1] + shadow_offset[1])

    # First draw shadow text
    cv2.putText(
        img, text, shadow_pos,
        cv2.FONT_HERSHEY_SIMPLEX, font_scale,
        shadow_color, thickness + 2, cv2.LINE_AA
    )
    # Then draw main text on top
    cv2.putText(
        img, text, pos,
        cv2.FONT_HERSHEY_SIMPLEX, font_scale,
        color, thickness, cv2.LINE_AA
    )


#############################################################################
#                       FILE / IMAGE UTILITIES
#############################################################################

# Chooses and returns a path to a random image from a specified directory
def choose_random_image(dir_path="pictures"):
    if not os.path.exists(dir_path):
        print(f"Directory '{dir_path}' does not exist.")
        return None

    # Filter only valid image files
    all_files = os.listdir(dir_path)
    image_files = [f for f in all_files if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))]
    if not image_files:
        print(f"No valid image files in '{dir_path}'")
        return None

    chosen = random.choice(image_files)  # Randomly pick an image
    chosen_path = os.path.join(dir_path, chosen)
    print(f"Chosen random image from '{dir_path}': {chosen_path}")
    return chosen_path


# Loads an image from a path and applies Canny edge detection
def load_edge_image(image_path):
    if image_path is None:
        return None
    img = cv2.imread(image_path)
    if img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)  # Convert to grayscale
    gray = cv2.GaussianBlur(gray, (5, 5), 0)  # Slightly blur image
    edges = cv2.Canny(gray, 30, 100)  # Apply Canny to detect edges
    return edges


# Returns the bounding box (xmin, ymin, xmax, ymax) of a binary mask
def get_bounding_box_of_mask(mask):
    coords = np.argwhere(mask != 0)
    if coords.size == 0:
        return None
    y_vals = coords[:, 0]
    x_vals = coords[:, 1]
    ymin, ymax = y_vals.min(), y_vals.max()
    xmin, xmax = x_vals.min(), x_vals.max()
    return (xmin, ymin, xmax, ymax)


# Crops an image to the given bounding box
def crop_to_bounding_box(img, bbox):
    (xmin, ymin, xmax, ymax) = bbox
    return img[ymin:ymax + 1, xmin:xmax + 1]


# Returns a canvas with only the user's drawn lines (non-white) copied
def create_user_drawing(canvas):
    h, w = canvas.shape[:2]
    # Identify all non-white pixels
    mask = (canvas != [255, 255, 255]).any(axis=2)
    user_drawing = np.ones((h, w, 3), dtype=np.uint8) * 255
    user_drawing[mask] = canvas[mask]
    return user_drawing


#############################################################################
#                    correlation_score
#############################################################################

# Compares user's drawing and reference edges, returns a score and some masks
def correlation_score(user_img, ref_img, dilation_size=10, factor=1.1, iter=6):
    # Ensure we have single-channel versions
    if len(user_img.shape) == 3:
        user_gray = cv2.cvtColor(user_img, cv2.COLOR_BGR2GRAY)
    else:
        user_gray = user_img

    if len(ref_img.shape) == 3:
        ref_gray = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)
    else:
        ref_gray = ref_img

    ref_gray = cv2.bitwise_not(ref_gray)  # Invert the reference edges
    _, user_bin = cv2.threshold(user_gray, 127, 255, cv2.THRESH_BINARY_INV)
    _, ref_bin = cv2.threshold(ref_gray, 127, 255, cv2.THRESH_BINARY_INV)

    # Dilate both user and reference images to allow for small inaccuracies
    user_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation_size, dilation_size))
    ref_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation_size, dilation_size))
    user_dil = cv2.dilate(user_bin, user_kernel, iterations=iter)
    ref_dil = cv2.dilate(ref_bin, ref_kernel, iterations=iter)

    # Calculate overlap vs union to get similarity score
    overlap = np.sum((user_dil == 255) & (ref_dil == 255))
    union = np.sum((user_dil == 255) | (ref_dil == 255))
    accuracy = 0.0 if union == 0 else float(overlap) / float(union)

    accuracy_percent = accuracy * 100.0
    final_score = min(accuracy_percent * factor, 100.0)  # Weighted factor, then capped at 100%
    return final_score, user_dil, ref_dil, user_bin, ref_bin


#############################################################################
#                    HAND TRACKING FUNCTIONS
#############################################################################

calibration_done = False
auto_calib_interval = 70  # Frequency (frames) at which we auto-calibrate
frame_count = 0

# Variables to store skin color ranges in different color spaces
lower_skin_hsv, upper_skin_hsv = None, None
lower_skin_ycrcb, upper_skin_ycrcb = None, None

last_finger_point = None  # Stores last fingertip position for drawing lines
use_kalman = True  # Flag to use Kalman filter or not
kalman = None
smoothed_center = None

roi_x, roi_y, roi_w, roi_h = None, None, None, None


# Initializes and configures a Kalman filter
def init_kalman_filter():
    kf = cv2.KalmanFilter(4, 2)  # 4 state variables, 2 measurements (x, y)

    # Transition matrix: basic constant velocity model
    kf.transitionMatrix = np.array([
        [1, 0, 1, 0],
        [0, 1, 0, 1],
        [0, 0, 1, 0],
        [0, 0, 0, 1]
    ], dtype=np.float32)

    # Maps measurements (x, y) into the state (x, y)
    kf.measurementMatrix = np.array([
        [1, 0, 0, 0],
        [0, 1, 0, 0]
    ], dtype=np.float32)

    # Noise covariance values
    kf.processNoiseCov = np.eye(4, dtype=np.float32) * 1e-3
    kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 1e-2
    kf.errorCovPost = np.eye(4, dtype=np.float32)
    return kf


# Sets the Kalman filter's initial position for the state
def set_kalman_position(kf, x, y):
    kf.statePost = np.array([[x], [y], [0], [0]], dtype=np.float32)


# Updates the Kalman filter with new measurements and returns filtered position
def update_kalman(kf, measured_x, measured_y):
    pred = kf.predict()  # Predict next position
    px, py = pred[0, 0], pred[1, 0]

    if measured_x is not None and measured_y is not None:
        measurement = np.array([[measured_x], [measured_y]], dtype=np.float32)
        corrected = kf.correct(measurement)  # Correct based on measurement
        cx, cy = corrected[0, 0], corrected[1, 0]
    else:
        cx, cy = px, py
    return cx, cy


# Returns the angle (in degrees) between three points: a, b, c
def angle_between_points(a, b, c):
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])

    # Dot product and magnitudes
    dot = ba[0] * bc[0] + ba[1] * bc[1]
    mag_ba = np.hypot(ba[0], ba[1])
    mag_bc = np.hypot(bc[0], bc[1])
    denom = (mag_ba * mag_bc) + 1e-9
    cos_angle = dot / denom

    # Clamp to [-1, 1] and convert to degrees
    cos_angle = max(-1.0, min(1.0, cos_angle))
    return np.degrees(np.arccos(cos_angle))


# Merges points that are within a certain threshold of each other into single points
def merge_close_points(points, distance_threshold=20):
    merged = []
    for pt in points:
        if not merged:
            merged.append(pt)
        else:
            found_close = False
            for i, mp in enumerate(merged):
                dist = np.hypot(pt[0] - mp[0], pt[1] - mp[1])
                if dist < distance_threshold:
                    avg_x = (pt[0] + mp[0]) // 2
                    avg_y = (pt[1] + mp[1]) // 2
                    merged[i] = (avg_x, avg_y)
                    found_close = True
                    break
            if not found_close:
                merged.append(pt)
    return merged


# Calculates the center of a contour using its moments (approx palm center)
def get_palm_center(contour):
    M = cv2.moments(contour)
    if M["m00"] != 0:
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        return (cx, cy)
    else:
        x, y, w, h = cv2.boundingRect(contour)
        return (x + w // 2, y + h // 2)


# Provides a single fallback fingertip if convexity defects weren't found
def fallback_single_finger(contour, center, min_radius=50):
    max_dist = 0
    best_point = None

    # Look for the farthest point from the center within a certain radius
    for pt in contour:
        x, y = pt[0]
        dist = np.hypot(x - center[0], y - center[1])
        if dist > max_dist:
            max_dist = dist
            best_point = (x, y)

    if best_point is not None and max_dist > min_radius:
        return best_point
    return None


# Manually calibrates skin color ranges by sampling a small region in the center
def calibrate_skin_color(frame):
    global calibration_done
    global lower_skin_hsv, upper_skin_hsv
    global lower_skin_ycrcb, upper_skin_ycrcb

    h, w, _ = frame.shape

    # Define region in the center of the frame to sample
    x1 = w // 2 - 12
    y1 = h // 2 - 12
    x2 = w // 2 + 13
    y2 = h // 2 + 13
    center_region = frame[y1:y2, x1:x2]

    # Analyze HSV region
    hsv_region = cv2.cvtColor(center_region, cv2.COLOR_BGR2HSV)
    hist_hsv = cv2.calcHist([hsv_region], [0], None, [180], [0, 180])
    peak_hue = np.argmax(hist_hsv)
    std_dev_hsv = int(np.std(hsv_region[:, :, 0]))

    l_hsv = np.array([max(0, peak_hue - 2 * std_dev_hsv), 30, 60], dtype=np.uint8)
    u_hsv = np.array([min(180, peak_hue + 2 * std_dev_hsv), 255, 255], dtype=np.uint8)

    # Analyze YCrCb region
    ycrcb_region = cv2.cvtColor(center_region, cv2.COLOR_BGR2YCrCb)
    cr_mean = int(np.mean(ycrcb_region[:, :, 1]))
    cb_mean = int(np.mean(ycrcb_region[:, :, 2]))
    std_dev_crcb = int(np.std(ycrcb_region[:, :, 1:3]))

    l_ycrcb = np.array([0, max(133, cr_mean - std_dev_crcb), max(77, cb_mean - std_dev_crcb)], dtype=np.uint8)
    u_ycrcb = np.array([255, min(173, cr_mean + std_dev_crcb), min(127, cb_mean + std_dev_crcb)], dtype=np.uint8)

    return l_hsv, u_hsv, l_ycrcb, u_ycrcb, frame


# Automatically recalibrates skin color by sampling a region around (cx, cy)
def auto_calibrate_skin_color(frame, cx, cy, box_size=50):
    global lower_skin_hsv, upper_skin_hsv
    global lower_skin_ycrcb, upper_skin_ycrcb

    h, w, _ = frame.shape
    x1 = max(cx - box_size // 2, 0)
    y1 = max(cy - box_size // 2, 0)
    x2 = min(cx + box_size // 2, w - 1)
    y2 = min(cy + box_size // 2, h - 1)

    region = frame[y1:y2, x1:x2].copy()

    # Similar approach as the manual calibration but focusing around new region
    hsv_region = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    hist_hsv = cv2.calcHist([hsv_region], [0], None, [180], [0, 180])
    peak_hue = np.argmax(hist_hsv)
    std_dev_hsv = int(np.std(hsv_region[:, :, 0]))

    new_lower_hsv = np.array([max(0, peak_hue - 2 * std_dev_hsv), 30, 60], dtype=np.uint8)
    new_upper_hsv = np.array([min(180, peak_hue + 2 * std_dev_hsv), 255, 255], dtype=np.uint8)

    ycrcb_region = cv2.cvtColor(region, cv2.COLOR_BGR2YCrCb)
    cr_mean = int(np.mean(ycrcb_region[:, :, 1]))
    cb_mean = int(np.mean(ycrcb_region[:, :, 2]))
    std_dev_crcb = int(np.std(ycrcb_region[:, :, 1:3]))

    new_lower_ycrcb = np.array([0, max(133, cr_mean - std_dev_crcb), max(77, cb_mean - std_dev_crcb)], dtype=np.uint8)
    new_upper_ycrcb = np.array([255, min(173, cr_mean + std_dev_crcb), min(127, cb_mean + std_dev_crcb)],
                               dtype=np.uint8)

    # Compare new hue and CrCb with old to see if big drift occurred
    old_hue = (lower_skin_hsv[0] + upper_skin_hsv[0]) // 2
    old_cr = (lower_skin_ycrcb[1] + upper_skin_ycrcb[1]) // 2
    old_cb = (lower_skin_ycrcb[2] + upper_skin_ycrcb[2]) // 2

    TH = 40
    diff_hue = abs(peak_hue - old_hue)
    diff_cr = abs(cr_mean - old_cr)
    diff_cb = abs(cb_mean - old_cb)

    # Update thresholds only if difference is small enough
    if diff_hue > TH or diff_cr > TH or diff_cb > TH:
        return (x1, y1, x2, y2)

    lower_skin_hsv, upper_skin_hsv = new_lower_hsv, new_upper_hsv
    lower_skin_ycrcb, upper_skin_ycrcb = new_lower_ycrcb, new_upper_ycrcb
    return (x1, y1, x2, y2)


# Attempts to cut the forearm portion from the mask based on a row-width check
def cut_forearm_automatically(mask, x, y, w, h, min_ratio=0.5, consecutive_rows=2):
    if h < 10:
        return False

    row_widths = []
    # Traverse rows from bottom to top
    for row_i in range(y + h - 1, y - 1, -1):
        left, right = None, None
        for col_i in range(x, x + w):
            if mask[row_i, col_i] != 0:
                if left is None:
                    left = col_i
                right = col_i
        if left is None or right is None:
            row_widths.append(0)
        else:
            row_widths.append(right - left + 1)

    # Look for consecutive rows that reduce drastically in width
    consecutive_count = 0
    for i in range(1, len(row_widths)):
        w_curr = row_widths[i]
        w_prev = row_widths[i - 1]
        if w_prev > 0 and w_curr < min_ratio * w_prev:
            consecutive_count += 1
        else:
            consecutive_count = 0

        if consecutive_count >= consecutive_rows:
            # Cut the mask below this row
            row_cut = (y + h - 1) - i
            mask[row_cut:y + h, x:x + w] = 0
            return True
    return False


# Detects the hand region, fingertips, and uses face detection to filter out faces
def detect_hand(frame_roi, offset_x=0, offset_y=0):
    global lower_skin_hsv, upper_skin_hsv
    global lower_skin_ycrcb, upper_skin_ycrcb
    global mask_hsv, mask_ycrcb, color_mask, edges_canny, mag
    global edge_mask_raw, edge_mask_closed, edge_full_mask, face_mask, final_mask
    global kalman, smoothed_center
    global use_kalman, show_debug

    # Convert to HSV and YCrCb for skin color detection
    hsv = cv2.cvtColor(frame_roi, cv2.COLOR_BGR2HSV)
    mask_hsv = cv2.inRange(hsv, lower_skin_hsv, upper_skin_hsv)
    ycrcb = cv2.cvtColor(frame_roi, cv2.COLOR_BGR2YCrCb)
    mask_ycrcb = cv2.inRange(ycrcb, lower_skin_ycrcb, upper_skin_ycrcb)

    # Combine both color space masks
    combined_mask = cv2.addWeighted(mask_hsv, 0.40, mask_ycrcb, 0.60, 0)
    _, color_mask = cv2.threshold(combined_mask, 50, 255, cv2.THRESH_BINARY)

    # Find largest contour in color_mask (rough bounding box to later connect edges)
    c1, _ = cv2.findContours(color_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    xR, yR, wR, hR = 0, 0, 0, 0
    if c1:
        cmax = max(c1, key=cv2.contourArea)
        area_cmax = cv2.contourArea(cmax)
        if area_cmax > 500:
            xR, yR, wR, hR = cv2.boundingRect(cmax)

    # Edge detection using canny, plus advanced gradient
    gray = cv2.cvtColor(frame_roi, cv2.COLOR_BGR2GRAY)
    edges_canny = cv2.Canny(gray, 50, 150)
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(grad_x, grad_y)
    mag = np.clip(mag, 0, 255).astype(np.uint8)

    # Combine the canny edges with gradient magnitude
    alpha = 0.6
    edge_integrated = cv2.addWeighted(edges_canny, alpha, mag, 1 - alpha, 0)
    _, edge_mask_raw = cv2.threshold(edge_integrated, 50, 255, cv2.THRESH_BINARY)

    # Close small gaps in edges
    kernel = np.ones((3, 3), np.uint8)
    edge_mask_closed = cv2.morphologyEx(edge_mask_raw, cv2.MORPH_CLOSE, kernel, iterations=1)

    # Draw a line along bottom of bounding box in edge mask if found
    if wR > 0 and hR > 0:
        cv2.line(edge_mask_closed, (xR, yR + hR), (xR + wR, yR + hR), 255, thickness=3)

    # Fill in all edge contours
    cont_edge, _ = cv2.findContours(edge_mask_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    edge_full_mask = np.zeros_like(edge_mask_closed)
    for c in cont_edge:
        cv2.drawContours(edge_full_mask, [c], -1, 255, cv2.FILLED)

    # Combine color-based mask with edge-based mask
    temp_mask = cv2.bitwise_or(color_mask, edge_full_mask)
    temp_mask = cv2.morphologyEx(temp_mask, cv2.MORPH_OPEN, kernel, iterations=2)
    temp_mask = cv2.morphologyEx(temp_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    # Detect faces and create a face mask that we remove from the combined mask
    gray2 = cv2.cvtColor(frame_roi, cv2.COLOR_BGR2GRAY)
    face_mask = np.ones_like(temp_mask, dtype=np.uint8) * 255
    faces = face_cascade.detectMultiScale(gray2, 1.3, 5)
    for (fx, fy, fw, fh) in faces:
        cv2.rectangle(face_mask, (fx, fy), (fx + fw, int(fy + 1.5 * fh)), 0, -1)

    # Final mask with face region removed
    final_mask = cv2.bitwise_and(temp_mask, face_mask)

    # Find the largest contour again, which should now be the hand
    cont_final, _ = cv2.findContours(final_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    biggest_mask = np.zeros_like(final_mask)
    max_contour = None
    area_m = 0
    if cont_final:
        max_contour = max(cont_final, key=cv2.contourArea)
        area_m = cv2.contourArea(max_contour)
        if area_m > 500:
            cv2.drawContours(biggest_mask, [max_contour], -1, 255, cv2.FILLED)

    result = frame_roi.copy()  # This is the ROI image used for debugging visuals
    final_fingertips = []

    # If large enough, proceed to fingertip detection logic
    if max_contour is not None and area_m > 1000:
        xF, yF, wF, hF = cv2.boundingRect(max_contour)

        # Attempt to cut the forearm region to avoid confusion
        if cut_forearm_automatically(biggest_mask, xF, yF, wF, hF, 0.5, 2):
            if show_debug:
                cv2.line(result, (xF, yF + hF // 2), (xF + wF, yF + hF // 2), (0, 0, 255), 2)
            print("Forearm cut applied")

        # Recompute largest contour after cutting
        cont_after, _ = cv2.findContours(biggest_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cont_after:
            max_contour = max(cont_after, key=cv2.contourArea)
            area2 = cv2.contourArea(max_contour)
            if area2 > 500:
                xF, yF, wF, hF = cv2.boundingRect(max_contour)

                # Center of bounding box used for auto-calibration
                cxF = xF + wF / 2
                cyF = yF + hF / 2
                measured_x, measured_y = cxF, cyF

                # Initialize Kalman if needed
                global smoothed_center
                if smoothed_center is None and use_kalman:
                    set_kalman_position(kalman, measured_x + offset_x, measured_y + offset_y)
                    smoothed_center = (measured_x + offset_x, measured_y + offset_y)

                # Kalman update
                if use_kalman:
                    new_x, new_y = update_kalman(kalman, measured_x + offset_x, measured_y + offset_y)
                else:
                    new_x, new_y = measured_x + offset_x, measured_y + offset_y

                smoothed_center = (new_x, new_y)

                if show_debug:
                    cv2.rectangle(result, (xF, yF), (xF + int(wF), yF + int(hF)), (0, 255, 0), 2)
                    cv2.putText(
                        result, "Local BB",
                        (xF, yF - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (0, 255, 0), 2
                    )

                # Palm center for possible reference
                cx, cy = get_palm_center(max_contour)

                # Compute convex hull and defects for fingertip detection
                hull = cv2.convexHull(max_contour, returnPoints=False)
                if len(hull) > 3:
                    defects = cv2.convexityDefects(max_contour, hull)
                    if defects is not None:
                        candidate_points = []
                        wrist_threshold_y = yF + 0.65 * hF  # Below this line we ignore as wrist/arm

                        # Analyze each defect to see if it indicates a fingertip
                        for i in range(defects.shape[0]):
                            s, e, f, d = defects[i, 0]
                            start = tuple(max_contour[s][0])
                            end = tuple(max_contour[e][0])
                            far = tuple(max_contour[f][0])

                            # Threshold on defect depth (d) and angle
                            if d > 5000:
                                ang = angle_between_points(start, far, end)
                                if ang < 100:
                                    # Further filter based on location
                                    if (far[1] < wrist_threshold_y and
                                            start[1] < wrist_threshold_y and
                                            end[1] < wrist_threshold_y):
                                        dist_start = np.hypot(start[0] - far[0], start[1] - far[1])
                                        dist_end = np.hypot(end[0] - far[0], end[1] - far[1])
                                        # Collect potential fingertip points
                                        candidate_points.append((start, dist_start))
                                        candidate_points.append((end, dist_end))
                                        if show_debug:
                                            cv2.line(result, start, end, (0, 255, 255), 2)
                                            cv2.circle(result, far, 5, (255, 0, 0), -1)

                        # Filter candidates for duplicates / very close points
                        if candidate_points:
                            highest_candidate, ref_distance = min(candidate_points, key=lambda x: x[0][1])
                            filtered_candidates = []
                            for pt, dist in candidate_points:
                                d_between = np.hypot(pt[0] - highest_candidate[0], pt[1] - highest_candidate[1])
                                if d_between <= 2.2 * ref_distance:
                                    filtered_candidates.append(pt)
                            fingertip_points = merge_close_points(filtered_candidates, distance_threshold=20)
                        else:
                            fingertip_points = []

                        # If no valid points found, fallback to a single finger approach
                        if len(fingertip_points) == 0:
                            single_pt = fallback_single_finger(max_contour, (cx, cy), 50)
                            if single_pt is not None and single_pt[1] < wrist_threshold_y:
                                fingertip_points = [single_pt]

                        final_fingertips = fingertip_points

                        # Debug display of fingertip count
                        if show_debug:
                            for p in final_fingertips:
                                cv2.circle(result, p, 8, (0, 0, 255), -1)
                            fingers_count = len(final_fingertips)
                            cv2.putText(
                                result,
                                f"Fingers: {fingers_count}",
                                (10, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 1,
                                (0, 255, 255), 2
                            )

    # Convert the local fingertip coordinates to full-frame coordinates
    final_fingertips_global = [(pt[0] + offset_x, pt[1] + offset_y) for pt in final_fingertips]
    return result, color_mask, edge_full_mask, biggest_mask, final_fingertips_global, max_contour


# Overlays the user canvas on the background frame so drawn lines show up
def overlay_canvas_on_image(canvas, background):
    out = background.copy()
    mask = (canvas != [255, 255, 255]).any(axis=2)
    out[mask] = canvas[mask]
    return out


#############################################################################
#                    HIDDEN DEV MODE (Keyboard + Mouse)
#############################################################################

dev_fingers_count = 0  # Number of fingers in dev mode
dev_mouse_down = False
dev_last_mouse_pos = None


# Mouse callback for dev mode drawing/erasing
def dev_mouse_callback(event, x, y, flags, param):
    global dev_mouse_down, dev_last_mouse_pos
    if event == cv2.EVENT_LBUTTONDOWN:
        dev_mouse_down = True
        dev_last_mouse_pos = (x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        dev_mouse_down = False
        dev_last_mouse_pos = None
    elif event == cv2.EVENT_MOUSEMOVE and dev_mouse_down:
        dev_last_mouse_pos = (x, y)


# Returns dev mode fingertip/eraser info
def get_dev_fingertips_action(canvas, frame_w, frame_h):
    global dev_fingers_count, dev_mouse_down, dev_last_mouse_pos
    eraser_point = None
    if dev_mouse_down and dev_last_mouse_pos is not None:
        mx, my = dev_last_mouse_pos
        if dev_fingers_count in [2, 3]:
            eraser_point = (mx, my)
    return dev_fingers_count, eraser_point


#############################################################################
#                         MULTI-STAGE GAME LOGIC
#############################################################################

# Overlays edges image in top-left corner
def overlay_transparent_edges_top_left(dst_frame, edges_img):
    h, w = edges_img.shape[:2]
    H, W = dst_frame.shape[:2]
    # Fit if edges_img is bigger than the frame
    if h > H:
        h = H
    if w > W:
        w = W

    region = dst_frame[0:h, 0:w]
    sub = edges_img[0:h, 0:w]
    mask = (sub == 255)
    region[mask] = (255, 255, 255)


# Places edges image in the center of dst_frame at (center_x, center_y)
def transparent_overlay_edges(dst_frame, edges_img, center_x, center_y):
    rh, rw = edges_img.shape[:2]
    x1 = center_x - rw // 2
    y1 = center_y - rh // 2
    x2 = x1 + rw
    y2 = y1 + rh
    H, W = dst_frame.shape[:2]

    # Clip coordinates to remain in the frame
    if x1 < 0:
        x1 = 0
    if y1 < 0:
        y1 = 0
    if x2 > W:
        x2 = W
    if y2 > H:
        y2 = H

    region = dst_frame[y1:y2, x1:x2]
    sub_h = y2 - y1
    sub_w = x2 - x1
    edges_sub = edges_img[0:sub_h, 0:sub_w]
    mask = (edges_sub == 255)
    region[mask] = (255, 255, 255)


# Scales hint image to a maximum height so it doesn't block the entire screen
def scale_hint_for_screen(hint_img, max_h):
    h, w = hint_img.shape[:2]
    if h <= max_h:
        return hint_img
    scale_factor = float(max_h) / h
    new_w = int(w * scale_factor)
    new_h = int(h * scale_factor)
    resized = cv2.resize(hint_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized


# Runs one stage of the game (easy, medium, or hard)
def run_stage(stage_name, cap, screen_w, screen_h, total_score_so_far=0.0):
    global last_finger_point, kalman, smoothed_center
    global roi_x, roi_y, roi_w, roi_h, show_debug

    folder_path = f"pictures/{stage_name}"  # Directory for stage-specific images
    ref_path = choose_random_image(folder_path)
    if ref_path is None:
        print("can't load image")
    else:
        ref_edges = load_edge_image(ref_path)
        if ref_edges is None:
            print("can't do canny")

    # Crop reference edges to bounding box for better display
    bbox_ref = get_bounding_box_of_mask(ref_edges)
    if bbox_ref:
        ref_cropped = crop_to_bounding_box(ref_edges, bbox_ref)
    else:
        ref_cropped = ref_edges

    # Pre-stage countdown
    countdown_duration = 5
    countdown_end = time.time() + countdown_duration
    o = True

    # Show a short countdown screen
    while True:
        now = time.time()
        left = countdown_end - now
        if left <= 5 and o:
            pygame.mixer.music.load(music_5sec)  # 5-second countdown music
            pygame.mixer.music.play(-1)
            o = False
        if left <= 0:
            break
        leftover_sec = int(left)

        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (screen_w, screen_h))
        display_frame = frame.copy()

        # Show reference shape in the center
        transparent_overlay_edges(display_frame, ref_cropped, screen_w // 2, screen_h // 2)

        # Blue rectangle indicating area to put your hand in for calibration
        cv2.rectangle(
            display_frame,
            (screen_w // 2 - 50, screen_h // 2 - 50),
            (screen_w // 2 + 50, screen_h // 2 + 100),
            (255, 0, 0), 2
        )

        # Show instructions
        draw_interesting_text(display_frame,
                              f"LEVEL {stage_name.upper()} starts in {leftover_sec} Seconds!",
                              (50, 40), 0.8, (255, 255, 0), 2)
        draw_interesting_text(display_frame,
                              "Place your hand inside the blue box",
                              (50, 80), 0.8, (255, 255, 0), 1)
        draw_interesting_text(display_frame,
                              "Remember the white shape!",
                              (50, 450), 0.8, (255, 255, 0), 1)

        cv2.imshow(WINDOW_NAME, display_frame)
        key = cv2.waitKey(30) & 0xFF
        if key == ord('q'):
            return total_score_so_far
        if key == ord('s'):
            show_debug = not show_debug

    # After countdown, calibrate skin color once
    ret, frame = cap.read()
    if ret:
        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (screen_w, screen_h))
        (l_hsv, u_hsv, l_ycrcb, u_ycrcb, frame_calib) = calibrate_skin_color(frame.copy())

        global lower_skin_hsv, upper_skin_hsv
        global lower_skin_ycrcb, upper_skin_ycrcb
        lower_skin_hsv, upper_skin_hsv = l_hsv, u_hsv
        lower_skin_ycrcb, upper_skin_ycrcb = l_ycrcb, u_ycrcb

    # Create a blank canvas on which the user will draw
    canvas = np.ones((screen_h, screen_w, 3), dtype=np.uint8) * 255
    last_finger_point = None

    # Stage timer
    start_t = time.time()
    end_t = start_t + TIME_LIMIT
    local_frame_count = 0
    stage_score = 0.0

    # If ROI is not set, define a small ROI in center
    if roi_x is None or roi_y is None or roi_w is None or roi_h is None:
        roi_x = screen_w // 2 - 25
        roi_y = screen_h // 2 - 25
        roi_w, roi_h = 50, 50

    # Play music for the drawing phase
    pygame.mixer.music.stop()
    pygame.mixer.music.load(music_20sec)
    pygame.mixer.music.play(-1)

    # Main loop for the stage
    while True:
        now = time.time()
        left = int(end_t - now)
        if left < 0:
            left = 0

        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (screen_w, screen_h))
        original_frame = frame.copy()
        display_frame = frame.copy()
        local_frame_count += 1

        # Ensure ROI stays within screen boundaries
        roi_x = max(0, roi_x)
        roi_y = max(0, roi_y)
        if roi_x + roi_w > screen_w:
            roi_w = screen_w - roi_x
        if roi_y + roi_h > screen_h:
            roi_h = screen_h - roi_y

        # Extract ROI region for hand detection
        roi_frame = original_frame[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w].copy()
        result_roi, c_mask, edge_full, biggest_mask, fingertips, max_contour = detect_hand(
            roi_frame, offset_x=roi_x, offset_y=roi_y
        )
        final_fingertips = fingertips

        # If debug mode, show various internal windows
        if show_debug:
            cv2.imshow("Color Mask", c_mask)
            cv2.imshow("Edge Mask", edge_full)
            cv2.imshow("Final Mask", biggest_mask)
            cv2.imshow("mask hsv", mask_hsv)
            cv2.imshow("mask ycrcb", mask_ycrcb)
            cv2.imshow("edges canny", edges_canny)
            cv2.imshow("magnitude", mag)
            cv2.imshow("edge mask raw", edge_mask_raw)
            cv2.imshow("edge mask closed", edge_mask_closed)
            cv2.imshow("edge full mask", edge_full_mask)
            cv2.imshow("face mask", face_mask)
            cv2.imshow("final mask", final_mask)

        # Save the old ROI to display debug results
        old_roi_x, old_roi_y, old_roi_w, old_roi_h = roi_x, roi_y, roi_w, roi_h

        # Adjust ROI dynamically to track the hand bounding box
        if max_contour is not None:
            xC, yC, wC, hC = cv2.boundingRect(max_contour)
            scale = 1.5
            new_w = int(wC * scale)
            new_h = int(hC * scale)
            cx_box = roi_x + xC + wC // 2
            cy_box = roi_y + yC + hC // 2
            roi_x = max(0, cx_box - new_w // 2)
            roi_y = max(0, cy_box - new_h // 2)
            if roi_x + new_w > screen_w:
                roi_x = screen_w - new_w
            if roi_y + new_h > screen_h:
                roi_y = screen_h - new_h
            roi_w = new_w
            roi_h = new_h

        # Auto-calibrate every 'auto_calib_interval' frames
        if biggest_mask is not None and local_frame_count % auto_calib_interval == 0 and max_contour is not None:
            xF, yF, wF, hF = cv2.boundingRect(max_contour)
            auto_calibrate_skin_color(
                original_frame, roi_x + xF + wF // 2, roi_y + yF + hF // 2, 50
            )

        # Display debug ROI on top of the original frame
        debug_display = original_frame.copy()
        debug_display[old_roi_y:old_roi_y + old_roi_h, old_roi_x:old_roi_x + old_roi_w] = result_roi
        result_frame = debug_display

        # Check how many fingertips we found
        fingers_count = len(final_fingertips)

        # Logic for drawing (1 finger), erasing (2/3 fingers), clearing canvas (5 fingers)
        if fingers_count == 1:
            current_point = final_fingertips[0] if len(final_fingertips) > 0 else None
            if current_point is not None:
                if last_finger_point is not None:
                    cv2.line(canvas, last_finger_point, current_point, DRAW_COLOR, 3)
                last_finger_point = current_point
            else:
                last_finger_point = None
        elif fingers_count in [2, 3]:
            # Use an average point between the first two fingertips for erasing
            if len(final_fingertips) >= 2:
                if fingers_count == 2:
                    x1, y1 = final_fingertips[0]
                    x2, y2 = final_fingertips[1]
                else:
                    # If 3 fingers, find the closest two
                    best_pair = None
                    best_dist = float('inf')
                    for i in range(len(final_fingertips)):
                        for j in range(i + 1, len(final_fingertips)):
                            dx = final_fingertips[i][0] - final_fingertips[j][0]
                            dy = final_fingertips[i][1] - final_fingertips[j][1]
                            dist_sq = dx * dx + dy * dy
                            if dist_sq < best_dist:
                                best_dist = dist_sq
                                best_pair = (final_fingertips[i], final_fingertips[j])
                    x1, y1 = best_pair[0]
                    x2, y2 = best_pair[1]
                mx = (x1 + x2) // 2
                my = (y1 + y2) // 2
                cv2.circle(canvas, (mx, my), 15, ERASE_COLOR, -1)
                cv2.circle(result_frame, (mx, my), 15, ERASE_COLOR, -1)
                last_finger_point = None
            else:
                last_finger_point = None
        elif fingers_count == 5:
            # Clear the entire canvas
            canvas[:] = 255
            last_finger_point = None

        # Combine canvas with camera feed
        combined_display = overlay_canvas_on_image(canvas, result_frame)
        final_display = combined_display.copy()

        # Draw a bottom gray bar
        bottom_bar_height = int(screen_h * BOTTOM_BAR_RATIO)
        draw_area_height = screen_h - bottom_bar_height
        cv2.rectangle(final_display, (0, draw_area_height), (screen_w, screen_h), (50, 50, 50), -1)

        # Optional small image overlay
        img_path = "image.png"
        img = cv2.imread(img_path)
        if img is not None:
            scale_factor = 0.28
            img_h, img_w, _ = img.shape
            new_w = int(img_w * scale_factor)
            new_h = int(img_h * scale_factor)
            img_resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            x1, y1 = 198, screen_h - img_resized.shape[0]
            x2, y2 = x1 + img_resized.shape[1], y1 + img_resized.shape[0]
            if y1 >= 0 and x2 <= screen_w and y2 <= screen_h:
                final_display[y1:y2, x1:x2] = img_resized

        # Time left and score overlay
        bar_y = draw_area_height + 30
        draw_interesting_text(final_display, f"{left} sec left!", (15, bar_y),
                              0.9, (0, 0, 255), 1)
        score_text = f"Level {stage_name.upper()} | Total Score: {total_score_so_far:.2f}"
        draw_interesting_text(final_display, score_text, (screen_w - 270, bar_y),
                              0.5, (255, 255, 0), 1)

        # Show the reference shape if the stage is ending
        if left < 5:
            transparent_overlay_edges(final_display, ref_cropped, screen_w // 2, screen_h // 2)

        cv2.imshow(WINDOW_NAME, final_display)
        key = cv2.waitKey(10) & 0xFF
        if key == ord('s'):
            show_debug = not show_debug
        if key == ord('q'):
            break
        if left <= 0:
            # Once time is up, compare final canvas to reference
            user_drawing = create_user_drawing(canvas)
            h_user, w_user = user_drawing.shape[:2]
            h_ref, w_ref = ref_cropped.shape[:2]

            # If shapes differ in size, pad reference to match user drawing
            if h_user != h_ref or w_user != w_ref:
                pad_ref = np.zeros((h_user, w_user), dtype=np.uint8)
                top = (h_user - h_ref) // 2 if h_ref < h_user else 0
                left_ = (w_user - w_ref) // 2 if w_ref < w_user else 0
                copy_h = min(h_ref, h_user)
                copy_w = min(w_ref, w_user)
                pad_ref[top:top + copy_h, left_:left_ + copy_w] = ref_cropped[0:copy_h, 0:copy_w]
                ref_matched = pad_ref
            else:
                ref_matched = ref_cropped

            # Calculate correlation score between user and reference
            stage_score, user_dil, ref_dil, user_bin, ref_bin = correlation_score(user_drawing, ref_matched)[0:5]
            break

    # Update total score
    total_score_new = total_score_so_far + stage_score

    # Create a side-by-side debug comparison
    side_by_side = np.hstack([
        cv2.cvtColor(user_bin, cv2.COLOR_GRAY2BGR),
        cv2.cvtColor(ref_bin, cv2.COLOR_GRAY2BGR)
    ])

    # Display stage score, total score, and a performance message
    draw_interesting_text(side_by_side, f"Stage Score: {stage_score:.2f}", (10, 30),
                          1, (255, 255, 0), 2)
    draw_interesting_text(side_by_side, f"Total Score: {total_score_new:.2f}", (10, 70),
                          1, (255, 255, 255), 2)
    perf_msg = get_stage_performance_message(stage_name, stage_score)
    draw_interesting_text(side_by_side, perf_msg, (10, 110),
                          1, (0, 255, 0), 2)

    cv2.imshow("Comparison", side_by_side)
    cv2.waitKey(0)
    cv2.destroyWindow("Comparison")
    return total_score_new


# Main function: runs the entire game workflow
def main():
    global dev_fingers_count, kalman, smoothed_center, show_debug

    # Open the default camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open camera.")
        return

    # Create a fullscreen window
    cv2.namedWindow(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    # Wait for user input to start the game or quit
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)
        H, W = frame.shape[:2]
        frame = cv2.resize(frame, (W, H))
        disp = frame.copy()

        # Prompt the user to press SPACE to start
        draw_interesting_text(disp, "Ready for a challenge? Press SPACE to start", (30, 50),
                              0.8, (255, 255, 0), 2)

        cv2.imshow(WINDOW_NAME, disp)
        key = cv2.waitKey(10) & 0xFF
        if key == 27 or key == ord('q'):  # ESC or 'q' to quit
            cap.release()
            cv2.destroyAllWindows()
            return
        elif key == 32:  # SPACE
            break
        if key == ord('s'):
            show_debug = not show_debug

    # Initialize Kalman filter for smoother tracking
    kalman = init_kalman_filter()
    smoothed_center = None
    screen_h, screen_w = disp.shape[:2]
    total_score = 0.0

    # Run each stage in STAGES list
    for stage_name in STAGES:
        total_score = run_stage(stage_name, cap, screen_w, screen_h, total_score_so_far=total_score)

    # After all stages, display final score
    final_frame = np.zeros((200, 700, 3), dtype=np.uint8)

    if total_score >= 250:
        performance_msg = "You are a true ShapeMaster!!"
    elif total_score >= 200:
        performance_msg = "Wonderful Preformance!"
    elif total_score >= 100:
        performance_msg = "Good effort, you'll get better!"
    else:
        performance_msg = "You're a NOOB... Keep practicing!"

    draw_interesting_text(final_frame, f"Final Score: {total_score:.2f}", (50, 70),
                          1, (255, 255, 255), 2)
    draw_interesting_text(final_frame, performance_msg, (50, 120),
                          1, (0, 255, 0), 2)

    cv2.imshow("Final Score", final_frame)
    cv2.waitKey(0)
    cap.release()
    cv2.destroyAllWindows()


# Run main if script is executed
if __name__ == "__main__":
    main()
