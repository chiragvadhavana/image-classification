# Image Classification App

## Project Description

This project is a **FastAPI and Streamlit-based image classification system** that uses **Redis and Celery** for task queue management and **PostgreSQL** for storing upload history and results. The app allows users to upload single images or ZIP files of images, which are then classified as "cat," "dog," or "none" using the **Gemini API**. Uploaded images are stored in **Google Cloud Storage**, and the classification results are saved in a PostgreSQL database. Streamlit provides the frontend for file upload, task status tracking, and download of the results in CSV format.

## Technologies Used

- **FastAPI**: Backend API framework that handles image uploads and integrates with Celery for processing tasks.
- **Streamlit**: Frontend to upload images, check task status, and download results.
- **Redis**: Message broker for Celery, managing task queues for image classification.
- **Celery**: Handles background processing of image classification tasks.
- **PostgreSQL**: Database for batch uploads, task status, and classification results.
- **Google Cloud Storage**: Stores uploaded images after they are processed.
- **Gemini API**: API used to classify images and return the result in JSON format.

## Project Diagram

![Project Diagram](Diagram.png)

## Todos

- **Git Connector**: This feature will allow the backend to interact with GitHub issues. When a user comments on any issue within the project with a specific set of commands and attaches a file ( file or link of file) , it will trigger the backend to process the request. The goal is to automate tasks based on comments given by user.
