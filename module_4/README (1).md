# 🧠 AI-Based Crowd Monitoring and Safety Management System

An **AI-powered real-time crowd monitoring system** that uses **computer vision (YOLOv8)** to detect, track, and analyze human presence within defined zones.  
It automatically triggers alerts for overcrowding and generates visual reports — enabling safer, smarter management of public spaces.

---

## 📸 Project Preview
> 🖼️ *Insert screenshots or demo GIFs here (e.g., Dashboard, Live Detection, Admin Panel)*

---

## 🚀 Table of Contents
1. [Project Overview](#-project-overview)
2. [Key Features](#-key-features) 
3. [System Architecture](#-system-architecture) 
4. [Technical Workflow](#-technical-workflow) 
5. [Technology Stack](#-technology-stack) 
6. [Core Modules Explained](#-core-modules-explained) 
7. [Database Models](#-database-models) 
8. [Frontend Functionality](#-frontend-functionality) 
9. [Alert Mechanism](#-alert-mechanism) 
10. [PDF and CSV Reporting](#-pdf-and-csv-reporting) 
11. [System Settings (Admin Panel)](#-system-settings-admin-panel) 
12. [Setup & Installation](#-setup--installation)
13. [Usage Guide](#-usage-guide)
14. [Results & Output](#-results--output)
15. [Challenges & Future Scope](#-challenges--future-scope)
16. [Project Credits](#-project-credits)

---

## 🎯 Project Overview

Traditional crowd monitoring relies heavily on human supervision — prone to delays and inefficiency.  
This project solves that by creating a **Flask-based web application** that leverages **AI-driven computer vision** to monitor and analyze live or recorded video feeds in real time.

### 🧩 Objectives:
- Detect and track each individual in a camera frame.
- Monitor how long they remain in “danger zones.”
- Trigger alerts when thresholds are exceeded.
- Provide real-time dashboard visualization and reports.
- Enable admin control and customization of alert settings.

---

## ✨ Key Features

| Feature | Description |
|----------|--------------|
| 🎥 Real-time Detection | Detects and tracks people using **YOLOv8**. |
| 🚧 Zone Drawing | User manually defines a **“Red Zone”** using the mouse before analysis. |
| ⏱️ Time Tracking | Tracks time spent by each person in danger zones. |
| ⚠️ Alert System | Generates three alert types: Per-Person, Zone Population, Overall Population. |
| 👥 Role-based Login | Secure login for **Users** and **Admins** using JWT authentication. |
| 🧾 Report Generation | Auto-generates **PDF** (ReportLab) and **CSV** reports for analysis. |
| 📊 Interactive Dashboard | Live analytics using **Chart.js** and **AJAX**. |
| ⚙️ System Settings | Admins can modify thresholds dynamically (auto-refreshes YOLO tracker). |
| 🔒 Secure & Scalable | Built with **Flask**, **PostgreSQL**, and environment-based configuration. |

---

## 🧱 System Architecture

> 🖼️ *Insert "System Architecture Diagram" here (showing camera → YOLOv8 → Flask → DB → Frontend)*

```text
Video Input (Camera/File)
        ↓
YOLOv8 Detection (Ultralytics)
        ↓
PersonTracker (detector.py)
        ↓
Flask Backend (app.py)
        ↓
Database (PostgreSQL) ──> Frontend (Chart.js / Dashboard)
        ↓
Report Generator (PDF, CSV)
```

---

## ⚙️ Technical Workflow

1. User logs in via **Flask-JWT** authentication.
2. Video is captured from **webcam or uploaded file**.
3. User defines a **danger zone (Red Zone)** using mouse.
4. YOLOv8 detects people and assigns tracking IDs.
5. System:
   - Calculates zone-wise time per person.
   - Triggers alerts if thresholds are breached.
6. Alerts are stored in PostgreSQL and visualized on the dashboard.
7. Admin can monitor, download reports, and modify alert parameters.

---

## 🧰 Technology Stack

| Component | Technology |
|------------|-------------|
| **Frontend** | HTML, CSS, JavaScript, Chart.js |
| **Backend Framework** | Flask (Python) |
| **AI Model** | YOLOv8 (Ultralytics) |
| **Database** | PostgreSQL (SQLAlchemy ORM) |
| **Authentication** | Flask-JWT-Extended |
| **Reporting** | ReportLab (PDF), CSV |
| **Environment Management** | python-dotenv |
| **Deployment** | Flask Server (Localhost/Cloud-ready) |

---

## 🧩 Core Modules Explained

### 1. `app.py`
Handles:
- User authentication (JWT)
- Route management (login, dashboard, analysis)
- Admin controls (user management, settings)
- Video streaming (live/uploaded)
- PDF/CSV generation

### 2. `detector.py`
- Initializes YOLOv8 model
- Tracks persons and calculates time spent in zones
- Generates alerts and overlays heatmap visualization

### 3. `repoet_generator.py`
- Creates **PDF reports** summarizing each person’s activity

### 4. `admin.js`
- Manages the **Admin Panel** tabs and user statistics

### 5. `script.js`
- Updates the **dashboard in real time**
- Draws charts and displays alerts dynamically

---

## 🗃️ Database Models

### 🧍 User
| Field | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| username | String | Unique username |
| password_hash | String | Encrypted password |
| email | String | Optional |
| role | String | `admin` or `user` |
| profile_pic | String | Path to uploaded picture |

### ⚠️ AlertHistory
| Field | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| user_id | ForeignKey | Linked to User |
| alert_type | String | e.g., "Per-Person" |
| message | String | Alert details |
| timestamp | DateTime | Time of alert |

### ⚙️ SystemSettings
| Key | Description | Default |
|------|-------------|----------|
| person_threshold | Max time (seconds) a person can stay in red zone | 10 |
| zone_threshold | Max number of people allowed in red zone | 5 |
| overall_threshold | Max total people allowed in frame | 20 |

---

## 🧭 Usage Guide

> 🖼️ *Insert screenshots of Login Page, Dashboard, and Admin Panel here*

1. Register (first user becomes **Admin**).
2. Log in → Go to Dashboard.
3. Choose **Live Analysis** or **Upload Video**.
4. Draw red zone using mouse.
5. Watch real-time detection & alerts.
6. Generate reports (PDF/CSV).

---

## 🧾 PDF and CSV Reporting

### 📘 PDF
Generated per person with:
- Person ID
- Zone-wise time
- Total time
- Alert flag

### 📗 CSV
Stores user alert logs:
- Timestamp
- Alert type
- Message

---

## ⚙️ Setup & Installation

```bash
# Clone the repository
git clone https://github.com/your-username/crowd-monitoring-ai.git
cd crowd-monitoring-ai

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # for Windows

# Install dependencies
pip install -r requirements.txt
```

### Create a `.env` File
```bash
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=crowd_monitoring
SECRET_KEY=your_secret_key
JWT_SECRET_KEY=your_jwt_key
```

### Run the App
```bash
python app.py
```
Access via: [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## 📊 Results & Output

> 🖼️ *Insert output screenshots (YOLO detection, heatmap, alert dashboard, report samples)*

- Real-time detection of multiple people
- Dynamic zone alerts
- Heatmap visualization
- Automatic logging and reporting

---

## 🚀 Challenges & Future Scope

### Challenges
- Managing occlusions in dense crowds
- Real-time inference speed on low-end systems

### Future Scope
- Multi-zone (red, yellow, green) support
- SMS/Email alert integration
- Cloud deployment with multi-camera view
- Edge AI device compatibility (Jetson, Raspberry Pi)

---

## 👨‍💻 Project Credits

**Developed by:**  
*Tushar Dayma*  
B.E. Artificial Intelligence & Machine Learning  
ISB&M Engineering College  

**Internship:** Infosys Springboard  
**Technologies:** Flask · YOLOv8 · PostgreSQL · Chart.js · ReportLab

---

> 🏷️ *This project demonstrates the integration of AI-based visual intelligence with scalable web technologies for public safety and automation.*
