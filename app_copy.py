from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv
import os
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Configure Gemini API
try:
    genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
    model = genai.GenerativeModel('gemini-1.5-flash')
    logger.info("Gemini API configured successfully")
except Exception as e:
    logger.error(f"Failed to configure Gemini API: {str(e)}")
    raise

def analyze_prompt_for_job_fit(prompt):
    analysis_prompt = f"""
    Analyze the following user prompt to determine the most suitable type of business and location for them to work at based on their skills, interests, or preferences:

    Prompt: "{prompt}"

    Provide the response in the following format:
    - Business Type: [e.g., restaurant, tech company, retail]
    - Location: [e.g., New York, Bangalore]
    - Reasoning: [Brief explanation of why these choices were made]

    Ensure the business type and location are realistic and appropriate for job opportunities.
    """
    try:
        response = model.generate_content(analysis_prompt)
        response_text = response.text.strip()

        business_type = ""
        location = ""
        lines = response_text.split('\n')
        for line in lines:
            if line.startswith('- Business Type:'):
                business_type = line.replace('- Business Type:', '').strip()
            elif line.startswith('- Location:'):
                location = line.replace('- Location:', '').strip()

        if not business_type or not location:
            raise ValueError("Could not extract business type or location from Gemini response.")

        logger.info(f"Prompt analyzed: Business Type={business_type}, Location={location}")
        return business_type, location
    except Exception as e:
        logger.error(f"Error analyzing prompt: {str(e)}")
        return "Local Business", "Nearby"

def generate_job_suggestions(business_name, business_type, location, description=""):
    prompt = f"""
    Generate 3 realistic job positions for this business:

    Business Name: {business_name}
    Business Type: {business_type}
    Location: {location}
    Description: {description}

    Return the response as a JSON array with exactly this structure:
    [
        {{
            "jobTitle": "Job Title Here",
            "keyResponsibilities": ["Responsibility 1", "Responsibility 2", "Responsibility 3"],
            "requiredSkills": ["Skill 1", "Skill 2", "Skill 3"],
            "expectedSalaryRange": "₹XX,XXX - ₹XX,XXX per month",
            "benefits": "List of benefits"
        }}
    ]

    Make sure the response is valid JSON and includes realistic Indian salary ranges.
    """
    try:
        response = model.generate_content(prompt)
        logger.info(f"Job suggestions generated for {business_name}")
        return response.text
    except Exception as e:
        logger.error(f"Error generating job suggestions: {str(e)}")
        return f"Error generating job suggestions: {str(e)}"

def extract_coordinates(page):
    url = page.url
    if '@' in url:
        coords = url.split('@')[1].split(',')[0:2]
        return f"{coords[0]}, {coords[1]}"
    return ""

def extract_location_url(page):
    """Extract the current page URL which contains the business location on Google Maps"""
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

    # Use provided business_type and location or analyze if combined
    if not location:
        # If location is empty, try to analyze the business_type for embedded location
        analyzed_type, analyzed_location = analyze_prompt_for_job_fit(business_type)
        business_type = analyzed_type
        location = analyzed_location

    full_search = f"{business_type} in {location}"
    logger.info(f"Starting scrape for: {full_search}, Total={total}")

    try:
        with sync_playwright() as p:
            logger.info("Initializing Playwright")
            browser = None
            try:
                browser = p.chromium.launch(headless=True)  # Set to True for production
                logger.info("Chromium browser launched")
            except Exception as e:
                logger.error(f"Failed to launch Chromium: {str(e)}")
                raise

            page = browser.new_page()

            # Start at the search location
            try:
                page.goto(f"https://www.google.com/maps/search/{full_search}", timeout=60000)
                page.wait_for_timeout(3000)
                logger.info("Navigated to Google Maps")
            except Exception as e:
                logger.error(f"Failed to navigate to Google Maps: {str(e)}")
                raise

            # Wait for results to load
            try:
                page.wait_for_selector('//a[contains(@href, "https://www.google.com/maps/place")]', timeout=30000)
                logger.info("Search results loaded")
            except Exception as e:
                logger.error(f"Failed to load search results: {str(e)}")
                raise

            # Scroll to load more results
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

            # Scrape data from each listing
            for i, listing in enumerate(listings):
                try:
                    logger.info(f"Processing listing {i+1}/{len(listings)}")
                    listing.click()
                    page.wait_for_timeout(3000)

                    # Extract business name
                    name_xpath = '//div[@class="TIHn2 "]//h1[@class="DUwDvf lfPIob"]'
                    name = page.locator(name_xpath).inner_text() if page.locator(name_xpath).count() > 0 else "Not found"

                    # Extract coordinates
                    coords = extract_coordinates(page)

                    # Extract location URL
                    location_url = extract_location_url(page)

                    # Extract phone number
                    phone_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
                    phone = page.locator(phone_xpath).inner_text() if page.locator(phone_xpath).count() > 0 else "Not found"

                    # Extract business type
                    business_type_xpath = '//div[@class="LBgpqf"]//button[@class="DkEaL "]'
                    scraped_business_type = page.locator(business_type_xpath).inner_text() if page.locator(business_type_xpath).count() > 0 else business_type

                    # Extract description
                    description = extract_description(page)

                    # Generate job suggestions
                    logger.info(f"Generating job suggestions for {name}")
                    job_suggestions = generate_job_suggestions(name, scraped_business_type, coords, description)

                    # Store the data
                    names_list.append(name)
                    coordinates_list.append(coords)
                    phones_list.append(phone)
                    descriptions_list.append(description)
                    job_suggestions_list.append(job_suggestions)
                    location_urls_list.append(location_url)

                    logger.info(f"✓ Scraped data for: {name}")

                    # Go back to results
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1000)
                except Exception as e:
                    logger.error(f"Error processing listing {i+1}: {str(e)}")
                    continue

            browser.close()
            logger.info("Browser closed")

    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}")
        raise

    # Create DataFrame
    df = pd.DataFrame({
        'Business Name': names_list,
        'Coordinates': coordinates_list,
        'Phone Number': phones_list,
        'Description': descriptions_list,
        'Job Suggestions': job_suggestions_list,
        'Location URL': location_urls_list
    })

    # Save to CSV
    filename = 'business_jobs_with_urls.csv'
    df.to_csv(filename, index=False)
    logger.info(f"Data saved to {filename}")

    # Convert DataFrame to list of dictionaries for JSON response
    return df.to_dict(orient='records'), business_type, location

@app.route('/')
def index():
    logger.info("Serving index page")
    return render_template('index.html')

@app.route('/api/generate', methods=['POST'])
def generate():
    logger.info("Received generate request")
    data = request.json
    business_type = data.get('business_type', '')
    location = data.get('location', '')
    
    # Combine business_type and location if both provided
    if business_type and location:
        full_prompt = f"{business_type} in {location}"
    else:
        full_prompt = business_type or location

    if not full_prompt:
        logger.warning("Empty prompt received")
        return jsonify({'error': 'Business type or location is required'}), 400

    try:
        # Scrape fewer results for faster response in chat interface
        results, final_business_type, final_location = scrape_jobs(business_type, location, total=3)
        
        # Get job suggestions from the first result for the chat response
        if results and len(results) > 0:
            first_result = results[0]
            job_suggestions = first_result.get('Job Suggestions', '[]')
            
            logger.info("Generate request completed successfully")
            return jsonify({
                'business_type': final_business_type,
                'location': final_location,
                'suggestions': job_suggestions,
                'all_results': results  # Include all scraped data
            })
        else:
            return jsonify({'error': 'No businesses found for your search'}), 404
            
    except Exception as e:
        logger.error(f"Generate endpoint failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/scrape', methods=['POST'])
def scrape():
    logger.info("Received scrape request")
    data = request.json
    user_prompt = data.get('prompt', '')
    total = min(max(int(data.get('total', 10)), 1), 50)

    if not user_prompt:
        logger.warning("Empty prompt received")
        return jsonify({'error': 'Prompt is required'}), 400

    try:
        # Analyze the prompt to extract business type and location
        business_type, location = analyze_prompt_for_job_fit(user_prompt)
        results, final_business_type, final_location = scrape_jobs(business_type, location, total)
        
        logger.info("Scraping completed successfully")
        return jsonify({
            'business_type': final_business_type,
            'location': final_location,
            'results': results
        })
    except Exception as e:
        logger.error(f"Scrape endpoint failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)