# © 2025 The Christman AI Project. All rights reserved.
#
# This code is released as part of a trauma-informed, dignity-first AI ecosystem
# designed to protect, empower, and elevate vulnerable populations.
#
# By using, modifying, or distributing this software, you agree to uphold the following:
# 1. Truth — No deception, no manipulation.
# 2. Dignity — Respect the autonomy and humanity of all users.
# 3. Protection — Never use this to exploit or harm vulnerable individuals.
# 4. Transparency — Disclose all modifications and contributions clearly.
# 5. No Erasure — Preserve the mission and ethical origin of this work.
#
# This is not just code. This is redemption in code.
# Contact: lumacognify@thechristmanaiproject.com
# https://thechristmanaiproject.com

"""
AlphaVox - Create Test LSTM Models
---------------------------------
This script creates simplified test LSTM models for testing the temporal nonverbal system
without waiting for the full training to complete.
"""

import os
import pickle

import numpy as np
from tensorflow.keras.layers import LSTM, Dense
from tensorflow.keras.models import Sequential

# Create models directory
os.makedirs("lstm_models", exist_ok=True)

# Create gesture model
print("Creating test gesture model...")
gesture_model = Sequential(
    [
        LSTM(32, input_shape=(10, 4), return_sequences=False),
        Dense(16, activation="relu"),
        Dense(4, activation="softmax"),
    ]
)
gesture_model.compile(
    optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"]
)

# Create eye movement model
print("Creating test eye movement model...")
eye_model = Sequential(
    [
        LSTM(32, input_shape=(10, 3), return_sequences=False),
        Dense(16, activation="relu"),
        Dense(2, activation="softmax"),
    ]
)
eye_model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])

# Create emotion model
print("Creating test emotion model...")
emotion_model = Sequential(
    [
        LSTM(32, input_shape=(10, 5), return_sequences=False),
        Dense(16, activation="relu"),
        Dense(6, activation="softmax"),
    ]
)
emotion_model.compile(
    optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"]
)

# Train on small amount of random data to initialize weights
print("Initializing models with random data...")
X_gesture = np.random.rand(10, 10, 4)
y_gesture = np.random.randint(0, 4, size=10)
gesture_model.fit(X_gesture, y_gesture, epochs=1, verbose=0)

X_eye = np.random.rand(10, 10, 3)
y_eye = np.random.randint(0, 2, size=10)
eye_model.fit(X_eye, y_eye, epochs=1, verbose=0)

X_emotion = np.random.rand(10, 10, 5)
y_emotion = np.random.randint(0, 6, size=10)
emotion_model.fit(X_emotion, y_emotion, epochs=1, verbose=0)

# Save models
print("Saving models...")
gesture_model.save("lstm_models/gesture_lstm_model.keras")
eye_model.save("lstm_models/eye_movement_lstm_model.keras")
emotion_model.save("lstm_models/emotion_lstm_model.keras")

# Create and save labels
gesture_labels = ["Hand Up", "Wave Left", "Wave Right", "Head Jerk"]
eye_labels = ["Looking Up", "Rapid Blinking"]
emotion_labels = ["Neutral", "Happy", "Sad", "Angry", "Fear", "Surprise"]

with open("lstm_models/gesture_labels.pkl", "wb") as f:
    pickle.dump(gesture_labels, f)

with open("lstm_models/eye_movement_labels.pkl", "wb") as f:
    pickle.dump(eye_labels, f)

with open("lstm_models/emotion_labels.pkl", "wb") as f:
    pickle.dump(emotion_labels, f)

print("Test models created and saved successfully.")
