from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv
import os
import logging
import json

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import os
app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')


# Load environment variables
load_dotenv()

# Configure Gemini API
try:
    genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
    model = genai.GenerativeModel('gemini-2.0-flash')
    logger.info("Gemini API configured successfully")
except Exception as e:
    logger.error(f"Failed to configure Gemini API: {str(e)}")
    raise

def analyze_prompt_for_job_fit(prompt):
    analysis_prompt = f"""
    Analyze the following user prompt to determine the most suitable type of business and location for job opportunities based on their skills, interests, or preferences:

    Prompt: "{prompt}"

    Provide the response in the following JSON format:
    {{
        "businessType": "[e.g., restaurant, tech company, retail]",
        "location": "[e.g., New York, Bangalore]",
        "reasoning": "[Brief explanation of why these choices were made]"
    }}

    If the prompt is vague, use "Local Business" for business type and "Nearby" for location.
    """
    try:
        response = model.generate_content(
            analysis_prompt,
            generation_config={
                "temperature": 0.5,
                "max_output_tokens": 512
            }
        )
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:-3].strip()
        try:
            data = json.loads(response_text)
            business_type = data.get("businessType", "Local Business")
            location = data.get("location", "Nearby")
            if not business_type or not location:
                logger.warning(f"Empty business type or location in Gemini response: {response_text}")
                return "Local Business", "Nearby"
            logger.info(f"Prompt analyzed: Business Type={business_type}, Location={location}")
            return business_type, location
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse Gemini response as JSON: {response_text}")
            return "Local Business", "Nearby"
    except Exception as e:
        logger.error(f"Error analyzing prompt: {str(e)}")
        return "Local Business", "Nearby"

def generate_job_suggestions(business_name, business_type, location, description=""):
    prompt = f"""
    Generate 3 realistic and detailed job positions tailored to the following business based on its type, location, and description:

    Business Name: {business_name}
    Business Type: {business_type}
    Location: {location}
    Description: {description}

    For each position, provide comprehensive details including:
    1. Job Title (specific and relevant to the business)
    2. Key Responsibilities (4-5 detailed points)
    3. Required Qualifications/Skills (4-5 specific points)
    4. Expected Salary Range (realistic Indian Rupees based on location and role)
    5. Benefits and Perks
    6. Experience Level Required
    7. Working Hours/Schedule
    8. Growth Opportunities

    Return the response as a JSON array with exactly this structure:
    [
        {{
            "jobTitle": "Specific Job Title Here",
            "keyResponsibilities": [
                "Detailed responsibility 1",
                "Detailed responsibility 2", 
                "Detailed responsibility 3",
                "Detailed responsibility 4"
            ],
            "requiredSkills": [
                "Specific skill/qualification 1",
                "Specific skill/qualification 2",
                "Specific skill/qualification 3", 
                "Specific skill/qualification 4"
            ],
            "expectedSalaryRange": "₹XX,XXX - ₹XX,XXX per month",
            "benefits": "Comprehensive benefits including health insurance, paid time off, bonuses, etc.",
            "experienceLevel": "Entry Level / Mid Level / Senior Level",
            "workingHours": "Working schedule and hours",
            "growthOpportunities": "Career advancement and learning opportunities available"
        }}
    ]

    Guidelines:
    - Make job titles specific to the business type and realistic for the given location
    - Include both technical and soft skills relevant to the industry
    - Salary should reflect the Indian market, adjusting for location (e.g., higher for metros, lower for tier-2 cities)
    - Ensure responsibilities are actionable and specific to the business
    - Vary the positions across different levels or departments
    - Ensure the response is valid JSON and tailored to the provided business details
    """
    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.7,
                "max_output_tokens": 2048
            }
        )
        response_text = response.text.strip()
        logger.info(f"Raw job suggestion for {business_name}: {response_text[:200]}...")
        if response_text.startswith("```json"):
            response_text = response_text[7:-3].strip()
        try:
            job_data = json.loads(response_text)
            if not isinstance(job_data, list) or not job_data:
                logger.warning(f"Invalid job data for {business_name}: {response_text}")
                return json.dumps([{"error": "Unable to generate valid job suggestions at this time"}])
            logger.debug(f"Generated job suggestions for {business_name}: {json.dumps(job_data)}")
            return json.dumps(job_data)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON for {business_name}: {response_text}")
            return json.dumps([{"error": "Unable to generate valid job suggestions at this time"}])
    except Exception as e:
        logger.error(f"Error generating job suggestion for {business_name}: {str(e)}")
        return json.dumps([{"error": "Unable to generate valid job suggestions at this time"}])

def extract_coordinates(page):
    url = page.url
    if '@' in url:
        coords = url.split('@')[1].split(',')[0:2]
        return f"{coords[0]}, {coords[1]}"
    return ""

def extract_location_url(page):
    return page.url

def extract_description(page):
    description_xpath = '//div[@class="WeS02d fontBodyMedium"]//div[@class="PYvSYb "]'
    if page.locator(description_xpath).count() > 0:
        return page.locator(description_xpath).inner_text()
    return ""

def scrape_jobs(business_type, location, total=5):
    names_list = []
    coordinates_list = []
    phones_list = []
    job_suggestions_list = []
    descriptions_list = []
    location_urls_list = []
    seen_names = set()

    full_search = f"{business_type} in {location}"
    logger.info(f"Starting scrape for: {full_search}, Total={total}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"https://www.google.com/maps/search/{full_search}", timeout=60000)
            page.wait_for_timeout(3000)
            logger.info("Navigated to Google Maps")
            page.wait_for_selector('//a[contains(@href, "https://www.google.com/maps/place")]', timeout=30000)
            logger.info("Search results loaded")

            previously_counted = 0
            while True:
                page.mouse.wheel(0, 10000)
                page.wait_for_timeout(2000)
                current_count = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').count()
                logger.info(f"Current results count: {current_count}")
                if current_count >= total:
                    listings = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()[:total]
                    logger.info(f"Total found: {len(listings)}")
                    break
                elif current_count == previously_counted:
                    listings = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()
                    logger.info(f"Reached all available results: {len(listings)}")
                    break
                else:
                    previously_counted = current_count

            for i, listing in enumerate(listings):
                try:
                    logger.info(f"Processing listing {i+1}/{len(listings)}")
                    listing.click()
                    page.wait_for_timeout(3000)

                    name_xpath = '//div[@class="TIHn2 "]//h1[@class="DUwDvf lfPIob"]'
                    name = page.locator(name_xpath).inner_text() if page.locator(name_xpath).count() > 0 else "Not found"

                    if name in seen_names:
                        logger.info(f"Skipping duplicate business: {name}")
                        continue
                    seen_names.add(name)

                    coords = extract_coordinates(page)
                    location_url = extract_location_url(page)
                    phone_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
                    phone = page.locator(phone_xpath).inner_text() if page.locator(phone_xpath).count() > 0 else "Not found"
                    business_type_xpath = '//div[@class="LBgpqf"]//button[@class="DkEaL "]'
                    scraped_business_type = page.locator(business_type_xpath).inner_text() if page.locator(business_type_xpath).count() > 0 else business_type
                    description = extract_description(page)

                    logger.info(f"Generating comprehensive job suggestions for {name}")
                    job_suggestions = generate_job_suggestions(name, scraped_business_type, coords, description)
                    logger.debug(f"Job suggestions for {name}: {job_suggestions}")  # Debug log to verify output

                    names_list.append(name)
                    coordinates_list.append(coords)
                    phones_list.append(phone)
                    descriptions_list.append(description)
                    job_suggestions_list.append(job_suggestions)
                    location_urls_list.append(location_url)

                    logger.info(f"✓ Scraped comprehensive data for: {name}")
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1000)

                    if len(names_list) >= total:
                        break
                except Exception as e:
                    logger.error(f"Error processing listing {i+1}: {str(e)}")
                    continue

            browser.close()
            logger.info("Browser closed")

    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}")
        raise

    df = pd.DataFrame({
        'Business Name': names_list,
        'Coordinates': coordinates_list,
        'Phone Number': phones_list,
        'Description': descriptions_list,
        'Job Suggestions': job_suggestions_list,
        'Location URL': location_urls_list
    })

    filename = 'business_jobs_with_urls.csv'
    df.to_csv(filename, index=False)
    logger.info(f"Data saved to {filename}")

    return df.to_dict(orient='records'), business_type, location

@app.route('/')
def index():
    logger.info("Serving index page")
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    logger.info("Received scrape request")
    data = request.json
    user_prompt = data.get('prompt', '')
    total = min(max(int(data.get('total', 5)), 1), 50)

    if not user_prompt:
        logger.warning("Empty prompt received")
        return jsonify({'error': 'Prompt is required'}), 400

    try:
        business_type, location = analyze_prompt_for_job_fit(user_prompt)
        results, final_business_type, final_location = scrape_jobs(business_type, location, total)
        logger.info("Comprehensive job scraping completed successfully")
        return jsonify({
            'business_type': final_business_type,
            'location': final_location,
            'results': results
        })
    except Exception as e:
        logger.error(f"Scrape endpoint failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run()
