import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
import re
import requests
import geopy
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import numpy as np
import pickle

df = pd.read_csv("ml_input.csv")
# Remove or comment out any .dt.time calls.
# Parse the column as a datetime (assuming it's something like "22:00:00" or "10:30 PM", etc.)
df['Departure Time'] = pd.to_datetime(df['Departure Time'], errors='coerce')
df['Arrival Time']   = pd.to_datetime(df['Arrival Time'], errors='coerce')

df['Departure Time'] = pd.to_datetime(df['Departure Time'], format='%H:%M:%S', errors='coerce')
df['Arrival Time']   = pd.to_datetime(df['Arrival Time'], format='%H:%M:%S', errors='coerce')

# Now you can safely extract hour and minute
df['Departure Hour']   = df['Departure Time'].dt.hour
df['Departure Minute'] = df['Departure Time'].dt.minute
df['Arrival Hour']     = df['Arrival Time'].dt.hour
df['Arrival Minute']   = df['Arrival Time'].dt.minute



temp = ['Seater', 'Sleeper']

# Create a regex pattern by joining list elements with "|"
pattern = '|'.join(temp)

# Check if any row contains either "Seater" or "Sleeper"
found = df[df['Bus Type'].str.contains(pattern, na=False)]
df=found

import pandas as pd
import requests
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# Initialize Nominatim geocoder
geolocator = Nominatim(user_agent="distance_calculator")

# Cache to store previously calculated distances
distance_cache = {}

def get_city_coordinates(city_name):
    """Get latitude and longitude of a city using Nominatim."""
    try:
        location = geolocator.geocode(city_name, timeout=10)
        if location:
            return (location.latitude, location.longitude)
        else:
            raise ValueError(f"City '{city_name}' not found.")
    except GeocoderTimedOut:
        raise ValueError(f"Geocoding timed out for city '{city_name}'.")

def calculate_distance_osrm(source, destination):
    """Calculate road distance between two cities using OSRM."""
    try:
        # Check if distance is already in cache
        if (source, destination) in distance_cache:
            return distance_cache[(source, destination)]

        # Get coordinates for source and destination
        source_coords = get_city_coordinates(source)
        destination_coords = get_city_coordinates(destination)

        # OSRM API endpoint
        url = f"http://router.project-osrm.org/route/v1/driving/{source_coords[1]},{source_coords[0]};{destination_coords[1]},{destination_coords[0]}?overview=false"

        # Fetch route data
        response = requests.get(url)
        data = response.json()

        # Extract distance in kilometers
        distance_km = data['routes'][0]['distance'] / 1000
        distance_km = round(distance_km, 2)

        # Store distance in cache for future use
        distance_cache[(source, destination)] = distance_km
        distance_cache[(destination, source)] = distance_km  # Assume distance is symmetric

        return distance_km
    except Exception as e:
        print(f"Error calculating distance between {source} and {destination}: {str(e)}")
        return None

if 'Source' in df.columns and not df.empty:
    s1 = df['Source'].iloc[0]
    d1 = df['Destination'].iloc[0]
else:
    raise ValueError("The DataFrame is empty or missing the 'Source' column!")

# Add a new column for distance
df['Distance'] =calculate_distance_osrm(s1,d1)



import re
def duration_to_minutes(duration):
    try:
        # Use regex to extract only numbers
        hours = re.search(r'(\d+)h', duration)
        minutes = re.search(r'(\d+)m', duration)

        h = int(hours.group(1)) if hours else 0
        m = int(minutes.group(1)) if minutes else 0

        return h * 60 + m
    except Exception as e:
        print(f"Error processing duration: {duration} - {e}")
        return None  # Handle errors safely

# Apply function safely
df['Journey Duration (minutes)'] = df['Journey Duration'].apply(duration_to_minutes)

df['Speed']=pd.Series(((df['Distance']/df['Journey Duration (minutes)'])*100))

df['cost/km']=pd.Series((df['Ticket Price']/df['Distance']))

import pandas as pd
import re

def classify_bus_type(bus_type):
    # Convert the string to lowercase for uniformity
    text = bus_type.lower()
    
    # Determine if it's AC or Non AC.
    # Check for "non ac" first to avoid false positives.
    if "non ac" in text or "non a/c" in text:
        ac_category = "Non A/C"
    elif "a/c" in text or "ac" in text or "a.c" in text:
        ac_category = "A/C"
    else:
        ac_category = ""
    
    # Determine the body type: Sleeper, Seater, Seater/Sleeper, or Semi Sleeper.
    # Check for "semi sleeper" first because it might contain "sleeper" too.
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
    
    # Return the combined classification.
    if ac_category:
        return f"{ac_category} {body}"
    else:
        return body

# Apply the function to create a new column with the standardized bus category
df['Bus Category'] = df['Bus Type'].apply(classify_bus_type)

# Display the unique standardized categories
print(df['Bus Category'].unique())

#emcode the required column 
with open(r"C:\Users\polak\OneDrive\Desktop\redbus\Lg_Bus_category.pkl", "rb") as file:
    encoder = pickle.load(file)
# Now transform your data:
df['Bus Category'] = encoder.transform(df['Bus Category'])

model = pickle.load(open(r"C:\Users\polak\OneDrive\Desktop\redbus\random_forest.pkl", "rb"))


expected=['Rating', 'Ticket Price', 'Departure Hour', 'Departure Minute',
       'Arrival Hour', 'Arrival Minute', 'Journey Duration (minutes)',
       'Bus Category']
df1=df[expected]


df1['Trip Classification'] = model.predict(df1)

df1['Trip Classification'] = df1['Trip Classification'].map({0.0: 'Budget Friendly', 1.0: 'Budget Friendly and Time Saving', 2.0 : 'Expensive',3.0:'Time Saving'})
expected2=['Bus Operator','Journey Duration','Bus Type','Available Seats']
df1['Departure Time'] = df['Departure Time'].dt.strftime('%H:%M:%S')
df1['Arrival Time']   = df['Arrival Time'].dt.strftime('%H:%M:%S')

for x in expected2:
    df1[x]=df[x]
df1.to_csv("ml_output.csv", index=False)
import os

output_file = "ml_output.csv"

if os.path.exists(output_file):
    print(f"✅ ML processing complete. {output_file} created successfully.")
else:
    print("❌ ERROR: ML processing failed. ml_output.csv was NOT created.")
