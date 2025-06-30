# 🧞‍♂️ Job Genie: AI-Powered Local Job Opportunity Engine

## 🌟 Project Vision: Bridging the Gap for India's Invisible Workforce
Every year, millions of non-technical workers in India — our skilled plumbers, electricians, cooks, delivery staff, and more — struggle to find local employment. They are the backbone of our economy, yet remain largely invisible to the digital job market.  
Existing portals are complex, text-heavy, and built for a very different demographic.

**Job Genie** aims to solve this critical problem.  
Our mission is to create a **voice-first platform** that connects these essential workers with local opportunities in a simple, intuitive way.

This repository contains the **core backend engine** of Job Genie — a proof-of-concept that intelligently identifies, scrapes, and generates hyper-local job postings from real businesses that need this workforce the most.  
This is the first step towards building a nationwide platform that truly gives a voice to India's local job market.

---

## ⚙️ What Does This Code Do?
This is a Flask-based web application that uses AI and web scraping to find and create hyper-local job opportunities.  
When a user provides a natural language prompt like:
> "I'm looking for a cook job in Hyderabad"

the application follows this process:
1. **Intelligent Prompt Analysis**:  
   Uses Google Gemini API to extract business type (e.g., `restaurant`) and location (e.g., `Hyderabad`).

2. **Dynamic Web Scraping**:  
   Uses Playwright to search Google Maps for businesses matching the extracted criteria. Scrapes details like business name, phone number, and location coordinates.

3. **AI-Powered Job Generation**:  
   For each scraped business, another Gemini call generates 3 realistic, localized job postings (with responsibilities, skills required, and salary estimates).

The final output is a list of real businesses with tailored job opportunities — ready to be shown to users.

---

## ✨ Key Features
✅ **Natural Language Understanding** — understands prompts like "Find me a delivery job in Delhi."  
✅ **Hyper-local Discovery** — scrapes real Google Maps data.  
✅ **Context-aware Job Creation** — realistic, localized postings with salary estimates in INR.  
✅ **Scalable & Robust** — built with Flask + Playwright, includes logging.  
✅ **RESTful API** — `/scrape` endpoint for integration with future frontend or voice interface.

---

## 🛠️ Technology Stack
- **Backend**: Python, Flask
- **AI/LLM**: Google Gemini API (`gemini-1.5-flash`)
- **Web Scraping**: Playwright
- **Data Handling**: Pandas
- **Environment Management**: python-dotenv

---

## 📦 Setup and Installation

### ✅ Prerequisites
- Python 3.8+
- Google Chrome (for Playwright)

---

### 📥 Step 1: Clone the Repository
```bash
git clone [<your-repository-url>](https://github.com/bunnyexe1/CODE_CUBICLE_SIX_EYES)
🐍 Step 2: Create a Virtual Environment
Windows:

bash
Copy
Edit
python -m venv venv
venv\Scripts\activate
macOS/Linux:

bash
Copy
Edit
python3 -m venv venv
source venv/bin/activate
📦 Step 3: Install Dependencies
Create a requirements.txt file with:

nginx
Copy
Edit
Flask
playwright
pandas
google-generativeai
python-dotenv
Then run:

bash
Copy
Edit
pip install -r requirements.txt
🌐 Step 4: Install Playwright Browsers
bash
Copy
Edit
playwright install
🔑 Step 5: Set Up Environment Variables
Create a .env file in the root directory:

env
Copy
Edit
GOOGLE_API_KEY="your_google_api_key_here"
🚀 How to Run the Application
bash
Copy
Edit
python app.py
The server will run at:
📍 http://127.0.0.1:5000

Open this in your browser.

Enter a prompt like: Find mechanic jobs in Mumbai

Enter the number of businesses to scrape

Click Scrape Jobs

You’ll get:

A list of local businesses + AI-generated job postings

Results saved to business_jobs_with_urls.csv

🛣️ Roadmap
✅ Proof of concept backend
🔜 Voice-first interface
🔜 Mobile app
🔜 Multi-language support for Indian regional languages
