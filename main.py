from playwright.sync_api import sync_playwright
from dataclasses import dataclass, asdict, field
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv
import os
import time

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-2.0-flash')

# Lists to store data
names_list = []
coordinates_list = []
phones_list = []
job_suggestions_list = []
descriptions_list = []
location_urls_list = []  # New list to store location URLs

def analyze_prompt_for_job_fit(prompt):
    """
    Use Gemini to analyze the user's prompt and determine suitable business type and location.
    """
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

        # Parse the response to extract Business Type and Location
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

        return business_type, location
    except Exception as e:
        print(f"Error analyzing prompt: {str(e)}")
        return "Local Business", "Nearby"  # Fallback values

def generate_job_suggestions(business_name, business_type, location, description=""):
    prompt = f"""
    Generate 3 realistic job positions for this business:

    Business Name: {business_name}
    Business Type: {business_type}
    Location: {location}
    Description: {description}

    For each position, provide:
    1. Job Title
    2. Key Responsibilities (3-4 points)
    3. Required Qualifications (3-4 points)
    4. Expected Salary Range (in Indian Rupees)

    Format each job as:
    Position: [Job Title]
    Responsibilities:
    - [Responsibility 1]
    - [Responsibility 2]
    - [Responsibility 3]
    Qualifications:
    - [Qualification 1]
    - [Qualification 2]
    - [Qualification 3]
    Salary: [Salary Range]

    Make the suggestions realistic and appropriate for the business type and location.
    Keep the response concise and focused on essential information.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating job suggestions: {str(e)}"

def extract_coordinates(page):
    url = page.url
    if '@' in url:
        coords = url.split('@')[1].split(',')[0:2]
        return f"{coords[0]}, {coords[1]}"
    return ""

def extract_location_url(page):
    """
    Extract the current page URL which contains the business location on Google Maps
    """
    return page.url

def extract_description(page):
    description_xpath = '//div[@class="WeS02d fontBodyMedium"]//div[@class="PYvSYb "]'
    if page.locator(description_xpath).count() > 0:
        return page.locator(description_xpath).inner_text()
    return ""

def main():
    # Get user prompt
    print("\nWelcome to the Business Job Scraper!")
    print("-----------------------------------")
    user_prompt = input("Tell me about yourself and what kind of job you're looking for: ")
    try:
        total = int(input("How many results do you want? (1-50): "))
        total = max(1, min(50, total))
    except ValueError:
        print("Invalid input. Defaulting to 10 results.")
        total = 10

    # Analyze prompt to determine business type and location
    print("\nAnalyzing your prompt to find suitable workplaces...")
    business_type, location = analyze_prompt_for_job_fit(user_prompt)
    full_search = f"{business_type} in {location}"
    print(f"\nSearching for: {full_search}")
    print(f"Number of results: {total}")
    print("-----------------------------------\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # Start at the search location
        page.goto(f"https://www.google.com/maps/search/{full_search}", timeout=60000)
        page.wait_for_timeout(2000)

        # Wait for results to load
        page.wait_for_selector('//a[contains(@href, "https://www.google.com/maps/place")]')

        # Scroll to load more results
        previously_counted = 0
        while True:
            page.mouse.wheel(0, 10000)
            page.wait_for_timeout(2000)

            current_count = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').count()

            if current_count >= total:
                listings = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()[:total]
                print(f"Total Found: {len(listings)}")
                break
            elif current_count == previously_counted:
                listings = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()
                print(f"Arrived at all available\nTotal Found: {len(listings)}")
                break
            else:
                previously_counted = current_count
                print(f"Currently Found: {current_count}")

        # Scrape data from each listing
        for listing in listings:
            listing.click()
            page.wait_for_timeout(2000)

            # Extract business name
            name_xpath = '//div[@class="TIHn2 "]//h1[@class="DUwDvf lfPIob"]'
            if page.locator(name_xpath).count() > 0:
                name = page.locator(name_xpath).inner_text()
            else:
                name = "Not found"

            # Extract coordinates
            coords = extract_coordinates(page)

            # Extract location URL
            location_url = extract_location_url(page)

            # Extract phone number
            phone_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
            if page.locator(phone_xpath).count() > 0:
                phone = page.locator(phone_xpath).inner_text()
            else:
                phone = "Not found"

            # Extract business type (fallback to Gemini-determined type if not found)
            business_type_xpath = '//div[@class="LBgpqf"]//button[@class="DkEaL "]'
            if page.locator(business_type_xpath).count() > 0:
                scraped_business_type = page.locator(business_type_xpath).inner_text()
            else:
                scraped_business_type = business_type

            # Extract description
            description = extract_description(page)

            # Generate job suggestions
            print(f"\nGenerating job suggestions for {name}...")
            job_suggestions = generate_job_suggestions(name, scraped_business_type, coords, description)

            # Store the data
            names_list.append(name)
            coordinates_list.append(coords)
            phones_list.append(phone)
            descriptions_list.append(description)
            job_suggestions_list.append(job_suggestions)
            location_urls_list.append(location_url)  # Store the location URL

            print(f"✓ Scraped data for: {name}")
            print(f"  URL: {location_url}")

            # Go back to results
            page.keyboard.press("Escape")
            page.wait_for_timeout(1000)

        # Create DataFrame and save to CSV
        df = pd.DataFrame({
            'Business Name': names_list,
            'Coordinates': coordinates_list,
            'Phone Number': phones_list,
            'Description': descriptions_list,
            'Job Suggestions': job_suggestions_list,
            'Location URL': location_urls_list  # Add the new column
        })

        # Save to CSV
        filename = 'business_jobs_with_urls.csv'
        df.to_csv(filename, index=False)
        print(f"\nData saved to {filename}")
        print("\nSample of collected data:")
        print(df[['Business Name', 'Phone Number', 'Location URL']].head())
        
        # Display summary
        print(f"\n📊 Summary:")
        print(f"Total businesses scraped: {len(df)}")
        print(f"Businesses with phone numbers: {len(df[df['Phone Number'] != 'Not found'])}")
        print(f"Businesses with descriptions: {len(df[df['Description'] != ''])}")

        browser.close()

if __name__ == "__main__":
    main()