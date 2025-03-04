import os
import pandas as pd
from flask import Flask, request, render_template
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from datetime import date
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
import re
import requests
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import pickle
import time

app = Flask(__name__)

# ### WebDriver Setup
def setup_driver():
    """Set up Chrome WebDriver with options for local and Render environments."""
    options = Options()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36')
    options.add_argument('--window-size=1920,1080')

    if os.getenv('RENDER'):
        print("Setting up headless Chrome for Render...")
        options.add_argument('--headless')
        options.add_argument('--disable-dev-shm-usage')  # Avoid shared memory issues
        options.add_argument('--no-sandbox')  # Required for Render
        options.binary_location = "/usr/bin/chromium-browser"
        service = Service("/usr/bin/chromedriver")
    else:
        print("Setting up local Chrome driver...")
        driver_path = 'C:\\Users\\polak\\Downloads\\chromedriver-win64\\chromedriver-win64\\chromedriver.exe'  # Adjust this path for your local setup
        service = Service(driver_path)

    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)  # Prevent long hangs
        return driver
    except Exception as e:
        print(f"Failed to initialize WebDriver: {str(e)}")
        return None

# ### Date Selection on Redbus
def select_date(driver):
    """Select today's date on the Redbus calendar."""
    wait = WebDriverWait(driver, 10)
    try:
        print("Clicking on the date field...")
        date_field = wait.until(EC.element_to_be_clickable((By.ID, 'onwardCal')))
        date_field.click()
        
        print("Waiting for the calendar to appear...")
        wait.until(EC.visibility_of_element_located((By.CLASS_NAME, 'DatePicker__CalendarContainer-sc-1kf43k8-0')))
        
        today = date.today()
        current_day = str(today.day)
        print(f"Selecting day: {current_day}")
        
        day_element = wait.until(EC.element_to_be_clickable(
            (By.XPATH, f"//span[contains(@class, 'DayTiles__CalendarDaysSpan-sc-1xum02u-1') and text()='{current_day}']")
        ))
        day_element.click()
        
        date_str = today.strftime("%d%b%Y")
        print(f"Selected date: {date_str}")
        return date_str
    except Exception as e:
        print(f"Error selecting date: {str(e)}")
        return None

# ### Scrape Bus Details
def scrape_city_pair(source, dest):
    """Scrape bus details between source and destination from Redbus."""
    driver = setup_driver()
    if driver is None:
        print("Driver initialization failed.")
        return None, None
    
    wait = WebDriverWait(driver, 15)
    short_wait = WebDriverWait(driver, 5)
    
    try:
        print(f"Navigating to Redbus for {source} to {dest}")
        driver.get('https://www.redbus.in')
        time.sleep(5)
        
        try:
            print("Handling popups...")
            short_wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Close')]"))).click()
        except TimeoutException:
            print("No popup found.")
        
        print("Entering source city...")
        source_input = wait.until(EC.presence_of_element_located((By.ID, 'src')))
        source_input.send_keys(source)
        wait.until(EC.element_to_be_clickable((By.XPATH, f"//ul[@class='sc-dnqmqq dZhbJF']/li//text[@class='placeHolderMainText' and contains(text(), '{source}')]/ancestor::li"))).click()
        
        print("Entering destination city...")
        dest_input = wait.until(EC.presence_of_element_located((By.ID, 'dest')))
        dest_input.send_keys(dest)
        wait.until(EC.element_to_be_clickable((By.XPATH, f"//ul[@class='sc-dnqmqq dZhbJF']/li//text[@class='placeHolderMainText' and contains(text(), '{dest}')]/ancestor::li"))).click()
        
        print("Selecting date...")
        date_str = select_date(driver)
        if date_str is None:
            print("Failed to select date.")
            return None, None
        
        print("Clicking search button...")
        search_button = wait.until(EC.element_to_be_clickable((By.ID, 'search_button')))
        search_button.click()
        
        print("Waiting for bus items to load...")
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'bus-item')))
        time.sleep(3)
        
        print("Scrolling to load all bus items...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_attempts = 15
        
        while scroll_attempts < max_attempts:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
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
        
        print("Collecting bus items...")
        bus_items = driver.find_elements(By.CLASS_NAME, 'bus-item')
        print(f"Found {len(bus_items)} bus items")
        
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
                try:
                    amenities = bus.find_elements(By.CLASS_NAME, 'amenity-icon')
                    if amenities:
                        bus_data['Amenities'] = ', '.join([amenity.get_attribute('title') or 'Unknown' for amenity in amenities])
                except:
                    pass
                data.append(bus_data)
            except StaleElementReferenceException:
                continue
        
        df = pd.DataFrame(data) if data else pd.DataFrame()
        print(f"Scraping complete. Found {len(df)} buses.")
        return df, date_str
    except Exception as e:
        print(f"Error scraping {source} to {dest}: {str(e)}")
        return None, None
    finally:
        driver.quit()

# ### Machine Learning Processing
def process_ml(df):
    """Process scraped data with ML model to classify trips."""
    print("Processing ML model...")
    try:
        # Time conversion
        df['Departure Time'] = pd.to_datetime(df['Departure Time'], errors='coerce')
        df['Arrival Time'] = pd.to_datetime(df['Arrival Time'], errors='coerce')
        df['Departure Hour'] = df['Departure Time'].dt.hour
        df['Departure Minute'] = df['Departure Time'].dt.minute
        df['Arrival Hour'] = df['Arrival Time'].dt.hour
        df['Arrival Minute'] = df['Arrival Time'].dt.minute

        # Filter for Seater or Sleeper
        pattern = '|'.join(['Seater', 'Sleeper'])
        df = df[df['Bus Type'].str.contains(pattern, na=False)]

        # Distance calculation
        geolocator = Nominatim(user_agent="distance_calculator")
        def get_city_coordinates(city_name):
            try:
                location = geolocator.geocode(city_name, timeout=10)
                return (location.latitude, location.longitude) if location else (None, None)
            except:
                return (None, None)

        def calculate_distance_osrm(source, destination):
            try:
                source_coords = get_city_coordinates(source)
                dest_coords = get_city_coordinates(destination)
                if not source_coords or not dest_coords:
                    print(f"Could not find coordinates for {source} or {destination}")
                    return None
                url = f"http://router.project-osrm.org/route/v1/driving/{source_coords[1]},{source_coords[0]};{dest_coords[1]},{dest_coords[0]}?overview=false"
                response = requests.get(url)
                data = response.json()
                if 'routes' not in data or not data['routes']:
                    print("No route found")
                    return None
                distance_km = data['routes'][0]['distance'] / 1000
                return round(distance_km, 2)
            except Exception as e:
                print(f"Error calculating distance: {str(e)}")
                return None

        s1, d1 = df['Source'].iloc[0], df['Destination'].iloc[0]
        distance = calculate_distance_osrm(s1, d1)
        if distance is None:
            print("Distance calculation failed.")
            return pd.DataFrame()
        df['Distance'] = distance

        # Journey duration in minutes
        def duration_to_minutes(duration):
            try:
                hours = re.search(r'(\d+)h', duration)
                minutes = re.search(r'(\d+)m', duration)
                h = int(hours.group(1)) if hours else 0
                m = int(minutes.group(1)) if minutes else 0
                return h * 60 + m
            except:
                return None
        df['Journey Duration (minutes)'] = df['Journey Duration'].apply(duration_to_minutes)

        # Speed and cost/km
        df['Speed'] = (df['Distance'] / df['Journey Duration (minutes)']) * 100
        df['Ticket Price'] = pd.to_numeric(df['Ticket Price'], errors='coerce')
        df['cost/km'] = df['Ticket Price'] / df['Distance']

        # Bus category classification
        def classify_bus_type(bus_type):
            text = bus_type.lower()
            if "non ac" in text or "non a/c" in text:
                ac_category = "Non A/C"
            elif "a/c" in text or "ac" in text or "a.c" in text:
                ac_category = "A/C"
            else:
                ac_category = ""
            if "semi sleeper" in text:
                body = "Semi Sleeper"
            elif "sleeper" in text and "seater" in text:
                body = "Seater/Sleeper"
            elif "sleeper" in text:
                body = "Sleeper"
            elif "seater" in text:
                body = "Seater"
            else:
                body = "Other"
            return f"{ac_category} {body}" if ac_category else body

        df['Bus Category'] = df['Bus Type'].apply(classify_bus_type)

        # Load encoder and model
        print("Loading pickled models...")
        with open('Lg_Bus_category.pkl', 'rb') as file:
            encoder = pickle.load(file)
        with open('random_forest.pkl', 'rb') as file:
            model = pickle.load(file)

        df['Bus Category'] = encoder.transform(df['Bus Category'])

        # Predict
        expected = ['Rating', 'Ticket Price', 'Departure Hour', 'Departure Minute',
                    'Arrival Hour', 'Arrival Minute', 'Journey Duration (minutes)', 'Bus Category']
        df1 = df[expected]
        df1['Trip Classification'] = model.predict(df1)
        df1['Trip Classification'] = df1['Trip Classification'].map({
            0.0: 'Budget Friendly', 
            1.0: 'Budget Friendly and Time Saving', 
            2.0: 'Expensive', 
            3.0: 'Time Saving'
        })

        # Add additional columns
        for col in ['Bus Operator', 'Journey Duration', 'Bus Type', 'Available Seats', 'Departure Time', 'Arrival Time']:
            df1[col] = df[col]
        df1['Departure Time'] = df1['Departure Time'].dt.strftime('%H:%M:%S')
        df1['Arrival Time'] = df1['Arrival Time'].dt.strftime('%H:%M:%S')

        print("ML processing complete.")
        return df1
    except Exception as e:
        print(f"Error in ML processing: {str(e)}")
        return pd.DataFrame()

# ### Flask Routes
@app.route('/')
def home():
    """Render the home page."""
    print("Serving home page...")
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    """Handle form submission, scrape data, process with ML, and display results."""
    source = request.form['source']
    destination = request.form['destination']
    trip_classification = request.form['trip_classification']
    print(f"Received request: source={source}, destination={destination}, classification={trip_classification}")
    
    try:
        print("Starting scraping...")
        df, date_str = scrape_city_pair(source, destination)
        if df is None or df.empty:
            print("No bus data found.")
            return "No bus data found for this route.", 404
        
        print("Scraping completed. Processing ML model...")
        df_result = process_ml(df)
        if df_result.empty:
            print("No predictions available.")
            return "No predictions available after processing.", 404
        
        df_filtered = df_result[df_result['Trip Classification'] == trip_classification]
        results = df_filtered.to_dict(orient='records')
        print("Rendering results...")
        return render_template(
            'result.html',
            results=results,
            source=source,
            destination=destination,
            journey_date=date_str,
            trip_classification=trip_classification
        )
    except Exception as e:
        print(f"Error during prediction: {str(e)}")
        return f"An error occurred: {str(e)}", 500

# ### Main Execution
if __name__ == "__main__":
    app.run(debug=True, port=5000)
