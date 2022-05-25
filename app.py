import geopandas as gpd
import streamlit as st
import ee
import leafmap.foliumap as leafmap
import geemap.foliumap as geemap
import datetime
import matplotlib.pyplot as plt


st.title("Water Spread Estimator")

st.sidebar.info("This app was developed by Antony Kishoare J, a Research Scholar, under the guidance of Dr.E. Arunbabu at Centre for Water Resources, Anna University.")

ee.Initialize()

st.write("This app is developed to calculate the water spread of a given area. The user can select the area of interest and the time period of interest. The app will then calculate the water spread of the area and the time period of interest. The app will also provide a map of the water spread of the area during the time period of interest.")

st.info("There are two ways to use this app.")
st.info("The first way is to upload a shapefile of the water body boundary. If you have the shapefile, click yes and upload the shapefile. This is directly compute the seasonal water spread area of the water body")
st.info("The second way is to use the interactive map to select the water body boundary. Here, first draw a polygon around the boundary of the water body using the interactive map. Then, export the file and upload it to the app.This will first find the boundary of the water body and then compute the seasonal water spread area of the water body.")

col_1, col_2 = st.columns(2)
width = 950
height = 600
with col_2:
    uploaded_file = st.file_uploader("Upload a vector dataset",
                                     type=["geojson", "zip"])
with col_1:
    option = st.radio("Do you have a boundary file?", ["Yes", "No"])

    basemap = st.selectbox("Select Basemap", ["OpenStreetMap","Google Terrain", "Google Hybrid"])

    if uploaded_file is None:

        if basemap == "Google Terrain":
            m = leafmap.Map(google_map="TERRAIN", center=[13, 80], zoom=10, draw_export=True)


        elif basemap == "Google Hybrid":
            m = leafmap.Map(google_map="HYBRID", center=[13, 80], zoom=10, draw_export=True)
        else:
            m = leafmap.Map(center=[13, 80], zoom=10, draw_export=True)

    if uploaded_file is not None:

        if basemap == "Google Terrain":
            m = geemap.Map(basemap="TERRAIN", center=[13, 80], zoom=10, draw_export=True)
        elif basemap == "Google Hybrid":
            m = geemap.Map(basemap="HYBRID", center=[13, 80], zoom=10, draw_export=True)
        else:
            m = geemap.Map(center=[13, 80], zoom=10, draw_export=True)

if option == "No":

    if uploaded_file is None:
        m.to_streamlit(width, height)

    if uploaded_file is not None:
        input_gdf = gpd.read_file(uploaded_file)
        input = geemap.gdf_to_ee(input_gdf)

        jrc = ee.Image("JRC/GSW1_3/GlobalSurfaceWater").select("max_extent")

        jrc_clip = jrc.clip(input)

        extent = jrc_clip.eq(1).selfMask().rename("extent")

        object_id = extent.connectedComponents(
            connectedness=ee.Kernel.plus(1), maxSize=1023
        )

        all_tanks = extent.addBands(object_id).reduceToVectors(
            geometry=input,
            crs=jrc.projection(),
            scale=30,
            geometryType='polygon',
            eightConnected=True,
            maxPixels=1e9,
            reducer=ee.Reducer.mean()
        )


        def addArea(feature):
            return feature.set({'area': feature.geometry().area(10).divide(100 * 100)})


        area = all_tanks.map(addArea)
        all_tanks_gdf = geemap.ee_to_gdf(area)
        max = all_tanks_gdf["area"].max() * 0.9

        tank = area.filter(ee.Filter.gte('area', max))

        m.addLayer(tank, {}, "Tank")
        m.centerObject(tank, 12)
        m.to_streamlit()

if option == "Yes":
    if uploaded_file is None:
        m.to_streamlit(width, height)

    if uploaded_file is not None:
        input_gdf = gpd.read_file(uploaded_file)
        tank = geemap.gdf_to_ee(input_gdf)

col_1, col_2 = st.columns(2)
if uploaded_file is not None:
    gdf = geemap.ee_to_gdf(tank)
    lon = gdf.centroid.iloc[0].x
    lon = round(lon, 2)
    lat = gdf.centroid.iloc[0].y
    lat = round(lat, 2)

with col_2:
    if uploaded_file is not None:
        st.subheader("Tank Details")
        tank_area = round(tank.geometry().area(10).divide(10000).getInfo(), 2)
        st.info("The maximum waterspread area of the tank: {} Ha".format(tank_area))
        st.info("Centroid Latitude of the tank: {}".format(lat))
        st.info("Centroid Longitude of the tank: {}".format(lon))

if uploaded_file is not None:
    cloudBitmask = ee.Number(2).pow(10).int()
    cirrusBitmask = ee.Number(2).pow(11).int()


    def masks2clouds(image):
        qa = image.select("QA60")
        mask = qa.bitwiseAnd(cloudBitmask).eq(0).And(qa.bitwiseAnd(cirrusBitmask).eq(0))
        return image.updateMask(mask)


    def ndwi(image):
        ndwi = image.normalizedDifference(['B3', 'B8'])
        return image.addBands(ndwi.rename("ndwi"))


    sentinel = ee.ImageCollection("COPERNICUS/S2").filterBounds(tank).map(masks2clouds).map(ndwi)

    with col_1:
        st.subheader("Normalized Difference Water Index")
        st.markdown(
            " The normalized difference water index is an index which is primariy used to identify the presence of water in the image. Its value ranges between -1 and 1. Pixels with ndwi value greater than or equal to zero are considered to have water ")
st.markdown("<h2 style='text-align: center;'>Select Date Range</h2>", unsafe_allow_html=True)
st.markdown("Please note that the waterspread area can be calculated only after March 2016")

col_1, col_2 = st.columns(2)

if uploaded_file is not None:

    with col_1:
        # insert date picker
        start_date = st.date_input("Enter start date", datetime.date(2016, 3, 1))
    with col_2:
        end_date = st.date_input("Enter end date", datetime.date(2022, 3, 31))
    st.info("The selected date range is from {} to {}".format(start_date, end_date))
    in_date = start_date.strftime("%Y-%m-%d")
    out_date = end_date.strftime("%Y-%m-%d")
    in_date = ee.Date(in_date)
    out_date = ee.Date(out_date)


    def wsarea(in_date, out_date, fc):
        img = sentinel.filterDate(in_date, out_date).select("ndwi").max().clip(fc)
        img1 = img.gt(0.1).selfMask()
        r_v = img1.addBands(img).reduceToVectors(
            geometry=fc,
            crs=img.projection(),
            scale=10,
            geometryType="polygon",
            eightConnected=False,
            maxPixels=5e12,
            reducer=ee.Reducer.sum()
        )
        try:
            vector = geemap.ee_to_gdf(r_v)
            dis = vector.dissolve()
            geometry = dis.geometry
        except Exception as e:
            geometry = geemap.ee_to_gdf(fc).boundary

        area = round(r_v.geometry().area(10).divide(1e4).getInfo(), 2)

        return geometry, area


    g1, a1 = wsarea(in_date, out_date, tank)
    tank_gdf = geemap.ee_to_gdf(tank)
    t1 = tank_gdf.boundary
    gd = gpd.GeoDataFrame(g1)
    gd.columns = ["geometry"]
    t1 = gpd.GeoDataFrame(t1)
    t1.columns = ["geometry"]
    g3 = gd.append(t1)

    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot(111)
    ax.set_aspect('equal')
    g3.plot(ax=ax, color='blue', linewidth=0.5)
    ax.set_title("Water Spread Area")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    st.pyplot(fig)
    st.subheader("The water spread area is {} Ha".format(a1))