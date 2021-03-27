# -*- coding: utf-8 -*-
"""ML_Project_BIXI_Predictions.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1YftBT7R_6EFbMO9l4561Td0pVGlXsJ7R

#MATH80629A Project: Predicting BIXI bike usage based on historical weather data

A project by: 
* William Désilets
* Simon Drolet (11178019)
* Gabriella Bincoletto-Montpetit (11149602)

# Part 1: Data pre-processing

## 1.1. Import relevant packages
"""

# Added a line of comments here as a test!
# Une autre ligne de test!

print("Bonjour!")

# !pip install -q xgboost==0.4a30     #XGboost
# import xgboost

import pandas as pd
import numpy as np
import math as math
import matplotlib.pyplot as plt
# from google.colab import files
import datetime as dt
from sklearn.cluster import KMeans
from sklearn.cluster import DBSCAN
# from geopy import distance
# from geopy.distance import great_circle
# from shapely.geometry import MultiPoint
# from geopy.distance import vincenty
import matplotlib.cm as cm
#import dask.dataframe as dd

# !git clone https://github.com/gbincoletto/MATH80629A

"""## 1.2. Weather Data

### 1.2.1. Import weather files
"""

# Since I have 84 files (7 years, 12 months per year) over 3 stations, I'll loop!

# This code lists the 252 weather URLs from our GitHub rep. Actually we only keep 162 because we remove Dec/Jan/Feb (No Bixis)!
weather_urls = list()
for s in [['7024745_','McTavish'],['7027329_','St-Hubert'],['7025251_','YUL']]: # McTavish, St-Hubert, YUL
  for y in range(7):
    for m in range(9):
      year = str(y + 2014)
      month = '0' + str(m+3) + '-'
      if len(month) == 4 : month = month[1:]
      url = 'https://raw.githubusercontent.com/gbincoletto/MATH80629A/main/' + s[1] + '/fr_climat_horaires_QC_' + s[0] + month + year + '_P1H.csv'
      weather_urls.append(url)

# Let's make all these CSVs into proper Pandas
weather_dfs = list()
n = 0
for file in weather_urls:
  weather_dfs.append(pd.read_csv(file))
  
  # A lot of columns are always empty, so let's remove them before anything else!
  weather_dfs[n] = weather_dfs[n].drop(['Date/Heure (HNL)','Temp Indicateur','Point de rosée Indicateur',\
                     'Hum. rel. Indicateur','Hauteur de précip. Indicateur',\
                     'Dir. du vent Indicateur','Vit. du vent Indicateur',\
                     'Visibilité Indicateur', 'Pression à la station Indicateur',\
                     'Hmdx Indicateur','Refroid. éolien Indicateur'],axis=1)
  
  # Let's clean up the "Heure" field so it's easier to use.
  weather_dfs[n]['Heure (HNL)'] = weather_dfs[n]['Heure (HNL)'].str.strip('0')
  weather_dfs[n]['Heure (HNL)'] = weather_dfs[n]['Heure (HNL)'].str.strip(':')
  weather_dfs[n]['Heure (HNL)'].mask(weather_dfs[n]['Heure (HNL)'] == '', '0', inplace=True)
  weather_dfs[n]['Heure (HNL)'] = weather_dfs[n]['Heure (HNL)'].astype(int)

  # BIXIs are only available from March 15 to November 15. Let's remove the useless days (keeping the day before)
  weather_dfs[n].drop(weather_dfs[n][(weather_dfs[n]['Mois'] == 3) & (weather_dfs[n]['Jour'] < 14)].index, inplace=True) # Mars
  weather_dfs[n].drop(weather_dfs[n][(weather_dfs[n]['Mois'] == 11) & (weather_dfs[n]['Jour'] > 15)].index, inplace=True) # Novembre

  # And we convert the field "Temps" to a list and remove NAN
  weather_dfs[n]['Temps'] = weather_dfs[n]['Temps'].fillna('ND')
  weather_dfs[n]['Temps'] = weather_dfs[n]['Temps'].str.split(',')

  n = n + 1
  if n % 21 == 0 : print('Upload %d percent complete' % (n/189*100)) # If I change the number of years this line won't work!

"""### 1.2.2. Cleaning"""

# We find all the possible weather conditions that can be identified in "Temps" to create indicative variables
# From: https://climat.meteo.gc.ca/glossary_f.html 

  # Here is the list that will be used

"""
  ND (0s everywhere)
  nan (0s everywhere)
  *
  BROUILLARD: Brume sèche OU Fumée (1), Brouillard OU Chasse-poussière élevée (2), brouillard verglaçant (3)
  PLUIE: Pluie OU Averses de pluie (1), Pluie modérée OU Averses de pluie modérée (2), Pluie forte OU Averses de pluie forte (3), Pluie verglaçante OU Averses de pluie verglaçante (4)
  BRUINE: Bruine (1), bruine verglaçante (2)
  ORAGES: Orages (1)
  NEIGE: Neige OU Averses de neige OU Neige en grains (1), Neige modérée (2), Poudrerie élevée OU Averses de granules de glace ou de grésil OU Granules de glace ou grésil OU Grêle (3) 
  SOLEIL: Généralement dégagé (1), dégagé (2)
  NUAGES: Généralement nuageux (1), nuageux (2)
"""

# NUAGES
def fnuages(row):
  if ('Généralement nuageux' in row['Temps']):
    val = 1
  elif ('Nuageux' in row['Temps']):
    val = 2
  else:
    val = 0
  return val

# SOLEIL
def fsoleil(row):
  if ('Généralement dégagé' in row['Temps']):
    val = 2
  elif ('Dégagé' in row['Temps']):
    val = 1
  else:
    val = 0
  return val

# ORAGES
def forages(row):
  if ('Orages' in row['Temps']) or ('Orage' in row['Temps']):
    val = 1
  else:
    val = 0
  return val

# NEIGE
def fneige(row):
  if ('Poudrerie élevée' in row['Temps']) or ('Grêle' in row['Temps']) or ('Granules de glace ou grésil' in row['Temps']) or ('Averses de granules de glace ou de grésil' in row['Temps']):
    val = 3
  elif ('Neige modérée' in row['Temps']):
    val = 2
  elif ('Neige' in row['Temps']) or ('Averses de neige' in row['Temps']) or ('Neige en grains' in row['Temps']):
    val = 1
  else:
    val = 0
  return val

# PLUIE
def fpluie(row):
  if ('Pluie verglaçante' in row['Temps']) or ('Averses de pluie verglaçante' in row['Temps']):
    val = 4
  elif ('Pluie forte' in row['Temps']) or ('Averses de pluie forte' in row['Temps']):
    val = 3
  elif ('Pluie modérée' in row['Temps']) or ('Averses de pluie modérées' in row['Temps']):
    val = 2
  elif ('Pluie' in row['Temps']) or ('Averses de pluie' in row['Temps']):
    val = 1
  else:
    val = 0
  return val

# BROUILLARD
def fbrouillard(row):
  if ('Brouillard verglaçant' in row['Temps']):
    val = 3
  elif ('Brouillard' in row['Temps']) or ('Chasse-poussière élevée' in row['Temps']):
    val = 2
  elif ('Brume sèche' in row['Temps']) or ('Fumée' in row['Temps']):
    val = 1
  else:
    val = 0
  return val

# BRUINE
def fbruine(row):
  if ('Bruine verglaçante' in row['Temps']):
    val = 2
  elif ('Bruine' in row['Temps']):
    val = 1
  else:
    val = 0
  return val

# Applying all the functions
for df in weather_dfs:
  df['Pluie'] = df.apply(fpluie,axis=1)
  df['Neige'] = df.apply(fneige,axis=1)
  df['Orages'] = df.apply(forages,axis=1)
  df['Bruine'] = df.apply(fbruine,axis=1)
  df['Brouillard'] = df.apply(fbrouillard,axis=1)
  df['Nuages'] = df.apply(fnuages,axis=1)
  df['Soleil'] = df.apply(fsoleil,axis=1)

# We will merge all the dataframes together into one huge table to make the splitting/aggregating easier
weather_df = pd.DataFrame()
for df in weather_dfs:
  weather_df = pd.concat([weather_df, df], ignore_index=True)

# Some of the column which should contain floats or int contain strings. Let's fix!
# NOTE: Only run this cell once! Else it will fail.

# First we change commas to periods in numbers
weather_df['Longitude (x)'] = (weather_df['Longitude (x)'].str.replace(',','.')).astype(float)
weather_df['Latitude (y)'] = (weather_df['Latitude (y)'].str.replace(',','.')).astype(float)
weather_df['Temp (°C)'] = (weather_df['Temp (°C)'].str.replace(',','.')).astype(float)
weather_df['Point de rosée (°C)'] = (weather_df['Point de rosée (°C)'].str.replace(',','.')).astype(float)
weather_df['Hauteur de précip. (mm)'] = (weather_df['Hauteur de précip. (mm)'].str.replace(',','.')).astype(float)
weather_df['Visibilité (km)'] = (weather_df['Visibilité (km)'].str.replace(',','.')).astype(float)
weather_df['Pression à la station (kPa)'] = (weather_df['Pression à la station (kPa)'].str.replace(',','.')).astype(float)

# I'll also change the station IDs so it's easier to use later
weather_df['ID climatologique'].mask(weather_df['ID climatologique'] == 7024745, 1, inplace=True)
weather_df['ID climatologique'].mask(weather_df['ID climatologique'] == 7027329, 2, inplace=True)
weather_df['ID climatologique'].mask(weather_df['ID climatologique'] == 7025251, 3, inplace=True)
weather_df['stationID'] = weather_df['ID climatologique']

# Finally, we can drop the fields which we have transformed earlier
weather_df = weather_df.drop(['Temps','ID climatologique', 'Nom de la Station'], axis=1)

"""### 1.2.3. Relevant functions"""

# Here are some functions that will be useful later (for weighted averages)

# Distance (HAVERSINE)
def distance(lon1,lat1,lon2,lat2):
    R = 6367.5
    dlon = np.abs(np.radians(lon2) - np.radians(lon1)) 
    dlat = np.abs(np.radians(lat2) - np.radians(lat1)) 
    a = np.sin(dlat/ 2)**2 + np.cos(np.radians(lat2)) * np.cos(np.radians(lat1)) * np.sin(dlon / 2)**2
    L = R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return L

# Weigthed Average
def weighted(x, cols, w="Distance"):
    return pd.Series(np.average(x[cols], weights=x[w], axis=0), cols)

# Let's write a function that allows to create a new df according to the specifications that we want!
# First we can choose what data to keep (Which year, month, day)
# Second we choose how to aggregate the data!

def create_weather_df(years=[weather_df.Année.min(),weather_df.Année.max()]\
                      , months=[weather_df.Mois.min(),weather_df.Mois.max()]\
                      , days=[weather_df.Jour.min(),weather_df.Jour.max()]\
                      , hours=[weather_df['Heure (HNL)'].min(),weather_df['Heure (HNL)'].max()]\
                      , aggType = 1 # 1 = hourly ; 2 = daily ; 3 = monthly
                      , geo = list()): # We can insert [Lon, Lat] 
  
  # Filtre temporel
  rdf = weather_df[(weather_df['Année'] >= years[0]) & (weather_df['Année'] <= years[1])]
  rdf = rdf[(rdf['Mois'] >= months[0]) & (rdf['Mois'] <= months[1])]
  rdf = rdf[(rdf['Jour'] >= days[0]) & (rdf['Jour'] <= days[1])]
  rdf = rdf[(rdf['Heure (HNL)'] >= hours[0]) & (rdf['Heure (HNL)'] <= hours[1])]

  # Creating a date ID (will vary based on type of aggregation)
  rdf.Année = rdf.Année.astype(str)
  rdf.Mois = rdf.Mois.astype(str)
  rdf.Jour = rdf.Jour.astype(str)
  rdf['Heure (HNL)'] = rdf['Heure (HNL)'].astype(str)
  rdf.loc[rdf['Mois'].str.len() == 1, 'Mois'] = '0' + rdf['Mois']
  rdf.loc[rdf['Jour'].str.len() == 1, 'Jour'] = '0' + rdf['Jour']
  rdf.loc[rdf['Heure (HNL)'].str.len() == 1, 'Heure (HNL)'] = '0' + rdf['Heure (HNL)']
  rdf['dateIDh'] = (rdf.Année + rdf.Mois + rdf.Jour + rdf['Heure (HNL)']).astype(int)
  rdf['dateIDd'] = (rdf.Année + rdf.Mois + rdf.Jour).astype(int)
  rdf['dateIDm'] = (rdf.Année + rdf.Mois).astype(int)

  
  if not geo: # Average across all three stations
    # Aggregate hourly data by default
    rdf = rdf.groupby('dateIDh').agg(Temp=("Temp (°C)", "mean"),
                                      DewPoint=("Point de rosée (°C)", "mean"),
                                      HumRel=("Hum. rel (%)", "mean"),
                                      PrecipitationHgt=("Hauteur de précip. (mm)", "mean"),
                                      WindDir=("Dir. du vent (10s deg)", "mean"),
                                      WindSpd=("Vit. du vent (km/h)", "mean"),
                                      Vis=("Visibilité (km)", "mean"),
                                      Pkpa=("Pression à la station (kPa)", "mean"),
                                      Hmdx=("Hmdx", "mean"),
                                      WindChill=("Refroid. éolien", "mean"),
                                      Rain=("Pluie", "max"),
                                      Snow=("Neige", "max"),
                                      Thunderstorm=("Orages", "max"),
                                      Drizzle=("Bruine", "max"),
                                      Fog=("Brouillard", "max"),
                                      Cloudy=("Nuages", "max"),
                                      Sunny=("Soleil", "max"),
                                      dateIDd=("dateIDd","mean"),
                                      dateIDm=("dateIDm","mean"),
                                      )
    

  else: # When geo option is ACTIVE
    # Ajouter une colonne de distance
    rdf['Distance'] = rdf.apply(lambda x: distance(x['Longitude (x)'], x['Latitude (y)'], geo[0], geo[1]), axis=1)
    # Date IDs
    rdf_date = rdf.groupby('dateIDh').agg(dateIDd=("dateIDd","mean"), dateIDm=("dateIDm","mean"))  
    # Hourly aggregation, weighted by distance (for continuous variables) # NOTE !!!! PRECIPITATION HEIGHT AND VIS NOT WORKING I THINK
    rdf_grouped = rdf.groupby('dateIDh')
    rdf_weighted = rdf_grouped.apply(weighted,["Temp (°C)",
                                       "Point de rosée (°C)",
                                       "Hum. rel (%)",
                                       "Dir. du vent (10s deg)",
                                       "Vit. du vent (km/h)",
                                       "Pression à la station (kPa)",
                                       "Hmdx",
                                       "Refroid. éolien"])
    # We have to do it separately for the precipitation height and visibility because station 3 has all NAN fro Precipitation, and station 1 has all NAN for Visibility
    # NOTE: This is not the most elegant as it's somehow hardcoded. It means the function will fail if we get new weather stations.
    # Precipitation
    rdf_precip = rdf.loc[rdf['stationID'].isin([1,2])]
    rdf_grouped2 = rdf_precip.groupby('dateIDh')
    rdf_weighted2 = rdf_grouped2.apply(weighted,["Hauteur de précip. (mm)"])
    rdf_weighted2.rename(columns={'Hauteur de précip. (mm)':'PrecipitationHgt'}, inplace=True)
    # Visibility
    rdf_vis = rdf.loc[rdf['stationID'].isin([2,3])]
    rdf_grouped3 = rdf_vis.groupby('dateIDh')
    rdf_weighted3 = rdf_grouped3.apply(weighted,["Visibilité (km)"])
    rdf_weighted3.rename(columns={'Visibilité (km)':'Vis'}, inplace=True)
    # We rename the columns of the original big batch weighted averages
    rdf_weighted.rename(columns={'Temp (°C)':'Temp',
                                 'Point de rosée (°C)':'DewPoint',
                                 'Hum. rel (%)':'HumRel',
                                 'Dir. du vent (10s deg)':'WindDir',
                                 'Vit. du vent (km/h)':'WindSpd',
                                 'Pression à la station (kPa)':'Pkpa',
                                 'Refroid. éolien':'WindChill'}, inplace=True)
    
    # For the categorical variables, we take the value closest to the location
    rdf_min = rdf.loc[rdf['stationID'].isin([2,3])] # Pas de données texte pour la station 1!
    rdf_min = rdf_min.loc[rdf['Distance'] == rdf_min['Distance'].min()]
    rdf_min = rdf_min.set_index('dateIDh')
    rdf_min = rdf_min[['Pluie','Neige','Orages','Brouillard']]
    # Annnnnd rename again:
    rdf_min = rdf_min.rename(columns={'Pluie':'Rain',
                                     'Neige':'Snow',
                                     'Orages':'Thunderstorm',
                                     'Brouillard':'Fog'
                                      })
    
    # Finally we add the column about cloud cover and drizzle, which are only available at one station
    rdf_sun = rdf.groupby('dateIDh').agg(Drizzle=("Bruine","max"), Cloudy=("Nuages","max"), Sunny=("Soleil","max")) 

    # We concatenate all the pandas together. The resulting df has the same format has the 'non-geo' one so we can pass it to agg=2 or agg=3 easily
    rdf = pd.concat([rdf_date,rdf_weighted,rdf_weighted2,rdf_weighted3,rdf_min,rdf_sun], axis=1)
    
      
  if aggType == 2 or aggType == 3:
    # Compute daily data
    rdf.loc[rdf["PrecipitationHgt"] > 0, 'RainToday'] = 1
    rdf.loc[rdf["PrecipitationHgt"] == 0, 'RainToday'] = 0
    rdf = rdf.groupby('dateIDd').agg(avgTemp=("Temp", "mean"),
                                      maxTemp=("Temp", "max"),
                                      minTemp=("Temp", "min"),
                                      avgDewPoint=("DewPoint", "mean"),
                                      avgHumRel=("HumRel", "mean"),
                                      maxHumRel=("HumRel", "max"),
                                      minHumRel=("HumRel", "min"),
                                      sumPrecipitationHgt=("PrecipitationHgt", "sum"),
                                      timePrecipitation=("RainToday", "mean"),
                                      precipitationToday=("RainToday", "max"),
                                      avgWindDir=("WindDir", "mean"),
                                      avgWindSpd=("WindSpd", "mean"),
                                      maxWindSpd=("WindSpd", "max"),
                                      avgVis=("Vis", "mean"),
                                      avgPkpa=("Pkpa", "mean"),
                                      avgHmdx=("Hmdx", "mean"),
                                      avgWindChill=("WindChill", "mean"),
                                      maxWindChill=("WindChill", "max"),
                                      minWindChill=("WindChill", "min"),
                                      Rain=("Rain", "max"), # Qualifie l'intensité maximale des précipitations dans la journée
                                      Snow=("Snow", "max"),
                                      Thunderstorm=("Thunderstorm", "max"),
                                      Drizzle=("Drizzle", "mean"),
                                      Fog=("Fog", "mean"),
                                      percentCloudy=("Cloudy", "mean"),
                                      percentSunny=("Sunny", "mean"),
                                      dateIDm=("dateIDm","mean")
                                      )
      
  if aggType == 3:
    # Dans un mois les max-min ne sont plus très utiles!
    rdf = rdf.groupby('dateIDm').agg(avgTemp=("avgTemp", "mean"),
                                         avgHigh=("maxTemp", "mean"),
                                         avgLow=("minTemp", "mean"),
                                         avgHumRel=("avgHumRel", "mean"),
                                         sumPrecipitationHgt=("sumPrecipitationHgt", "sum"),
                                         avgDailyPrecipitation=("timePrecipitation", "mean"),
                                         daysRain=("precipitationToday", "sum"), 
                                         avgWindSpd=("avgWindSpd", "mean"),
                                         avgWindChill=("avgWindChill", "mean"),
                                         avgHighWindchill=("maxWindChill","mean"),
                                         avgLowWindchill=("minWindChill","mean"),
                                         percentCloudy=("percentCloudy", "mean"),
                                         percentSunny=("percentSunny", "mean")
                                         )

  return rdf

"""### 1.2.4. Create useful weather pandas"""

# You can then call the dataframe that you want with the "create_weater_df"
#  ****** But, adventurer, watch out: it takes much more time to generate the dataframe you want when you call the function with the GEO option. Choose wisely.
df = create_weather_df(years=[2018,2020], months=[7,11], days=[8,22], aggType=3, geo=[-73.56,45.50]) 
df

"""## 1.2. BIXI Data

### 1.2.1. Importing BIXI trip data
"""

# The data has been pre-processed offline, and then separated into 40 dataframes (10 per year from 2017 to 2020). 
#The exact steps are available,annexed at the end of the collab.

bixi_rides_urls = list()
for y in [2017, 2018, 2019, 2020]:  
  for m in range(1,10):
    year = str(y)
    dfnumber = str(m)
    url = 'https://raw.githubusercontent.com/gbincoletto/MATH80629A/main/Final%20Bixi%20Data/bixi_' + year + '_' + dfnumber + '.csv'
    bixi_rides_urls.append(url)

bixi_rides_urls

# We can now turn the raw data located at these URLs into DFs **LONG RUNTIME ALERT**

bixi_rides_dfs = list()
for file in bixi_rides_urls:
    bixi_rides_dfs.append(pd.read_csv(file))
    
# Then we can concatenate the 40 dataframes into one central dataset.

bixi_master_data = pd.concat(bixi_rides_dfs)

bixi_master_data.head()

# Removing trips lasting less than one minute, as recommended by other studies in the field.

bixi_master_data = bixi_master_data.drop(bixi_master_data[bixi_master_data.duration_sec <= 60].index)
bixi_master_data

bixi_master_data.to_csv('bixi_master_data.csv') 
files.download('bixi_master_data.csv')

"""### 1.2.2. Importing location of BIXI stations



"""

# We will use our previous loop to import the annual Bixi station locations from GitHub. 

bixi_stations_urls = list()
for y in [2017, 2018, 2019, 2020]:
  year = str(y)
  url_2 = 'https://raw.githubusercontent.com/gbincoletto/MATH80629A/main/bixidata/Stations_' + year + '.csv'
  bixi_stations_urls.append(url_2)

# Using the URLs assembled in our list, we will then create proper pandas dataframes from the raw data.

bixi_stations_dfs = list()
for file in bixi_stations_urls:
    bixi_stations_dfs.append(pd.read_csv(file))

# Quickly declare individually our reference documents.
#stations_2014 = bixi_stations_dfs[0]
##stations_2015 = bixi_stations_dfs[1]
#stations_2016 = bixi_stations_dfs[2]
stations_2017 = bixi_stations_dfs[3]
stations_2018 = bixi_stations_dfs[4]
stations_2019 = bixi_stations_dfs[5]
stations_2020 = bixi_stations_dfs[6]

# Correcting data irregularities
stations_2019['code'] = stations_2019['Code']
stations_2019 = stations_2019.drop(['Code'], axis=1)
stations_2017 = stations_2017.drop(['is_public'], axis=1)

# Then, we will create a new key variable, specifically designed to join Longitude/Latitude values to our trip data. 

#stations_2014['Station_Key_ID'] = '2014' + stations_2014['code'].map(str)
#stations_2015['Station_Key_ID'] = '2015' + stations_2015['code'].map(str)
#stations_2016['Station_Key_ID'] = '2016' + stations_2016['code'].map(str)
stations_2017['Station_Key_ID'] = '2017' + stations_2017['code'].map(str)
stations_2018['Station_Key_ID'] = '2018' + stations_2018['code'].map(str)
stations_2019['Station_Key_ID'] = '2019' + stations_2019['code'].map(str) 
stations_2020['Station_Key_ID'] = '2020' + stations_2020['code'].map(str)

# Then, we can concatenate the dataframes into one final reference document.

bixi_master_stations = pd.concat([stations_2014, stations_2015, stations_2016, stations_2017, stations_2018, stations_2019,stations_2020])

"""### 1.2.3. Adding geographical location to the BIXI trip dataset"""

# Due to limited RAM, we will have to split our main dataset to create new variables and effectuate operations. **RUNTIME ALERT - Limite côté RAM!!*

#master_2014 = bixi_master_data.loc[bixi_master_data['start_date'].astype(str).str[0:4] == '2014']
#master_2015 = bixi_master_data.loc[bixi_master_data['start_date'].astype(str).str[0:4] == '2015']
#master_2016 = bixi_master_data.loc[bixi_master_data['start_date'].astype(str).str[0:4] == '2016']
#
#
#
#

#master_2017 = bixi_master_data.loc[bixi_master_data['start_date'].astype(str).str[0:4] == '2017']

#master_2018 = bixi_master_data.loc[bixi_master_data['start_date'].astype(str).str[0:4] == '2018']

#master_2019 = bixi_master_data.loc[bixi_master_data['start_date'].astype(str).str[0:4] == '2019']

#master_2020 = bixi_master_data.loc[bixi_master_data['start_date'].astype(str).str[0:4] == '2020']

# Creating two sub-DFs to facilitate the merging process. 

start_long_lat = bixi_master_stations[['Station_Key_ID', 'longitude', 'latitude']]
start_long_lat.columns = ['Start_Station_Key_ID', 'start_longitude', 'start_latitude']

end_long_lat = bixi_master_stations[['Station_Key_ID', 'longitude', 'latitude']]
end_long_lat.columns = ['End_Station_Key_ID', 'end_longitude', 'end_latitude']

# We will now create a loop to insert our merge key in the bike trips dataset, and then add the geographical values (Lon/Lat) based on this key.

for i in [master_2017, master_2018, master_2019, master_2020]:# master_2014, master_2015, master_2016, 
  i['Start_Station_Key_ID'] =  i['start_date'].astype(str).str[0:4] + i['start_station_code'].astype(str)
  i['End_Station_Key_ID'] =  i['end_date'].astype(str).str[0:4] + i['end_station_code'].astype(str)

# Finally, adding the geographical values and then recreating our master_data set. **NOT SURPRISINGLY, LONG RUNTIME ALERT**

master_2017 = master_2017.merge(start_long_lat, on ='Start_Station_Key_ID')
master_2017 = master_2017.merge(end_long_lat, on ='End_Station_Key_ID')

master_2018 = master_2018.merge(start_long_lat, on ='Start_Station_Key_ID')
master_2018 = master_2018.merge(end_long_lat, on ='End_Station_Key_ID')

master_2019 = master_2019.merge(start_long_lat, on ='Start_Station_Key_ID')
master_2019 = master_2019.merge(end_long_lat, on ='End_Station_Key_ID')

master_2020 = master_2020.merge(start_long_lat, on ='Start_Station_Key_ID')
master_2020 = master_2020.merge(end_long_lat, on ='End_Station_Key_ID')

bixi_master_data = pd.concat([master_2017, master_2018, master_2019, master_2020])

bixi_master_data.head

"""### 1.2.4. Aggregating function"""

# ******* WIP, please do not panic if this function fails *******

# This function will allow us to calculate the amount of bike rentals in ANY given time period
# Note: by any I mean hourly, daily or monthly
# Note#2: must also be part of the dataset - no information is available on pre-2017 dates

def calc_bike_volumes(df, years, months, days, hours, aggtype = 1): # Format [20XX,20XX], it's an interval! Same format for the other arguments please. No default values.
  
  pd.options.mode.chained_assignment = None  # default='warn'
  rdf = df

  # Creating a date ID (will vary based on type of aggregation)
  rdf['Année'] = rdf['start_date'].astype(str).str[0:4]
  rdf['Mois'] = rdf['start_date'].astype(str).str[5:7]
  rdf['Jour'] = rdf['start_date'].astype(str).str[8:10]
  rdf['Heure'] = rdf['start_date'].astype(str).str[11:13]
  rdf['dateIDh'] = (rdf.Année + rdf.Mois + rdf.Jour + rdf['Heure']).astype(int)
  rdf['dateIDd'] = (rdf.Année + rdf.Mois + rdf.Jour).astype(int)
  rdf['dateIDm'] = (rdf.Année + rdf.Mois).astype(int)
  
  # Filtre temporel
  rdf = rdf[(rdf['Année'].astype(int) >= years[0]) & (df['Année'].astype(int) <= years[1])]
  rdf = rdf[(rdf['Mois'].astype(int) >= months[0]) & (rdf['Mois'].astype(int) <= months[1])]
  rdf = rdf[(rdf['Jour'].astype(int) >= days[0]) & (rdf['Jour'].astype(int) <= days[1])]
  rdf = rdf[(rdf['Heure'].astype(int) >= hours[0]) & (rdf['Heure'].astype(int) <= hours[1])]

  if (not years) or (not months) or (not hours) or (not hours):
    print('Please input all the required arguments?')
  
  # This will aggregate what we need to get the number of trips in the given timeframe (by blocks) and average trip length.
  else:

    # Aggregate using the hour ID
    if aggtype == 1:
      rdf = rdf.groupby('dateIDh').agg(Duration=("duration_sec", "mean"),
                                       Volume=("duration_sec", "count"))
      return rdf

    # Aggregate using the day ID
    if aggtype == 2:
      rdf = rdf.groupby('dateIDd').agg(Duration=("duration_sec", "mean"),
                                       Volume=("duration_sec", "count"))
      return rdf

    # Aggregate using the month ID
    if aggtype == 3:
      rdf = rdf.groupby('dateIDm').agg(Duration=("duration_sec", "mean"),
                                       Volume=("duration_sec", "count"))
      return rdf

# Testing the function (it works!)
small_master_data = bixi_master_data.head(5000000)
rdf = calc_bike_volumes(small_master_data,[2017,2018],[3,5],[6,7],[1,3],aggtype=1)
rdf

# For some reason, this block of code does not work inside a function. So we'll just use it here!
# UPDATE: The function works now!

s = small_master_data # ------------------------------------------------- INSERT DATAFRAME (BIXI MASTER HERE)
s['Année'] = s['start_date'].astype(str).str[0:4]
s['Mois'] = s['start_date'].astype(str).str[5:7]
s['Jour'] = s['start_date'].astype(str).str[8:10]
s['Heure'] = s['start_date'].astype(str).str[11:13]
s['dateIDh'] = (s.Année + s.Mois + s.Jour + s['Heure']).astype(int)
s['dateIDd'] = (s.Année + s.Mois + s.Jour).astype(int)
s['dateIDm'] = (s.Année + s.Mois).astype(int)

years = [2017,2018] # -------------------------------------------- INSERT YEARS HERE
months = [3,5] # ------------------------------------------------- INSERT MONTHS HERE
days = [6,7] # ------------------------------------------------- INSERT DAYS HERE
hours = [1,3] # ------------------------------------------------- INSERT HOURS HERE

s = s[(s['Année'].astype(int) >= years[0]) & (s['Année'].astype(int) <= years[1])]
s = s[(s['Mois'].astype(int) >= months[0]) & (s['Mois'].astype(int) <= months[1])]
s = s[(s['Jour'].astype(int) >= days[0]) & (s['Jour'].astype(int) <= days[1])]
s = s[(s['Heure'].astype(int) >= hours[0]) & (s['Heure'].astype(int) <= hours[1])]

# --------- IF WANT HOURLY AGG. USE THIS LINE
rdf = s.groupby('dateIDh').agg(Duration=("duration_sec", "mean"),Volume=("duration_sec", "count"))
rdf

# --------- IF WANT DAILY AGG. USE THIS LINE
# rdf = s.groupby('dateIDd').agg(Duration=("duration_sec", "mean"),Volume=("duration_sec", "count"))

# --------- IF WANT MONTHLY AGG. USE THIS LINE
# rdf = s.groupby('dateIDm').agg(Duration=("duration_sec", "mean"),Volume=("duration_sec", "count"))

"""## 1.3. Neighbourhood Clusters

### 1.3.1. Setting up the data
"""

# We will attemps to create neighbourhood clusters for BIXI stations using their latitude and longitude. 
# We will ignore the variable 'code' and will use the Station_Key_ID as the primary key.

bixi_master_stations.head()

# First, we see that there a lot of duplicates of the same stations.
bixi_master_stations.loc[bixi_master_stations['name']=='Square St-Louis']

# We are only interested in 2020 stations, so we will only keep Station_Key_ID starting with 2020. There are 640 stations.
bixi_master_stations = bixi_master_stations[bixi_master_stations['Station_Key_ID'].astype(str).str.startswith('2020')]
bixi_master_stations.tail()

# We then plot the geographical points; good news: it indeed looks like the BIXI station map! 
plot_bixi_master_stations = plt.plot(bixi_master_stations['longitude'], bixi_master_stations['latitude'],
             marker='.', linewidth=0, color='#128128')
plot_bixi_master_stations = plt.grid(which='major', color='#cccccc', alpha=0.45)
plot_bixi_master_stations = plt.title ('Geographical distribution of BIXI stations', family='DejaVu Sans', fontsize=12)
plot_bixi_master_stations = plt.xlabel('Longitude')
plot_bixi_master_stations = plt.ylabel('Latitude')
plot_bixi_master_stations = plt.show()

# We then create a new dataframe to only keep the variables Station_Key_ID, Longitude and Latitude for our clustering analysis
cluster_bixi_stations=bixi_master_stations.loc[:,['Station_Key_ID','latitude','longitude']]
cluster_bixi_stations.head()

"""### 1.3.2. K-Means method"""

# We will validate the number of clusters by using the elbow method 
K_clusters = range(1,10)
kmeans = [KMeans(n_clusters=i) for i in K_clusters]
Y_axis = cluster_bixi_stations[['latitude']]
X_axis = cluster_bixi_stations[['longitude']]
score = [kmeans[i].fit(Y_axis).score(Y_axis) for i in range(len(kmeans))]

# Visualize the graph -- we see that 3 or 4 clusters could be interesting.
plt.plot(K_clusters, score)
plt.xlabel('Number of Clusters')
plt.ylabel('Score')
plt.title('Elbow Curve')
plt.show()

# Computer K-means clustering using 4 clusters

kmeans = KMeans(n_clusters = 4, init ='k-means++')
kmeans.fit(cluster_bixi_stations[cluster_bixi_stations.columns[1:3]])
cluster_bixi_stations['cluster_label'] = kmeans.fit_predict(cluster_bixi_stations[cluster_bixi_stations.columns[1:4]])
centers = kmeans.cluster_centers_ # Coordinates of cluster centers.
labels = kmeans.predict(cluster_bixi_stations[cluster_bixi_stations.columns[1:4]]) # Labels of each point
cluster_bixi_stations.tail(10)

# Visualize the clusters and centroids 

cluster_bixi_stations.plot.scatter(x = 'latitude', y = 'longitude', c=labels, s=50, cmap='viridis')
plt.scatter(centers[:, 0], centers[:, 1], c='black', s=200, alpha=0.5)

"""### 1.3.3. DBSCAN method"""

# We now create a new dataframe to only keep the variables Station_Key_ID, Longitude and Latitude for our clustering analysis
cluster_bixi_stations2=bixi_master_stations.loc[:,['Station_Key_ID','latitude','longitude']]
cluster_bixi_stations2.head()

# define the number of kilometers in one radiation
# which will be used to convert esp from km to radiation
kms_per_rad = 6371.0088

# define a function to calculate the geographic coordinate 
# centroid of a cluster of geographic points
# it will be used later to calculate the centroids of DBSCAN cluster
# because Scikit-learn DBSCAN cluster class does not come with centroid attribute.
def get_centroid(cluster):
  """calculate the centroid of a cluster of geographic coordinate points
  Args:
    cluster coordinates, nx2 array-like (array, list of lists, etc) 
    n is the number of points(latitude, longitude)in the cluster.
  Return:
    geometry centroid of the cluster
    
  """
  cluster_ary = np.asarray(cluster)
  centroid = cluster_ary.mean(axis = 0)
  return centroid

# testing get_centroid function
test_cluster= [[ 43.70487299, -79.57753802], 
               [ 43.71138367, -79.56524418],
               [ 43.72616079, -79.57319998],
               [ 43.73547907, -79.56258364],
               [ 43.72070325, -79.57202018],
               [ 43.73126031, -79.5598719 ]]
test_centroid = get_centroid(test_cluster)
print(test_centroid)

# convert eps to radians for use by haversine
epsilon = 0.1/kms_per_rad

# Extract intersection coordinates (latitude, longitude)
bixi_coords = cluster_bixi_stations2[['latitude', 'longitude']].values

import time
from sklearn import metrics

start_time = time.time()
dbsc = (DBSCAN(eps=epsilon, min_samples=1, algorithm='ball_tree', metric='haversine')
        .fit(np.radians(bixi_coords)))
bixi_cluster_labels = dbsc.labels_

# get the number of clusters
num_clusters = len(set(dbsc.labels_))
print(num_clusters)

# print the outcome
message = 'Clustered {:,} points down to {:,} clusters, for {:.1f}% compression in {:,.2f} seconds'
print(message.format(len(cluster_bixi_stations2), num_clusters, 100*(1 - float(num_clusters) / len(cluster_bixi_stations2)), time.time()-start_time))
print('Silhouette coefficient: {:0.03f}'.format(metrics.silhouette_score(bixi_coords, bixi_cluster_labels)))

# turn the clusters into a pandas series, where each element is a cluster of points
dbsc_clusters = pd.Series([bixi_coords[bixi_cluster_labels==n] for n in range(num_clusters)])

# get centroid of each cluster
bixi_centroids = dbsc_clusters.map(get_centroid)
# unzip the list of centroid points (lat, lon) tuples into separate lat and lon lists
cent_lats, cent_lons = zip(*bixi_centroids)
# from these lats/lons create a new df of one representative point for each cluster
centroids_pd = pd.DataFrame({'longitude':cent_lons, 'latitude':cent_lats})

print(centroids_pd)

# Plot the clusters and cluster centroid
fig, ax = plt.subplots(figsize=[20, 12])
bixi_scatter = ax.scatter(cluster_bixi_stations2['longitude'], cluster_bixi_stations2['latitude'], c=bixi_cluster_labels, cmap = cm.Dark2, edgecolor='None', alpha=0.7, s=120)
centroid_scatter = ax.scatter(centroids_pd['longitude'], centroids_pd['latitude'], marker='x', linewidths=2, c='k', s=50)
ax.set_title('BIXI Clusters & Centroid', fontsize = 30)
ax.set_xlabel('Longitude', fontsize=24)
ax.set_ylabel('Latitude', fontsize = 24)
ax.legend([bixi_scatter, centroid_scatter], ['Bixi stations', 'Neighbourhood Centroid'], loc='upper right', fontsize = 20)

# convert eps to radians for use by haversine
epsilon = 1.5/kms_per_rad

# Extract intersection coordinates (latitude, longitude)
bixi_coords = cluster_bixi_stations2.as_matrix(columns = ['latitude', 'longitude'])

start_time = time.time()
dbsc = (DBSCAN(eps=epsilon, min_samples=1, algorithm='ball_tree', metric='haversine')
        .fit(np.radians(bixi_coords)))
bixi_cluster_labels = dbsc.labels_

# get the number of clusters
num_clusters = len(set(dbsc.labels_))

# print the outcome
message = 'Clustered {:,} points down to {:,} clusters, for {:.1f}% compression in {:,.2f} seconds'
print(message.format(len(facility_pd), num_clusters, 100*(1 - float(num_clusters) / len(facility_pd)), time.time()-start_time))
print('Silhouette coefficient: {:0.03f}'.format(metrics.silhouette_score(fac_coords, fac_cluster_labels)))

# turn the clusters into a pandas series,where each element is a cluster of points
dbsc_clusters = pd.Series([fac_coords[fac_cluster_labels==n] for n in range(num_clusters)])
# Clustered 1,396 points down to 20 clusters, for 98.6% compression in 0.13 seconds
# Silhouette coefficient: -0.166

X = cluster_bixi_stations[['latitude', 'longitude']].values

def greatCircleDistance(x, y):
    lat1, lon1 = x[0], x[1]
    lat2, lon2 = y[0], y[1]
    return vincenty((lat1, lon1), (lat2, lon2)).meters

eps = [500, 600, 700]    # unit: meter
min_sample = [8, 10]
n1, n2 = len(eps), len(min_sample)
plt.subplots(nrows=n2, ncols=n1, figsize=(20, 15))

for j in range(n2):
  for i in range(n1):
    est = DBSCAN(eps=eps[i], min_samples=min_sample[j], metric=greatCircleDistance).fit(X)
    cluster_bixi_stations['cluster'] = est.labels_.tolist()

    ax = plt.subplot(n2, n1, n1*j+i+1)
    ax.set_title("DBSCAN ('greatCircle', eps={}, min_sample={})".format(eps[i], min_sample[j]))

plot_stations_map(ax, cluster_bixi_stations)

# Merge cluster labels in bixi_master_stations dataframe
clustering_bixi_stations = clustering_bixi_stations[['code','cluster_label']]
clustering_bixi_stations.head(5)

bixi_master_stations = bixi_master_stations.merge(clustering_bixi_stations, left_on='code', right_on='code')
bixi_master_stations.head(50)

