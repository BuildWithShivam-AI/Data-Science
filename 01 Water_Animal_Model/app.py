import streamlit as st
import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.preprocessing.image import ImageDataGenerator
import numpy as np
from PIL import Image
import os
from sklearn.model_selection import train_test_split
import glob

# Set random seed for reproducibility
tf.random.set_seed(42)

# Constants
IMAGE_SIZE = (224, 224)
BATCH_SIZE = 32
EPOCHS = 10

def create_model(num_classes):
    """Create a CNN model for image classification"""
    model = models.Sequential([
        layers.Conv2D(32, (3, 3), activation='relu', input_shape=(*IMAGE_SIZE, 3)),
        layers.MaxPooling2D((2, 2)),
        layers.Conv2D(64, (3, 3), activation='relu'),
        layers.MaxPooling2D((2, 2)),
        layers.Conv2D(64, (3, 3), activation='relu'),
        layers.MaxPooling2D((2, 2)),
        layers.Conv2D(128, (3, 3), activation='relu'),
        layers.MaxPooling2D((2, 2)),
        layers.Flatten(),
        layers.Dense(128, activation='relu'),
        layers.Dropout(0.5),
        layers.Dense(num_classes, activation='softmax')
    ])
    return model

def prepare_data():
    """Prepare the dataset for training"""
    data_dir = "archive"
    
    # Get all class names (folder names)
    class_names = [d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))]
    
    # Create data generator
    datagen = ImageDataGenerator(
        rescale=1./255,
        validation_split=0.2,
        rotation_range=20,
        width_shift_range=0.2,
        height_shift_range=0.2,
        horizontal_flip=True,
        fill_mode='nearest'
    )

    # Prepare training dataset
    train_generator = datagen.flow_from_directory(
        data_dir,
        target_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        subset='training'
    )

    # Prepare validation dataset
    validation_generator = datagen.flow_from_directory(
        data_dir,
        target_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        subset='validation'
    )

    return train_generator, validation_generator, class_names

def train_model():
    """Train the model and return it along with class names"""
    # Prepare data
    train_generator, validation_generator, class_names = prepare_data()
    
    # Create and compile model
    model = create_model(len(class_names))
    model.compile(
        optimizer='adam',
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    
    # Train model
    history = model.fit(
        train_generator,
        epochs=EPOCHS,
        validation_data=validation_generator
    )
    
    return model, class_names

def preprocess_image(image):
    """Preprocess a single image for prediction"""
    img = image.resize(IMAGE_SIZE)
    img_array = tf.keras.preprocessing.image.img_to_array(img)
    img_array = tf.expand_dims(img_array, 0)
    img_array = img_array / 255.0
    return img_array

def main():
    st.title("Marine Animal Classification")
    st.write("This application classifies different types of marine animals from images.")
    
    # Add sidebar
    st.sidebar.title("Options")
    
    # Check if model exists
    model_path = "marine_animal_model"
    if not os.path.exists(model_path):
        if st.sidebar.button("Train Model"):
            st.write("Training model... This may take a while...")
            model, class_names = train_model()
            
            # Save model and class names
            model.save(model_path)
            with open("class_names.txt", "w") as f:
                f.write("\n".join(class_names))
            
            st.success("Model trained successfully!")
    
    # Load existing model and class names
    if os.path.exists(model_path):
        model = tf.keras.models.load_model(model_path)
        with open("class_names.txt", "r") as f:
            class_names = f.read().splitlines()
        
        # File uploader
        uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])
        
        if uploaded_file is not None:
            # Display the uploaded image
            image = Image.open(uploaded_file)
            st.image(image, caption='Uploaded Image', use_column_width=True)
            
            # Make prediction
            processed_image = preprocess_image(image)
            prediction = model.predict(processed_image)
            predicted_class = class_names[np.argmax(prediction)]
            confidence = np.max(prediction) * 100
            
            # Display results
            st.write(f"Prediction: {predicted_class}")
            st.write(f"Confidence: {confidence:.2f}%")
            
            # Display top 3 predictions
            st.write("\nTop 3 Predictions:")
            top_3_idx = np.argsort(prediction[0])[-3:][::-1]
            for idx in top_3_idx:
                st.write(f"{class_names[idx]}: {prediction[0][idx]*100:.2f}%")

if __name__ == "__main__":
    main()
