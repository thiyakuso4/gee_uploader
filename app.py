import os
import ee
import geemap
import streamlit as st
import json
import time
import zipfile
import glob
import fiona
from shapely.ops import transform
import geopandas as gpd


# To support read and write KML
fiona.drvsupport.supported_drivers["KML"] = "rw"

# Preparing values
json_data = st.secrets["json_data"]
json_object = json.loads(json_data, strict=False)
service_account = st.secrets["service_account"]
json_object = json.dumps(json_object)# Authorising the app
credentials = ee.ServiceAccountCredentials(service_account, key_data=json_object)

# Initialize Google Earth Engine
ee.Initialize(credentials, project='ee-landflux')

# Set the title that appears on the browser tab
st.set_page_config(page_title="KML/Shapefile/GeoJSON uploader")
# Set up the Streamlit app layout and title
st.title("Upload kml, shapefile or geojson file to Google Earth Engine")

# Instructions for the app
st.write("This app allows you to upload a kml, shapefile or geojson file to Google Earth Engine.")

# Upload widget for file input
uploaded_file = st.file_uploader("Upload a .zip (shapefile) or .geojson file or .kml file", type=["zip", "geojson", "kml"])


# Function to drop Z values from a geometry
def drop_z(geometry):
    if geometry.has_z:
        return transform(lambda x, y, z=None: (x, y), geometry)
    return geometry


# Define helper functions
def get_vector(uploaded_file, out_dir=None):
    if out_dir is None:
        out_dir = "./"
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    vector = None
    out_name = None

    # Save uploaded file to disk
    content = uploaded_file.getvalue()
    out_file = os.path.join(out_dir, uploaded_file.name)
    with open(out_file, "wb") as fp:
        fp.write(content)
    
    if uploaded_file.name.endswith(".zip"):
        out_name = uploaded_file.name[:-4]
        with zipfile.ZipFile(out_file, "r") as zip_ref:
            extract_dir = os.path.join(out_dir, out_name + "_" + geemap.random_string(3))
            zip_ref.extractall(extract_dir)
            files = glob.glob(extract_dir + "/*.shp")
            if files:
                vector = geemap.shp_to_ee(files[0])
            else:
                files = glob.glob(extract_dir + "/*.geojson")
                if files:
                    vector = geemap.geojson_to_ee(files[0])
    elif uploaded_file.name.endswith(".kml"):
            gdf = gpd.read_file(out_file)
            # Drop Z values from all geometries
            gdf['geometry'] = gdf['geometry'].apply(drop_z)
            gdf.to_file(out_file)
            out_name = uploaded_file.name.replace('.kml', "")
            vector = geemap.kml_to_ee(out_file)
    else:
        out_name = uploaded_file.name.replace(".geojson", "").replace(".json", "")
        vector = geemap.geojson_to_ee(out_file)

    return vector, out_name

def import_asset_to_gee(ee_object, asset_name, asset_path="projects/ee-landflux/assets/ecoexplorer"):
    asset_id = f"{asset_path}/{asset_name}"
    exportTask = ee.batch.Export.table.toAsset(
        collection=ee_object,
        description="Upload to GEE",
        assetId=asset_id
    )
    exportTask.start()
    while exportTask.active():
        time.sleep(5)
    asset_permission = json.dumps({"writers": [], "all_users_can_read": True, "readers": []})
    ee.data.setAssetAcl(asset_id, asset_permission)

# Map setup
Map = geemap.Map(center=(40, -100), zoom=4, height="750px")

# Handle file upload and display
if uploaded_file:
    st.write("Processing the uploaded file...")
    try:
        fc, layer_name = get_vector(uploaded_file)
        import_asset_to_gee(fc, layer_name)        
        st.write(f"File {layer_name} uploaded successfully. Please return to Ecoexplorer and refresh the browser window.")
    except Exception as e:
        st.error(f"An error occurred: {e}")
else:
    st.info("Please upload a kml, shapefile (.zip) or geojson file.")
