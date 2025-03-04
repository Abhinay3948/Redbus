from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import pandas as pd
import time
from itertools import permutations
from datetime import date
from flask import Flask, request, render_template, redirect, url_for
import pandas as pd
import subprocess  
app = Flask(__name__)

# Route for home page
@app.route('/')
def home():
    return render_template('index.html')
'''
# List of cities to process
cities = [
    # Metro Cities
    "Goa","Nashik", "Aurangabad", "Solapur", "Kolhapur",
    "Mahabaleshwar", "Panchgani", "Lonavala", "Khandala", "Shirdi", "Ahmednagar","Pune","Hyderabad"
]
'''
# Generate all unique source-destination pairs
#city_pairs = list(permutations(cities, 2))

# Set up Chrome WebDriver with improved options
def setup_driver(driver_path='C:\\Users\\polak\\Downloads\\chromedriver-win64\\chromedriver-win64\\chromedriver.exe'):
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')  # Avoid detection as bot
    options.add_argument('--headless')  # Run in headless mode (optional: remove to see browser)
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/133.0.6943.142')
    options.add_argument('--window-size=1920,1080')
    service = Service(driver_path)
    return webdriver.Chrome(service=service, options=options)

# Select today's date
def select_date(driver):
    wait = WebDriverWait(driver, 10)
    try:
        # Click the date field to open the calendar
        date_field = wait.until(EC.element_to_be_clickable((By.ID, 'onwardCal')))
        date_field.click()
        
        # Wait for the calendar to appear
        wait.until(EC.visibility_of_element_located((By.CLASS_NAME, 'DatePicker__CalendarContainer-sc-1kf43k8-0')))
        
        # Get today's date
        today = date.today()
        current_day = str(today.day)  # Convert day to string for XPath
        
        # Find and click the span with today's day number
        day_element = wait.until(EC.element_to_be_clickable(
            (By.XPATH, f"//span[contains(@class, 'DayTiles__CalendarDaysSpan-sc-1xum02u-1') and text()='{current_day}']")
        ))
        day_element.click()
        
        # Format the date for filename (e.g., "02Oct2023")
        date_str = today.strftime("%d%b%Y")
        return date_str
        
    except Exception as e:
        print(f"Error selecting date: {str(e)}")
        driver.save_screenshot('date_selection_error.png')
        return None

# Scrape bus details for a city pair
def scrape_city_pair(source, dest):
    global date1
    driver = setup_driver()
    wait = WebDriverWait(driver, 15)  # Increased timeout
    short_wait = WebDriverWait(driver, 5)
    
    try:
        print(f"Navigating to Redbus for {source} to {dest}")
        driver.get('https://www.redbus.in')
        time.sleep(5)
        
        # Handle popups
        try:
            short_wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Close')]"))).click()
        except TimeoutException:
            pass
        
        # Enter source and destination
        source_input = wait.until(EC.presence_of_element_located((By.ID, 'src')))
        source_input.send_keys(source)
        wait.until(EC.element_to_be_clickable((By.XPATH, f"//ul[@class='sc-dnqmqq dZhbJF']/li//text[@class='placeHolderMainText' and contains(text(), '{source}')]/ancestor::li"))).click()
        
        dest_input = wait.until(EC.presence_of_element_located((By.ID, 'dest')))
        dest_input.send_keys(dest)
        wait.until(EC.element_to_be_clickable((By.XPATH, f"//ul[@class='sc-dnqmqq dZhbJF']/li//text[@class='placeHolderMainText' and contains(text(), '{dest}')]/ancestor::li"))).click()
        
        # Select today's date and get formatted date string
        date_str = select_date(driver)
        date1=date_str
        if date_str is None:
            print("Failed to select date, skipping.")
            return
        
        # Click search button
        search_button = wait.until(EC.element_to_be_clickable((By.ID, 'search_button')))
        search_button.click()
        
        # Wait for bus items to load and scroll to load all
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'bus-item')))
        time.sleep(3)
        
        # Improved scrolling mechanism
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_attempts = 15
        
        while scroll_attempts < max_attempts:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)  # Wait for content to load
            
            # Try to click "View More" buttons if they exist
            try:
                view_more = driver.find_elements(By.XPATH, "//div[contains(text(), 'View More') or contains(text(), 'Show More')]")
                if view_more:
                    driver.execute_script("arguments[0].click();", view_more[0])
                    time.sleep(2)
            except:
                pass
            
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
                last_height = new_height
        
        # Collect all bus items
        bus_items = driver.find_elements(By.CLASS_NAME, 'bus-item')
        print(f"Found {len(bus_items)} bus items for {source} to {dest}")
        
        # Extract bus details using updated class names
        data = []
        for bus in bus_items:
            try:
                text_lines = bus.text.split('\n')
                
                bus_data = {
                    'Source': source,
                    'Destination': dest,
                    'Bus Operator': bus.find_element(By.CLASS_NAME, 'travels').text if bus.find_elements(By.CLASS_NAME, 'travels') else 'N/A',
                    'Bus Type': bus.find_element(By.CLASS_NAME, 'bus-type').text if bus.find_elements(By.CLASS_NAME, 'bus-type') else 'N/A',
                    'Departure Time': bus.find_element(By.CLASS_NAME, 'dp-time').text if bus.find_elements(By.CLASS_NAME, 'dp-time') else 'N/A',
                    'Arrival Time': bus.find_element(By.CLASS_NAME, 'bp-time').text if bus.find_elements(By.CLASS_NAME, 'bp-time') else 'N/A',
                    'Journey Duration': bus.find_element(By.CLASS_NAME, 'dur').text if bus.find_elements(By.CLASS_NAME, 'dur') else 'N/A',
                    'Starting Point': next((line for line in text_lines if 'Start' in line or 'Pickup' in line), 'N/A'),
                    'Ending Point': next((line for line in text_lines if 'End' in line or 'Drop' in line), 'N/A'),
                    'Available Seats': bus.find_element(By.CLASS_NAME, 'seat-left').text if bus.find_elements(By.CLASS_NAME, 'seat-left') else 'N/A',
                    'Rating': bus.find_element(By.CSS_SELECTOR, '.rating-sec span').text if bus.find_elements(By.CSS_SELECTOR, '.rating-sec span') else 'N/A',
                    'Ticket Price': bus.find_element(By.CLASS_NAME, 'fare').text.replace('INR ', '') if bus.find_elements(By.CLASS_NAME, 'fare') else 'N/A',
                    'Amenities': 'N/A'
                }
                
                # Extract amenities if available
                try:
                    amenities = bus.find_elements(By.CLASS_NAME, 'amenity-icon')
                    if amenities:
                        bus_data['Amenities'] = ', '.join([amenity.get_attribute('title') or 'Unknown' for amenity in amenities])
                except:
                    pass
                
                data.append(bus_data)
            except StaleElementReferenceException:
                continue
            except Exception as e:
                print(f"Error extracting bus details: {str(e)}")
        
        # Save results to CSV with today's date in filename
        if data:
            df = pd.DataFrame(data)
            filename = f"{source}_to_{dest}_{date_str}.csv"
            df.to_csv(filename, index=False)
            print(f"Saved {len(data)} buses to {filename}")
        else:
            print(f"No buses found for {source} to {dest}")


        return date_str   
    except Exception as e:
        print(f"Error scraping {source} to {dest}: {str(e)}")
        driver.save_screenshot(f'error_{source}_to_{dest}.png')
    finally:
        driver.quit()


@app.route('/predict', methods=['POST'])
def predict():
    source = request.form['source']
    destination = request.form['destination']
    trip_classification = request.form['trip_classification']

    # Call the scraping function from app.py
    print(f"Scraping Redbus data for {source} to {destination}...")
    date_str = scrape_city_pair(source, destination)  # Run Redbus scraper

    # Read the scraped CSV file
    file_path = f"{source}_to_{destination}_{date_str}.csv"  # Match app.py output
    df = pd.read_csv(file_path)

    # Send data to ML pipeline (ml.py)
    print("Sending data to ML model...")
    df.to_csv("ml_input.csv", index=False)
    subprocess.run(["python", "ml.py"])  # Run ML script

    # Read the processed ML output
    df_result = pd.read_csv("ml_output.csv")  # Processed predictions

    # Filter results based on user input
    df_filtered = df_result[df_result['Trip Classification'] == trip_classification]

    # Convert filtered DataFrame to a list of dictionaries
    results = df_filtered.to_dict(orient='records')

    # Pass the results along with other details to the template
    return render_template(
        'result.html',
        results=results,
        source=source,
        destination=destination,
        journey_date=date_str,
        trip_classification=trip_classification
    )
# Main execution
'''def main():
    for source, dest in city_pairs:
        print(f"Processing {source} to {dest}")
        scrape_city_pair(source, dest)
        time.sleep(5)  # Delay between requests to avoid overwhelming the server
'''
if __name__ == "__main__":
    app.run(debug=True, port=5001)

