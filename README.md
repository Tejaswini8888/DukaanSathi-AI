
# 🛒 DukaanSathi AI
### Voice-Powered Smart Kirana Assistant using Gnani AI

DukaanSathi AI is a voice-powered retail assistant designed to help small kirana store owners manage customer orders, billing, inventory, and sales using Telugu and English voice commands.

Built for the **Great Indian AI Internship Challenge by Gnani AI**.

## 🎯 Problem Statement

Small retail shopkeepers often manage orders, inventory, and billing manually. This process can be time-consuming and prone to errors.

Many existing digital solutions also require typing and navigating complex interfaces, creating barriers for shopkeepers who prefer regional languages.

## 💡 Our Solution

DukaanSathi AI simplifies daily retail operations through voice-based interaction.

A shopkeeper can speak a customer order in Telugu or English. The system transcribes the speech, identifies the customer, products, quantities, and units, and generates an order preview.

After confirmation, the application saves the order, updates inventory, and provides voice-based confirmation.

## ✨ Key Features

### 🎙️ Voice-Based Ordering
- Telugu and English speech recognition
- Support for code-mixed voice commands
- Customer and product identification
- Quantity and unit extraction

### 🧾 Smart Billing
- Automatic order preview
- Explicit confirmation before saving
- Automatic bill calculation
- Duplicate-order protection

### 📦 Inventory Management
- Real-time stock tracking
- Automatic inventory deduction
- Low-stock alerts
- Out-of-stock detection
- Alternative product suggestions

### 🔊 Voice Confirmation
- Gnani AI Text-to-Speech integration
- Spoken order confirmations

### 📊 Sales Analytics
- Daily, weekly, and monthly sales summaries
- Revenue trend analysis
- Top-selling products
- Recent orders and dashboard statistics

## 🤖 Gnani AI Integration

DukaanSathi AI integrates Gnani AI speech technologies:

**Speech-to-Text (STT)**

Converts Telugu and English voice commands into text for order processing.

**Text-to-Speech (TTS)**

Generates spoken order confirmations.

These integrations make the application accessible to shopkeepers who prefer voice interaction over typing.

## 🛠️ Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python, FastAPI |
| Frontend | HTML, CSS, JavaScript |
| Database | SQLite, SQLAlchemy |
| Speech Recognition | Gnani AI STT |
| Speech Synthesis | Gnani AI TTS |
| Order Understanding | Rule-based NLP |
| API Testing | FastAPI Swagger UI |

## 🏗️ Project Architecture

```text
Voice Input
    |
    v
Gnani AI Speech-to-Text
    |
    v
Order Understanding
    |
    v
Product and Stock Validation
    |
    v
Order Preview
    |
    v
User Confirmation
    |
    v
Billing + Database + Inventory Update
    |
    v
Gnani AI Text-to-Speech
    |
    v
Voice Confirmation
```

## 📁 Project Structure

```text
DukaanSathi-AI/
|
|-- backend/
|   |-- main.py
|   |-- database.py
|   |-- models.py
|   |-- schemas.py
|   |-- gnani_service.py
|   |-- tts_service.py
|   |-- order_understanding.py
|   |-- order_processor.py
|   |-- order_schemas.py
|   |-- inventory.py
|   |-- billing.py
|
|-- frontend/
|   |-- index.html
|   |-- style.css
|   |-- script.js
|   |-- app.py
|
|-- tests/
|-- docs/
|-- requirements.txt
|-- .gitignore
|-- README.md
```

## 🚀 Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Tejaswini8888/DukaanSathi-AI.git
cd DukaanSathi-AI
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate on Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API Credentials

Create a `.env` file in the project root.

Add the Gnani AI credentials required by the backend.

Never commit actual API keys to GitHub.

### 5. Run the Application

```bash
python -m uvicorn backend.main:app --reload
```

Open the application:

http://127.0.0.1:8000/app

API Documentation:

http://127.0.0.1:8000/docs

## 🎬 Demo Video

Demo video: Coming soon.

## 📸 Screenshots

Application screenshots will be added in the `docs/` folder.

## 🌍 Real-World Impact

DukaanSathi AI aims to make retail automation accessible to small businesses by:

- Reducing manual order-entry work
- Simplifying billing and stock management
- Supporting regional-language interaction
- Improving visibility into daily sales
- Making digital tools easier to use for local retailers

## 🔮 Future Enhancements

- Support for additional Indian languages
- Improved conversational order understanding
- Cloud deployment
- Multi-store support
- Advanced demand forecasting

## 👩‍💻 Developer

**Tejaswini Madarapu**

B.Tech – Artificial Intelligence & Machine Learning

Aditya University, Surampalem

GitHub: https://github.com/Tejaswini8888

## 🏆 Challenge

Developed for the **Great Indian AI Internship Challenge – Gnani AI**.

#GnaniAI #GreatIndianAIInternshipChallenge
